"""End-to-end pipeline: extract → align → constrained generation."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from concordcoder.alignment.dialogue import AlignmentDialogue
from concordcoder.alignment.llm_dialogue import LLMAlignmentDialogue
from concordcoder.extraction.bundle_builder import BundleBuilder
from concordcoder.generation.constrained_gen import ConstrainedGenerator
from concordcoder.generation.stub import write_plan
from concordcoder.schemas import (
    GenerationRequest,
    GenerationResult,
    OutputFormat,
    CostMetrics,
    SingleTaskResult,
    SingleTaskSpec,
)


def run_pipeline(
    repo_root: str | Path,
    task_text: str,
    answers: dict[str, str] | None = None,
    llm_client=None,
    interactive: bool = False,
) -> GenerationResult:
    """Full ConcordCoder pipeline. ``llm_client`` is required (set API keys or pass an instance)."""
    if llm_client is None:
        raise ValueError(
            "llm_client is required for run_pipeline. Set OPENAI_API_KEY (and optional "
            "OPENAI_BASE_URL) or ANTHROPIC_API_KEY, or pass an LLMClient instance."
        )
    repo_root = Path(repo_root).resolve()

    # ── Phase 1: Context Extraction ──────────────────────────────
    builder = BundleBuilder(repo_root, llm_client=llm_client)
    bundle = builder.build(task_text)

    # ── Phase 2: Alignment Dialogue ───────────────────────────────
    if interactive:
        dialogue = LLMAlignmentDialogue(llm_client=llm_client)
        alignment = dialogue.run_interactive(bundle)
    else:
        dialogue = LLMAlignmentDialogue(llm_client=llm_client)
        alignment = dialogue.run_batch(bundle, prefilled_answers=answers)

    # ── Phase 3: Constrained Generation ──────────────────────────
    req = GenerationRequest(
        repo_root=str(repo_root),
        user_request=task_text,
        bundle=bundle,
        alignment=alignment,
        output_format=OutputFormat.MARKDOWN_PLAN,
    )
    generator = ConstrainedGenerator(llm_client=llm_client)
    result = generator.generate(req)

    return result


def run_single_task(
    repo_root: str | Path,
    spec: SingleTaskSpec,
    llm_client=None,
    *,
    fast_extract: bool = False,
) -> SingleTaskResult:
    """Single bounded run: alignment mode controlled by ``spec.full_align`` (default: LLM batch alignment)."""
    if llm_client is None:
        raise ValueError(
            "llm_client is required for run_single_task. Set OPENAI_API_KEY (and optional "
            "OPENAI_BASE_URL) or ANTHROPIC_API_KEY, or pass an LLMClient instance."
        )
    repo_root = Path(repo_root).resolve()
    t_start = time.perf_counter()

    eff_max_files = min(40, 120) if fast_extract else 120

    t_extract_0 = time.perf_counter()
    builder = BundleBuilder(
        repo_root,
        llm_client=llm_client,
        fast=fast_extract,
        target_file=spec.target_file,
        target_symbol=spec.target_symbol,
    )
    bundle = builder.build(spec.task)
    offline_extract_sec = time.perf_counter() - t_extract_0

    t_align_0 = time.perf_counter()
    if spec.full_align:
        dialogue = LLMAlignmentDialogue(llm_client=llm_client)
        alignment = dialogue.run_batch(bundle, prefilled_answers=spec.answers)
    else:
        legacy = AlignmentDialogue()
        alignment = legacy.draft_record(bundle, spec.answers or None)
    online_align_sec = time.perf_counter() - t_align_0

    if spec.allowlist_paths:
        alignment = alignment.model_copy(update={"allowlist_paths": spec.allowlist_paths})

    assembly = None
    probe_data: dict = {}
    anchor_text = ""
    anchor_logprobs: list | None = None
    anchor_logprob_error: str | None = None

    if spec.use_anchor and spec.target_file and spec.target_symbol:
        from concordcoder.extraction.call_graph import build_call_graph
        from concordcoder.generation.anchor_pipeline import (
            assemble_inlinecoder_mvp,
            draft_anchor,
            draft_anchor_with_logprobs,
        )

        cg_builder, analyses = build_call_graph(repo_root, max_files=eff_max_files)
        use_real_lp = (
            spec.with_probe
            and os.environ.get("CONCORD_REAL_LOGPROBS", "").lower() in ("1", "true", "yes")
            and getattr(llm_client, "backend", "") == "openai"
        )
        if use_real_lp:
            try:
                anchor_text, anchor_logprobs = draft_anchor_with_logprobs(
                    spec.target_file, spec.target_symbol, analyses, llm_client
                )
            except (RuntimeError, ValueError) as e:
                anchor_text = draft_anchor(
                    spec.target_file, spec.target_symbol, analyses, llm_client
                )
                anchor_logprobs = None
                anchor_logprob_error = str(e)
        else:
            anchor_text = draft_anchor(
                spec.target_file, spec.target_symbol, analyses, llm_client
            )
        assembly = assemble_inlinecoder_mvp(
            repo_root,
            spec.target_file,
            spec.target_symbol,
            anchor_text,
            analyses,
            cg_builder,
        )

        if spec.with_probe:
            from concordcoder.generation.probing import ProbingEngine, mock_logprobs_from_code

            engine = ProbingEngine(llm_client=llm_client, bundle=bundle)
            tokens = (
                anchor_logprobs
                if anchor_logprobs
                else mock_logprobs_from_code(anchor_text)
            )
            if anchor_logprobs:
                logprob_source = "openai_chat_logprobs"
            elif anchor_logprob_error:
                logprob_source = "mock_fallback_after_anchor_error"
            else:
                logprob_source = "mock_default"
            if anchor_logprobs is not None and len(anchor_logprobs) == 0:
                tokens = mock_logprobs_from_code(anchor_text)
                logprob_source = "mock_fallback_empty_logprobs"
            pr = engine.run(anchor_text, tokens)
            probe_data = {
                "needs_probing": pr.needs_probing,
                "probe_questions": pr.probe_questions,
                "low_confidence_summary": pr.low_confidence_summary,
                "n_probes": len(pr.probes),
                "logprob_source": logprob_source,
            }
            if anchor_logprob_error:
                probe_data["logprob_error"] = anchor_logprob_error

    req = GenerationRequest(
        repo_root=str(repo_root),
        user_request=spec.task,
        bundle=bundle,
        alignment=alignment,
        output_format=spec.output_format,
        assembly=assembly,
    )
    t_gen_0 = time.perf_counter()
    result = ConstrainedGenerator(llm_client=llm_client).generate(req)
    online_gen_sec = time.perf_counter() - t_gen_0

    parsed = list(result.structured_files)
    udiff = result.unified_diff_text or ""

    return SingleTaskResult(
        spec=spec,
        generation=result,
        parsed_files=parsed,
        unified_diff=udiff,
        probe=probe_data,
        alignment_turn_log=list(alignment.turn_log),
        cost=CostMetrics(
            online_runtime_sec=online_align_sec + online_gen_sec,
            online_turns=max(0, len(alignment.turn_log)),
            offline_extract_sec=offline_extract_sec,
            offline_git_sec=0.0,
            offline_analysis_sec=0.0,
            total_runtime_sec=time.perf_counter() - t_start,
        ),
    )


def write_single_task_artifacts(
    st: SingleTaskResult,
    out_dir: str | Path,
) -> Path:
    """Write ``result.json``, optional ``files/``, ``plan.md`` / ``diff.patch`` under ``out_dir``."""
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    g = st.generation
    fmt = st.spec.output_format

    if st.parsed_files:
        files_root = out / "files"
        for item in st.parsed_files:
            p = files_root / item.path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(item.content, encoding="utf-8")

    if fmt == OutputFormat.MARKDOWN_PLAN:
        text = g.code_plan
        if g.cognitive_summary and g.cognitive_summary not in text:
            text += "\n\n" + g.cognitive_summary
        if g.warnings:
            text += "\n\n---\n**警告**\n" + "\n".join(f"- {w}" for w in g.warnings)
        (out / "plan.md").write_text(text, encoding="utf-8")
    elif fmt == OutputFormat.UNIFIED_DIFF and st.unified_diff:
        (out / "diff.patch").write_text(st.unified_diff, encoding="utf-8")
    elif fmt == OutputFormat.JSON_FILES and g.code_plan:
        (out / "raw_model_output.txt").write_text(g.code_plan, encoding="utf-8")

    st_out = st.model_copy(update={"out_dir": str(out)})
    (out / "result.json").write_text(
        json.dumps(st_out.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out


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
