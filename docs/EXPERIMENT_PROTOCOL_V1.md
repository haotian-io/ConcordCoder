# Experiment Protocol v1 (Week1)

## 1) Task setting

- Unit of evaluation: one bounded repository-level task per run.
- Target: maintenance-style tasks with non-trivial context dependencies.

## 2) Compared methods

- **ConcordCoder**: extraction -> probing/alignment -> constrained generation.
- **Baseline-Direct**: same LLM backend, direct generation without proactive alignment.
- **Baseline-PostHoc**: direct generation + bounded post-hoc correction rounds.

## 3) Fairness controls

All methods are run under the same global budget:

- **Max turns**: 3 interaction rounds.
- **Prompt+completion token budget**: fixed per task.
- **Wall-clock budget**: fixed per task.
- **Stop criterion**: stop at first valid patch passing task checks, or budget exhaustion.

For ConcordCoder vs Baseline-PostHoc:

- Feedback information volume is matched by turn count and token budget.
- If ConcordCoder gets N clarifying prompts, PostHoc baseline receives up to N
  corrective feedback prompts.

## 4) RQ metrics

### RQ1: outcome quality

- Task pass rate.
- Patch validity rate.
- Regression indicator (new failures introduced).
- Optional: pass@k under fixed k and fixed total token budget.

### RQ2: user understanding and confidence

Within-participant cross-task design:

- Each participant completes two different tasks:
  - one with ConcordCoder,
  - one with baseline (counterbalanced order).

Metrics:

- **Objective understanding score**: short quiz on design constraints and impacted
  modules after each task.
- **Artifact quality**: rubric score (correctness, maintainability, constraint compliance).
- **Subjective confidence**: Likert scale for "I understand why this change is correct".

### RQ3: cost-benefit

- Online cost: runtime, interaction turns, token usage.
- Offline cost: extraction/preprocessing runtime (AST/call graph/Git).
- Net efficiency: quality gain per unit online+offline cost.

## 5) Data logging requirements

Per run, store:

- task id, method, backend model,
- runtime/tokens/turns,
- produced patch and validation result,
- alignment probes and accepted constraints (if applicable).
- fairness budget fields (`max_turns`, token caps, wall-clock cap).
- cost split fields (online/offline/total), plus `alignment_turn_log_n`.

## 6) Threats to validity (week1)

- Small pilot sample size.
- Task selection bias toward moderate complexity.
- Heuristic artifact rubric before full inter-rater calibration.
