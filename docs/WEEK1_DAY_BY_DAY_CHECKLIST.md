# Week1 Day-by-Day Checklist

## Day 1: Story narrowing and claim boundary

- **Inputs**: `Plan - Haotian.md`, `docs/WEEK1_V0_PROPOSAL.md`.
- **Actions**:
  - Freeze single-task scope and B-track claim boundary.
  - Align terminology across proposal and README.
  - Record explicit non-goals (no broad multi-task claims).
- **Acceptance**:
  - Proposal scope section finalized.
  - One-page method narrative is internally consistent.

## Day 2: Protocol and fairness controls

- **Inputs**: `docs/EXPERIMENT_PROTOCOL_V1.md`.
- **Actions**:
  - Finalize baselines (`direct`, `posthoc`) and fairness constraints.
  - Lock turn/token/time budgets and stopping criteria.
  - Confirm RQ1/RQ2/RQ3 metric definitions.
- **Acceptance**:
  - Protocol file includes executable comparison rules.
  - No ambiguous fairness knobs remain.

## Day 3: Hotspot and probing implementation checks

- **Inputs**: `src/concordcoder/generation/probing.py`, `tests/test_probing.py`.
- **Actions**:
  - Validate multi-factor hotspot score behavior.
  - Validate dynamic threshold and Top-N selection.
  - Ensure tests cover new risk components.
- **Acceptance**:
  - `pytest tests/test_probing.py` passes.
  - Hotspot math documented in `docs/EVALUATION.md`.

## Day 4: Pilot dry-run and cost capture

- **Inputs**: `scripts/mini_eval.py`, `docs/COST_ACCOUNTING_TEMPLATE.md`.
- **Actions**:
  - Run pilot on real repo/tasks.
  - Capture online/offline timing and token usage.
  - Save run artifacts and first-pass summary.
- **Acceptance**:
  - At least one full run completes with logged metrics.
  - Cost table fields are fully populated or explicitly `NA`.

## Day 5: Protocol refinement from pilot evidence

- **Inputs**: day-4 outputs, `docs/WEEK1_PILOT_V0_REPORT.md`.
- **Actions**:
  - Refine metric wording and failure taxonomy.
  - Update threats to validity and known limitations.
  - Add mismatch notes between method assumptions and observed behavior.
- **Acceptance**:
  - Pilot report updated with concrete evidence.
  - Limitation section includes actionable next-step fixes.

## Day 6: Demo and artifact packaging

- **Inputs**: proposal/protocol/pilot docs.
- **Actions**:
  - Prepare concise demo flow and reproducibility commands.
  - Bundle docs into v0 artifact package index.
  - Validate links and paths resolve in repository.
- **Acceptance**:
  - One command checklist can guide a new collaborator.
  - Artifact index is complete and readable.

## Day 7: v0 freeze and handoff

- **Inputs**: all week outputs.
- **Actions**:
  - Freeze v0 docs.
  - Final consistency pass across README, protocol, and report.
  - Produce next-week backlog (high-impact only).
- **Acceptance**:
  - v0 package has proposal + protocol + pilot report + runbook + templates.
  - All critical TODOs closed.
