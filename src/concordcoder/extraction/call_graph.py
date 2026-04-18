"""Call graph builder: constructs module-level import dependency and function call graph."""

from __future__ import annotations

import ast
from pathlib import Path

from concordcoder.extraction.ast_analyzer import ASTAnalyzer, FileAnalysis


class CallGraphBuilder:
    """Build a lightweight call/import graph from AST analysis results.

    Output ``graph`` maps a file's relative path to the set of other
    repo-internal files it imports.  Use ``get_callers`` / ``get_callees``
    for navigation.
    """

    def __init__(self) -> None:
        self.import_graph: dict[str, list[str]] = {}   # rel_path → [dep_rel_paths]
        self.function_calls: dict[str, list[str]] = {}  # "file:func" → ["file:func", ...]
        self._module_to_path: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self, repo_root: Path, analyses: dict[str, FileAnalysis]) -> None:
        """Build call graph from pre-computed FileAnalysis map."""
        self._build_module_map(repo_root, analyses)
        self._build_import_graph(analyses)

    def get_dependents(self, rel_path: str) -> list[str]:
        """Return files that import ``rel_path``."""
        result = []
        for src, deps in self.import_graph.items():
            if rel_path in deps:
                result.append(src)
        return result

    def get_dependencies(self, rel_path: str) -> list[str]:
        """Return files that ``rel_path`` imports."""
        return self.import_graph.get(rel_path, [])

    def affected_by(self, changed_paths: list[str]) -> list[str]:
        """Breadth-first: files potentially affected if ``changed_paths`` change."""
        visited: set[str] = set(changed_paths)
        frontier = list(changed_paths)
        while frontier:
            nxt = []
            for path in frontier:
                for dep in self.get_dependents(path):
                    if dep not in visited:
                        visited.add(dep)
                        nxt.append(dep)
            frontier = nxt
        return [p for p in visited if p not in changed_paths]

    def to_dict(self) -> dict[str, list[str]]:
        return dict(self.import_graph)

    def summarize(self, top_n: int = 10) -> list[str]:
        """Return human-readable summary of most-imported files."""
        counts: dict[str, int] = {}
        for deps in self.import_graph.values():
            for d in deps:
                counts[d] = counts.get(d, 0) + 1
        ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return [f"{p} (imported by {n} files)" for p, n in ranked]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_module_map(self, repo_root: Path, analyses: dict[str, FileAnalysis]) -> None:
        """Map Python module dotted path → relative file path."""
        for rel_path in analyses:
            p = Path(rel_path)
            # Convert file path to module notation
            parts = list(p.with_suffix("").parts)
            if parts and parts[-1] == "__init__":
                parts = parts[:-1]
            module = ".".join(parts)
            self._module_to_path[module] = rel_path

    def _build_import_graph(self, analyses: dict[str, FileAnalysis]) -> None:
        for rel_path, analysis in analyses.items():
            deps: list[str] = []
            for imp in analysis.imports:
                if imp.is_from:
                    resolved = self._resolve_module(imp.module)
                    if resolved:
                        deps.append(resolved)
                else:
                    for name in imp.names:
                        resolved = self._resolve_module(name)
                        if resolved:
                            deps.append(resolved)
            self.import_graph[rel_path] = list(dict.fromkeys(deps))  # dedup, preserve order

    def _resolve_module(self, module: str) -> str | None:
        """Try to resolve dotted module name to a repo-relative path."""
        if not module:
            return None
        # Try full path, then progressively shorter prefixes
        parts = module.split(".")
        for length in range(len(parts), 0, -1):
            candidate = ".".join(parts[:length])
            if candidate in self._module_to_path:
                return self._module_to_path[candidate]
        return None


def build_call_graph(repo_root: Path, max_files: int = 120) -> tuple[CallGraphBuilder, dict[str, FileAnalysis]]:
    """Convenience function: run AST analysis then build call graph."""
    analyzer = ASTAnalyzer()
    analyses = analyzer.analyze_repo(repo_root, max_files=max_files)
    builder = CallGraphBuilder()
    builder.build(repo_root, analyses)
    return builder, analyses
