"""Structured artifacts passed between extraction → alignment → generation."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OutputFormat(str, Enum):
    """Machine-readable / presentation output for `concord once`."""

    MARKDOWN_PLAN = "markdown_plan"   # 当前默认：长文本 + 认知摘要
    JSON_FILES = "json_files"         # 严格 JSON：{"files":[{"path","content"}]}
    UNIFIED_DIFF = "unified_diff"     # 统一 diff 文本（便于试跑 patch）


class ContextDependencyLevel(str, Enum):
    """CoderEval-style context dependency (short tasks; subset of full 6-level scale)."""

    SELF_CONTAINED = "self-contained"
    SLIB_RUNNABLE = "slib-runnable"
    PLIB_RUNNABLE = "plib-runnable"
    CLASS_RUNNABLE = "class-runnable"
    FILE_RUNNABLE = "file-runnable"
    PROJECT_RUNNABLE = "project-runnable"


class EvidenceLevel(str, Enum):
    TEST = "test"
    TYPE = "type"
    IMPLEMENTATION = "implementation"
    COMMENT = "comment"
    DOC = "doc"
    GIT = "git"


class SnippetRef(BaseModel):
    path: str
    start_line: int
    end_line: int
    text: str = ""
    evidence_level: EvidenceLevel = EvidenceLevel.IMPLEMENTATION
    relevance_score: float = 0.0


class Constraint(BaseModel):
    """Hard constraints are enforced by checks; soft are preferences."""

    id: str
    description: str
    hard: bool = True
    source: str | None = None  # e.g. path:test_x or alignment:round2


class RiskItem(BaseModel):
    category: str
    detail: str
    severity: str = "medium"  # low | medium | high


class ContextBundle(BaseModel):
    """Output of context extraction / fusion."""

    task_summary: str = ""
    structural_facts: list[str] = Field(default_factory=list)
    snippets: list[SnippetRef] = Field(default_factory=list)
    constraints_guess: list[Constraint] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    # --- Phase 1 升级新增字段 ---
    call_graph: dict[str, list[str]] = Field(default_factory=dict)
    entry_points: list[str] = Field(default_factory=list)
    design_constraints: list[Constraint] = Field(default_factory=list)
    historical_decisions: list[str] = Field(default_factory=list)
    test_expectations: list[str] = Field(default_factory=list)
    affected_modules: list[str] = Field(default_factory=list)

    metadata: dict[str, Any] = Field(default_factory=dict)


class AssembledContext(BaseModel):
    """InlineCoder-style MVP: anchor draft + upstream/downstream snippet windows."""

    anchor_draft: str = ""
    upstream_snippets: list[SnippetRef] = Field(default_factory=list)
    downstream_snippets: list[SnippetRef] = Field(default_factory=list)


class AlignmentRecord(BaseModel):
    """Output of alignment dialogue, input to constrained generation."""

    refined_intent: str = ""
    confirmed_constraints: list[Constraint] = Field(default_factory=list)
    allowlist_paths: list[str] = Field(default_factory=list)
    test_acceptance_criteria: list[str] = Field(default_factory=list)
    rejected_constraints: list[Constraint] = Field(default_factory=list)  # 用户明确否决的
    implementation_preference: str = ""   # 用户选择的方案描述
    notes: str = ""


class GenerationRequest(BaseModel):
    repo_root: str
    user_request: str
    bundle: ContextBundle
    alignment: AlignmentRecord
    assembly: AssembledContext | None = None
    output_format: OutputFormat = Field(default=OutputFormat.MARKDOWN_PLAN)


class FileContentItem(BaseModel):
    """One file in a json_files model output."""

    path: str
    content: str


class GenerationResult(BaseModel):
    """Output of constrained code generation."""

    code_plan: str = ""               # 生成的代码/计划文本
    cognitive_summary: str = ""       # 认知摘要（为什么这样实现）
    changed_files: list[str] = Field(default_factory=list)
    constraint_compliance: dict[str, bool] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    # Populated when output_format is JSON_FILES and parsing succeeds
    structured_files: list[FileContentItem] = Field(default_factory=list)
    # Populated for UNIFIED_DIFF when treated as the primary payload
    unified_diff_text: str = ""


class SingleTaskSpec(BaseModel):
    """Input contract for a single bounded run (e.g. `concord once`)."""

    task_id: str | None = None
    task: str
    allowlist_paths: list[str] = Field(default_factory=list)
    no_align: bool = True
    full_align: bool = False
    output_format: OutputFormat = OutputFormat.MARKDOWN_PLAN
    answers: dict[str, str] = Field(default_factory=dict)


class SingleTaskResult(BaseModel):
    """Output of `run_single_task` including optional parsed artifacts."""

    spec: SingleTaskSpec
    generation: GenerationResult
    parsed_files: list[FileContentItem] = Field(default_factory=list)
    unified_diff: str = ""
    out_dir: str | None = None
