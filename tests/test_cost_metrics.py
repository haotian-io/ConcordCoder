from concordcoder.schemas import CostMetrics, SingleTaskResult, SingleTaskSpec, GenerationResult


def test_cost_metrics_defaults():
    c = CostMetrics()
    assert c.online_runtime_sec == 0.0
    assert c.total_runtime_sec == 0.0
    assert c.online_turns == 0


def test_single_task_result_includes_cost_and_rq2_fields():
    st = SingleTaskResult(
        spec=SingleTaskSpec(task="x"),
        generation=GenerationResult(),
    )
    assert st.cost.total_runtime_sec == 0.0
    assert st.alignment_turn_log == []
    assert st.user_confidence_score is None
