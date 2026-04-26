#!/usr/bin/env python3
"""
RQ1 Experiment Runner — Local SWE-bench Lite

读取本地 Parquet 格式的 SWE-bench Lite 数据集（无需联网），
对指定 instance_id 分别运行：
  - ConcordCoder 完整管线（with alignment）
  - Direct Baseline（无对齐，单轮生成）
并输出结构化 JSON 结果，用于 RQ1 对比分析。

用法：
  # 打印 meta（无需 LLM key）
  python3 scripts/rq1_runner.py --instance-id astropy__astropy-12907 --print-meta

  # dry-run（检查数据读取 + spec 构建）
  python3 scripts/rq1_runner.py --instance-id astropy__astropy-12907 --dry-run

  # 跑单条（需 checkout 仓库 + API key）
  export CONCORD_SWE_REPO_ROOT=/path/to/astropy
  python3 scripts/rq1_runner.py --instance-id astropy__astropy-12907 --out-dir results/rq1/

  # 跑 demo 5 条（需逐条 checkout）
  python3 scripts/rq1_runner.py --config experiments/swe_tiny_config.yaml --dry-run

环境变量：
  CONCORD_SWE_REPO_ROOT   已 checkout 到 base_commit 的仓库根路径
  OPENAI_API_KEY          OpenAI key（优先）
  ANTHROPIC_API_KEY       Anthropic key（备用）
  SWE_BENCH_LOCAL_DIR     本地数据集目录（默认: ../SWE-bench_Lite/data）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

_CODE_ROOT = Path(__file__).resolve().parent.parent
if str(_CODE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_CODE_ROOT / "src"))

# ── 默认路径 ────────────────────────────────────────────────────────────────
_DEFAULT_LOCAL_DIR = _CODE_ROOT.parent / "SWE-bench_Lite" / "data"
_DEFAULT_SPLIT = "test"


# ── 数据加载 ─────────────────────────────────────────────────────────────────

def _local_parquet_path(split: str = _DEFAULT_SPLIT) -> Path:
    local_dir = Path(os.environ.get("SWE_BENCH_LOCAL_DIR", str(_DEFAULT_LOCAL_DIR)))
    p = local_dir / f"{split}-00000-of-00001.parquet"
    if not p.exists():
        raise FileNotFoundError(
            f"本地数据集未找到: {p}\n"
            f"请设 SWE_BENCH_LOCAL_DIR 或确认数据已下载到 {local_dir}"
        )
    return p


def _load_all_rows(split: str = _DEFAULT_SPLIT) -> list[dict]:
    """优先读本地 Parquet，失败则回退到 HF datasets。"""
    try:
        import pandas as pd
        p = _local_parquet_path(split)
        df = pd.read_parquet(p)
        return df.to_dict(orient="records")
    except FileNotFoundError:
        print("[WARN] 本地 Parquet 未找到，尝试 Hugging Face 在线加载...", file=sys.stderr)
        from datasets import load_dataset
        ds = load_dataset("SWE-bench/SWE-bench_Lite", split=split)
        return [dict(r) for r in ds]


def _load_instance(instance_id: str, split: str = _DEFAULT_SPLIT) -> dict:
    rows = _load_all_rows(split)
    for row in rows:
        if row.get("instance_id") == instance_id:
            return row
    ids = [r["instance_id"] for r in rows[:10]]
    raise SystemExit(
        f"instance_id not found: {instance_id!r}\n示例前10: {ids}"
    )


def _list_ids(n: int, split: str = _DEFAULT_SPLIT) -> list[str]:
    rows = _load_all_rows(split)
    return [r["instance_id"] for r in rows[:n]]


# ── RQ1 path metrics ───────────────────────────────────────────────────────

def _norm_relpath(p: str) -> str:
    """Normalize ``a/foo``, ``b/foo`` → ``foo`` for SWE file matching."""
    p = (p or "").replace("\\", "/").strip()
    if p in ("/dev/null", "dev/null"):
        return ""
    for prefix in ("a/", "b/"):
        if p.startswith(prefix) and len(p) > 2 and p[2:3] not in ("/",):
            p = p[2:]
    return p.lstrip("./")


def _predicted_paths_from_task(st) -> list[str]:
    """``parsed_files`` (json_files) + ``changed_files`` + diff heuristics."""
    from concordcoder.generation.json_output import paths_from_unified_diff

    out: list[str] = []
    for f in st.parsed_files or []:
        if getattr(f, "path", ""):
            out.append(f.path)
    out.extend(st.generation.changed_files or [])
    u = (st.unified_diff or st.generation.unified_diff_text or "").strip()
    if u:
        out.extend(paths_from_unified_diff(u))
    raw = (st.generation.code_plan or "").strip()
    if not out and raw:
        out.extend(paths_from_unified_diff(raw))
    return list(dict.fromkeys([p for p in out if p]))[:50]


def _file_hit_rate(pred: list[str], gold: list[str]) -> float:
    gs = {_norm_relpath(x) for x in gold if x and _norm_relpath(x)}
    if not gs:
        return 0.0
    hit = sum(1 for p in pred if _norm_relpath(p) in gs)
    return hit / len(gs)


# ── Patch 解析 ───────────────────────────────────────────────────────────────

def _first_path_from_patch(patch: str) -> str | None:
    if not patch:
        return None
    for line in patch.splitlines():
        m = re.match(r"^---\s+a/(\S+)", line)
        if m:
            return m.group(1)
    return None


def _all_paths_from_patch(patch: str) -> list[str]:
    paths = []
    for line in (patch or "").splitlines():
        m = re.match(r"^\+\+\+\s+b/(\S+)", line)
        if m:
            paths.append(m.group(1))
    return list(dict.fromkeys(paths))


# ── Meta 打印 ────────────────────────────────────────────────────────────────

def _print_meta(inst: dict) -> None:
    repo = inst.get("repo", "")
    bc = inst.get("base_commit", "")
    iid = inst.get("instance_id", "")
    target_files = _all_paths_from_patch(inst.get("patch", ""))
    print(f"instance_id : {iid}")
    print(f"repo        : {repo}")
    print(f"base_commit : {bc}")
    print(f"target_files: {target_files}")
    print(f"problem_len : {len(inst.get('problem_statement', ''))}")
    if repo and bc:
        name = repo.split("/")[-1]
        print("\n# Checkout command:")
        print(f"git clone https://github.com/{repo}.git {name} && cd {name} && git checkout {bc}")
        print(f"export CONCORD_SWE_REPO_ROOT=$(pwd)/{name}")


# ── YAML config ──────────────────────────────────────────────────────────────

def _load_yaml_ids(config: Path) -> list[str]:
    try:
        import yaml
        raw = yaml.safe_load(config.read_text())
        return [str(x) for x in (raw or {}).get("instance_ids", [])]
    except Exception as e:
        print(f"[WARN] YAML 加载失败: {e}", file=sys.stderr)
        return []


# ── 运行函数 ─────────────────────────────────────────────────────────────────

def run_concordcoder(inst: dict, repo_root: Path, llm) -> dict:
    """运行 ConcordCoder 完整管线（with alignment）。"""
    from concordcoder.pipeline import run_single_task
    from concordcoder.schemas import OutputFormat, SingleTaskSpec

    iid = inst["instance_id"]
    task = (inst.get("problem_statement") or "")[:20000]
    target_file = _first_path_from_patch(inst.get("patch") or "")

    spec = SingleTaskSpec(
        task_id=iid,
        task=task,
        no_align=False,
        full_align=True,
        output_format=OutputFormat.UNIFIED_DIFF,
        use_anchor=False,
        with_probe=False,
        target_file=target_file,
        target_symbol=None,
        answers={},
    )

    t0 = time.time()
    st = run_single_task(repo_root, spec, llm_client=llm, fast_extract=False)
    elapsed = time.time() - t0

    target_files_gold = _all_paths_from_patch(inst.get("patch") or "")
    pred_paths = _predicted_paths_from_task(st)
    file_hit_rate = _file_hit_rate(pred_paths, target_files_gold)

    return {
        "condition": "concordcoder",
        "instance_id": iid,
        "repo": inst.get("repo"),
        "base_commit": inst.get("base_commit"),
        "target_file_gold": target_file,
        "target_files_gold": target_files_gold,
        "predicted_files": pred_paths,
        "file_hit_rate": file_hit_rate,
        "n_predicted_paths": len(pred_paths),
        "code_plan_len": len(st.generation.code_plan or ""),
        "unified_diff_len": len(st.generation.unified_diff_text or ""),
        "warnings_n": len(st.generation.warnings),
        "warnings": st.generation.warnings,
        "n_constraints": len(st.generation.constraint_compliance),
        "constraint_compliance": st.generation.constraint_compliance,
        "n_parsed_files": len(st.parsed_files),
        "probe": st.probe,
        "elapsed_s": round(elapsed, 2),
        "alignment_turn_log_n": len(st.alignment_turn_log),
        "cost": st.cost.model_dump(mode="json"),
    }


def run_baseline(inst: dict, repo_root: Path, llm) -> dict:
    """运行 Direct Baseline（无对齐，跳过 Phase 2）。"""
    from concordcoder.pipeline import run_single_task
    from concordcoder.schemas import OutputFormat, SingleTaskSpec

    iid = inst["instance_id"]
    task = (inst.get("problem_statement") or "")[:20000]
    target_file = _first_path_from_patch(inst.get("patch") or "")

    spec = SingleTaskSpec(
        task_id=iid,
        task=task,
        no_align=True,
        full_align=False,
        output_format=OutputFormat.UNIFIED_DIFF,
        use_anchor=False,
        with_probe=False,
        target_file=target_file,
        target_symbol=None,
        answers={},
    )

    t0 = time.time()
    st = run_single_task(repo_root, spec, llm_client=llm, fast_extract=True)
    elapsed = time.time() - t0

    target_files_gold = _all_paths_from_patch(inst.get("patch") or "")
    pred_paths = _predicted_paths_from_task(st)
    file_hit_rate = _file_hit_rate(pred_paths, target_files_gold)

    return {
        "condition": "baseline_direct",
        "instance_id": iid,
        "repo": inst.get("repo"),
        "base_commit": inst.get("base_commit"),
        "target_file_gold": target_file,
        "target_files_gold": target_files_gold,
        "predicted_files": pred_paths,
        "file_hit_rate": file_hit_rate,
        "n_predicted_paths": len(pred_paths),
        "code_plan_len": len(st.generation.code_plan or ""),
        "unified_diff_len": len(st.generation.unified_diff_text or ""),
        "warnings_n": len(st.generation.warnings),
        "warnings": st.generation.warnings,
        "n_constraints": 0,
        "constraint_compliance": {},
        "n_parsed_files": len(st.parsed_files),
        "probe": {},
        "elapsed_s": round(elapsed, 2),
        "alignment_turn_log_n": len(st.alignment_turn_log),
        "cost": st.cost.model_dump(mode="json"),
    }


def run_baseline_posthoc(inst: dict, repo_root: Path, llm) -> dict:
    """Post-hoc style baseline with bounded corrective hints."""
    from concordcoder.pipeline import run_single_task
    from concordcoder.schemas import OutputFormat, SingleTaskSpec

    iid = inst["instance_id"]
    task = (inst.get("problem_statement") or "")[:20000]
    target_file = _first_path_from_patch(inst.get("patch") or "")
    posthoc_hint = (
        "Post-hoc feedback budget: if uncertain, preserve public API and avoid "
        "breaking tests; prefer minimal patch."
    )
    spec = SingleTaskSpec(
        task_id=iid,
        task=task,
        no_align=True,
        full_align=False,
        output_format=OutputFormat.UNIFIED_DIFF,
        use_anchor=False,
        with_probe=False,
        target_file=target_file,
        target_symbol=None,
        answers={"posthoc_feedback": posthoc_hint},
    )
    t0 = time.time()
    st = run_single_task(repo_root, spec, llm_client=llm, fast_extract=False)
    elapsed = time.time() - t0
    target_files_gold = _all_paths_from_patch(inst.get("patch") or "")
    pred_paths = _predicted_paths_from_task(st)
    file_hit_rate = _file_hit_rate(pred_paths, target_files_gold)
    return {
        "condition": "baseline_posthoc",
        "instance_id": iid,
        "repo": inst.get("repo"),
        "base_commit": inst.get("base_commit"),
        "target_file_gold": target_file,
        "target_files_gold": target_files_gold,
        "predicted_files": pred_paths,
        "file_hit_rate": file_hit_rate,
        "n_predicted_paths": len(pred_paths),
        "code_plan_len": len(st.generation.code_plan or ""),
        "unified_diff_len": len(st.generation.unified_diff_text or ""),
        "warnings_n": len(st.generation.warnings),
        "warnings": st.generation.warnings,
        "n_constraints": 0,
        "constraint_compliance": {},
        "n_parsed_files": len(st.parsed_files),
        "probe": {},
        "elapsed_s": round(elapsed, 2),
        "alignment_turn_log_n": len(st.alignment_turn_log),
        "cost": st.cost.model_dump(mode="json"),
    }


# ── 主函数 ───────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="RQ1 Runner: ConcordCoder vs Baseline on local SWE-bench Lite."
    )
    p.add_argument("--instance-id", help="单条 instance_id")
    p.add_argument("--config", type=Path, help="YAML config（含 instance_ids）")
    p.add_argument("--list-ids", type=int, metavar="N", help="列出前 N 个 instance_id 后退出")
    p.add_argument("--print-meta", action="store_true", help="打印 meta 信息（无需 LLM）")
    p.add_argument("--dry-run", action="store_true", help="只构建 spec，不调用 LLM")
    p.add_argument("--out-dir", type=Path, default=Path("results/rq1"), help="结果输出目录")
    p.add_argument("--conditions", default="concordcoder,baseline",
                   help="运行条件，逗号分隔: concordcoder,baseline,baseline_posthoc")
    p.add_argument("--split", default=_DEFAULT_SPLIT, help="数据集 split（默认: test）")
    args = p.parse_args()

    split = args.split
    conditions = [c.strip() for c in args.conditions.split(",")]
    fairness_budget = {
        "max_turns": int(os.environ.get("CONCORD_FAIR_MAX_TURNS", "3")),
        "max_prompt_tokens": int(os.environ.get("CONCORD_FAIR_MAX_PROMPT_TOKENS", "4000")),
        "max_completion_tokens": int(os.environ.get("CONCORD_FAIR_MAX_COMPLETION_TOKENS", "4000")),
        "max_wallclock_sec": int(os.environ.get("CONCORD_FAIR_MAX_WALLCLOCK_SEC", "300")),
    }

    if args.list_ids:
        ids = _list_ids(args.list_ids, split)
        print(json.dumps({"split": split, "instance_ids": ids}, ensure_ascii=False, indent=2))
        return

    # 收集 instance_ids
    ids: list[str] = []
    if args.instance_id:
        ids.append(args.instance_id)
    if args.config:
        ids.extend(_load_yaml_ids(args.config))
    if not ids:
        p.error("请指定 --instance-id 或 --config")

    # print-meta 模式
    if args.print_meta:
        for iid in ids:
            inst = _load_instance(iid, split)
            print("─" * 60)
            _print_meta(inst)
        return

    # dry-run 模式
    if args.dry_run:
        rows = []
        for iid in ids:
            inst = _load_instance(iid, split)
            target_file = _first_path_from_patch(inst.get("patch") or "")
            rows.append({
                "instance_id": iid,
                "repo": inst.get("repo"),
                "base_commit": inst.get("base_commit"),
                "target_file": target_file,
                "target_files_gold": _all_paths_from_patch(inst.get("patch") or ""),
                "problem_len": len(inst.get("problem_statement") or ""),
                "dry_run": True,
            })
        print(json.dumps({"status": "dry_run", "rows": rows}, ensure_ascii=False, indent=2))
        return

    # 检查环境
    repo_str = os.environ.get("CONCORD_SWE_REPO_ROOT", "").strip()
    if not repo_str:
        sys.exit(
            "请设置 CONCORD_SWE_REPO_ROOT 到已 checkout 的仓库根目录。\n"
            "先运行 --print-meta 获取 checkout 命令。"
        )
    repo_root = Path(repo_str).resolve()
    if not repo_root.is_dir():
        sys.exit(f"CONCORD_SWE_REPO_ROOT 不是有效目录: {repo_root}")

    if len(ids) > 1:
        sys.exit(
            "非 dry-run 模式每次只支持 1 个 instance_id（每条 base_commit 不同）。\n"
            "请循环逐条运行，每次 checkout 对应 commit。"
        )

    # 初始化 LLM
    from concordcoder.llm_client import get_llm_client
    try:
        llm = get_llm_client()
    except EnvironmentError as e:
        sys.exit(str(e))

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    iid = ids[0]
    inst = _load_instance(iid, split)
    results = []

    for cond in conditions:
        print(f"\n[RQ1] Running {cond} on {iid} ...")
        try:
            if cond == "concordcoder":
                row = run_concordcoder(inst, repo_root, llm)
            elif cond == "baseline" or cond == "baseline_direct":
                row = run_baseline(inst, repo_root, llm)
            elif cond == "baseline_posthoc":
                row = run_baseline_posthoc(inst, repo_root, llm)
            else:
                print(f"[WARN] 未知条件: {cond}", file=sys.stderr)
                continue
            row["fairness_budget"] = fairness_budget
            results.append(row)
            print(f"  ✅  elapsed={row['elapsed_s']}s  warnings={row['warnings_n']}  "
                  f"unified_diff_len={row['unified_diff_len']}")
        except Exception as e:
            print(f"  ❌  {cond} failed: {e}", file=sys.stderr)
            results.append({"condition": cond, "instance_id": iid, "error": str(e)})

    # 保存结果
    out_obj = {
        "driver": "rq1_runner",
        "split": split,
        "instance_id": iid,
        "conditions": conditions,
        "rows": results,
        "fairness_budget": fairness_budget,
    }
    safe_id = iid.replace("/", "_")
    out_file = out_dir / f"{safe_id}.json"
    out_file.write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[RQ1] 结果已保存: {out_file}")
    print(json.dumps(out_obj, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
