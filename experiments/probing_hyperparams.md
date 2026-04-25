# Probing / logprobs — hyperparameters and environment (reproducibility)

**Languages:** [English](probing_hyperparams.md) | [中文](probing_hyperparams.zh-CN.md) | [日本語](probing_hyperparams.ja.md)

For each run between [`ProbingEngine`](https://github.com/haotian-io/ConcordCoder/blob/master/Code/src/concordcoder/generation/probing.py) and [`LLMClient.chat_with_logprobs`](https://github.com/haotian-io/ConcordCoder/blob/master/Code/src/concordcoder/llm_client.py), **pin** the fields below and copy the values you used into a paper appendix or a checked-in copy of this file.

## 1. Code defaults (`probing.py` constants)

| Field | Default | Meaning |
|-------|---------|---------|
| `DEFAULT_CONFIDENCE_THRESHOLD` | `0.45` | Nodes below this confidence are more likely to trigger probes |
| `DEFAULT_CHURN_ALPHA` | `0.6` | α in `hotspot_score = (1 - conf) * (1 + α * git_churn)` |
| `DEFAULT_MAX_PROBES` | `3` | Max probes per task |

If you override constructor args in an experiment, record the **new values** and **reason** (e.g. ablation with no churn: set α=0).

## 2. Environment variables

| Variable | Values | Note |
|----------|--------|------|
| `CONCORD_REAL_LOGPROBS` | `0` / `1` | If `1`, try OpenAI `logprobs` on the anchor path; on failure, fall back to mock (`probe.logprob_source` in result JSON) |

## 3. LLM side (`LLMClient`)

| Field | Default | Baseline alignment |
|-------|---------|--------------------|
| `temperature` | `0.2` | Same as RQ1 direct baseline (see `experiments/baseline_direct.py` env) |
| `max_tokens` | `4096` | Note in the table if you change it for fair comparison |

## 4. Evaluation tasks (one row per run)

Rows should match identifiers you actually ran: e.g. YAML `id` from your [`examples/mini_eval/`](examples/mini_eval/README.md) task directory, or SWE-bench `instance_id` from [`scripts/swe_bench_batch.py`](../scripts/swe_bench_batch.py) / [`swe_tiny_config.yaml`](swe_tiny_config.yaml). Keep **one** table per submission to avoid version drift.

| Task id | confidence_threshold | churn_alpha | max_probes | CONCORD_REAL_LOGPROBS | Notes |
|---------|----------------------|-------------|------------|-------------------------|--------|
| (e.g. `django__django-11099` or your YAML `id`) | 0.45 | 0.6 | 3 | 1 | |
| … | | | | | |
