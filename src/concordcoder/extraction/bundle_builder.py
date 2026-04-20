"""Upgraded BundleBuilder: keyword matching + AST analysis + call graph + git history + test extraction."""

from __future__ import annotations

import re
from pathlib import Path

from concordcoder.extraction.ast_analyzer import ASTAnalyzer
from concordcoder.extraction.call_graph import CallGraphBuilder
from concordcoder.extraction.git_historian import GitHistorian
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
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.max_files = max_files
        self.max_snippet_chars = max_snippet_chars
        self.llm_client = llm_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self, task_text: str) -> ContextBundle:
        tokens = self._tokens(task_text)

        # ---- Layer 0: keyword snippet retrieval ----
        snippets = self._keyword_snippets(tokens)

        # ---- Layer 1: AST + call graph ----
        analyzer = ASTAnalyzer()
        analyses = analyzer.analyze_repo(self.repo_root, max_files=self.max_files)
        cg_builder = CallGraphBuilder()
        cg_builder.build(self.repo_root, analyses)

        structural_facts = self._structural_facts(analyses, cg_builder, tokens)
        entry_points = self._detect_entry_points(analyses)
        affected_modules = self._detect_affected_modules(analyses, cg_builder, tokens)
        design_constraints = self._constraints_from_ast(analyses, tokens)

        # ---- Layer 2: git history ----
        historian = GitHistorian(self.repo_root)
        git_analysis = historian.analyze(max_commits=80)
        historical_decisions = []
        if git_analysis.available:
            historical_decisions = git_analysis.design_decisions
            if git_analysis.hotspot_files:
                structural_facts.append(
                    "最频繁修改的文件（热点）: " + ", ".join(git_analysis.hotspot_files[:5])
                )

        # ---- Layer 3: test file analysis ----
        test_extractor = TestExtractor()
        test_analysis = test_extractor.analyze_repo(self.repo_root)
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
            call_graph=cg_builder.to_dict(),
            entry_points=entry_points,
            historical_decisions=historical_decisions,
            test_expectations=test_expectations,
            affected_modules=affected_modules,
            metadata={
                "builder": "multi_layer_v1",
                "files_scanned": len(analyses),
                "test_files": len(test_analysis.test_files),
                "git_available": git_analysis.available,
            },
        )

    # ------------------------------------------------------------------
    # Layer helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text)}

    def _keyword_snippets(self, tokens: set[str]) -> list[SnippetRef]:
        snippets: list[SnippetRef] = []
        skip = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}

        scanned = 0
        for root, dirs, files in sorted(
            (entry for entry in self.repo_root.walk() if True),
            key=lambda x: str(x[0]),
        ) if hasattr(self.repo_root, "walk") else self._os_walk():
            pass

        # cross-compatible path walk
        import os
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

    def _os_walk(self):
        import os
        return os.walk(self.repo_root)

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
