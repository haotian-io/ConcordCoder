"""End-to-end pipeline: extract → align → constrained generation."""

from __future__ import annotations

from pathlib import Path

from concordcoder.alignment.dialogue import AlignmentDialogue
from concordcoder.alignment.llm_dialogue import LLMAlignmentDialogue
from concordcoder.extraction.bundle_builder import BundleBuilder
from concordcoder.generation.constrained_gen import ConstrainedGenerator
from concordcoder.generation.stub import write_plan
from concordcoder.schemas import GenerationRequest, GenerationResult


def run_pipeline(
    repo_root: str | Path,
    task_text: str,
    answers: dict[str, str] | None = None,
    llm_client=None,
    interactive: bool = False,
) -> GenerationResult:
    """Full ConcordCoder pipeline.

    Args:
        repo_root: Path to the repository root.
        task_text: Natural language task description.
        answers: Pre-filled answers for batch/non-interactive use.
        llm_client: Optional LLMClient instance. If None, uses rule-based fallbacks.
        interactive: If True, start interactive terminal dialogue for alignment.

    Returns:
        GenerationResult with code, cognitive summary, and compliance report.
    """
    repo_root = Path(repo_root).resolve()

    # ── Phase 1: Context Extraction ──────────────────────────────
    builder = BundleBuilder(repo_root, llm_client=llm_client)
    bundle = builder.build(task_text)

    # ── Phase 2: Alignment Dialogue ───────────────────────────────
    if interactive and llm_client is not None:
        dialogue = LLMAlignmentDialogue(llm_client=llm_client)
        alignment = dialogue.run_interactive(bundle)
    elif llm_client is not None:
        dialogue = LLMAlignmentDialogue(llm_client=llm_client)
        alignment = dialogue.run_batch(bundle, prefilled_answers=answers)
    else:
        # Fallback: rule-based dialogue (no LLM)
        legacy = AlignmentDialogue()
        alignment = legacy.draft_record(bundle, answers)

    # ── Phase 3: Constrained Generation ──────────────────────────
    req = GenerationRequest(
        repo_root=str(repo_root),
        user_request=task_text,
        bundle=bundle,
        alignment=alignment,
    )
    generator = ConstrainedGenerator(llm_client=llm_client)
    result = generator.generate(req)

    return result


def run_pipeline_and_write(
    repo_root: str | Path,
    task_text: str,
    answers: dict[str, str] | None = None,
    plan_name: str = "CONCORD_PLAN.md",
    llm_client=None,
    interactive: bool = False,
) -> Path:
    """Run pipeline and write the result to a markdown plan file."""
    result = run_pipeline(
        repo_root=repo_root,
        task_text=task_text,
        answers=answers,
        llm_client=llm_client,
        interactive=interactive,
    )
    output_text = result.code_plan
    if result.cognitive_summary and result.cognitive_summary not in output_text:
        output_text += "\n\n" + result.cognitive_summary
    if result.warnings:
        output_text += "\n\n---\n**⚠️ 警告:**\n" + "\n".join(f"- {w}" for w in result.warnings)
    return write_plan(repo_root, output_text, plan_name)
