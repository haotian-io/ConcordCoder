#!/usr/bin/env python3
"""
RQ1 结果分析与可视化脚本

读取 rq1_runner.py 产出的 JSON 结果，生成：
  1. 汇总统计表（CSV + 打印）
  2. 对比柱状图（concordcoder vs baseline）
  3. 结果摘要 JSON（供论文 LaTeX 引用）

用法：
  python3 scripts/rq1_analyze.py --results-dir results/rq1/ --out-dir results/rq1/plots/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_CODE_ROOT = Path(__file__).resolve().parent.parent
if str(_CODE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_CODE_ROOT / "src"))


# ── 数据加载 ─────────────────────────────────────────────────────────────────

def load_results(results_dir: Path) -> list[dict]:
    rows = []
    for f in sorted(results_dir.glob("*.json")):
        try:
            obj = json.loads(f.read_text())
            for row in obj.get("rows", []):
                if "error" not in row:
                    rows.append(row)
        except Exception as e:
            print(f"[WARN] 跳过 {f.name}: {e}", file=sys.stderr)
    return rows


# ── 统计 ─────────────────────────────────────────────────────────────────────

def compute_stats(rows: list[dict]) -> dict:
    from collections import defaultdict
    import statistics

    by_cond: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cond[r.get("condition", "unknown")].append(r)

    stats = {}
    for cond, rlist in by_cond.items():
        def _avg(key):
            vals = [r[key] for r in rlist if key in r and r[key] is not None]
            return round(statistics.mean(vals), 4) if vals else None

        def _pct(key, threshold=0):
            vals = [r[key] for r in rlist if key in r and r[key] is not None]
            if not vals:
                return None
            return round(sum(1 for v in vals if v > threshold) / len(vals), 4)

        stats[cond] = {
            "n": len(rlist),
            "avg_elapsed_s": _avg("elapsed_s"),
            "avg_warnings_n": _avg("warnings_n"),
            "avg_code_plan_len": _avg("code_plan_len"),
            "avg_unified_diff_len": _avg("unified_diff_len"),
            "avg_file_hit_rate": _avg("file_hit_rate"),
            "pct_with_diff": _pct("unified_diff_len", 0),
            "avg_n_parsed_files": _avg("n_parsed_files"),
        }
    return stats


# ── 打印 ─────────────────────────────────────────────────────────────────────

def print_stats(stats: dict) -> None:
    print("\n" + "═" * 70)
    print("  RQ1 结果汇总")
    print("═" * 70)
    header = f"{'条件':<22} {'N':>4} {'平均耗时(s)':>12} {'文件命中率':>10} {'平均警告数':>10} {'有diff比例':>10}"
    print(header)
    print("─" * 70)
    for cond, s in stats.items():
        print(
            f"{cond:<22} {s['n']:>4} {str(s['avg_elapsed_s']):>12} "
            f"{str(s['avg_file_hit_rate']):>10} {str(s['avg_warnings_n']):>10} "
            f"{str(s['pct_with_diff']):>10}"
        )
    print("═" * 70 + "\n")


# ── 画图 ─────────────────────────────────────────────────────────────────────

def plot_comparison(rows: list[dict], out_dir: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("[WARN] matplotlib 未安装，跳过画图", file=sys.stderr)
        return

    out_dir.mkdir(parents=True, exist_ok=True)

    # 论文级配置
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "figure.dpi": 150,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    # 颜色
    COLORS = {
        "concordcoder": "#2563EB",    # 蓝
        "baseline_direct": "#DC2626", # 红
        "baseline": "#DC2626",
    }

    # 按条件分组
    from collections import defaultdict
    by_cond: dict[str, list[dict]] = defaultdict(list)
    by_iid: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        cond = r.get("condition", "unknown")
        iid = r.get("instance_id", "?")
        by_cond[cond].append(r)
        by_iid[iid][cond] = r

    # ── 图 1: 文件命中率对比（配对条形图）──────────────────────────────────
    conds = list(by_cond.keys())
    iids = sorted(by_iid.keys())
    n = len(iids)

    if n > 0 and len(conds) >= 1:
        fig, axes = plt.subplots(1, 2, figsize=(12, max(4, n * 0.5 + 1.5)))

        # 文件命中率
        ax = axes[0]
        for i, cond in enumerate(conds):
            vals = [by_iid[iid].get(cond, {}).get("file_hit_rate", 0) for iid in iids]
            x = [j + i * 0.35 for j in range(n)]
            color = COLORS.get(cond, f"C{i}")
            ax.barh(x, vals, height=0.32, color=color, alpha=0.85,
                    label=cond.replace("_", " ").title())
        ax.set_yticks([j + 0.17 for j in range(n)])
        ax.set_yticklabels([iid.split("__")[-1][:20] for iid in iids], fontsize=8)
        ax.set_xlabel("File Hit Rate")
        ax.set_title("(a) File Hit Rate by Condition")
        ax.set_xlim(0, 1.05)
        ax.legend(loc="lower right", fontsize=9)

        # 耗时对比
        ax = axes[1]
        for i, cond in enumerate(conds):
            vals = [by_iid[iid].get(cond, {}).get("elapsed_s", 0) for iid in iids]
            x = [j + i * 0.35 for j in range(n)]
            color = COLORS.get(cond, f"C{i}")
            ax.barh(x, vals, height=0.32, color=color, alpha=0.85,
                    label=cond.replace("_", " ").title())
        ax.set_yticks([j + 0.17 for j in range(n)])
        ax.set_yticklabels([iid.split("__")[-1][:20] for iid in iids], fontsize=8)
        ax.set_xlabel("Elapsed Time (s)")
        ax.set_title("(b) Latency by Condition")
        ax.legend(loc="lower right", fontsize=9)

        fig.suptitle("RQ1: ConcordCoder vs. Baseline on SWE-bench Lite", fontsize=13, y=1.02)
        fig.tight_layout()
        out = out_dir / "rq1_comparison.pdf"
        fig.savefig(out, bbox_inches="tight")
        out_png = out_dir / "rq1_comparison.png"
        fig.savefig(out_png, bbox_inches="tight", dpi=150)
        plt.close(fig)
        print(f"[PLOT] 已保存: {out} + {out_png}")

    # ── 图 2: 聚合指标对比条形图 ────────────────────────────────────────────
    metrics = [
        ("avg_file_hit_rate", "File Hit Rate (↑)"),
        ("avg_warnings_n", "Avg Warnings (↓)"),
        ("pct_with_diff", "Pct w/ Diff Output (↑)"),
    ]
    stats = compute_stats(rows)
    if len(stats) >= 1:
        fig, axes = plt.subplots(1, len(metrics), figsize=(4 * len(metrics), 4))
        if len(metrics) == 1:
            axes = [axes]
        for ax, (mkey, mlabel) in zip(axes, metrics):
            cond_list = list(stats.keys())
            vals = [stats[c].get(mkey, 0) or 0 for c in cond_list]
            colors = [COLORS.get(c, "gray") for c in cond_list]
            bars = ax.bar(range(len(cond_list)), vals, color=colors, alpha=0.85, width=0.5)
            ax.set_xticks(range(len(cond_list)))
            ax.set_xticklabels(
                [c.replace("_", "\n").title() for c in cond_list],
                fontsize=9
            )
            ax.set_title(mlabel, fontsize=10)
            for bar, val in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                        f"{val:.3f}", ha="center", va="bottom", fontsize=9)
        fig.suptitle("RQ1 Aggregate Metrics", fontsize=12)
        fig.tight_layout()
        out = out_dir / "rq1_aggregate.pdf"
        fig.savefig(out, bbox_inches="tight")
        out_png = out_dir / "rq1_aggregate.png"
        fig.savefig(out_png, bbox_inches="tight", dpi=150)
        plt.close(fig)
        print(f"[PLOT] 已保存: {out} + {out_png}")


# ── CSV 输出 ─────────────────────────────────────────────────────────────────

def save_csv(rows: list[dict], out_dir: Path) -> None:
    try:
        import csv
        out = out_dir / "rq1_rows.csv"
        keys = [
            "condition", "instance_id", "repo", "elapsed_s",
            "file_hit_rate", "warnings_n", "code_plan_len",
            "unified_diff_len", "n_parsed_files",
        ]
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        print(f"[CSV] 已保存: {out}")
    except Exception as e:
        print(f"[WARN] CSV 保存失败: {e}", file=sys.stderr)


# ── 主函数 ───────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="RQ1 结果分析与可视化")
    p.add_argument("--results-dir", type=Path, default=Path("results/rq1"),
                   help="rq1_runner.py 输出的 JSON 目录")
    p.add_argument("--out-dir", type=Path, default=Path("results/rq1/plots"),
                   help="图表输出目录")
    p.add_argument("--no-plot", action="store_true", help="跳过画图")
    args = p.parse_args()

    rows = load_results(args.results_dir)
    if not rows:
        print(f"[WARN] 未找到有效结果行于 {args.results_dir}", file=sys.stderr)
        print("请先运行: python3 scripts/rq1_runner.py --instance-id <id> ...")
        sys.exit(1)

    print(f"[INFO] 加载 {len(rows)} 条结果行")
    stats = compute_stats(rows)
    print_stats(stats)

    # 保存摘要
    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary_file = args.out_dir / "rq1_summary.json"
    summary_file.write_text(json.dumps({"stats": stats, "n_rows": len(rows)},
                                        ensure_ascii=False, indent=2))
    print(f"[JSON] 摘要已保存: {summary_file}")

    save_csv(rows, args.out_dir)

    if not args.no_plot:
        plot_comparison(rows, args.out_dir)


if __name__ == "__main__":
    main()
