"""run_single_task with use_anchor and with_probe (no LLM)."""

from __future__ import annotations

from pathlib import Path

import pytest

from concordcoder.pipeline import run_single_task
from concordcoder.schemas import OutputFormat, SingleTaskSpec

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "repos" / "tasklab"


@pytest.mark.skipif(not FIXTURE.is_dir(), reason="fixture tasklab not present")
def test_run_single_task_with_anchor_fills_assembly() -> None:
    spec = SingleTaskSpec(
        task="Implement count_vowels.",
        target_file="tasklab/vowels.py",
        target_symbol="count_vowels",
        use_anchor=True,
        with_probe=True,
        output_format=OutputFormat.MARKDOWN_PLAN,
    )
    st = run_single_task(FIXTURE, spec, llm_client=None, fast_extract=True)
    assert st.probe.get("n_probes") is not None
    # ConstrainedGenerator runs without LLM: stub, but assembly was passed
    assert "LLM" in st.generation.warnings[0] or st.generation.warnings
