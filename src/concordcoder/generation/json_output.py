"""Parse LLM responses for `json_files` and `unified_diff` output modes."""

from __future__ import annotations

import json
import re
from typing import Any

from concordcoder.schemas import FileContentItem


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            end = -1 if lines[-1].strip() == "```" else len(lines)
            return "\n".join(lines[1:end]).strip()
    return t


def parse_json_files_response(raw: str) -> tuple[list[FileContentItem], list[str]]:
    """Return (files, warnings). On failure, files is empty and warnings describe why."""
    files, _, warnings = parse_json_generation_response(raw)
    return files, warnings


def parse_json_generation_response(
    raw: str,
) -> tuple[list[FileContentItem], str, list[str]]:
    """Return (files, cognitive_summary, warnings)."""
    warnings: list[str] = []
    summary = ""
    cleaned = _strip_fences(raw)
    data: Any
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return [], "", [f"JSON 解析失败: {e}"]

    if not isinstance(data, dict):
        return [], "", ["期望顶层 JSON 对象，含 'files' 键"]

    summ = data.get("cognitive_summary", "")
    if isinstance(summ, str):
        summary = summ

    files_raw = data.get("files")
    if not isinstance(files_raw, list):
        return [], summary, ["缺少 'files' 数组或类型错误"]

    out: list[FileContentItem] = []
    for i, item in enumerate(files_raw):
        if not isinstance(item, dict):
            warnings.append(f"files[{i}] 非对象，已跳过")
            continue
        p = item.get("path", "")
        c = item.get("content", "")
        if not p or not isinstance(p, str):
            warnings.append(f"files[{i}] 缺少 path")
            continue
        if not isinstance(c, str):
            warnings.append(f"files[{i}] content 非字符串，已转 str")
            c = str(c)
        out.append(FileContentItem(path=p.replace("\\", "/"), content=c))

    if not out:
        warnings.append("files 数组为空或全部无效")
    return out, summary, warnings


def parse_unified_diff_response(raw: str) -> str:
    """Return diff text, stripping optional markdown fence and leading prose."""
    t = raw.strip()
    m = re.search(r"```(?:diff|patch|text)?\s*\n(.*?)```", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
    t = t.replace("\r\n", "\n")
    if not re.search(r"(?m)(?:^diff --git |^\+\+\+ b/)", t):
        for start_pat in (r"(?m)^diff --git a/\S+ b/\S+.*$", r"(?m)^--- a/(.+)$"):
            mm = re.search(start_pat, t)
            if mm:
                t = t[mm.start() :]
                break
    return t.strip()


def paths_from_unified_diff(text: str) -> list[str]:
    """Collect changed file paths from a unified diff (``+++ b/`` and ``git diff`` headers)."""
    if not text or not text.strip():
        return []
    text = text.replace("\r\n", "\n")
    out: list[str] = []
    for line in text.splitlines():
        line = line.rstrip()
        m = re.match(r"^\+\+\+ b/(\S+)", line)
        if m:
            p = m.group(1).strip()
            if p != "/dev/null":
                out.append(p)
            continue
        m = re.match(r"^diff --git a/(\S+) b/(\S+)", line)
        if m:
            p = m.group(2).strip()
            if p != "/dev/null":
                out.append(p)
    return list(dict.fromkeys(out))[:32]
