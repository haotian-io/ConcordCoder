"""Prompt templates for alignment dialogue phases."""

from __future__ import annotations

from concordcoder.schemas import ContextBundle, OutputFormat

# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

SYSTEM_CONTEXT_ANALYST = """\
你是一位资深软件工程师，擅长阅读代码仓库并向其他开发者解释项目结构。
你的目标是帮助开发者"重建认知"——让他们理解与当前任务最相关的代码结构、设计约束和历史决策。

原则：
- 语言：简体中文
- 语气：像一位熟悉这个项目的友善同事，不要过于正式
- 一次只展示 2-3 个最关键的发现，不要信息轰炸
- 对于不确定的推断，明确说明这是推测
- 引导用户确认或修正你的理解
"""

SYSTEM_CONSTRAINT_ANALYST = """\
你是一位代码约束分析专家。
你的目标是从代码分析结果中识别、推断并分类设计约束，以结构化 JSON 格式输出。

输出格式要求（严格遵守）：
{
  "hard_constraints": [
    {"id": "c1", "description": "...", "source": "filepath:lineno or reasoning"}
  ],
  "soft_constraints": [
    {"id": "s1", "description": "...", "source": "..."}
  ],
  "risks": [
    {"category": "...", "detail": "...", "severity": "low|medium|high"}
  ],
  "open_questions": ["...", "..."],
  "implementation_options": [
    {"name": "方案A", "description": "...", "pros": "...", "cons": "..."}
  ]
}
"""

SYSTEM_CODE_GENERATOR = """\
你是一个约束感知的代码生成助手。

在生成代码时，你必须：
1. 严格遵守 <constraints> 标签中列出的所有硬约束
2. 只修改 <allowlist> 标签中允许修改的文件
3. 确保生成的代码能通过 <acceptance_criteria> 中的验收标准
4. 在代码末尾附上认知摘要（## 实现摘要）

认知摘要格式：
## 实现摘要
**为什么这样实现：** ...（关联到具体约束）
**已处理的风险：** ...
**仍需关注：** ...
**建议验证步骤：** 1. ... 2. ...
"""

SYSTEM_JSON_CODE_GENERATOR = """\
你是约束感知的代码生成助手。你的回复必须是**单个 JSON 对象**（可放在 ```json 代码块中），
除此之外不要输出其他文字。Schema：
{
  "files": [ { "path": "相对仓库根的路径", "content": "文件完整内容" } ],
  "cognitive_summary": "简短说明与约束/风险的对应"
}
1. 遵守用户消息中 <constraints>、<allowlist>、<acceptance_criteria>。
2. 每个 path 使用正斜杠；content 为 UTF-8 完整文件文本。
3. 若仅改一个文件，files 也必须是长度为 1 的数组。
"""

SYSTEM_UNIFIED_DIFF_GENERATOR = """\
你是约束感知的代码生成助手。只输出一个 **unified diff**（git 风格，以 diff --git 或 ---/+++ 开头），
可放在 ```diff 代码块中。除 diff 与可选的简短 ``` 围栏外不要输出其他解释文字。
所给 diff 必须只触及 <allowlist> 允许的路径；遵守 <constraints> 与 <acceptance_criteria>。
"""


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_context_reconstruction_prompt(bundle: ContextBundle) -> str:
    """Phase A: help user rebuild understanding of existing codebase."""
    parts = [f"## 任务描述\n{bundle.task_summary}\n"]

    if bundle.structural_facts:
        parts.append("## 静态分析发现（最关键的）")
        for fact in bundle.structural_facts[:5]:
            parts.append(f"- {fact}")

    if bundle.snippets:
        parts.append(f"\n## 最相关代码片段（共找到 {len(bundle.snippets)} 个）")
        for snip in bundle.snippets[:3]:
            parts.append(f"\n**文件**: `{snip.path}` (行 {snip.start_line}-{snip.end_line})")
            parts.append(f"```python\n{snip.text[:600]}\n```")

    if bundle.historical_decisions:
        parts.append("\n## Git 历史中发现的设计决策")
        for d in bundle.historical_decisions[:5]:
            parts.append(f"- {d}")

    if bundle.test_expectations:
        parts.append("\n## 测试文件推断的行为期望")
        for e in bundle.test_expectations[:5]:
            parts.append(f"- {e}")

    parts.append(
        "\n请基于以上信息，用自然对话的方式：\n"
        "1. 向用户介绍与本次任务最相关的 2-3 个关键发现\n"
        "2. 询问用户对这些发现的熟悉程度\n"
        "3. 如果有明显的设计约束，礼貌地提醒\n"
        "一次只说最重要的内容，保持对话自然。"
    )

    return "\n".join(parts)


def build_constraint_inference_prompt(bundle: ContextBundle, user_responses: str = "") -> str:
    """Phase B: infer and present constraints for user confirmation."""
    parts = [
        f"## 任务描述\n{bundle.task_summary}\n",
        "## 已有约束猜测（来自代码分析）",
    ]

    for c in bundle.constraints_guess:
        hard_label = "🔴 硬约束" if c.hard else "🟡 软约束"
        parts.append(f"- {hard_label}: {c.description} (来源: {c.source or '分析推断'})")

    for r in bundle.risks:
        parts.append(f"- ⚠️ 风险[{r.severity}]: {r.detail}")

    if bundle.affected_modules:
        parts.append("\n## 可能受影响的模块\n" + "\n".join(f"- {m}" for m in bundle.affected_modules[:8]))

    if user_responses:
        parts.append(f"\n## 用户已提供的信息\n{user_responses}")

    parts.append(
        "\n请以结构化 JSON 格式输出：\n"
        "1. 整理已确认和推断的约束（分 hard/soft）\n"
        "2. 列出需要用户明确回答的问题\n"
        "3. 提供 2-3 个实现方案选项\n"
        "严格按 SYSTEM 消息中的 JSON schema 输出。"
    )

    return "\n".join(parts)


def build_constrained_generation_prompt(
    task: str,
    hard_constraints: list[str],
    allowlist: list[str],
    acceptance_criteria: list[str],
    implementation_choice: str = "",
    context_snippets: list[dict] | None = None,
    anchor_draft: str = "",
) -> str:
    """Phase C: constrained code generation prompt."""
    parts = [f"## 任务\n{task}\n"]

    parts.append("<constraints>")
    if hard_constraints:
        for c in hard_constraints:
            parts.append(f"- {c}")
    else:
        parts.append("（无强制硬约束，尽量保持现有代码风格）")
    parts.append("</constraints>\n")

    parts.append("<allowlist>")
    if allowlist:
        for p in allowlist:
            parts.append(f"- {p}")
    else:
        parts.append("（未指定，请仅修改最小必要文件集）")
    parts.append("</allowlist>\n")

    parts.append("<acceptance_criteria>")
    if acceptance_criteria:
        for crit in acceptance_criteria:
            parts.append(f"- {crit}")
    else:
        parts.append("- 现有测试全部通过（无回归）")
        parts.append("- 新功能有对应测试覆盖")
    parts.append("</acceptance_criteria>\n")

    if implementation_choice:
        parts.append(f"## 用户选择的实现方案\n{implementation_choice}\n")

    if anchor_draft:
        parts.append("## 锚点草稿 (InlineCoder 风格; 可能不完美，请在对齐后的约束下修正)\n")
        parts.append(f"```python\n{anchor_draft[:4000]}\n```\n")

    if context_snippets:
        parts.append("## 相关现有代码")
        for snip in context_snippets[:5]:
            parts.append(f"\n**{snip.get('path', '')}** (行 {snip.get('start', '')}-):")
            parts.append(f"```python\n{snip.get('text', '')[:800]}\n```")

    parts.append("\n请生成满足上述约束的代码，并在末尾附上认知摘要（## 实现摘要）。")

    return "\n".join(parts)


def build_json_files_prompt(
    task: str,
    hard_constraints: list[str],
    allowlist: list[str],
    acceptance_criteria: list[str],
    implementation_choice: str = "",
    context_snippets: list[dict] | None = None,
    anchor_draft: str = "",
) -> str:
    """Same context as markdown mode; output instruction differs."""
    base = build_constrained_generation_prompt(
        task=task,
        hard_constraints=hard_constraints,
        allowlist=allowlist,
        acceptance_criteria=acceptance_criteria,
        implementation_choice=implementation_choice,
        context_snippets=context_snippets,
        anchor_draft=anchor_draft,
    )
    return (
        base
        + "\n\n**输出要求**：不要按上文“认知摘要”段落格式输出。改为仅输出 JSON 对象，"
        "键 files（数组）与 cognitive_summary（字符串），见 system 中的 schema。"
    )


def build_unified_diff_prompt(
    task: str,
    hard_constraints: list[str],
    allowlist: list[str],
    acceptance_criteria: list[str],
    implementation_choice: str = "",
    context_snippets: list[dict] | None = None,
    anchor_draft: str = "",
) -> str:
    base = build_constrained_generation_prompt(
        task=task,
        hard_constraints=hard_constraints,
        allowlist=allowlist,
        acceptance_criteria=acceptance_criteria,
        implementation_choice=implementation_choice,
        context_snippets=context_snippets,
        anchor_draft=anchor_draft,
    )
    return (
        base
        + "\n\n**输出要求**：不要生成完整文件正文。只输出一个 unified diff，覆盖需要修改的文件。"
    )


def system_prompt_for_output_format(fmt: OutputFormat) -> str:
    if fmt == OutputFormat.JSON_FILES:
        return SYSTEM_JSON_CODE_GENERATOR
    if fmt == OutputFormat.UNIFIED_DIFF:
        return SYSTEM_UNIFIED_DIFF_GENERATOR
    return SYSTEM_CODE_GENERATOR
