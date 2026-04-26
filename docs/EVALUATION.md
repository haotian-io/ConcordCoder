# Evaluation and benchmarks

This document is part of the **public repository** and describes reproducible drivers shipped here. Formal research questions (RQ1–RQ3), user-study protocol, and full experimental claims appear in the **accompanying paper** (cite the publisher or arXiv version when available).

## SWE-bench Lite (repository-level issues)

- **Driver:** [`scripts/swe_bench_batch.py`](../scripts/swe_bench_batch.py) loads [`SWE-bench/SWE-bench_Lite`](https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite) (see [overview](https://www.swebench.com/lite.html)).
- **Demo list:** [`experiments/swe_tiny_config.yaml`](../experiments/swe_tiny_config.yaml).
- **Step-by-step:** [`experiments/DEMO_SWE_BENCH_LITE.md`](../experiments/DEMO_SWE_BENCH_LITE.md).
- **Official leaderboard harness (optional):** [`experiments/SWE_HARNESS_APPENDIX.md`](../experiments/SWE_HARNESS_APPENDIX.md).

Environment: `pip install -e ".[eval]"` plus LLM keys; per-instance `git checkout` at `base_commit` as documented in the demo.

## Bring-your-own tasks (`mini_eval`)

- **Driver:** [`scripts/mini_eval.py`](../scripts/mini_eval.py).
- **YAML templates:** [`examples/mini_eval/`](../examples/mini_eval/).

## Probing and logprobs (reproducibility table)

- **English:** [`experiments/probing_hyperparams.md`](../experiments/probing_hyperparams.md)  
- **中文:** [`experiments/probing_hyperparams.zh-CN.md`](../experiments/probing_hyperparams.zh-CN.md)  
- **日本語:** [`experiments/probing_hyperparams.ja.md`](../experiments/probing_hyperparams.ja.md)

For OpenAI chat logprobs on anchor paths, set `CONCORD_REAL_LOGPROBS=1` (see table and `LLMClient` in source).

### Hotspot score used in probing

Week1 protocol uses a multi-factor hotspot score:

`score(n) = (1 - confidence(n)) * (1 + w1*churn + w2*centrality + w3*fan_io + w4*public_api)`

Probe selection follows `score(n) > theta(task,budget)` and keeps only Top-N
targets (N bounded by probing budget).

Current implementation is heuristic and intentionally lightweight; deferred
signals for later iterations include test-failure linkage, rollback density,
bug-fix commit density, and coverage-aware priors.

## Direct baseline (RQ1 comparison script)

- [`experiments/baseline_direct.py`](../experiments/baseline_direct.py) — single-turn baseline using the same LLM budget knobs as documented in the script header.
- `scripts/rq1_runner.py` also supports `baseline_posthoc` for budget-matched post-hoc comparison.

## Fairness and cost fields in artifacts

`mini_eval.py` and `rq1_runner.py` rows include:

- `fairness_budget` (`max_turns`, prompt/completion token caps, wall-clock cap),
- `alignment_turn_log_n`,
- `cost` (`online_*`, `offline_*`, `total_runtime_sec`),
- optional RQ2 placeholders (`artifact_quality_score`, `user_confidence_score`).
