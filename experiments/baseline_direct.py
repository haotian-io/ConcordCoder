#!/usr/bin/env python3
"""RQ1 **Direct** 基线：单轮、无 Phase1/2，仅把自然语言任务发给与 Concord 同后端的 LLM。

与主包解耦；用于与 ``run_single_task`` 在**同一** ``temperature`` / ``max_tokens`` / 模型上可比。

环境（锁预算与 [`LLMClient`](../src/concordcoder/llm_client.py) 一致，可用下列覆盖）：

- ``CONCORD_BASELINE_TEMP`` — 默认 ``0.2``（与 ``LLMClient`` 一致）
- ``CONCORD_BASELINE_MAX_TOKENS`` — 默认 ``4096``
- ``OPENAI_API_KEY`` 或 ``ANTHROPIC_API_KEY`` 等
- 任务与仓库根（只用于在 prompt 里写一句 ``repo:`` 上下文，**不**跑 Concord 抽取）：

  - ``CONCORD_BASELINE_TASK`` — 任务句（必填之一）
  - 或 ``--task`` 命令行
  - ``CONCORD_BASELINE_REPO`` — 可选，打印在 prompt 中便于你记录实验

标准输出为 **一行 JSON**（与 mini_eval 风格兼容，可追加到实验表）::

  {"baseline": "direct", "model": "...", "temperature": 0.2, "reply_len": 1234}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_CODE_ROOT = Path(__file__).resolve().parent.parent
if str(_CODE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_CODE_ROOT / "src"))

from concordcoder.eval_baselines import run_direct_baseline


def main() -> None:
    ap = argparse.ArgumentParser(description="Direct one-shot LLM baseline for RQ1.")
    ap.add_argument(
        "--task",
        "-t",
        help="自然语言任务（或设环境变量 CONCORD_BASELINE_TASK）",
    )
    args = ap.parse_args()

    task = (args.task or os.environ.get("CONCORD_BASELINE_TASK") or "").strip()
    if not task:
        print(
            json.dumps(
                {
                    "error": "Set --task or CONCORD_BASELINE_TASK",
                },
                ensure_ascii=False,
            )
        )
        sys.exit(1)
    repo_hint = (os.environ.get("CONCORD_BASELINE_REPO") or "").strip()

    temp = float(os.environ.get("CONCORD_BASELINE_TEMP", "0.2"))
    max_tok = int(os.environ.get("CONCORD_BASELINE_MAX_TOKENS", "4096"))

    from concordcoder.llm_client import get_llm_client

    try:
        client = get_llm_client()
    except EnvironmentError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)

    client.temperature = temp
    client.max_tokens = max_tok

    result = run_direct_baseline(task=task, client=client, repo_hint=repo_hint)
    reply = result["reply"]

    out = {
        "baseline": "direct",
        "model": client.model,
        "backend": client.backend,
        "temperature": client.temperature,
        "max_tokens": client.max_tokens,
        "reply_len": len(reply or ""),
        "elapsed_s": round(float(result["elapsed_s"]), 2),
        "rounds_used": result["rounds_used"],
        "prompt_tokens": result["prompt_tokens"],
        "completion_tokens": result["completion_tokens"],
        "fairness_budget": {
            "max_turns": int(os.environ.get("CONCORD_FAIR_MAX_TURNS", "3")),
            "max_prompt_tokens": int(os.environ.get("CONCORD_FAIR_MAX_PROMPT_TOKENS", "4000")),
            "max_completion_tokens": int(os.environ.get("CONCORD_FAIR_MAX_COMPLETION_TOKENS", "4000")),
            "max_wallclock_sec": int(os.environ.get("CONCORD_FAIR_MAX_WALLCLOCK_SEC", "300")),
        },
    }
    print(json.dumps(out, ensure_ascii=False))
    print("---REPLY-START---", file=sys.stderr)
    print(reply, file=sys.stderr)
    print("---REPLY-END---", file=sys.stderr)


if __name__ == "__main__":
    main()
