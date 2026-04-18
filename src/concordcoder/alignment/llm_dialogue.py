"""LLM-driven alignment dialogue: three-phase conversation state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

from concordcoder.alignment.prompts import (
    SYSTEM_CONSTRAINT_ANALYST,
    SYSTEM_CONTEXT_ANALYST,
    build_constraint_inference_prompt,
    build_context_reconstruction_prompt,
)
from concordcoder.schemas import AlignmentRecord, Constraint, ContextBundle


class DialoguePhase(Enum):
    CONTEXT_RECONSTRUCTION = auto()   # Phase A: rebuild context awareness
    CONSTRAINT_CONFIRMATION = auto()  # Phase B: confirm constraints
    SOLUTION_CODESIGN = auto()        # Phase C: choose implementation option
    DONE = auto()


@dataclass
class DialogueTurn:
    role: str    # "assistant" or "user"
    content: str


@dataclass
class DialogueState:
    phase: DialoguePhase = DialoguePhase.CONTEXT_RECONSTRUCTION
    history: list[DialogueTurn] = field(default_factory=list)
    confirmed_constraints: list[Constraint] = field(default_factory=list)
    rejected_constraints: list[Constraint] = field(default_factory=list)
    allowlist_paths: list[str] = field(default_factory=list)
    implementation_preference: str = ""
    acceptance_criteria: list[str] = field(default_factory=list)
    pending_questions: list[str] = field(default_factory=list)
    max_turns: int = 8   # safety limit
    turns_taken: int = 0


class LLMAlignmentDialogue:
    """Interactive, LLM-powered alignment dialogue.

    Usage (interactive CLI mode):
        dialogue = LLMAlignmentDialogue(llm_client=client)
        record = dialogue.run_interactive(bundle, print_fn=print, input_fn=input)

    Usage (batch/programmatic mode):
        record = dialogue.run_batch(bundle, prefilled_answers={...})
    """

    def __init__(self, llm_client=None) -> None:
        self.llm = llm_client

    # ------------------------------------------------------------------
    # Interactive mode: human in the loop
    # ------------------------------------------------------------------

    def run_interactive(
        self,
        bundle: ContextBundle,
        print_fn: Callable[[str], None] = print,
        input_fn: Callable[[str], str] = input,
    ) -> AlignmentRecord:
        """Run the full alignment dialogue interactively in the terminal."""
        state = DialogueState()
        state.pending_questions = self._initial_questions(bundle)

        print_fn("\n" + "═" * 60)
        print_fn("  📋  ConcordCoder 认知对齐对话  ")
        print_fn("═" * 60)
        print_fn("（输入 'done' 或 'skip' 可跳过当前阶段，输入 'quit' 中止）\n")

        # ---- Phase A: Context Reconstruction ----
        self._run_phase_a(bundle, state, print_fn, input_fn)

        # ---- Phase B: Constraint Confirmation ----
        self._run_phase_b(bundle, state, print_fn, input_fn)

        # ---- Phase C: Solution Co-design ----
        self._run_phase_c(bundle, state, print_fn, input_fn)

        state.phase = DialoguePhase.DONE
        record = self._build_record(bundle, state)

        print_fn("\n" + "═" * 60)
        print_fn("✅  认知对齐完成！开始生成代码...")
        print_fn("═" * 60 + "\n")

        return record

    # ------------------------------------------------------------------
    # Batch mode: pre-filled answers (for automated experiments)
    # ------------------------------------------------------------------

    def run_batch(
        self,
        bundle: ContextBundle,
        prefilled_answers: dict[str, str] | None = None,
    ) -> AlignmentRecord:
        """Non-interactive mode: use prefilled answers and LLM for constraint inference."""
        answers = prefilled_answers or {}
        state = DialogueState()

        # If LLM available, run constraint inference
        if self.llm:
            inferred = self._llm_infer_constraints(bundle, user_summary=str(answers))
            self._apply_inferred(inferred, state, bundle)

        # Apply simple rule-based constraints from answers
        self._apply_answer_rules(answers, state, bundle)

        return self._build_record(bundle, state)

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    def _run_phase_a(
        self, bundle: ContextBundle, state: DialogueState,
        print_fn, input_fn,
    ) -> None:
        """Phase A: context reconstruction."""
        print_fn("━" * 50)
        print_fn("📂  阶段 A：项目上下文重建")
        print_fn("━" * 50)

        if self.llm:
            prompt = build_context_reconstruction_prompt(bundle)
            assistant_msg = self.llm.chat(
                [{"role": "user", "content": prompt}],
                system=SYSTEM_CONTEXT_ANALYST,
            )
        else:
            assistant_msg = self._fallback_context_summary(bundle)

        print_fn(f"\n🤖  {assistant_msg}\n")
        state.history.append(DialogueTurn("assistant", assistant_msg))

        user_resp = self._prompt_user(
            input_fn,
            "💬  你对以上内容有疑问，或需要更多解释吗？（或输入 'done' 继续）: ",
            state,
        )
        if user_resp:
            state.history.append(DialogueTurn("user", user_resp))
            # Follow-up response
            if self.llm and user_resp.lower() not in ("done", "skip", ""):
                follow_up = self.llm.chat(
                    [
                        {"role": "assistant", "content": assistant_msg},
                        {"role": "user", "content": user_resp},
                    ],
                    system=SYSTEM_CONTEXT_ANALYST,
                )
                print_fn(f"\n🤖  {follow_up}\n")
                state.history.append(DialogueTurn("assistant", follow_up))

    def _run_phase_b(
        self, bundle: ContextBundle, state: DialogueState,
        print_fn, input_fn,
    ) -> None:
        """Phase B: constraint confirmation."""
        print_fn("━" * 50)
        print_fn("📌  阶段 B：约束确认")
        print_fn("━" * 50)

        if self.llm:
            user_context = " ".join(t.content for t in state.history if t.role == "user")
            prompt = build_constraint_inference_prompt(bundle, user_responses=user_context)
            inferred = self.llm.chat_json(
                [{"role": "user", "content": prompt}],
                system=SYSTEM_CONSTRAINT_ANALYST,
            )
            self._apply_inferred(inferred, state, bundle)
            self._print_constraint_checklist(inferred, print_fn)
        else:
            self._print_fallback_constraints(bundle, print_fn)
            for c in bundle.constraints_guess:
                state.confirmed_constraints.append(c)

        # Ask user to confirm/modify
        print_fn("\n💬  请确认以上约束（直接回车=全部接受，或输入修改意见）: ", )
        user_input = self._prompt_user(input_fn, "", state)
        if user_input:
            state.history.append(DialogueTurn("user", user_input))
            # Check for explicit rejections
            if "不需要" in user_input or "去掉" in user_input or "remove" in user_input.lower():
                print_fn("📝  已记录你的修改意见，将在生成时考虑。")

        # Collect acceptance criteria
        print_fn("\n❓  你有特定的验收标准吗？（如 'pytest 全通过'，或直接回车使用默认）: ")
        crit_input = self._prompt_user(input_fn, "", state)
        if crit_input and crit_input.lower() not in ("", "skip", "done"):
            state.acceptance_criteria.append(crit_input)
        else:
            state.acceptance_criteria.append("现有测试全部通过（无回归）")
            state.acceptance_criteria.append("新功能有对应测试覆盖")

    def _run_phase_c(
        self, bundle: ContextBundle, state: DialogueState,
        print_fn, input_fn,
    ) -> None:
        """Phase C: solution co-design."""
        print_fn("━" * 50)
        print_fn("💡  阶段 C：实现方案讨论")
        print_fn("━" * 50)

        options = getattr(state, "_implementation_options", [])
        if not options:
            print_fn("\n  暂无具体方案选项，将使用默认策略：最小侵入性实现。")
            state.implementation_preference = "最小侵入性实现，优先复用现有模块。"
        else:
            print_fn("\n以下是建议的实现方案：\n")
            for i, opt in enumerate(options[:3], 1):
                name = opt.get("name", f"方案{i}")
                desc = opt.get("description", "")
                pros = opt.get("pros", "")
                cons = opt.get("cons", "")
                print_fn(f"  [{i}] {name}")
                print_fn(f"      描述: {desc}")
                if pros:
                    print_fn(f"      优点: {pros}")
                if cons:
                    print_fn(f"      缺点: {cons}")
                print_fn()

            choice = self._prompt_user(
                input_fn,
                f"💬  你倾向于哪个方案？（输入 1-{len(options[:3])} 或描述你的想法）: ",
                state,
            )
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    state.implementation_preference = options[idx].get("name", choice)
            elif choice:
                state.implementation_preference = choice

        print_fn(f"\n  ✅  方案确定：{state.implementation_preference or '默认策略'}")

        # Allowlist
        print_fn("\n❓  哪些文件/目录可以修改？（留空=由系统判断，多个用逗号分隔）: ")
        al_input = self._prompt_user(input_fn, "", state)
        if al_input and al_input.lower() not in ("", "skip"):
            state.allowlist_paths = [p.strip() for p in al_input.split(",") if p.strip()]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _prompt_user(self, input_fn, prompt: str, state: DialogueState) -> str:
        if state.turns_taken >= state.max_turns:
            return ""
        raw = input_fn(prompt).strip()
        state.turns_taken += 1
        if raw.lower() == "quit":
            raise KeyboardInterrupt("User quit alignment dialogue.")
        if raw.lower() in ("done", "skip"):
            return ""
        return raw

    def _llm_infer_constraints(self, bundle: ContextBundle, user_summary: str = "") -> dict:
        prompt = build_constraint_inference_prompt(bundle, user_responses=user_summary)
        result = self.llm.chat_json(
            [{"role": "user", "content": prompt}],
            system=SYSTEM_CONSTRAINT_ANALYST,
        )
        return result if isinstance(result, dict) else {}

    def _apply_inferred(self, inferred: dict, state: DialogueState, bundle: ContextBundle) -> None:
        for i, c in enumerate(inferred.get("hard_constraints", [])):
            state.confirmed_constraints.append(
                Constraint(
                    id=c.get("id", f"hard_{i}"),
                    description=c.get("description", ""),
                    hard=True,
                    source=c.get("source", "llm_inference"),
                )
            )
        for i, c in enumerate(inferred.get("soft_constraints", [])):
            state.confirmed_constraints.append(
                Constraint(
                    id=c.get("id", f"soft_{i}"),
                    description=c.get("description", ""),
                    hard=False,
                    source=c.get("source", "llm_inference"),
                )
            )
        state.pending_questions = inferred.get("open_questions", [])
        state._implementation_options = inferred.get("implementation_options", [])  # type: ignore[attr-defined]

    def _apply_answer_rules(self, answers: dict, state: DialogueState, bundle: ContextBundle) -> None:
        if answers.get("api_stable", "").lower() in ("yes", "y", "是", "true"):
            state.confirmed_constraints.append(
                Constraint(
                    id="api_stable",
                    description="不得更改公开 API 函数签名（调用方稳定性）。",
                    hard=True,
                    source="alignment:user",
                )
            )
        if answers.get("intent_override"):
            pass  # Used in _build_record
        state.acceptance_criteria.extend(bundle.test_expectations[:3])

    def _build_record(self, bundle: ContextBundle, state: DialogueState) -> AlignmentRecord:
        return AlignmentRecord(
            refined_intent=bundle.task_summary,
            confirmed_constraints=state.confirmed_constraints or list(bundle.constraints_guess),
            allowlist_paths=state.allowlist_paths,
            test_acceptance_criteria=state.acceptance_criteria or ["现有测试全部通过（无回归）"],
            implementation_preference=state.implementation_preference,
            notes=f"对话轮次: {state.turns_taken}，阶段: {state.phase.name}",
        )

    def _initial_questions(self, bundle: ContextBundle) -> list[str]:
        return [
            "本次改动是否需要保持对外公开 API / CLI 不变？",
            "是否需要兼容旧数据格式或迁移路径？",
            "失败时的期望行为：抛错、降级还是重试？",
        ] + bundle.open_questions

    @staticmethod
    def _fallback_context_summary(bundle: ContextBundle) -> str:
        """Summary when no LLM is available."""
        lines = [f"📦 我分析了仓库，任务是：{bundle.task_summary}"]
        if bundle.structural_facts:
            lines.append("\n主要发现：")
            for f in bundle.structural_facts[:3]:
                lines.append(f"  · {f}")
        if bundle.snippets:
            lines.append(f"\n找到 {len(bundle.snippets)} 个相关代码片段（最相关：{bundle.snippets[0].path}）")
        if bundle.risks:
            lines.append(f"\n⚠️  潜在风险：{bundle.risks[0].detail}")
        return "\n".join(lines)

    @staticmethod
    def _print_constraint_checklist(inferred: dict, print_fn) -> None:
        if "raw" in inferred:
            print_fn(f"\n[约束推断结果]\n{inferred['raw'][:800]}\n")
            return
        hard = inferred.get("hard_constraints", [])
        soft = inferred.get("soft_constraints", [])
        risks = inferred.get("risks", [])
        print_fn("\n【推断的约束清单】")
        for c in hard:
            print_fn(f"  🔴 [必须] {c.get('description', '')} (来源: {c.get('source', '')})")
        for c in soft:
            print_fn(f"  🟡 [建议] {c.get('description', '')} (来源: {c.get('source', '')})")
        for r in risks:
            print_fn(f"  ⚠️  [风险/{r.get('severity','')}] {r.get('detail', '')}")

    @staticmethod
    def _print_fallback_constraints(bundle: ContextBundle, print_fn) -> None:
        print_fn("\n【推断的约束清单（无 LLM 模式）】")
        for c in bundle.constraints_guess:
            label = "🔴 [必须]" if c.hard else "🟡 [建议]"
            print_fn(f"  {label} {c.description}")
        for r in bundle.risks:
            print_fn(f"  ⚠️  [风险/{r.severity}] {r.detail}")
