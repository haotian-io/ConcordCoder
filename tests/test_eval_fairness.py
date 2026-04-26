from pathlib import Path


def test_mini_eval_exposes_fairness_budget_keys():
    txt = Path("scripts/mini_eval.py").read_text(encoding="utf-8")
    assert "CONCORD_FAIR_MAX_TURNS" in txt
    assert "CONCORD_FAIR_MAX_PROMPT_TOKENS" in txt
    assert "fairness_budget" in txt


def test_rq1_runner_supports_posthoc_condition():
    txt = Path("scripts/rq1_runner.py").read_text(encoding="utf-8")
    assert "baseline_posthoc" in txt
    assert "fairness_budget" in txt
