# Probing / logprobs 超参与环境（论文可复现记录用）

**语言 / Languages:** [English](probing_hyperparams.md) | [中文](probing_hyperparams.zh-CN.md) | [日本語](probing_hyperparams.ja.md)

在 [`ProbingEngine`](https://github.com/haotian-io/ConcordCoder/blob/master/Code/src/concordcoder/generation/probing.py) 与 [`LLMClient.chat_with_logprobs`](https://github.com/haotian-io/ConcordCoder/blob/master/Code/src/concordcoder/llm_client.py) 之间记录一次实验时**建议固定**下列字段，并把你实际采用的取值贴在论文附录或本文件副本中。

## 1. 代码内默认（`probing.py` 常量）

| 参数 | 默认 | 含义 |
|------|------|------|
| `DEFAULT_CONFIDENCE_THRESHOLD` | `0.45` | 低于该 node 置信度则易触发探针 |
| `DEFAULT_CHURN_ALPHA` | `0.6` | `hotspot_score = (1 - conf) * (1 + α * git_churn)` 中 α |
| `DEFAULT_MAX_PROBES` | `3` | 每任务最大探针条数 |

若你在实验中改过构造参数，在此写明**新数值**与**理由**（如消融「无 churn」令 α=0）。

## 2. 环境变量

| 变量 | 值 | 说明 |
|------|-----|------|
| `CONCORD_REAL_LOGPROBS` | `0` / `1` | 为 `1` 时锚点路径上尝试 OpenAI `logprobs`；失败则回退 mock，结果 JSON 中 `probe.logprob_source` 标明 |

## 3. LLM 侧（`LLMClient`）

| 参数 | 默认 | 与基线约定 |
|------|------|------------|
| `temperature` | `0.2` | 与 RQ1 Direct 基线脚本**同一**温度（见 `experiments/baseline_direct.py` 环境变量） |
| `max_tokens` | `4096` | 若与基线可比，在表中注明 |

## 4. 评测任务（每跑一行一条）

行应与**实际跑过**的任务标识一一对应：例如自备任务 YAML 里的 `id`（见 [`examples/mini_eval/`](examples/mini_eval/README.zh-CN.md)），或 SWE-bench 的 `instance_id`（[`scripts/swe_bench_batch.py`](../scripts/swe_bench_batch.py)、[`swe_tiny_config.yaml`](swe_tiny_config.yaml)）。同一次投稿仅保留**一张**本表，避免多版本混淆。

| 任务 id | confidence_threshold | churn_alpha | max_probes | CONCORD_REAL_LOGPROBS | 备注 |
|---------|----------------------|------------|------------|------------------------|------|
| （例 `django__django-11099` 或 YAML 内 `id`） | 0.45 | 0.6 | 3 | 1 | |
| … | | | | | |
