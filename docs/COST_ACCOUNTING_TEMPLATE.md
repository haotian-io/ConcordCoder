# Cost Accounting Template (Week1 Pilot)

Use this schema per task-method run. Keep one row per run in CSV or JSONL.

## Fields

- `task_id`: unique task identifier.
- `method`: `concord` | `baseline_direct` | `baseline_posthoc`.
- `model_backend`: backend/model string.
- `online_runtime_sec`: end-to-end online runtime.
- `online_turns`: number of interaction turns.
- `online_prompt_tokens`: total prompt tokens.
- `online_completion_tokens`: total completion tokens.
- `offline_extract_sec`: context extraction time.
- `offline_git_sec`: git mining time.
- `offline_analysis_sec`: static/call-graph analysis time.
- `total_runtime_sec`: online + offline.
- `passed_tests`: boolean.
- `regression_count`: integer.
- `artifact_quality_score`: numeric rubric score.
- `user_confidence_score`: Likert (RQ2 runs only).
- `alignment_turn_log_n`: number of logged alignment turns.
- `fair_max_turns`: configured fairness turn cap.
- `fair_max_prompt_tokens`: configured fairness prompt-token cap.
- `fair_max_completion_tokens`: configured fairness completion-token cap.
- `fair_max_wallclock_sec`: configured fairness wall-clock cap.

## Minimal CSV header

```text
task_id,method,model_backend,online_runtime_sec,online_turns,online_prompt_tokens,online_completion_tokens,offline_extract_sec,offline_git_sec,offline_analysis_sec,total_runtime_sec,passed_tests,regression_count,artifact_quality_score,user_confidence_score,alignment_turn_log_n,fair_max_turns,fair_max_prompt_tokens,fair_max_completion_tokens,fair_max_wallclock_sec
```

## Notes

- Keep budget settings fixed across compared methods.
- If a metric is unavailable in pilot, write `NA` explicitly.
