#!/usr/bin/env python3
"""
RQ1 并发测试脚本 - 同时测试5个模型
"""
import os
import sys
import json
import time
import concurrent.futures
from pathlib import Path
from typing import Optional

_CODE_ROOT = Path("/home/liuhaotian/Jap/ConcordCoder/Code")
if str(_CODE_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_CODE_ROOT / "src"))

# 配置
API_KEY = 'sk-EKztVaWERPFH6c8ftI2WDO6ajGYB1ekg6Tc42nExMC83vzs7'
BASE_URL = 'https://api.bltcy.ai/v1'
MODELS = ["gpt-5.5", "deepseek-v4-flash", "deepseek-v4-pro", "gemini-3.1-pro-preview", "glm-5.1"]
INSTANCE_ID = "astropy__astropy-12907"
REPO_ROOT = "/home/liuhaotian/Jap/ConcordCoder/astropy"


def run_single_model(model_name: str) -> dict:
    """对单个模型运行测试"""
    from concordcoder.llm_client import LLMClient
    from concordcoder.pipeline import run_single_task
    from concordcoder.schemas import OutputFormat, SingleTaskSpec

    print(f"[{model_name}] 开始测试...")

    # 加载数据
    from datasets import load_dataset
    ds = load_dataset("SWE-bench/SWE-bench_Lite", split="test")
    inst = None
    for row in ds:
        if row["instance_id"] == INSTANCE_ID:
            inst = dict(row)
            break

    if not inst:
        return {"model": model_name, "error": f"Instance {INSTANCE_ID} not found"}

    # 创建LLM客户端（直接传入参数，避免并发环境变量竞争）
    llm = LLMClient(backend="openai", model=model_name, api_key=API_KEY, base_url=BASE_URL)

    iid = inst["instance_id"]
    task = (inst.get("problem_statement") or "")[:20000]

    import re
    def first_path_from_patch(patch: str) -> Optional[str]:
        if not patch:
            return None
        for line in patch.splitlines():
            m = re.match(r"^---\s+a/(\S+)", line)
            if m:
                return m.group(1)
        return None

    def all_paths_from_patch(patch: str) -> list[str]:
        paths = []
        for line in (patch or "").splitlines():
            m = re.match(r"^\+\+\+\s+b/(\S+)", line)
            if m:
                paths.append(m.group(1))
        return list(dict.fromkeys(paths))

    def norm_relpath(p: str) -> str:
        p = (p or "").replace("\\", "/").strip()
        if p in ("/dev/null", "dev/null"):
            return ""
        for prefix in ("a/", "b/"):
            if p.startswith(prefix) and len(p) > 2 and p[2:3] not in ("/",):
                p = p[2:]
        return p.lstrip("./")

    def file_hit_rate(pred: list[str], gold: list[str]) -> float:
        gs = {norm_relpath(x) for x in gold if x and norm_relpath(x)}
        if not gs:
            return 0.0
        hit = sum(1 for p in pred if norm_relpath(p) in gs)
        return hit / len(gs)

    target_file = first_path_from_patch(inst.get("patch") or "")
    target_files_gold = all_paths_from_patch(inst.get("patch") or "")

    # ConcordCoder
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
    st = run_single_task(Path(REPO_ROOT), spec, llm_client=llm, fast_extract=False)
    elapsed = time.time() - t0

    # 提取预测的文件路径
    pred_paths = []
    for f in st.parsed_files or []:
        if getattr(f, "path", ""):
            pred_paths.append(f.path)
    pred_paths.extend(st.generation.changed_files or [])

    fhr = file_hit_rate(pred_paths, target_files_gold)

    result = {
        "model": model_name,
        "instance_id": iid,
        "repo": inst.get("repo"),
        "target_file_gold": target_file,
        "target_files_gold": target_files_gold,
        "predicted_files": pred_paths,
        "file_hit_rate": round(fhr, 4),
        "unified_diff_len": len(st.generation.unified_diff_text or ""),
        "warnings_n": len(st.generation.warnings),
        "n_constraints": len(st.generation.constraint_compliance),
        "constraint_compliance": st.generation.constraint_compliance,
        "elapsed_s": round(elapsed, 2),
        "alignment_turns": len(st.alignment_turn_log),
        "cost": st.cost.model_dump(mode="json"),
    }

    print(f"[{model_name}] 完成! FHR={fhr:.2f}, elapsed={elapsed:.1f}s")
    return result


def main():
    print(f"=" * 60)
    print(f"RQ1 并发测试 - 5个模型同时测试")
    print(f"=" * 60)
    print(f"Instance: {INSTANCE_ID}")
    print(f"Repo: {REPO_ROOT}")
    print(f"Models: {MODELS}")
    print()

    os.environ["CONCORD_SWE_REPO_ROOT"] = REPO_ROOT

    t0 = time.time()

    # 并发执行所有模型
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(run_single_model, m): m for m in MODELS}
        results = []
        for future in concurrent.futures.as_completed(futures):
            model = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"[{model}] 错误: {e}")
                results.append({"model": model, "error": str(e)})

    total_time = time.time() - t0

    # 汇总结果
    print()
    print(f"=" * 60)
    print(f"测试结果汇总 (总耗时: {total_time:.1f}s)")
    print(f"=" * 60)

    for r in results:
        model = r.get("model", "?")
        fhr = r.get("file_hit_rate", "?")
        elapsed = r.get("elapsed_s", "?")
        diff_len = r.get("unified_diff_len", "?")
        warnings = r.get("warnings_n", "?")
        error = r.get("error", "")
        status = f"✅ FHR={fhr}" if "error" not in r else f"❌ {error}"
        print(f"  {model:30s} | {status} | elapsed={elapsed}s | diff={diff_len}")

    # 保存结果
    out_dir = Path("results/rq1_concurrent")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{INSTANCE_ID.replace('/', '_')}_multi.json"
    out_file.write_text(json.dumps({
        "instance_id": INSTANCE_ID,
        "models": MODELS,
        "total_time_s": round(total_time, 2),
        "results": results
    }, ensure_ascii=False, indent=2))

    print(f"\n结果已保存: {out_file}")


if __name__ == "__main__":
    main()
