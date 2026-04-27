from concordcoder.eval_baselines import run_direct_baseline


class _FakeClient:
    def __init__(self) -> None:
        self.calls = []

    def chat(self, messages, system=""):
        self.calls.append({"messages": list(messages), "system": system})
        return "--- a/foo.py\n+++ b/foo.py\n@@\n-print('old')\n+print('new')\n"

    def drain_token_usage(self):
        return (123, 45)


def test_run_direct_baseline_single_round():
    client = _FakeClient()

    result = run_direct_baseline(
        task="Update foo output",
        client=client,
        repo_hint="/tmp/repo",
    )

    assert result["rounds_used"] == 1
    assert result["prompt_tokens"] == 123
    assert result["completion_tokens"] == 45
    assert "+++ b/foo.py" in result["reply"]
    assert len(client.calls) == 1
    assert "Repository root" in client.calls[0]["messages"][0]["content"]


def test_run_direct_baseline_with_feedback_rounds():
    client = _FakeClient()

    result = run_direct_baseline(
        task="Update foo output",
        client=client,
        feedback_rounds=["Please make the patch smaller.", "Preserve public API."],
    )

    assert result["rounds_used"] == 3
    assert len(client.calls) == 3
    assert client.calls[-1]["messages"][-1]["content"] == "Preserve public API."
