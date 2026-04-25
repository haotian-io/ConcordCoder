#!/usr/bin/env python3
"""
SWE-bench Lite → ``run_single_task`` 的最小批处理（RQ1 主轨之一，与 ``mini_eval.py`` 并列）。

数据集与背景：

- 默认从 Hugging Face 加载 **SWE-bench/SWE-bench_Lite**（test 切分，300 条）；与官方说明
  https://www.swebench.com/lite.html 及数据集卡
  https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite 一致。
- 可用环境变量 ``CONCORD_SWE_DATASET`` / ``CONCORD_SWE_SPLIT`` 覆盖（例如回退
  ``princeton-nlp/SWE-bench_Lite``）。
- **不**实现官方 Docker harness（``swebench.harness.run_evaluation``）；不自动 ``git clone`` /
  ``git checkout``。评测者需在每条 instance 的 ``base_commit`` 上准备好本地克隆，并设
  ``CONCORD_SWE_REPO_ROOT`` 指向该根目录。官方 Resolved\% 需另行生成 predictions JSONL 后跑 harness
  （见 ``experiments/DEMO_SWE_BENCH_LITE.md`` 附录说明）。

环境：

- ``CONCORD_SWE_REPO_ROOT``：已检出到**对应 instance 的 base_commit** 的仓库绝对路径。一次非 dry-run
  运行只处理**一条** instance（每条 base_commit 不同，需换检出后再跑）。
- ``OPENAI_API_KEY`` / ``ANTHROPIC_API_KEY`` 等同 ``concord once``。

依赖（可选，与 ``[eval]`` 一致）::

    pip install "datasets>=2.16"   # 以及 concord 的 [openai] 等

典型用法（先 ``git checkout <base_commit>``，见 ``--print-meta`` 输出）::

  export CONCORD_SWE_REPO_ROOT=/abs/path/to/checkout
  python3 scripts/swe_bench_batch.py --instance-id "django__django-10914" --out-row run.json

打印单条 instance 的 clone/checkout 提示（不访问 API）::

  python3 scripts/swe_bench_batch.py --instance-id "django__django-10914" --print-meta

与 ``experiments/swe_tiny_config.yaml``：可写 ``dataset`` / ``split`` / ``instance_ids``；``--config``
指向该文件。非 dry-run 多 id 会报错（设计上每次一条）。

干跑::

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

_DEFAULT_HF_DATASET = "SWE-bench/SWE-bench_Lite"
_DEFAULT_SPLIT = "test"


def _default_dataset() -> str:
    return os.environ.get("CONCORD_SWE_DATASET", _DEFAULT_HF_DATASET).strip()


def _default_split() -> str:
    return os.environ.get("CONCORD_SWE_SPLIT", _DEFAULT_SPLIT).strip()


def _load_yaml_config(path: Path | None) -> dict:
    if not path:
        return {}
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _dataset_split_from_merged(file_cfg: dict) -> tuple[str, str]:
    ds = (file_cfg.get("dataset") or "").strip() or _default_dataset()
    sp = (file_cfg.get("split") or "").strip() or _default_split()
    return ds, sp


def _load_rows(dataset: str, split: str):
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise SystemExit(
            "Install optional: pip install 'datasets>=2.16' "
            "(e.g. pip install -e '.[eval]')"
        ) from e
    return load_dataset(dataset, split=split)


def _load_instance(instance_id: str, dataset: str, split: str) -> dict:
    ds = _load_rows(dataset, split)
    for row in ds:
        if row.get("instance_id") == instance_id:
            return dict(row)
    raise SystemExit(
        f"instance_id not found in {dataset!r} split={split!r}: {instance_id!r}"
    )


def _first_path_from_patch(patch: str) -> str | None:
    if not patch:
        return None
    for line in patch.splitlines():
        m = re.match(r"^---\s+a/(\S+)", line)
        if m:
            return m.group(1)
    return None


def _instance_ids_from_config(data: dict) -> list[str]:
    raw = data.get("instance_ids") or []
    return [str(x) for x in raw]


def _print_meta_block(inst: dict) -> dict:
    repo = inst.get("repo") or ""
    bc = inst.get("base_commit") or ""
    iid = inst.get("instance_id") or ""
    url = f"https://github.com/{repo}" if repo else ""
    lines = [
        f"instance_id: {iid}",
        f"repo: {repo}",
        f"base_commit: {bc}",
        "",
        "# Suggested checkout (run in empty parent dir; then export CONCORD_SWE_REPO_ROOT to the clone root):",
    ]
    if repo and bc:
        name = repo.split("/")[-1] if "/" in repo else repo
        lines.append(f"git clone {url}.git {name} && cd {name} && git checkout {bc}")
    meta = {
        "instance_id": iid,
        "repo": repo,
        "base_commit": bc,
        "github_url": url,
        "suggested_shell": lines[-1] if len(lines) > 5 else None,
    }
    return {"meta": meta, "lines": lines}


def main() -> None:
    p = argparse.ArgumentParser(description="SWE-bench Lite row → run_single_task (MVF).")
    p.add_argument(
        "--instance-id",
        help="A single instance_id from SWE-bench Lite (e.g. owner__repo-nnnn).",
    )
    p.add_argument(
        "--config",
        type=Path,
        help="YAML with optional dataset, split, instance_ids (see experiments/swe_tiny_config.yaml).",
    )
    p.add_argument(
        "--list-ids",
        type=int,
        metavar="N",
        help="Print first N instance_id from the configured dataset split and exit.",
    )
    p.add_argument(
        "--print-meta",
        action="store_true",
        help="Print repo, base_commit, and suggested git clone/checkout for each requested instance_id (no LLM).",
    )
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

    file_cfg = _load_yaml_config(args.config)
    dataset, split = _dataset_split_from_merged(file_cfg)

    if args.list_ids is not None:
        try:
            ds = _load_rows(dataset, split)
        except SystemExit:
            raise
        except Exception as e:
            print(json.dumps({"error": str(e), "dataset": dataset, "split": split}))
            raise SystemExit(1) from e
        n = max(0, int(args.list_ids))
        ids = [ds[i]["instance_id"] for i in range(min(n, len(ds)))]
        print(
            json.dumps(
                {"dataset": dataset, "split": split, "instance_ids": ids},
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    ids: list[str] = []
    if args.instance_id:
        ids.append(args.instance_id)
    if args.config:
        ids.extend(_instance_ids_from_config(file_cfg))
    if not ids:
        p.error(
            "Provide --instance-id and/or --config with non-empty instance_ids, "
            "or use --list-ids"
        )

    if args.print_meta:
        blocks = []
        for iid in ids:
            inst = _load_instance(iid, dataset, split)
            blk = _print_meta_block(inst)
            blocks.append(blk["meta"])
            print("\n".join(blk["lines"]))
            print()
        print(json.dumps({"dataset": dataset, "split": split, "instances": blocks}, indent=2))
        return

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
        inst = _load_instance(iid, dataset, split)
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
                    "dataset": dataset,
                    "split": split,
                    "repo": inst.get("repo"),
                    "base_commit": inst.get("base_commit"),
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
                "dataset": dataset,
                "split": split,
                "repo": inst.get("repo"),
                "base_commit": inst.get("base_commit"),
                "target_file": target_file,
                "code_plan_len": len(st.generation.code_plan or ""),
                "warnings_n": len(st.generation.warnings),
                "n_parsed_files": len(st.parsed_files),
                "probe": st.probe,
            }
        )

    out_obj = {
        "driver": "swe_bench_batch",
        "dataset": dataset,
        "split": split,
        "track": "swe_bench_lite",
        "rows": rows,
    }
    text = json.dumps(out_obj, ensure_ascii=False, indent=2)
    if args.out_row:
        args.out_row.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
