"""PoC script: end-to-end Confidence-Guided Probing demonstration.

Demonstrates Contribution 2 of ConcordCoder:
  1. Simulate LLM generating code with token-level logprobs
  2. Run ProbingEngine to detect low-confidence AST nodes
  3. Display probe questions that would be asked before regeneration

Run:
    cd /Users/qingxia/SE/Study/Research/ConcordCoder
    /opt/anaconda3/bin/conda run -n base python experiments/perplexity_poc.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from concordcoder.generation.probing import (
    ProbingEngine,
    TokenWithLogprob,
    mock_logprobs_from_code,
)
from concordcoder.schemas import ContextBundle, Constraint

# ─── Mock ContextBundle (simulates Phase 1 output) ──────────────────────────

MOCK_BUNDLE = ContextBundle(
    task_summary="为支付模块新增带指数退避的重试逻辑",
    structural_facts=[
        "payment/handler.py 中 process_payment() 被 checkout.py、subscription.py 等 3 处调用",
        "retry_policy.py 目前最大重试次数为 3 次",
    ],
    historical_decisions=[
        "payment.py: 修改了事务提交逻辑以避免重复扣款",
        "payment.py: 重构了异常处理，从 raise 改为 return error_code",
        "transaction.py: 修改",
    ],
    constraints_guess=[
        Constraint(id="C1", description="process_payment 函数签名不可更改（被3处调用）", hard=True, source="ast"),
    ],
)

# ─── Simulated Generated Code ────────────────────────────────────────────────

GENERATED_CODE = '''\
import time
import logging
from payment.handler import process_payment
from retry_policy import RetryPolicy

logger = logging.getLogger(__name__)

def process_payment_with_retry(user_id: str, amount: float) -> bool:
    """Add exponential backoff retry logic around process_payment."""
    policy = RetryPolicy(max_retries=3, base_delay=1.0)
    last_error = None

    for attempt in range(policy.max_retries + 1):
        try:
            result = process_payment(user_id, amount)
            if result:
                logger.info(f"Payment succeeded on attempt {attempt + 1}")
                return True
        except Exception as exc:
            last_error = exc
            logger.warning(f"Payment attempt {attempt + 1} failed: {exc}")

        # Exponential backoff
        if attempt < policy.max_retries:
            delay = policy.base_delay * (2 ** attempt)
            time.sleep(delay)

    logger.error(f"All {policy.max_retries + 1} payment attempts failed: {last_error}")
    raise last_error
'''


def run_poc(use_real_api: bool = False) -> None:
    """Run the Probing PoC."""
    print("=" * 70)
    print("  ConcordCoder — Confidence-Guided Probing Demo (Contribution 2)")
    print("=" * 70)

    print("\n📄 Generated Code:\n")
    print(GENERATED_CODE)

    # Step 1: Get logprobs (mock or real)
    if use_real_api:
        import openai
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Python code generation assistant.",
                },
                {
                    "role": "user",
                    "content": (
                        "Generate Python code that adds exponential backoff retry "
                        "around a payment processing function. Keep it concise."
                    ),
                },
            ],
            logprobs=True,
            top_logprobs=5,
            max_tokens=400,
        )
        from concordcoder.generation.probing import parse_openai_logprobs
        logprobs = parse_openai_logprobs(response)
        generated = response.choices[0].message.content or GENERATED_CODE
    else:
        print("ℹ️  Using mock logprobs (no API key required).")
        logprobs = mock_logprobs_from_code(GENERATED_CODE, seed_confidence=0.82)
        generated = GENERATED_CODE

    print(f"\n📊 Total tokens: {len(logprobs)}")

    # Quick confidence summary
    mean_conf = sum(math.exp(t.logprob) for t in logprobs) / max(len(logprobs), 1)
    print(f"   Mean confidence: {mean_conf:.1%}")
    low_conf_toks = [t for t in logprobs if math.exp(t.logprob) < 0.4]
    print(f"   Low-confidence tokens (<40%): {len(low_conf_toks)}")

    # Step 2: Run ProbingEngine
    print("\n🔍 Running ProbingEngine...")
    engine = ProbingEngine(
        llm_client=None,          # No LLM in PoC; uses rule-based probe generation
        bundle=MOCK_BUNDLE,
        confidence_threshold=0.45,
        churn_alpha=0.6,
        max_probes=3,
    )
    result = engine.run(generated, logprobs)

    # Step 3: Display results
    print("\n" + "─" * 60)
    print(result.low_confidence_summary)

    if result.needs_probing:
        print("\n💬 Probe Questions that would be asked to the user:\n")
        for i, q in enumerate(result.probe_questions, 1):
            print(f"  [{i}] {q}\n")

        print("─" * 60)
        print("📌 Probe Targets (sorted by hotspot score):")
        for p in result.probes:
            print(
                f"  • {p.span.node_type}:`{p.span.node_name}` "
                f"(line ~{p.span.line_hint}) | "
                f"conf={p.confidence:.0%}, churn={p.git_churn:.0%}, "
                f"score={p.hotspot_score:.3f}"
            )

        print("\n  → In production: user answers these questions")
        print("  → AlignmentRecord.add_late_probe() stores the new constraints")
        print("  → Only the flagged spans are re-generated (not full restart)")
    else:
        print("\n✅ No probing needed — generation confidence is sufficient.")

    print("\n" + "=" * 70)
    print("  PoC Complete")
    print("=" * 70)


if __name__ == "__main__":
    import os
    use_real = bool(os.environ.get("OPENAI_API_KEY"))
    run_poc(use_real_api=use_real)
