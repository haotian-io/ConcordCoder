# `mini_eval` (bring your own real repo)

**Languages:** [English](README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

`scripts/mini_eval.py` does **not** ship with any sample project. You need:

1. The root path of a **real** Python repository clone on your machine (source files to edit, optional `tests/`).
2. A set of **task YAML** files (same shape as `single_task`’s `FixtureTaskYaml`), in a directory or matched by a glob.

## Environment variables

| Variable | Required | Meaning |
|----------|----------|---------|
| `CONCORD_EVAL_REPO_ROOT` | yes | Absolute path to the repository root under test |
| `CONCORD_EVAL_TASKS_DIR` | one of | Directory containing `*.yaml` / `*.yml` |
| `CONCORD_EVAL_TASKS_GLOB` | one of | e.g. `/path/to/tasks/*.yaml` (do not set both with DIR) |

Like `concord once`, you need `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`); optional `OPENAI_BASE_URL`.

## Example

```bash
cd /path/to/ConcordCoder   # repository root (pyproject.toml)
pip install -e ".[dev,openai]"

export CONCORD_EVAL_REPO_ROOT=/abs/path/to/your/repo
export CONCORD_EVAL_TASKS_DIR=/abs/path/to/your/task_yamls
python3 scripts/mini_eval.py
```

Copy `sample_task.template.yaml` from this directory into your task folder and replace `target_file` / `target_symbol` with real paths and names in that repo.
