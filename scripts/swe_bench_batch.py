#!/usr/bin/env python3
"""
SWE-bench Lite → ``run_single_task`` 的最小批处理（与 ``mini_eval.py`` 并列的 RQ1 扩展轨）。

**不**实现官方 Docker harness；**不**自动克隆仓库。你需要在 ``base_commit`` 上自行为每条 instance
准备好本地目录，并通过 ``CONCORD_SWE_REPO_ROOT`` 指到该根目录。

环境：

- ``CONCORD_SWE_REPO_ROOT``：已检出到**对应 instance 的 base_commit** 的仓库绝对路径。一次运行通常
  只处理**一条** instance，跑完再换下一提交（或分多次调用）。
- ``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY`` 等同 ``concord once``。

依赖（可选，与 ``[eval]`` 一致）::

    pip install "datasets>=2.16"   # 以及 concord 的 [openai] 等

典型用法（先 ``git checkout`` 到该 instance 的 base）::

  export CONCORD_SWE_REPO_ROOT=/abs/path/to/checkout
  python3 scripts/swe_bench_batch.py --instance-id "django__django-11099" --out-row run.json

仅列出前若干条 id（不访问 API）::

  python3 scripts/swe_bench_batch.py --list-ids 5

与 ``experiments/swe_tiny_config.yaml``：可用 ``--config`` 内 ``instance_ids`` 批量跑；此时仍要求
每条之间你自行更换目录/提交（本脚本不自动化）。

干跑（构造 ``SingleTaskSpec`` 并 ``print``，不调 LLM）::

  python3 scripts/swe_bench_batch.py --instance-id "..." --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

_CODE_ROOT = Path(__file__).resolve().parent.parent
if str(_CODE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_CODE_ROOT / "src"))


def _load_instance(instance_id: str) -> dict:
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise SystemExit(
            "Install optional: pip install 'datasets>=2.16' "
            "(e.g. pip install -e '.[eval]')"
        ) from e
    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    for row in ds:
        if row.get("instance_id") == instance_id:
            return dict(row)
    raise SystemExit(f"instance_id not found in SWE-bench_Lite: {instance_id!r}")


def _first_path_from_patch(patch: str) -> str | None:
    if not patch:
        return None
    for line in patch.splitlines():
        m = re.match(r"^---\s+a/(\S+)", line)
        if m:
            return m.group(1)
    return None


def _load_config_ids(path: Path) -> list[str]:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data:
        return []
    raw = data.get("instance_ids") or []
    return [str(x) for x in raw]


def main() -> None:
    p = argparse.ArgumentParser(description="SWE-bench Lite row → run_single_task (MVF).")
    p.add_argument(
        "--instance-id",
        help="A single instance_id from SWE-bench_Lite (e.g. owner__repo-nnnn).",
    )
    p.add_argument(
        "--config",
        type=Path,
        help="YAML with instance_ids (see experiments/swe_tiny_config.yaml).",
    )
    p.add_argument("--list-ids", type=int, metavar="N", help="Print first N instance_id and exit.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Build spec and print JSON; do not call the LLM.",
    )
    p.add_argument(
        "--out-row",
        type=Path,
        help="Write one JSON result row to this file (else stdout).",
    )
    p.add_argument(
        "--no-align",
        action="store_true",
        help="Pass no_align to SingleTaskSpec (ablation: skip LLM batch alignment).",
    )
    args = p.parse_args()

    if args.list_ids is not None:
        try:
            from datasets import load_dataset
        except ImportError as e:
            print(
                json.dumps(
                    {
                        "error": "pip install 'datasets>=2.16' required for --list-ids",
                    }
                )
            )
            raise SystemExit(1) from e
        ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
        ids = [ds[i]["instance_id"] for i in range(min(args.list_ids, len(ds)))]
        print(json.dumps({"instance_ids": ids}, ensure_ascii=False, indent=2))
        return

    ids: list[str] = []
    if args.instance_id:
        ids.append(args.instance_id)
    if args.config:
        ids.extend(_load_config_ids(args.config))
    if not ids:
        p.error("Provide --instance-id and/or --config with non-empty instance_ids, or use --list-ids")

    if not args.dry_run and len(ids) > 1:
        print(
            json.dumps(
                {
                    "error": "Non-dry run supports one instance per invocation "
                    "(each instance has its own base_commit; checkout and set "
                    "CONCORD_SWE_REPO_ROOT, then re-run for the next id).",
                    "instance_ids_requested": ids,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    repo = os.environ.get("CONCORD_SWE_REPO_ROOT", "").strip()
    if not repo and not args.dry_run:
        print(
            json.dumps(
                {
                    "error": "Set CONCORD_SWE_REPO_ROOT to a clone at the instance's base_commit.",
                },
                ensure_ascii=False,
            )
        )
        sys.exit(1)
    if args.dry_run and not repo:
        repo = "/dev/null/placeholder"  # dry-run only

    from concordcoder.pipeline import run_single_task
    from concordcoder.schemas import OutputFormat, SingleTaskSpec
    from concordcoder.llm_client import get_llm_client

    rows: list[dict] = []
    for iid in ids:
        inst = _load_instance(iid)
        task = (inst.get("problem_statement") or "")[:20000]
        target_file = _first_path_from_patch(inst.get("patch") or "")
        spec = SingleTaskSpec(
            task_id=iid,
            task=task,
            no_align=bool(args.no_align),
            full_align=not bool(args.no_align),
            output_format=OutputFormat.JSON,
            use_anchor=False,
            with_probe=False,
            target_file=target_file,
            target_symbol=None,
            answers={},
        )
        if args.dry_run:
            rows.append(
                {
                    "instance_id": iid,
                    "spec_task_len": len(spec.task),
                    "target_file": target_file,
                    "dry_run": True,
                }
            )
            continue
        try:
            llm = get_llm_client()
        except EnvironmentError as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
            sys.exit(1)
        st = run_single_task(Path(repo).resolve(), spec, llm_client=llm, fast_extract=False)
        rows.append(
            {
                "instance_id": iid,
                "target_file": target_file,
                "code_plan_len": len(st.generation.code_plan or ""),
                "warnings_n": len(st.generation.warnings),
                "n_parsed_files": len(st.parsed_files),
                "probe": st.probe,
            }
        )

    out_obj = {
        "driver": "swe_bench_batch",
        "track": "parallel_to_mini_eval",
        "rows": rows,
    }
    text = json.dumps(out_obj, ensure_ascii=False, indent=2)
    if args.out_row:
        args.out_row.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
