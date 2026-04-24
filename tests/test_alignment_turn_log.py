"""AlignmentRecord.turn_log populated in batch mode."""

from __future__ import annotations

from concordcoder.alignment.llm_dialogue import LLMAlignmentDialogue
from concordcoder.schemas import ContextBundle


def test_run_batch_turn_log_has_tags() -> None:
    bundle = ContextBundle(task_summary="test task")
    dlg = LLMAlignmentDialogue(llm_client=None)
    rec = dlg.run_batch(bundle, prefilled_answers={})
    assert rec.turn_log
    assert rec.turn_log[0].phase == "B"
    assert rec.turn_log[0].xai_question_type == "Why"
    assert rec.turn_log[0].evidence_category == "constraints_batch"
