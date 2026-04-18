"""LLM client abstraction: supports OpenAI and Anthropic (Claude) backends."""

from __future__ import annotations

import json
import os
from typing import Any


class LLMClient:
    """Thin wrapper around OpenAI / Anthropic APIs.

    Set OPENAI_API_KEY or ANTHROPIC_API_KEY in environment.
    ``backend`` can be "openai" or "anthropic".
    """

    def __init__(
        self,
        backend: str = "openai",
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> None:
        self.backend = backend.lower()
        self.temperature = temperature
        self.max_tokens = max_tokens

        if self.backend == "openai":
            self.model = model or "gpt-4o"
            self._client = self._init_openai()
        elif self.backend == "anthropic":
            self.model = model or "claude-3-5-sonnet-20241022"
            self._client = self._init_anthropic()
        else:
            raise ValueError(f"Unsupported backend: {backend}. Choose 'openai' or 'anthropic'.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, messages: list[dict[str, str]], system: str = "") -> str:
        """Send a list of {role, content} messages and return the assistant reply."""
        if self.backend == "openai":
            return self._openai_chat(messages, system)
        else:
            return self._anthropic_chat(messages, system)

    def chat_json(self, messages: list[dict[str, str]], system: str = "") -> Any:
        """Like ``chat`` but parse the response as JSON."""
        raw = self.chat(messages, system)
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"raw": raw}

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    def _init_openai(self):
        try:
            from openai import OpenAI  # type: ignore[import]
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise EnvironmentError("OPENAI_API_KEY not set.")
            return OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("openai not installed. Run: pip install openai")

    def _openai_chat(self, messages: list[dict[str, str]], system: str) -> str:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)
        response = self._client.chat.completions.create(
            model=self.model,
            messages=all_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content or ""

    def _init_anthropic(self):
        try:
            import anthropic  # type: ignore[import]
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise EnvironmentError("ANTHROPIC_API_KEY not set.")
            return anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("anthropic not installed. Run: pip install anthropic")

    def _anthropic_chat(self, messages: list[dict[str, str]], system: str) -> str:
        response = self._client.messages.create(
            model=self.model,
            system=system or "You are a helpful coding assistant.",
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.content[0].text if response.content else ""
