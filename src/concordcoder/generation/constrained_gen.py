"""Constrained code generator with constraint validation and cognitive summary."""

from __future__ import annotations

from concordcoder.alignment.prompts import (
    build_constrained_generation_prompt,
    build_json_files_prompt,
    build_unified_diff_prompt,
    system_prompt_for_output_format,
)
from concordcoder.generation.anchor_pipeline import merge_assembly_for_prompt
from concordcoder.generation.json_output import (
    parse_json_generation_response,
    parse_unified_diff_response,
)
from concordcoder.schemas import (
    Constraint,
    ContextBundle,
    FileContentItem,
    GenerationRequest,
    GenerationResult,
    OutputFormat,
)


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
            raise RuntimeError(
                "LLM client is required. Set OPENAI_API_KEY (and optional OPENAI_BASE_URL) "
                "or ANTHROPIC_API_KEY, or pass an LLMClient instance."
            )

        hard_descriptions = [
            c.description for c in req.alignment.confirmed_constraints if c.hard
        ]
        context_snippets = self._context_snippets(req)
        fmt = req.output_format
        anchor = ""
        if req.assembly and req.assembly.anchor_draft:
            anchor = req.assembly.anchor_draft

        if fmt == OutputFormat.JSON_FILES:
            user_prompt = build_json_files_prompt(
                task=req.user_request,
                hard_constraints=hard_descriptions,
                allowlist=req.alignment.allowlist_paths,
                acceptance_criteria=req.alignment.test_acceptance_criteria,
                implementation_choice=req.alignment.implementation_preference,
                context_snippets=context_snippets,
                anchor_draft=anchor,
            )
        elif fmt == OutputFormat.UNIFIED_DIFF:
            user_prompt = build_unified_diff_prompt(
                task=req.user_request,
                hard_constraints=hard_descriptions,
                allowlist=req.alignment.allowlist_paths,
                acceptance_criteria=req.alignment.test_acceptance_criteria,
                implementation_choice=req.alignment.implementation_preference,
                context_snippets=context_snippets,
                anchor_draft=anchor,
            )
        else:
            user_prompt = build_constrained_generation_prompt(
                task=req.user_request,
                hard_constraints=hard_descriptions,
                allowlist=req.alignment.allowlist_paths,
                acceptance_criteria=req.alignment.test_acceptance_criteria,
                implementation_choice=req.alignment.implementation_preference,
                context_snippets=context_snippets,
                anchor_draft=anchor,
            )

        system = system_prompt_for_output_format(fmt)
        messages = [{"role": "user", "content": user_prompt}]
        warnings: list[str] = []

        for attempt in range(1, self.MAX_RETRIES + 1):
            code_text = self.llm.chat(messages, system=system)
            check_text = self._text_for_violation_check(code_text, fmt)
            violations = self._check_violations(check_text, req.alignment.confirmed_constraints)

            if not violations:
                break

            feedback = self._build_violation_feedback(violations)
            messages.append({"role": "assistant", "content": code_text})
            messages.append({"role": "user", "content": feedback})
            warnings.append(
                f"第 {attempt} 次生成发现约束违规，已重新生成: {'; '.join(v['desc'] for v in violations)}"
            )

        compliance = {c.id: True for c in req.alignment.confirmed_constraints}
        final_check = self._text_for_violation_check(code_text, fmt)
        final_violations = self._check_violations(final_check, req.alignment.confirmed_constraints)
        for v in final_violations:
            compliance[v["id"]] = False
            warnings.append(f"⚠️ 约束 [{v['id']}] 最终仍未满足: {v['desc']}")

        structured: list[FileContentItem] = []
        unified_diff = ""
        cognitive_summary = ""

        if fmt == OutputFormat.JSON_FILES:
            structured, cognitive_summary, p_warnings = parse_json_generation_response(code_text)
            warnings.extend(p_warnings)
            if not structured:
                warnings.append("JSON 模式解析失败，已保留原始 LLM 输出于 code_plan；请检查或改用 markdown 格式。")
            if not cognitive_summary:
                cognitive_summary = self._extract_cognitive_summary(code_text)
        elif fmt == OutputFormat.UNIFIED_DIFF:
            unified_diff = parse_unified_diff_response(code_text)
            cognitive_summary = "（unified diff 模式：主要载荷见 unified_diff_text）"
        else:
            cognitive_summary = self._extract_cognitive_summary(code_text)

        changed_files = self._estimate_changed_files(code_text, req.bundle, fmt, structured, unified_diff)

        return GenerationResult(
            code_plan=code_text,
            cognitive_summary=cognitive_summary,
            changed_files=changed_files,
            constraint_compliance=compliance,
            warnings=warnings,
            structured_files=structured,
            unified_diff_text=unified_diff,
        )

    @staticmethod
    def _context_snippets(req: GenerationRequest) -> list[dict]:
        if req.assembly:
            merged = merge_assembly_for_prompt(req.assembly)
            base = [
                {"path": s.path, "start": s.start_line, "text": s.text}
                for s in req.bundle.snippets[:4]
            ]
            seen: set[tuple[str, int]] = set()
            out: list[dict] = []
            for b in merged + base:
                k = (b.get("path", ""), b.get("start", 0))
                if k in seen:
                    continue
                seen.add(k)
                out.append(b)
            return out[:12]
        return [
            {"path": s.path, "start": s.start_line, "text": s.text} for s in req.bundle.snippets[:5]
        ]

    @staticmethod
    def _text_for_violation_check(code_text: str, fmt: OutputFormat) -> str:
        if fmt != OutputFormat.JSON_FILES:
            return code_text
        _files, _, _ = parse_json_generation_response(code_text)
        if not _files:
            return code_text
        return "\n".join(f.content for f in _files)

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

            if "签名" in desc_lower or "api" in desc_lower:
                continue

            if "不得修改" in desc_lower or "do not modify" in desc_lower:
                import re

                path_match = re.findall(r"`([^`]+\.py)`", c.description)
                for p in path_match:
                    if p in code_text and "open(" in lower:
                        violations.append({"id": c.id, "desc": c.description})

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
        lines.append("\n请重新输出完整的修正后内容，并确保遵守以上约束。")
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
        return code_text[-500:].strip() if len(code_text) > 500 else code_text

    def _estimate_changed_files(
        self,
        code_text: str,
        bundle: ContextBundle,
        fmt: OutputFormat,
        structured: list,
        unified_diff: str,
    ) -> list[str]:
        if fmt == OutputFormat.JSON_FILES and structured:
            return [f.path for f in structured[:20]]
        if fmt == OutputFormat.UNIFIED_DIFF and unified_diff:
            import re

            paths = re.findall(r"^\+\+\+ b/(.+)$", unified_diff, re.MULTILINE)
            return list(dict.fromkeys(paths))[:20]
        changed = []
        for snip in bundle.snippets:
            import os

            basename = os.path.basename(snip.path).replace(".py", "")
            if basename in code_text and snip.path not in changed:
                changed.append(snip.path)
        return changed[:10]

