"""LLMClient.chat_with_logprobs (OpenAI path, mocked transport)."""

from __future__ import annotations

import pytest

from concordcoder.llm_client import LLMClient


def test_chat_with_logprobs_openai_parses_tokens(monkeypatch):
    class TokenItem:
        def __init__(self, token: str, logprob: float) -> None:
            self.token = token
            self.logprob = logprob
            self.bytes: list[int] = []

    class LogprobsObj:
        content = [TokenItem("def", -0.05), TokenItem(" x", -0.2)]

    class Message:
        content = "def x"

    class Choice:
        message = Message()
        logprobs = LogprobsObj()

    class Response:
        choices = [Choice()]

    captured: dict = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return Response()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client = LLMClient(backend="openai", model="gpt-4o-mini")
    client._client = FakeClient()

    text, tokens = client.chat_with_logprobs(
        [{"role": "user", "content": "ping"}],
        system="sys",
    )

    assert captured.get("logprobs") is True
    assert text == "def x"
    assert len(tokens) == 2
    assert tokens[0].token == "def"
    assert tokens[0].logprob == -0.05


def test_chat_with_logprobs_rejects_anthropic(monkeypatch):
    pytest.importorskip("anthropic", reason="anthropic optional")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    client = LLMClient(backend="anthropic")
    with pytest.raises(ValueError, match="only supported for backend='openai'"):
        client.chat_with_logprobs([{"role": "user", "content": "x"}])
