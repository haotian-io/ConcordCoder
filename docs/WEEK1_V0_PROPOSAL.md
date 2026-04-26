# ConcordCoder Week1 v0 Proposal (B Track)

## Scope and claim boundary

This v0 focuses on a single repository-level task at a time. The contribution is
not "best overall code generation", but a practical method that reduces intent
misalignment before code regeneration.

## Problem statement

Existing code agents often optimize post-hoc fixing: generate first, then debug
through repeated feedback loops. In maintenance scenarios, this amplifies three
gaps:

- model understanding of the current repository,
- user memory of legacy design decisions,
- original architectural intent.

ConcordCoder treats this as a cognitive alignment problem and inserts a short
pre-generation alignment stage.

## Method overview (single-task)

1. **Context extraction and anchor draft**
   - Build structural context from AST/call graph/Git traces/tests.
   - Produce a lightweight anchor draft to expose model assumptions.
2. **Proactive alignment dialogue**
   - Convert uncertainty + hotspot signals into bounded probe questions.
   - Turn user responses into explicit constraints.
3. **Constrained generation**
   - Regenerate under confirmed constraints and scoped context assembly.

## What is new in this v0

- **Pre-generation intervention** instead of pure post-hoc retries.
- **Hotspot-aware probing** using multi-factor risk score (not churn only).
- **Fair-comparison protocol** with bounded interaction and token budgets.
- **Cost accounting split** into online vs offline cost.

## Main research questions (v0)

- **RQ1**: Does pre-generation alignment improve task outcome quality?
- **RQ2**: Does it improve user understanding recovery and confidence?
- **RQ3**: Is the interaction overhead offset by downstream gains?

## Why this is "B-track ready"

- Tight scope: only single-task generation, no broad multi-task claims.
- Reproducible protocol in repository docs and scripts.
- Explicit limitations and threat-to-validity section.

## Limitations (explicitly acknowledged)

- Multi-factor hotspot score is still heuristic and lightweight.
- User study scale in week-1 is pilot-level, not final significance evidence.
- Some production signals are deferred: rollback density, test-failure linkage,
  bug-fix commit density, coverage-aware risk priors.
