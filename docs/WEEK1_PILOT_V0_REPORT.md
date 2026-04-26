# Week1 Pilot v0 Report

## Executed checks

- `python3 -m pytest -q tests/test_probing.py` -> `21 passed`
- `python3 -m pytest -q` -> `44 passed`
- `python3 scripts/mini_eval.py --help` -> expected config gate error
  (`CONCORD_EVAL_REPO_ROOT` and task inputs required)

## What this pilot validates

- Multi-factor hotspot probing implementation compiles and passes tests.
- Dynamic threshold and risk-component outputs are test-covered.
- Evaluation entrypoint is reproducible and correctly enforces explicit dataset
  and repository inputs (no hidden default fixture dependency).

## Week1 v0 artifact pack

- Proposal scope and claims: `docs/WEEK1_V0_PROPOSAL.md`
- Experiment protocol (fairness/RQ2/RQ3): `docs/EXPERIMENT_PROTOCOL_V1.md`
- Cost accounting template: `docs/COST_ACCOUNTING_TEMPLATE.md`
- Evaluation appendix updates: `docs/EVALUATION.md`

## Remaining step for real task-level pilot

Provide real evaluation inputs, then run:

```bash
export CONCORD_EVAL_REPO_ROOT=/abs/path/to/target/repo
export CONCORD_EVAL_TASKS_DIR=/abs/path/to/task_yamls
python3 scripts/mini_eval.py
```

This environment-specific run is intentionally not faked in repository CI.
