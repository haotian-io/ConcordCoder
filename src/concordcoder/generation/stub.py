"""Placeholder for constrained patch generation + verify loop."""

from __future__ import annotations

from pathlib import Path

from concordcoder.schemas import AlignmentRecord, ContextBundle, GenerationRequest


def constrained_generation_placeholder(req: GenerationRequest) -> str:
    """Returns a human-readable plan; swap for LLM + patch apply + pytest/lint."""
    lines = [
        "# ConcordCoder generation plan (stub)",
        "",
        f"Repo: {req.repo_root}",
        "",
        "## Refined intent",
        req.alignment.refined_intent or req.user_request,
        "",
        "## Hard constraints",
    ]
    for c in req.alignment.confirmed_constraints:
        if c.hard:
            lines.append(f"- [{c.id}] {c.description}")
    lines.extend(["", "## Soft constraints"])
    for c in req.alignment.confirmed_constraints:
        if not c.hard:
            lines.append(f"- [{c.id}] {c.description}")
    lines.extend(["", "## Evidence snippets (sample)", ""])
    for s in req.bundle.snippets[:5]:
        lines.append(f"- {s.path}:{s.start_line}-{s.end_line}")
    lines.append("")
    lines.append("Next: wire OpenAI/Anthropic + `subprocess` test loop.")
    return "\n".join(lines)


def write_plan(repo_root: str | Path, text: str, name: str = "CONCORD_PLAN.md") -> Path:
    path = Path(repo_root) / name
    path.write_text(text, encoding="utf-8")
    return path
