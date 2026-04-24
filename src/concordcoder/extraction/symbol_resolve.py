"""Resolve target_symbol to FunctionInfo within static analysis results."""

from __future__ import annotations

from concordcoder.extraction.ast_analyzer import FileAnalysis, FunctionInfo


def find_function_for_symbol(
    analyses: dict[str, FileAnalysis],
    target_file: str,
    target_symbol: str,
) -> FunctionInfo | None:
    """Match ``target_symbol`` to a function in ``target_file`` (qualname or short name)."""
    analysis = analyses.get(target_file)
    if not analysis:
        return None
    for fn in analysis.functions:
        if fn.qualname == target_symbol or fn.name == target_symbol:
            return fn
        if target_symbol.endswith("." + fn.name) and fn.qualname == target_symbol:
            return fn
    return None


def symbol_tokens(target_symbol: str) -> set[str]:
    """Extra keyword tokens for snippet retrieval when narrowing."""
    parts = target_symbol.replace(".", " ").split()
    return {p.lower() for p in parts if len(p) > 2}
