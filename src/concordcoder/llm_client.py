"""LLM client abstraction: supports OpenAI and Anthropic (Claude) backends."""

from __future__ import annotations

import json
import os
from typing import Any


def get_llm_client(backend: str | None = None) -> "LLMClient":
    """Construct an ``LLMClient`` or raise if no API key / init fails.

    Resolves ``backend`` from env when omitted: ``OPENAI_API_KEY`` → openai,
    else ``ANTHROPIC_API_KEY`` → anthropic.

    For OpenAI-compatible proxies, set ``OPENAI_BASE_URL`` (e.g. ``https://host/v1``).
    """
    if backend is None:
        if os.environ.get("OPENAI_API_KEY"):
            backend = "openai"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            backend = "anthropic"
        else:
            raise EnvironmentError(
                "No LLM API key set. Set OPENAI_API_KEY or ANTHROPIC_API_KEY "
                "(and optional OPENAI_BASE_URL for OpenAI-compatible endpoints)."
            )
    return LLMClient(backend=backend)


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

    def chat_with_logprobs(
        self, messages: list[dict[str, str]], system: str = ""
    ) -> tuple[str, list]:
        """OpenAI chat completion with ``logprobs=True``; returns (assistant_text, tokens).

        ``tokens`` is a list of :class:`~concordcoder.generation.probing.TokenWithLogprob`.
        Only the **openai** backend is supported; Anthropic messages API does not expose
        token logprobs in the same way — callers should fall back to mocks.

        Requires ``pip install openai`` and ``OPENAI_API_KEY``.
        """
        if self.backend != "openai":
            raise ValueError(
                "chat_with_logprobs is only supported for backend='openai'. "
                "Use mock token logprobs for other backends."
            )
        from concordcoder.generation.probing import parse_openai_logprobs

        all_messages: list[dict[str, str]] = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=all_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                logprobs=True,
                top_logprobs=5,
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI API request (with logprobs) failed: {e}") from e
        choice = response.choices[0]
        text = (choice.message.content or "").strip()
        tokens = parse_openai_logprobs(response)
        return text, tokens

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
            base_url = os.environ.get("OPENAI_BASE_URL")
            if base_url:
                return OpenAI(api_key=api_key, base_url=base_url)
            return OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("openai not installed. Run: pip install openai")

    def _openai_chat(self, messages: list[dict[str, str]], system: str) -> str:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=all_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI API request failed: {e}") from e
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
        try:
            response = self._client.messages.create(
                model=self.model,
                system=system or "You are a helpful coding assistant.",
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except Exception as e:
            raise RuntimeError(f"Anthropic API request failed: {e}") from e
        return response.content[0].text if response.content else ""
