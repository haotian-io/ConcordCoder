#!/usr/bin/env python3
"""
SWE-bench-scale driver — **skeleton only** (RQ1 large-benchmark track).

This script does **not** run SWE-bench by default. It documents env vars and
optional dependencies, and prints a one-line JSON status for CI / notebooks.

Per ``Paper/main.tex`` §limitations:benchmarks and the project summary appendix A (roadmap) §2,
full SWE-bench integration is **parallel** to ``scripts/mini_eval.py``, not a replacement.

Planned usage (after you wire a runner):
  export SWE_INSTANCE_IDS=...   # optional comma-separated subset
  python3 scripts/swe_bench_driver_skeleton.py --dry-run

Optional Python deps (not in core ``pyproject.toml``):
  pip install swebench  # https://github.com/swe-bench/SWE-bench
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


def main() -> None:
    p = argparse.ArgumentParser(description="SWE-bench driver skeleton (status JSON only).")
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Default: only print planned layout (default True).",
    )
    args = p.parse_args()

    swebench_ok = False
    try:
        import swebench  # noqa: F401

        swebench_ok = True
    except ImportError:
        pass

    instance_ids = os.environ.get("SWE_INSTANCE_IDS", "")
    out = {
        "driver": "swe_bench_driver_skeleton",
        "status": "skeleton_not_run",
        "dry_run": args.dry_run,
        "swebench_import_ok": swebench_ok,
        "mini_eval_preserved": str(_CODE_ROOT / "scripts" / "mini_eval.py"),
        "swe_bench_batch_mvf": str(_CODE_ROOT / "scripts" / "swe_bench_batch.py"),
        "env": {
            "SWE_INSTANCE_IDS_set": bool(instance_ids.strip()),
            "OPENAI_API_KEY_set": bool(os.environ.get("OPENAI_API_KEY")),
        },
        "next_steps": [
            "MVF batch (HF Lite + run_single_task): see scripts/swe_bench_batch.py and experiments/swe_tiny_config.yaml",
            "Install optional: pip install 'datasets>=2.16' (e.g. pip install -e '.[eval]')",
            "Report Pass@k / constraint violations alongside mini_eval JSON, not instead of it",
            "mini_eval requires CONCORD_EVAL_REPO_ROOT and CONCORD_EVAL_TASKS_DIR or CONCORD_EVAL_TASKS_GLOB",
        ],
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
