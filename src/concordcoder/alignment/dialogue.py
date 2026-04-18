"""Turn ContextBundle into AlignmentRecord via scripted prompts (LLM optional)."""

from __future__ import annotations

from concordcoder.schemas import AlignmentRecord, Constraint, ContextBundle


class AlignmentDialogue:
    """Baseline: emit checklist + draft alignment without LLM. Plug LLM for real runs."""

    def propose_questions(self, bundle: ContextBundle) -> list[str]:
        qs = [
            "本次改动是否需要保持对外公开 API / CLI 不变？",
            "是否需要兼容旧数据格式或迁移路径？",
            "失败时的期望行为：抛错、降级还是重试？",
        ]
        qs.extend(bundle.open_questions)
        return qs

    def draft_record(self, bundle: ContextBundle, answers: dict[str, str] | None = None) -> AlignmentRecord:
        answers = answers or {}
        refined = bundle.task_summary
        if answers.get("intent_override"):
            refined = answers["intent_override"]

        constraints: list[Constraint] = []
        constraints.extend(bundle.constraints_guess)
        if answers.get("api_stable", "").lower() in ("yes", "y", "是", "true"):
            constraints.append(
                Constraint(
                    id="api_stable",
                    description="Do not change public API signatures without explicit approval.",
                    hard=True,
                    source="alignment:user",
                )
            )

        criteria: list[str] = []
        if bundle.open_questions:
            criteria.append("Resolve open_questions from extraction phase.")

        return AlignmentRecord(
            refined_intent=refined,
            confirmed_constraints=constraints,
            allowlist_paths=[],
            test_acceptance_criteria=criteria,
            notes="Draft alignment (no LLM). Replace with interactive session.",
        )
