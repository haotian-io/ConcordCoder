# Probing / logprobs：ハイパーパラメータと環境（再現用メモ）

**言語 / Languages:** [English](probing_hyperparams.md) | [中文](probing_hyperparams.zh-CN.md) | [日本語](probing_hyperparams.ja.md)

[`ProbingEngine`](https://github.com/haotian-io/ConcordCoder/blob/master/Code/src/concordcoder/generation/probing.py) と [`LLMClient.chat_with_logprobs`](https://github.com/haotian-io/ConcordCoder/blob/master/Code/src/concordcoder/llm_client.py) をまたぐ各実験で、**次の項目を固定**し、採用値を論文付録か本ファイルのコピーに残してください。

## 1. コード既定（`probing.py` 定数）

| パラメータ | 既定 | 意味 |
|------------|------|------|
| `DEFAULT_CONFIDENCE_THRESHOLD` | `0.45` | この信頼度未満のノードはプローブが出やすい |
| `DEFAULT_CHURN_ALPHA` | `0.6` | `hotspot_score = (1 - conf) * (1 + α * git_churn)` の α |
| `DEFAULT_MAX_PROBES` | `3` | タスクあたりのプローブ数上限 |

コンストラクタ引数を変えた場合は**新値**と**理由**を明記（例: churn なしの ablation で α=0）。

## 2. 環境変数

| 変数 | 値 | 説明 |
|------|-----|------|
| `CONCORD_REAL_LOGPROBS` | `0` / `1` | `1` のときアンカー経路で OpenAI `logprobs` を試行。失敗時は mock。`probe.logprob_source` を参照 |

## 3. LLM 側（`LLMClient`）

| パラメータ | 既定 | ベースライン整合 |
|------------|------|------------------|
| `temperature` | `0.2` | RQ1 直接ベースライン（`experiments/baseline_direct.py` の環境変数）と**同じ** |
| `max_tokens` | `4096` | 比較条件を変えたなら表に記す |

## 4. ゴールドタスク集合

行は [`gold_tasks/README.ja.md`](gold_tasks/README.ja.md) でチェックしたタスク id と 1:1 対応（[en](gold_tasks/README.md) / [zh](gold_tasks/README.zh-CN.md)）。投稿ごとに**表は 1 枚**に揃え、版が混在しないよう注意。

| タスク id | confidence_threshold | churn_alpha | max_probes | CONCORD_REAL_LOGPROBS | 備考 |
|-----------|----------------------|------------|------------|------------------------|------|
|（例 gold_01）| 0.45 | 0.6 | 3 | 1 | |
| … | | | | | |
