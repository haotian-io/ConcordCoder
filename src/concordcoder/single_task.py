"""Single-task specification (YAML) and optional apply-to-repo for pytest evaluation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from concordcoder.schemas import ContextDependencyLevel


class FixtureTaskYaml(BaseModel):
    """YAML fixture: one function/symbol in a small repo (CoderEval-style)."""

    id: str
    task: str
    target_file: str
    target_symbol: str
    dependency_level: ContextDependencyLevel
    alignment_answers: dict[str, str] = Field(
        default_factory=dict,
        description="Keys passed to LLMAlignmentDialogue.run_batch (e.g. api_stable).",
    )


def load_task_spec(path: Path) -> FixtureTaskYaml:
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Task file must be a mapping: {path}")
    return FixtureTaskYaml.model_validate(data)


def _extract_code_block(text: str) -> str | None:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def apply_generation_to_repo(
    repo_root: Path,
    target_file: str,
    generated_text: str,
    *,
    begin_marker: str = "# CONCORD_TASK_BEGIN",
    end_marker: str = "# CONCORD_TASK_END",
) -> bool:
    """Replace the region between markers in ``target_file`` with code from a markdown block.

    Markers are expected as indented comments inside the function body. Each line in the
    generated block is prefixed with 4 spaces so it remains valid Python inside the function.

    Returns True if a replacement was written.
    """
    block = _extract_code_block(generated_text)
    if not block:
        return False
    path = repo_root / target_file
    if not path.is_file():
        return False
    full = path.read_text(encoding="utf-8")
    if begin_marker not in full or end_marker not in full:
        return False
    pattern = re.compile(
        re.escape(begin_marker) + r"\n(.*?)\n[ \t]*" + re.escape(end_marker),
        re.DOTALL,
    )
    m = pattern.search(full)
    if not m:
        return False
    inner = "\n".join(
        "    " + (ln if ln.strip() else "")
        for ln in block.rstrip().splitlines()
    )
    new_full = pattern.sub(
        begin_marker + "\n" + inner + "\n    " + end_marker,
        full,
        count=1,
    )
    path.write_text(new_full, encoding="utf-8")
    return True


def result_summary_line(result: Any) -> dict[str, Any]:
    """JSON-serializable row for eval baselines."""
    from concordcoder.schemas import GenerationResult

    if not isinstance(result, GenerationResult):
        return {"error": "not_a_generation_result"}
    return {
        "code_len": len(result.code_plan or ""),
        "warnings_n": len(result.warnings),
        "compliance": result.constraint_compliance,
        "cognitive_len": len(result.cognitive_summary or ""),
    }
