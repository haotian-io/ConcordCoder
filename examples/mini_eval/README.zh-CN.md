# mini_eval 使用说明（自备真实仓库）

**语言 / Languages:** [English](README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

`scripts/mini_eval.py` **不再**随仓库附带任何示例项目。你需要：

1. 本地任意 **真实克隆** 的 Python 仓库根路径（含你要改的源文件与可选 `tests/`）。
2. 一组 **任务 YAML**（格式与 `single_task` 的 `FixtureTaskYaml` 一致），放在你机器上的某一目录，或用 glob 指向它们。

## 环境变量

| 变量 | 必填 | 含义 |
|------|------|------|
| `CONCORD_EVAL_REPO_ROOT` | 是 | 被评测仓库根目录的绝对路径 |
| `CONCORD_EVAL_TASKS_DIR` | 二选一 | 含 `*.yaml` / `*.yml` 的目录 |
| `CONCORD_EVAL_TASKS_GLOB` | 二选一 | 例如 `/path/to/tasks/*.yaml`（不要与 DIR 同时设） |

与 `concord once` 相同，需要 `OPENAI_API_KEY`（或 `ANTHROPIC_API_KEY`），可选 `OPENAI_BASE_URL`。

## 示例

```bash
cd /path/to/ConcordCoder   # 仓库根（含 pyproject.toml）
pip install -e ".[dev,openai]"

export CONCORD_EVAL_REPO_ROOT=/abs/path/to/your/repo
export CONCORD_EVAL_TASKS_DIR=/abs/path/to/your/task_yamls
python3 scripts/mini_eval.py
```

可将本目录下的 `sample_task.template.yaml` 复制到你的任务目录，把 `target_file` / `target_symbol` 改成该仓库内的真实路径与符号名。
