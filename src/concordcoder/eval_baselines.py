"""Helpers for evaluation-time baselines that bypass the main Concord pipeline."""

from __future__ import annotations

from time import perf_counter


def run_direct_baseline(
    *,
    task: str,
    client,
    repo_hint: str = "",
    feedback_rounds: list[str] | None = None,
) -> dict:
    """Run a minimal direct/post-hoc baseline against the raw LLM.

    The baseline intentionally bypasses ConcordCoder extraction, alignment,
    probing, and constrained generation. It asks the LLM to produce a minimal
    unified diff patch directly from the natural-language task.
    """

    system = (
        "You are an expert software engineer working on an existing repository. "
        "Return a minimal unified diff patch whenever possible. "
        "Keep the patch focused, preserve public APIs unless the task requires "
        "otherwise, and avoid unrelated edits."
    )
    user = (
        "Generate a concise unified diff patch for the following repository-level task.\n\n"
        f"Task: {task}\n"
    )
    if repo_hint:
        user += f"\nRepository root (path hint only): {repo_hint}\n"

    feedback_rounds = feedback_rounds or []
    messages = [{"role": "user", "content": user}]
    t0 = perf_counter()
    reply = client.chat(messages, system=system)
    rounds_used = 1

    for feedback in feedback_rounds:
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": feedback})
        reply = client.chat(messages, system=system)
        rounds_used += 1

    prompt_tokens = completion_tokens = None
    if hasattr(client, "drain_token_usage"):
        prompt_tokens, completion_tokens = client.drain_token_usage()

    return {
        "reply": reply,
        "rounds_used": rounds_used,
        "elapsed_s": perf_counter() - t0,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
