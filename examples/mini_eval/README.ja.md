# `mini_eval` 利用手順（独自の実リポジトリ必須）

**言語 / Languages:** [English](README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

`scripts/mini_eval.py` には**サンプルアプリ**は同梱されません。次が必要です。

1. 手元の **実クローン** である Python リポジトリのルート（編集するソースと任意の `tests/` を含む）。
2. **タスク YAML** 一式（`single_task` の `FixtureTaskYaml` と同形）。専用ディレクトリに置くか glob で指定。

## 環境変数

| 変数 | 必須 | 意味 |
|------|------|------|
| `CONCORD_EVAL_REPO_ROOT` | はい | 評価対象リポジトリの絶対パス |
| `CONCORD_EVAL_TASKS_DIR` | どちらか | `*.yaml` / `*.yml` を置くディレクトリ |
| `CONCORD_EVAL_TASKS_GLOB` | どちらか | 例: `/path/to/tasks/*.yaml`（DIR と同時に設定しない） |

`concord once` と同様、`OPENAI_API_KEY` または `ANTHROPIC_API_KEY` が必要。任意で `OPENAI_BASE_URL`。

## 例

```bash
cd /path/to/ConcordCoder/Code   # pyproject.toml がある階層
pip install -e ".[dev,openai]"

export CONCORD_EVAL_REPO_ROOT=/abs/path/to/your/repo
export CONCORD_EVAL_TASKS_DIR=/abs/path/to/your/task_yamls
python3 scripts/mini_eval.py
```

同ディレクトリの `sample_task.template.yaml` をタスク用フォルダへコピーし、対象リポ内の `target_file` / `target_symbol` を実在パスに差し替えてください。
