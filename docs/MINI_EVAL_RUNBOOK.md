# Mini Eval Runbook (Real Pilot)

## 1) Prerequisites

- Python environment activated.
- Package installed in editable mode:

```bash
cd /path/to/ConcordCoder
pip install -e ".[dev,all]"
```

- One LLM key configured:
  - `OPENAI_API_KEY` or
  - `ANTHROPIC_API_KEY`

## 2) Required inputs

Set real paths (no built-in sample fallback):

```bash
export CONCORD_EVAL_REPO_ROOT=/abs/path/to/target/repo
export CONCORD_EVAL_TASKS_DIR=/abs/path/to/task_yamls
```

Optional (if you use a glob file pattern instead of a directory):

```bash
export CONCORD_EVAL_TASKS_GLOB="/abs/path/to/tasks/*.yaml"
```

## 3) Run commands

### 3.1 Pilot run

```bash
python3 scripts/mini_eval.py
```

### 3.2 Save JSON output to file

```bash
python3 scripts/mini_eval.py > pilot_result.json
```

### 3.3 Basic validation

```bash
python3 -m pytest -q
```

## 4) Result capture

Record each run into `docs/templates/pilot_run_log.csv` using:

- method
- task id
- runtime
- tokens
- pass/fail
- regressions
- artifact score
- user confidence (if human session exists)

## 5) Common failures and fixes

- **Missing repo/tasks env**:
  - Symptom: `CONCORD_EVAL_REPO_ROOT is required`.
  - Fix: export required env vars before running.
- **No LLM key**:
  - Symptom: backend/client init error.
  - Fix: set one backend key and retry.
- **Task YAML parse error**:
  - Symptom: YAML loading exception.
  - Fix: validate YAML syntax and required fields.

## 6) Reproducibility checklist

- Keep model/backend fixed across compared methods.
- Keep turn/time/token budgets fixed.
- Log failures as-is; do not silently rerun only failed methods.
