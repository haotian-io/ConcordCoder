"""Confidence-Guided Probing: Perplexity-based probe trigger mechanism.

This module implements Contribution 2 of ConcordCoder:
  - Estimates LLM generation confidence at AST node level via token logprobs
  - Weights low-confidence nodes by multi-factor structural risk
  - Generates targeted probe questions for uncertain + high-risk code regions
  - Triggers selective re-generation only for flagged spans (not full restart)

Comparison with InlineCoder (arXiv:2601.00376):
  - InlineCoder:  perplexity → automatic upstream/downstream retrieval (no human)
  - ConcordCoder: perplexity + structural hotspot score → probe question
                  → targeted re-generation of the uncertain span

API:
    from concordcoder.generation.probing import ProbingEngine
    engine = ProbingEngine(llm_client=client, bundle=bundle)
    result = engine.run(draft_code, draft_logprobs)
    # result.probes: List[ProbeTarget]  — ask user about these
    # result.probe_questions: List[str] — ready-to-display questions
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from concordcoder.schemas import ContextBundle


# ─── Data structures ────────────────────────────────────────────────────────

@dataclass
class TokenWithLogprob:
    """A single generated token together with its log-probability."""
    token: str
    logprob: float   # natural log (base e); range (-∞, 0]
    bytes: list[int] = field(default_factory=list)

    @property
    def probability(self) -> float:
        return math.exp(self.logprob)


@dataclass
class ASTSpan:
    """A contiguous range of tokens corresponding to an AST node."""
    node_type: str          # e.g. "FunctionDef", "Call", "ClassDef"
    node_name: str          # e.g. "process_payment"
    start_token: int        # index into token list
    end_token: int          # exclusive
    file_hint: str = ""     # file path hint (if extractable from context)
    line_hint: int = 0      # approximate source line


@dataclass
class ProbeTarget:
    """An AST span that warrants a probe question."""
    span: ASTSpan
    confidence: float           # in [0, 1]
    git_churn: float            # normalized [0, 1]; 0 = never modified
    hotspot_score: float
    risk_components: dict[str, float] = field(default_factory=dict)
    probe_question: str = ""    # generated probe text


@dataclass
class ProbingResult:
    """Output of ProbingEngine.run()."""
    probes: list[ProbeTarget]                   # sorted by hotspot_score desc
    probe_questions: list[str]                  # displayable questions
    low_confidence_summary: str                 # short paragraph for the user
    flagged_lines: list[tuple[int, int]]        # (start_line, end_line) pairs
    needs_probing: bool                         # True if any probes exist


# ─── Core Engine ────────────────────────────────────────────────────────────

class ProbingEngine:
    """Detect uncertain code regions and generate targeted probe questions.

    Args:
        llm_client: Optional LLMClient (used only for probe question generation).
        bundle: ContextBundle from Phase 1; provides git_churn data.
        confidence_threshold: Spans below this confidence trigger probing.
        churn_alpha: Scaling coefficient for churn contribution.
        max_probes: Maximum number of probe questions to generate per run.
    """

    DEFAULT_CONFIDENCE_THRESHOLD = 0.45
    DEFAULT_CHURN_ALPHA = 0.6
    DEFAULT_MAX_PROBES = 3
    DEFAULT_SCORE_THETA = 0.50

    def __init__(
        self,
        llm_client=None,
        bundle: "ContextBundle | None" = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        churn_alpha: float = DEFAULT_CHURN_ALPHA,
        max_probes: int = DEFAULT_MAX_PROBES,
        score_theta: float = DEFAULT_SCORE_THETA,
        top_n: int | None = None,
        w_churn: float = 0.40,
        w_centrality: float = 0.25,
        w_fan_io: float = 0.20,
        w_public_api: float = 0.15,
    ) -> None:
        self.llm = llm_client
        self.bundle = bundle
        self.confidence_threshold = confidence_threshold
        self.churn_alpha = churn_alpha
        self.max_probes = max_probes
        self.score_theta = score_theta
        self.top_n = top_n
        self.w_churn = w_churn
        self.w_centrality = w_centrality
        self.w_fan_io = w_fan_io
        self.w_public_api = w_public_api

    # ── Main entry point ──────────────────────────────────────────────────

    def run(
        self,
        generated_code: str,
        token_logprobs: list[TokenWithLogprob],
    ) -> ProbingResult:
        """Analyze generated code + logprobs; return probing recommendations.

        Args:
            generated_code: The LLM-generated Python code string.
            token_logprobs: Token-level log-probabilities from the LLM API.

        Returns:
            ProbingResult with probe targets and human-readable questions.
        """
        # Step 1: Extract AST spans from generated code
        spans = self._extract_ast_spans(generated_code, token_logprobs)

        # Step 2: Compute per-span confidence from token logprobs
        span_confidences = self._compute_span_confidences(spans, token_logprobs)

        # Step 3: Query git churn rates
        git_churn = self._query_git_churn()

        # Step 4: Score spans and select probe targets
        probes = self._select_probe_targets(spans, span_confidences, git_churn)

        # Step 5: Generate probe questions
        for p in probes:
            p.probe_question = self._generate_probe_question(p, generated_code)

        flagged_lines = [(p.span.line_hint, p.span.line_hint + 10) for p in probes if p.span.line_hint > 0]

        return ProbingResult(
            probes=probes,
            probe_questions=[p.probe_question for p in probes],
            low_confidence_summary=self._build_summary(probes),
            flagged_lines=flagged_lines,
            needs_probing=len(probes) > 0,
        )

    # ── Step 1: AST Span Extraction ────────────────────────────────────────

    def _extract_ast_spans(
        self, code: str, tokens: list[TokenWithLogprob]
    ) -> list[ASTSpan]:
        """Parse code and map AST nodes to approximate token offsets.

        Strategy: build char-offset index from tokens, then use Python's
        ast module to find function/class/call nodes and map them.
        """
        spans: list[ASTSpan] = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return spans

        # Build char → token index (rough)
        char_to_tok = self._build_char_token_index(tokens)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = node.name
                span = self._node_to_span(node, name, char_to_tok, tokens, code)
                if span:
                    spans.append(span)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    name = f"{getattr(node.func.value, 'id', '?')}.{node.func.attr}"
                elif isinstance(node.func, ast.Name):
                    name = node.func.id
                else:
                    continue
                span = self._node_to_span(node, name, char_to_tok, tokens, code, "Call")
                if span:
                    spans.append(span)

        return spans

    def _build_char_token_index(self, tokens: list[TokenWithLogprob]) -> dict[int, int]:
        """Create a char_offset → token_index mapping."""
        char_to_tok: dict[int, int] = {}
        char_offset = 0
        for i, tok in enumerate(tokens):
            for _ in tok.token:
                char_to_tok[char_offset] = i
                char_offset += 1
        return char_to_tok

    def _node_to_span(
        self, node: ast.AST, name: str,
        char_to_tok: dict[int, int],
        tokens: list[TokenWithLogprob],
        code: str,
        node_type: str = "",
    ) -> ASTSpan | None:
        start_line = getattr(node, "lineno", 0)
        end_line = getattr(node, "end_lineno", start_line)

        # Convert line numbers to approximate char offsets
        lines = code.splitlines(keepends=True)
        start_char = sum(len(line) for line in lines[: start_line - 1]) if start_line > 1 else 0
        end_char = sum(len(line) for line in lines[: end_line]) if end_line > 0 else len(code)

        start_tok = char_to_tok.get(start_char, 0)
        end_tok = char_to_tok.get(min(end_char, len(code) - 1), len(tokens) - 1)

        if end_tok <= start_tok:
            return None

        return ASTSpan(
            node_type=node_type or type(node).__name__,
            node_name=name,
            start_token=start_tok,
            end_token=end_tok,
            line_hint=start_line,
        )

    # ── Step 2: Span Confidence ────────────────────────────────────────────

    def _compute_span_confidences(
        self, spans: list[ASTSpan], tokens: list[TokenWithLogprob]
    ) -> dict[int, float]:
        """Compute mean per-token probability for each span (indexed by span index)."""
        confidences: dict[int, float] = {}
        for i, span in enumerate(spans):
            span_tokens = tokens[span.start_token : span.end_token]
            if not span_tokens:
                confidences[i] = 1.0
                continue
            mean_prob = sum(t.probability for t in span_tokens) / len(span_tokens)
            confidences[i] = mean_prob
        return confidences

    # ── Step 3: Git Churn ─────────────────────────────────────────────────

    def _query_git_churn(self) -> dict[str, float]:
        """Extract file-level git churn from ContextBundle (normalized 0–1)."""
        churn: dict[str, float] = {}
        if self.bundle is None:
            return churn
        # historical_decisions contains strings like "payment.py: modified 5 times"
        # Use a simple heuristic: presence in historical_decisions increases churn
        for decision in getattr(self.bundle, "historical_decisions", []):
            parts = decision.split(":")
            if parts:
                fname = parts[0].strip()
                # Count mentions as proxy for churn frequency
                count = churn.get(fname, 0.0) + 1.0
                churn[fname] = count

        # Normalize to [0, 1]
        if churn:
            max_churn = max(churn.values())
            if max_churn > 0:
                churn = {k: v / max_churn for k, v in churn.items()}
        return churn

    def _span_churn(self, span: ASTSpan, churn: dict[str, float]) -> float:
        """Best-effort churn lookup for a span's likely file."""
        if span.file_hint:
            key = Path(span.file_hint).name
            return churn.get(key, 0.0)
        # Fall back: search by node name substring
        for fname, rate in churn.items():
            if span.node_name.lower() in fname.lower():
                return rate
        return 0.0

    # ── Step 4: Probe Target Selection ────────────────────────────────────

    def _select_probe_targets(
        self,
        spans: list[ASTSpan],
        confidences: dict[int, float],
        git_churn: dict[str, float],
    ) -> list[ProbeTarget]:
        targets: list[ProbeTarget] = []
        theta = self._dynamic_theta(len(spans))
        top_n = self.top_n if self.top_n is not None else self.max_probes
        for i, span in enumerate(spans):
            conf = confidences.get(i, 1.0)
            churn = self._span_churn(span, git_churn)
            centrality = self._span_centrality(span)
            fan_io = self._span_fan_io(span)
            public_api = self._span_public_api(span)
            weighted_risk = (
                self.w_churn * (self.churn_alpha * churn)
                + self.w_centrality * centrality
                + self.w_fan_io * fan_io
                + self.w_public_api * public_api
            )
            score = (1.0 - conf) * (1.0 + weighted_risk)

            if score > theta or conf < self.confidence_threshold:
                targets.append(
                    ProbeTarget(
                        span=span,
                        confidence=conf,
                        git_churn=churn,
                        hotspot_score=score,
                        risk_components={
                            "churn": churn,
                            "centrality": centrality,
                            "fan_io": fan_io,
                            "public_api": public_api,
                            "theta": theta,
                        },
                    )
                )

        # Sort by score, deduplicate overlapping spans, cap at max_probes
        targets.sort(key=lambda t: -t.hotspot_score)
        targets = self._deduplicate_overlapping(targets)
        return targets[: min(top_n, self.max_probes)]

    def _dynamic_theta(self, n_spans: int) -> float:
        """Adaptive threshold theta(task, budget) for score(n) > theta selection."""
        complexity = min(1.0, n_spans / 20.0)
        budget_pressure = min(1.0, self.max_probes / 5.0)
        theta = self.score_theta - 0.12 * complexity + 0.08 * budget_pressure
        return max(0.25, min(0.75, theta))

    def _span_centrality(self, span: ASTSpan) -> float:
        if self.bundle is None or not getattr(self.bundle, "call_graph", None):
            return 0.0
        graph = self.bundle.call_graph
        node = span.node_name
        out_degree = len(graph.get(node, []))
        in_degree = sum(1 for _, vs in graph.items() if node in vs)
        degree = in_degree + out_degree
        max_degree = max(
            [len(vs) for vs in graph.values()] + [sum(1 for _, vs in graph.items() if k in vs) for k in graph],
            default=1,
        )
        return min(1.0, degree / max(max_degree, 1))

    def _span_fan_io(self, span: ASTSpan) -> float:
        if self.bundle is None or not getattr(self.bundle, "call_graph", None):
            return 0.0
        graph = self.bundle.call_graph
        node = span.node_name
        fan_out = len(graph.get(node, []))
        fan_in = sum(1 for _, vs in graph.items() if node in vs)
        return min(1.0, (fan_in + fan_out) / 10.0)

    def _span_public_api(self, span: ASTSpan) -> float:
        node = span.node_name
        if node.startswith("_"):
            return 0.0
        if self.bundle is None:
            return 0.5
        entry_points = set(getattr(self.bundle, "entry_points", []) or [])
        if node in entry_points:
            return 1.0
        for c in getattr(self.bundle, "design_constraints", []) or []:
            if "public api" in c.description.lower() and node in c.description:
                return 1.0
        return 0.5

    def _deduplicate_overlapping(self, targets: list[ProbeTarget]) -> list[ProbeTarget]:
        """Remove spans that are substantially contained within a higher-scored span."""
        kept: list[ProbeTarget] = []
        for t in targets:
            dominated = any(
                k.span.start_token <= t.span.start_token and t.span.end_token <= k.span.end_token
                for k in kept
            )
            if not dominated:
                kept.append(t)
        return kept

    # ── Step 5: Probe Question Generation ─────────────────────────────────

    def _generate_probe_question(self, probe: ProbeTarget, code: str) -> str:
        """Generate a human-readable probe question for a low-confidence span."""
        node_desc = f"`{probe.span.node_name}`"
        if probe.span.line_hint:
            node_desc += f"（第 {probe.span.line_hint} 行附近）"

        if self.llm:
            prompt = (
                f"我在生成代码时，对 {node_desc} 的处理逻辑置信度较低"
                f"（置信度: {probe.confidence:.0%}，历史修改热度: {probe.git_churn:.0%}）。\n"
                f"请基于以下上下文，生成一个简洁的确认性问题，问用户这段逻辑的期望行为：\n\n"
                f"代码片段：\n```python\n{self._extract_code_lines(code, probe.span.line_hint, 8)}\n```\n\n"
                f"问题格式：「请确认：...」或「关于 ... 的处理，你期望...？」"
            )
            try:
                question = self.llm.chat([{"role": "user", "content": prompt}])
                return question.strip()
            except Exception:
                pass  # Fall through to rule-based

        # Rule-based fallback
        churn_note = ""
        if probe.git_churn > 0.3:
            churn_note = "（该区域有较多历史修改记录，可能存在隐性约束）"

        return (
            f"⚠️ 我在生成 {node_desc} 时置信度较低{churn_note}。\n"
            f"   请确认：这段逻辑在以下情况应如何处理？\n"
            f"   a) 正常路径的期望返回值是什么？\n"
            f"   b) 异常/边界条件下应该抛出异常还是返回错误码？"
        )

    def _extract_code_lines(self, code: str, start_line: int, n_lines: int) -> str:
        lines = code.splitlines()
        start = max(0, start_line - 1)
        end = min(len(lines), start + n_lines)
        return "\n".join(f"{start + i + 1:3d}: {line}" for i, line in enumerate(lines[start:end]))

    # ── Summary ───────────────────────────────────────────────────────────

    def _build_summary(self, probes: list[ProbeTarget]) -> str:
        if not probes:
            return "✅ 所有代码区域的生成置信度均在阈值之上，无需额外确认。"
        lines = [f"⚠️ 检测到 {len(probes)} 个低置信度区域，建议在生成完成前确认："]
        for p in probes:
            loc = f"第 {p.span.line_hint} 行" if p.span.line_hint else "未知位置"
            lines.append(
                f"  · `{p.span.node_name}` ({loc}) "
                f"— 置信度 {p.confidence:.0%}，历史热度 {p.git_churn:.0%}"
            )
        return "\n".join(lines)


# ─── OpenAI API Helper ───────────────────────────────────────────────────────

def parse_openai_logprobs(openai_response) -> list[TokenWithLogprob]:
    """Convert OpenAI API logprobs response to our internal format.

    Usage:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            logprobs=True,
            top_logprobs=5,
        )
        tokens = parse_openai_logprobs(response)
    """
    tokens: list[TokenWithLogprob] = []
    choices = getattr(openai_response, "choices", [])
    if not choices:
        return tokens
    logprobs_obj = getattr(choices[0], "logprobs", None)
    if logprobs_obj is None:
        return tokens
    content = getattr(logprobs_obj, "content", None) or []
    for item in content:
        tokens.append(
            TokenWithLogprob(
                token=getattr(item, "token", ""),
                logprob=getattr(item, "logprob", 0.0),
                bytes=getattr(item, "bytes", []) or [],
            )
        )
    return tokens


def mock_logprobs_from_code(code: str, seed_confidence: float = 0.85) -> list[TokenWithLogprob]:
    """Generate mock token logprobs for testing without a real LLM.

    Introduces intentional low-confidence regions around common risk patterns
    (try/except, cross-file calls, database operations).
    """
    import random
    rng = random.Random(42)

    risk_keywords = {"try", "except", "commit", "rollback", "transaction", "retry", "raise", "asyncio"}
    tokens: list[TokenWithLogprob] = []

    # Tokenize by whitespace (very rough)
    for word in code.split():
        base_conf = seed_confidence
        # Introduce low confidence around risk keywords
        if any(kw in word.lower() for kw in risk_keywords):
            base_conf = rng.uniform(0.25, 0.45)
        else:
            base_conf = rng.uniform(0.75, 0.98)
        logprob = math.log(max(base_conf, 1e-9))
        tokens.append(TokenWithLogprob(token=word + " ", logprob=logprob))
        # Add space token
        tokens.append(TokenWithLogprob(token=" ", logprob=math.log(0.99)))

    return tokens
