"""Upgraded BundleBuilder: keyword matching + AST analysis + call graph + git history + test extraction."""

from __future__ import annotations

import re
import time
from pathlib import Path
from types import SimpleNamespace

from concordcoder.extraction.ast_analyzer import ASTAnalyzer
from concordcoder.extraction.call_graph import CallGraphBuilder
from concordcoder.extraction.git_historian import GitHistorian
from concordcoder.extraction.symbol_resolve import find_function_for_symbol, symbol_tokens
from concordcoder.extraction.test_extractor import TestExtractor
from concordcoder.schemas import (
    Constraint,
    ContextBundle,
    EvidenceLevel,
    RiskItem,
    SnippetRef,
)

_ENTRY_NAMES = {"__init__.py", "main.py", "app.py", "cli.py", "index.ts", "main.go", "server.py"}


class BundleBuilder:
    """Multi-layer context extractor.

    Layer 0 (always): keyword window snippet retrieval (baseline)
    Layer 1 (always): AST static analysis – functions, classes, call graph
    Layer 2 (always): Git history analysis – design decisions, hotspots
    Layer 3 (always): Test file analysis – inferred constraints
    Layer 4 (optional): LLM summarisation (enabled when llm_client is provided)
    """

    CODE_GLOBS = ("*.py", "*.ts", "*.tsx", "*.js", "*.jsx", "*.go", "*.java", "*.rs")

    def __init__(
        self,
        repo_root: str | Path,
        max_files: int = 120,
        max_snippet_chars: int = 1200,
        llm_client=None,   # optional: LLMClient instance for layer-4 summarisation
        target_file: str | None = None,
        target_symbol: str | None = None,
        fast: bool = False,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.max_files = max_files
        self.max_snippet_chars = max_snippet_chars
        self.llm_client = llm_client
        self.target_file = target_file.replace("\\", "/") if target_file else None
        self.target_symbol = target_symbol
        self.fast = fast
        # Populated by build() for cost accounting
        self.timings: dict[str, float] = {
            "keyword_sec": 0.0,
            "ast_sec": 0.0,
            "git_sec": 0.0,
            "test_sec": 0.0,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self, task_text: str) -> ContextBundle:
        tokens = self._tokens(task_text)
        if self.target_symbol:
            tokens = set(tokens) | symbol_tokens(self.target_symbol)

        # ---- Layer 0: keyword snippet retrieval ----
        _t0 = time.perf_counter()
        snippets = self._keyword_snippets(tokens)
        self.timings["keyword_sec"] = time.perf_counter() - _t0

        # ---- Layer 1: AST + call graph ----
        _t0 = time.perf_counter()
        analyzer = ASTAnalyzer()
        eff_max = min(40, self.max_files) if self.fast else self.max_files
        analyses = analyzer.analyze_repo(self.repo_root, max_files=eff_max)
        cg_builder = CallGraphBuilder()
        cg_builder.build(self.repo_root, analyses)

        structural_facts = self._structural_facts(analyses, cg_builder, tokens)
        entry_points = self._detect_entry_points(analyses)
        affected_modules = self._detect_affected_modules(analyses, cg_builder, tokens)
        design_constraints = self._constraints_from_ast(analyses, tokens)
        self.timings["ast_sec"] = time.perf_counter() - _t0

        # ---- Layer 2: git history ----
        _t0 = time.perf_counter()
        if self.fast:
            git_analysis = SimpleNamespace(
                available=False,
                error="fast 模式已跳过",
                design_decisions=[],
                hotspot_files=[],
            )
        else:
            historian = GitHistorian(self.repo_root)
            git_analysis = historian.analyze(max_commits=80)
        self.timings["git_sec"] = time.perf_counter() - _t0
        historical_decisions = []
        if git_analysis.available:
            historical_decisions = git_analysis.design_decisions
            if git_analysis.hotspot_files:
                structural_facts.append(
                    "最频繁修改的文件（热点）: " + ", ".join(git_analysis.hotspot_files[:5])
                )

        # ---- Layer 3: test file analysis ----
        _t0 = time.perf_counter()
        if self.fast:
            test_analysis = SimpleNamespace(
                expectations=[],
                fixture_names=[],
                test_files=[],
            )
        else:
            test_extractor = TestExtractor()
            test_analysis = test_extractor.analyze_repo(self.repo_root)
        self.timings["test_sec"] = time.perf_counter() - _t0
        test_expectations = [
            f"[{e.test_file}::{e.test_name}] {e.description}"
            for e in test_analysis.expectations[:20]
        ]
        if test_analysis.fixture_names:
            structural_facts.append(
                "pytest fixtures: " + ", ".join(sorted(set(test_analysis.fixture_names))[:10])
            )
        if test_analysis.test_files:
            structural_facts.append(
                f"测试文件 ({len(test_analysis.test_files)} 个): "
                + ", ".join(test_analysis.test_files[:5])
            )

        call_graph_dict = cg_builder.to_dict()
        metadata_narrow: dict = {
            "builder": "multi_layer_v1",
            "files_scanned": len(analyses),
            "test_files": len(test_analysis.test_files),
            "git_available": git_analysis.available,
            "fast": self.fast,
        }

        # ---- Optional: narrow scope to one file + symbol (single-task mode) ----
        if self.target_file and self.target_symbol:
            structural_facts.insert(
                0,
                f"收窄模式：目标符号 `{self.target_symbol}` 于 `{self.target_file}`",
            )
            snippets, call_graph_dict = self._apply_narrow_scope(
                analyses,
                cg_builder,
                snippets,
                call_graph_dict,
            )
            metadata_narrow["narrow_mode"] = True
            metadata_narrow["target_file"] = self.target_file
            metadata_narrow["target_symbol"] = self.target_symbol
        else:
            metadata_narrow["narrow_mode"] = False

        # ---- Open questions ----
        open_q: list[str] = []
        if not snippets:
            open_q.append("任务关键词与仓库文件无交集，请提供模块名或文件路径。")
        if not git_analysis.available:
            open_q.append(f"无法读取 git 历史: {git_analysis.error}")

        # ---- Risks ----
        risks = self._detect_risks(analyses, cg_builder, tokens, git_analysis)

        return ContextBundle(
            task_summary=task_text.strip(),
            structural_facts=structural_facts[:25],
            snippets=snippets[:30],
            constraints_guess=design_constraints,
            design_constraints=design_constraints,
            risks=risks,
            open_questions=open_q,
            call_graph=call_graph_dict,
            entry_points=entry_points,
            historical_decisions=historical_decisions,
            test_expectations=test_expectations,
            affected_modules=affected_modules,
            metadata=metadata_narrow,
        )

    # ------------------------------------------------------------------
    # Layer helpers
    # ------------------------------------------------------------------

    def _apply_narrow_scope(
        self,
        analyses: dict,
        cg_builder: CallGraphBuilder,
        snippets: list[SnippetRef],
        call_graph_dict: dict[str, list[str]],
    ) -> tuple[list[SnippetRef], dict[str, list[str]]]:
        assert self.target_file and self.target_symbol
        tf = self.target_file
        fn = find_function_for_symbol(analyses, tf, self.target_symbol)
        priority: set[str] = {tf}
        priority |= set(cg_builder.get_dependents(tf))
        priority |= set(cg_builder.get_dependencies(tf))
        new_snippets: list[SnippetRef] = []
        for rel in sorted(priority):
            a = analyses.get(rel)
            if not a:
                continue
            path = self.repo_root / rel
            if not path.is_file():
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            if not lines:
                continue
            if rel == tf and fn is not None:
                start = max(0, fn.start_line - 2)
                end = min(len(lines), fn.end_line + 2)
            else:
                key = self.target_symbol.split(".")[-1].lower()
                hit = next((i for i, line in enumerate(lines) if key in line.lower()), 0)
                start = max(0, hit - 3)
                end = min(len(lines), hit + 22)
            text = "\n".join(lines[start:end])
            if len(text) > self.max_snippet_chars:
                text = text[: self.max_snippet_chars] + "\n…"
            new_snippets.append(
                SnippetRef(
                    path=rel,
                    start_line=start + 1,
                    end_line=end,
                    text=text,
                    evidence_level=EvidenceLevel.IMPLEMENTATION,
                    relevance_score=100.0 if rel == tf else 55.0,
                )
            )
        if not new_snippets:
            for s in snippets:
                if s.path in priority or s.path.replace("\\", "/") in priority:
                    new_snippets.append(s)
        if not new_snippets:
            new_snippets = snippets
        sub: dict[str, list[str]] = {}
        for k, v in call_graph_dict.items():
            if k in priority:
                sub[k] = [d for d in v if d in priority]
        for k in priority:
            sub.setdefault(k, [d for d in call_graph_dict.get(k, []) if d in priority])
        return new_snippets, sub

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text)}

    def _keyword_snippets(self, tokens: set[str]) -> list[SnippetRef]:
        snippets: list[SnippetRef] = []
        skip = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}

        import os
        scanned = 0
        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if d not in skip and not d.startswith(".")]
            for name in files:
                if not any(name.endswith(ext.replace("*", "")) for ext in self.CODE_GLOBS):
                    continue
                if scanned >= self.max_files:
                    break
                path = Path(root) / name
                rel = str(path.relative_to(self.repo_root))
                try:
                    raw = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                scanned += 1
                lines = raw.splitlines()
                score = sum(1 for t in tokens if t in raw.lower())
                if score == 0:
                    continue
                hit_idx = next(
                    (i for i, line in enumerate(lines) if any(t in line.lower() for t in tokens)),
                    0,
                )
                start = max(0, hit_idx - 5)
                end = min(len(lines), hit_idx + 25)
                window = "\n".join(lines[start:end])
                if len(window) > self.max_snippet_chars:
                    window = window[: self.max_snippet_chars] + "\n…"
                snippets.append(
                    SnippetRef(
                        path=rel,
                        start_line=start + 1,
                        end_line=end,
                        text=window,
                        evidence_level=EvidenceLevel.IMPLEMENTATION,
                        relevance_score=float(score),
                    )
                )

        # Sort by relevance score descending
        snippets.sort(key=lambda s: s.relevance_score, reverse=True)
        return snippets


    def _structural_facts(self, analyses, cg_builder: CallGraphBuilder, tokens: set[str]) -> list[str]:
        facts: list[str] = []
        summary = cg_builder.summarize(top_n=5)
        if summary:
            facts.append("最被依赖的模块: " + "; ".join(summary))

        # Collect public functions whose names match task tokens
        for rel_path, analysis in analyses.items():
            for fn in analysis.functions:
                if fn.is_public and any(t in fn.name.lower() for t in tokens):
                    sig = f"{fn.name}({', '.join(fn.args)})"
                    callers = cg_builder.get_dependents(rel_path)
                    caller_str = f"（被 {len(callers)} 个文件导入）" if callers else ""
                    facts.append(f"[{rel_path}] 公开函数 `{sig}`{caller_str}")

        return facts

    def _detect_entry_points(self, analyses) -> list[str]:
        return [rel for rel in analyses if Path(rel).name in _ENTRY_NAMES]

    def _detect_affected_modules(self, analyses, cg_builder: CallGraphBuilder, tokens: set[str]) -> list[str]:
        candidate_paths = [
            rel for rel, a in analyses.items()
            if any(t in rel.lower() for t in tokens)
        ]
        affected = cg_builder.affected_by(candidate_paths)
        return affected[:15]

    def _constraints_from_ast(self, analyses, tokens: set[str]) -> list[Constraint]:
        constraints: list[Constraint] = []
        for rel_path, analysis in analyses.items():
            for fn in analysis.functions:
                if not fn.is_public:
                    continue
                if not any(t in fn.name.lower() or t in rel_path.lower() for t in tokens):
                    continue
                if fn.docstring and any(
                    kw in fn.docstring.lower()
                    for kw in ("do not", "must not", "never", "deprecated", "backward compat")
                ):
                    constraints.append(
                        Constraint(
                            id=f"docstring_{fn.name}",
                            description=f"`{fn.name}` 的文档注释包含约束: {fn.docstring[:200]}",
                            hard=True,
                            source=f"{rel_path}:{fn.start_line}",
                        )
                    )
        return constraints

    def _detect_risks(self, analyses, cg_builder: CallGraphBuilder, tokens: set[str], git_analysis) -> list[RiskItem]:
        risks: list[RiskItem] = []

        # Risk: high-fanout public function being touched
        for rel_path, analysis in analyses.items():
            for fn in analysis.functions:
                if not fn.is_public:
                    continue
                if not any(t in fn.name.lower() or t in rel_path.lower() for t in tokens):
                    continue
                deps = cg_builder.get_dependents(rel_path)
                if len(deps) >= 3:
                    risks.append(
                        RiskItem(
                            category="high_fanout",
                            detail=f"`{fn.qualname}` 所在的 {rel_path} 被 {len(deps)} 个文件导入，修改签名影响范围广。",
                            severity="high",
                        )
                    )

        # Risk: hotspot file overlap
        if git_analysis.available:
            hotspot_set = set(git_analysis.hotspot_files[:5])
            for rel_path in analyses:
                if rel_path in hotspot_set and any(t in rel_path.lower() for t in tokens):
                    risks.append(
                        RiskItem(
                            category="hotspot",
                            detail=f"{rel_path} 是高频修改热点文件，存在冲突风险。",
                            severity="medium",
                        )
                    )

        return risks
