"""Structured artifacts passed between extraction → alignment → generation."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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


class GenerationResult(BaseModel):
    """Output of constrained code generation."""

    code_plan: str = ""               # 生成的代码/计划文本
    cognitive_summary: str = ""       # 认知摘要（为什么这样实现）
    changed_files: list[str] = Field(default_factory=list)
    constraint_compliance: dict[str, bool] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
