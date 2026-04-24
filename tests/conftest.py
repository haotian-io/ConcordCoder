"""Shared test doubles for LLM-dependent paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StubLLM:
    """Minimal stand-in for LLMClient: returns fixed markdown/JSON for tests."""

    reply: str = field(
        default=(
            "# Plan\n\n```python\n# stub output\nx = 1\n```\n\n"
            "Summary: test stub."
        )
    )
    last_messages: list[dict[str, str]] = field(default_factory=list)
    last_system: str = ""

    def chat(self, messages: list[dict[str, str]], system: str = "") -> str:
        self.last_messages = list(messages)
        self.last_system = system
        return self.reply

    def chat_json(self, messages: list[dict[str, str]], system: str = "") -> Any:
        self.last_messages = list(messages)
        self.last_system = system
        return {
            "refined_intent": "t",
            "confirmed_constraints": [],
            "suggested_qa": [],
        }
