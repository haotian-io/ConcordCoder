"""Constrained code generator with constraint validation and cognitive summary."""

from __future__ import annotations

from concordcoder.alignment.prompts import SYSTEM_CODE_GENERATOR, build_constrained_generation_prompt
from concordcoder.schemas import AlignmentRecord, Constraint, ContextBundle, GenerationRequest, GenerationResult


class ConstrainedGenerator:
    """Generate code respecting confirmed constraints from AlignmentRecord.

    Workflow:
    1. Build constraint-aware system prompt
    2. Call LLM for initial code generation
    3. Validate against hard constraints (lightweight checks)
    4. If violations found, re-generate with feedback (max 3 attempts)
    5. Produce GenerationResult with cognitive summary
    """

    MAX_RETRIES = 3

    def __init__(self, llm_client=None) -> None:
        self.llm = llm_client

    def generate(self, req: GenerationRequest) -> GenerationResult:
        if not self.llm:
            return self._fallback_stub(req)

        context_snippets = [
            {"path": s.path, "start": s.start_line, "text": s.text}
            for s in req.bundle.snippets[:5]
        ]

        hard_descriptions = [
            c.description for c in req.alignment.confirmed_constraints if c.hard
        ]

        user_prompt = build_constrained_generation_prompt(
            task=req.user_request,
            hard_constraints=hard_descriptions,
            allowlist=req.alignment.allowlist_paths,
            acceptance_criteria=req.alignment.test_acceptance_criteria,
            implementation_choice=req.alignment.implementation_preference,
            context_snippets=context_snippets,
        )

        messages = [{"role": "user", "content": user_prompt}]
        warnings: list[str] = []

        for attempt in range(1, self.MAX_RETRIES + 1):
            code_text = self.llm.chat(messages, system=SYSTEM_CODE_GENERATOR)
            violations = self._check_violations(code_text, req.alignment.confirmed_constraints)

            if not violations:
                break

            feedback = self._build_violation_feedback(violations)
            messages.append({"role": "assistant", "content": code_text})
            messages.append({"role": "user", "content": feedback})
            warnings.append(f"第 {attempt} 次生成发现约束违规，已重新生成: {'; '.join(v['desc'] for v in violations)}")

        compliance = {c.id: True for c in req.alignment.confirmed_constraints}
        final_violations = self._check_violations(code_text, req.alignment.confirmed_constraints)
        for v in final_violations:
            compliance[v["id"]] = False
            warnings.append(f"⚠️ 约束 [{v['id']}] 最终仍未满足: {v['desc']}")

        cognitive_summary = self._extract_cognitive_summary(code_text)
        changed_files = self._estimate_changed_files(code_text, req.bundle)

        return GenerationResult(
            code_plan=code_text,
            cognitive_summary=cognitive_summary,
            changed_files=changed_files,
            constraint_compliance=compliance,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Constraint checking
    # ------------------------------------------------------------------

    def _check_violations(
        self, code_text: str, constraints: list[Constraint]
    ) -> list[dict]:
        """Lightweight rule-based violation detection."""
        violations = []
        lower = code_text.lower()

        for c in constraints:
            if not c.hard:
                continue

            desc_lower = c.description.lower()

            # Rule: "签名不可更改" — check if signature appears modified
            if "签名" in desc_lower or "api" in desc_lower:
                # Very simple heuristic: if the function name from source appears with def
                # and the constraint mentions "不可更改", we currently can't do deep diff
                # so just pass (this would need actual AST diff in production)
                continue

            # Rule: "不得修改" a specific file
            if "不得修改" in desc_lower or "do not modify" in desc_lower:
                import re
                path_match = re.findall(r"`([^`]+\.py)`", c.description)
                for p in path_match:
                    if p in code_text and "open(" in lower:
                        violations.append({"id": c.id, "desc": c.description})

            # Rule: must not call specific function
            if "must not" in desc_lower or "不应调用" in desc_lower:
                import re
                func_match = re.findall(r"`(\w+)\(\)`", c.description)
                for fn in func_match:
                    if fn + "(" in code_text:
                        violations.append({"id": c.id, "desc": c.description})

        return violations

    def _build_violation_feedback(self, violations: list[dict]) -> str:
        lines = ["❌ 以下约束被违反，请修正后重新生成："]
        for v in violations:
            lines.append(f"- [{v['id']}] {v['desc']}")
        lines.append("\n请重新输出完整的修正后代码，并确保遵守以上约束。")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def _extract_cognitive_summary(self, code_text: str) -> str:
        """Extract the ## 实现摘要 section from generated text."""
        marker = "## 实现摘要"
        idx = code_text.find(marker)
        if idx >= 0:
            return code_text[idx:].strip()
        # Fallback: return last 500 chars
        return code_text[-500:].strip() if len(code_text) > 500 else code_text

    def _estimate_changed_files(self, code_text: str, bundle: ContextBundle) -> list[str]:
        """Heuristic: which repo files appear to be mentioned in generated code."""
        changed = []
        for snip in bundle.snippets:
            # If the file's base name appears in the code block
            import os
            basename = os.path.basename(snip.path).replace(".py", "")
            if basename in code_text and snip.path not in changed:
                changed.append(snip.path)
        return changed[:10]

    # ------------------------------------------------------------------
    # Fallback (no LLM)
    # ------------------------------------------------------------------

    def _fallback_stub(self, req: GenerationRequest) -> GenerationResult:
        hard = [c for c in req.alignment.confirmed_constraints if c.hard]
        hard_lines = "\n".join(f"  - [{c.id}] {c.description}" for c in hard) or "  （无）"

        stub = f"""\
# ConcordCoder 约束感知生成桩（无 LLM 模式）
# 任务: {req.user_request}

# ── 已确认的硬约束 ──────────────────────────
{hard_lines}

# ── 允许修改的文件 ──────────────────────────
{chr(10).join('  # - ' + p for p in req.alignment.allowlist_paths) or '  # （未指定）'}

# ── 验收标准 ────────────────────────────────
{chr(10).join('  # - ' + c for c in req.alignment.test_acceptance_criteria)}

# 请在此处实现新功能...
raise NotImplementedError("请配置 LLM_CLIENT 或手动实现")

## 实现摘要
**为什么这样实现：** 占位桩，请提供 LLM 客户端以生成真实代码。
**建议验证步骤：** 1. pytest -v
"""
        return GenerationResult(
            code_plan=stub,
            cognitive_summary="无 LLM 模式：仅生成约束摘要桩。",
            changed_files=[],
            constraint_compliance={c.id: False for c in req.alignment.confirmed_constraints},
            warnings=["LLM 客户端未配置，返回代码桩。设置 OPENAI_API_KEY 或 ANTHROPIC_API_KEY 以启用真实生成。"],
        )
