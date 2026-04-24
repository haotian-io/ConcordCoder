"""InlineCoder-style MVP: signature-only anchor draft + upstream/downstream snippet assembly."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from concordcoder.extraction.ast_analyzer import FileAnalysis
from concordcoder.extraction.call_graph import CallGraphBuilder
from concordcoder.extraction.symbol_resolve import find_function_for_symbol
from concordcoder.schemas import AssembledContext, EvidenceLevel, SnippetRef

if TYPE_CHECKING:
    pass


ANCHOR_SYSTEM = """\
你是代码补全助手。用户只提供了函数签名（可能还有类方法），请写一版最短的「草稿实现」(anchor)。
要求：用 Python；可包含 TODO；不要解释；只输出函数/方法体代码块（不要重复签名除非必要）。\
"""


def draft_anchor(
    target_file: str,
    target_symbol: str,
    analyses: dict[str, FileAnalysis],
    llm_client=None,
) -> str:
    """Blind anchor implementation from signature (InlineCoder step 1)."""
    fn = find_function_for_symbol(analyses, target_file, target_symbol)
    if not fn:
        return f"# anchor: could not resolve {target_symbol!r} in {target_file}"
    if not llm_client:
        raise ValueError(
            "draft_anchor requires an LLM client when use_anchor is enabled; set API keys or pass LLMClient."
        )

    args = ", ".join(fn.args)
    qual = fn.qualname
    prompt = (
        f"目标文件: {target_file}\n"
        f"完整限定名: {qual or fn.name}\n"
        f"参数列表: {args}\n"
        f"起止行: {fn.start_line}-{fn.end_line}\n"
        "请只输出可替换进文件的一段草稿实现（方法体或函数体），使用 pass/TODO/raise 均可。"
    )
    out = llm_client.chat(
        [{"role": "user", "content": prompt}],
        system=ANCHOR_SYSTEM,
    )
    return out.strip()


def assemble_inlinecoder_mvp(
    repo_root: Path,
    target_file: str,
    target_symbol: str,
    anchor_draft: str,
    analyses: dict[str, FileAnalysis],
    cg_builder: CallGraphBuilder,
    max_window: int = 1200,
) -> AssembledContext:
    """Upstream = callers' windows; downstream = imported modules (MVP, not literal inlining)."""
    upstream: list[SnippetRef] = []
    downstream: list[SnippetRef] = []
    for caller in sorted(cg_builder.get_dependents(target_file)):
        upstream.extend(_file_window_around_name(repo_root, analyses, caller, target_symbol, 40.0, max_window))
    for dep in sorted(cg_builder.get_dependencies(target_file)):
        downstream.extend(_file_top_snippet(repo_root, dep, 45.0, max_window))
    if not upstream and not downstream:
        tf = find_function_for_symbol(analyses, target_file, target_symbol)
        if tf:
            tpath = repo_root / target_file
            if tpath.is_file():
                lines = tpath.read_text(encoding="utf-8", errors="replace").splitlines()
                a = max(0, tf.start_line - 1)
                b = min(len(lines), tf.end_line)
                text = "\n".join(lines[a:b])
                if len(text) > max_window:
                    text = text[:max_window] + "\n…"
                upstream.append(
                    SnippetRef(
                        path=target_file,
                        start_line=a + 1,
                        end_line=b,
                        text=text,
                        evidence_level=EvidenceLevel.IMPLEMENTATION,
                        relevance_score=10.0,
                    )
                )
    return AssembledContext(
        anchor_draft=anchor_draft,
        upstream_snippets=upstream[:8],
        downstream_snippets=downstream[:8],
    )


def _file_top_snippet(
    repo_root: Path,
    rel: str,
    score: float,
    max_chars: int,
) -> list[SnippetRef]:
    path = repo_root / rel
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return []
    n = min(len(lines), 60)
    text = "\n".join(lines[:n])
    if len(text) > max_chars:
        text = text[:max_chars] + "\n…"
    return [
        SnippetRef(
            path=rel,
            start_line=1,
            end_line=n,
            text=text,
            evidence_level=EvidenceLevel.IMPLEMENTATION,
            relevance_score=score,
        )
    ]


def _file_window_around_name(
    repo_root: Path,
    analyses: dict[str, FileAnalysis],
    rel: str,
    target_symbol: str,
    score: float,
    max_chars: int,
) -> list[SnippetRef]:
    path = repo_root / rel
    if not path.is_file():
        return []
    name_key = target_symbol.split(".")[-1]
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return []
    hit = next((i for i, ln in enumerate(lines) if name_key in ln), 0)
    start = max(0, hit - 5)
    end = min(len(lines), hit + 25)
    text = "\n".join(lines[start:end])
    if len(text) > max_chars:
        text = text[:max_chars] + "\n…"
    return [
        SnippetRef(
            path=rel,
            start_line=start + 1,
            end_line=end,
            text=text,
            evidence_level=EvidenceLevel.IMPLEMENTATION,
            relevance_score=score,
        )
    ]


def merge_assembly_for_prompt(assembly: AssembledContext) -> list[dict]:
    """Merge upstream + downstream snippets for ConstrainedGenerator (ordered, dedup by path+start)."""
    seen: set[tuple[str, int]] = set()
    out: list[dict] = []
    for block, label in (
        (assembly.upstream_snippets, "upstream"),
        (assembly.downstream_snippets, "downstream"),
    ):
        for s in block:
            key = (s.path, s.start_line)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "path": s.path,
                    "start": s.start_line,
                    "end": s.end_line,
                    "text": f"[{label}]\n{s.text}",
                }
            )
    return out
