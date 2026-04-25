# Gold-task YAML templates (10)

**Languages:** [English](README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

This directory does **not** ship a real application repository. It only provides **10** task templates isomorphic to `examples/mini_eval/sample_task.template.yaml` for you to:

- Fill in real `id`, `task`, `target_file` / `target_symbol`, and optional `alignment_answers` on your machine.  
- Copy the finished files into the directory pointed to by `CONCORD_EVAL_TASKS_DIR`, set `CONCORD_EVAL_REPO_ROOT`, and run [`scripts/mini_eval.py`](../scripts/mini_eval.py).  
- Report **metadata** (no secret paths) for the “10-gold set” in an appendix or methods section of a paper / regression log.

## Steps

1. Clone and pin a commit: branch or tag on the code version that matches the task description.  
2. Copy `task_01.template.yaml` to e.g. `myrepo_task01.yaml` and replace placeholders with real relative paths and symbols.  
3. You may **skip** any template that does not apply; all ten do not have to be filled.  
4. Record the list of task IDs you actually use and store it with the hyperparameter table in [`probing_hyperparams.md`](../probing_hyperparams.md).

## Optional: `dependency_level`

`dependency_level` is a free label (CoderEval 6-level style, see `schemas.ContextDependencyLevel`) for stratified tables in a paper. Leaving it empty does not affect `concord` runs.

## File list (naming hint only)

| File | Suggested focus |
|------|-----------------|
| `task_01` … `task_03` | `slib` / single-file |
| `task_04` … `task_06` | several symbols, `file-runnable` |
| `task_07` … `task_10` | cross-module, `project-runnable`–like |

## Checklist (templates)

- [ ] task_01 — filled with real paths and used in mini_eval or paper  
- [ ] task_02  
- [ ] task_03  
- [ ] task_04  
- [ ] task_05  
- [ ] task_06  
- [ ] task_07  
- [ ] task_08  
- [ ] task_09  
- [ ] task_10  
