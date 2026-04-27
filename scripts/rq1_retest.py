#!/usr/bin/env python3
"""重测3个失败模型，带详细日志输出"""
import os, sys, json, time, concurrent.futures, re
from pathlib import Path
from typing import Optional

sys.path.insert(0, "/home/liuhaotian/Jap/ConcordCoder/Code/src")

API_KEY = 'sk-EKztVaWERPFH6c8ftI2WDO6ajGYB1ekg6Tc42nExMC83vzs7'
BASE_URL = 'https://api.bltcy.ai/v1'
MODELS = ["gemini-3.1-pro-preview", "deepseek-v4-flash", "deepseek-v4-pro"]
INSTANCE_ID = "astropy__astropy-12907"
REPO_ROOT = "/home/liuhaotian/Jap/ConcordCoder/astropy"


def run_single_model(model_name: str) -> dict:
    """对单个模型运行测试，并捕获原始LLM输出"""
    from concordcoder.llm_client import LLMClient
    from concordcoder.pipeline import run_single_task
    from concordcoder.schemas import OutputFormat, SingleTaskSpec

    print(f"[{model_name}] 开始重测...", flush=True)

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

    # 创建LLM客户端
    llm = LLMClient(backend="openai", model=model_name, api_key=API_KEY, base_url=BASE_URL)

    # 先测试API连通性
    print(f"[{model_name}] 测试API连通性...", flush=True)
    try:
        test_reply = llm.chat([{"role": "user", "content": "Reply with OK"}], system="Reply with one word.")
        print(f"[{model_name}] API连通: {test_reply[:100]}", flush=True)
    except Exception as e:
        return {"model": model_name, "error": f"API连通失败: {e}"}

    iid = inst["instance_id"]
    task = (inst.get("problem_statement") or "")[:20000]

    def first_path_from_patch(patch):
        if not patch: return None
        for line in patch.splitlines():
            m = re.match(r"^---\s+a/(\S+)", line)
            if m: return m.group(1)
        return None

    def all_paths_from_patch(patch):
        paths = []
        for line in (patch or "").splitlines():
            m = re.match(r"^\+\+\+\s+b/(\S+)", line)
            if m: paths.append(m.group(1))
        return list(dict.fromkeys(paths))

    target_file = first_path_from_patch(inst.get("patch") or "")
    target_files_gold = all_paths_from_patch(inst.get("patch") or "")

    # 运行ConcordCoder管线
    spec = SingleTaskSpec(
        task_id=iid, task=task,
        no_align=False, full_align=True,
        output_format=OutputFormat.UNIFIED_DIFF,
        use_anchor=False, with_probe=False,
        target_file=target_file, target_symbol=None, answers={},
    )

    t0 = time.time()
    st = run_single_task(Path(REPO_ROOT), spec, llm_client=llm, fast_extract=False)
    elapsed = time.time() - t0

    # 提取关键信息
    pred_paths = []
    for f in st.parsed_files or []:
        if getattr(f, "path", ""):
            pred_paths.append(f.path)
    pred_paths.extend(st.generation.changed_files or [])

    diff_text = st.generation.unified_diff_text or ""
    code_plan = st.generation.code_plan or ""

    # 详细日志
    print(f"[{model_name}] 管线完成! elapsed={elapsed:.1f}s", flush=True)
    print(f"[{model_name}] unified_diff_text长度: {len(diff_text)}", flush=True)
    print(f"[{model_name}] code_plan长度: {len(code_plan)}", flush=True)
    print(f"[{model_name}] predicted_files: {pred_paths}", flush=True)
    print(f"[{model_name}] target_files_gold: {target_files_gold}", flush=True)

    if diff_text:
        print(f"[{model_name}] diff前200字符: {diff_text[:200]}", flush=True)
    if code_plan and not diff_text:
        print(f"[{model_name}] code_plan前500字符: {code_plan[:500]}", flush=True)

    # FHR
    def norm_relpath(p):
        p = (p or "").replace("\\", "/").strip()
        if p in ("/dev/null", "dev/null"): return ""
        for prefix in ("a/", "b/"):
            if p.startswith(prefix) and len(p) > 2 and p[2:3] not in ("/",): p = p[2:]
        return p.lstrip("./")

    gs = {norm_relpath(x) for x in target_files_gold if x and norm_relpath(x)}
    fhr = sum(1 for p in pred_paths if norm_relpath(p) in gs) / len(gs) if gs else 0.0

    result = {
        "model": model_name,
        "instance_id": iid,
        "file_hit_rate": round(fhr, 4),
        "predicted_files": pred_paths,
        "target_files_gold": target_files_gold,
        "unified_diff_len": len(diff_text),
        "code_plan_len": len(code_plan),
        "diff_preview": diff_text[:500] if diff_text else "",
        "code_plan_preview": code_plan[:500] if (code_plan and not diff_text) else "",
        "warnings_n": len(st.generation.warnings),
        "n_constraints": len(st.generation.constraint_compliance),
        "constraint_compliance": st.generation.constraint_compliance,
        "elapsed_s": round(elapsed, 2),
        "alignment_turns": len(st.alignment_turn_log),
        "cost": st.cost.model_dump(mode="json"),
    }

    print(f"[{model_name}] FHR={fhr:.2f}, 完成!", flush=True)
    return result


def main():
    print("=" * 60, flush=True)
    print("RQ1 重测 - 3个失败模型并发", flush=True)
    print("=" * 60, flush=True)

    os.environ["CONCORD_SWE_REPO_ROOT"] = REPO_ROOT
    t0 = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(run_single_model, m): m for m in MODELS}
        results = []
        for future in concurrent.futures.as_completed(futures):
            model = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"[{model}] 异常: {e}", flush=True)
                results.append({"model": model, "error": str(e)})

    total = time.time() - t0

    print(f"\n{'='*60}", flush=True)
    print(f"重测结果 (总耗时: {total:.1f}s)", flush=True)
    print("=" * 60, flush=True)
    for r in results:
        m = r.get("model", "?")
        fhr = r.get("file_hit_rate", "?")
        el = r.get("elapsed_s", "?")
        dl = r.get("unified_diff_len", "?")
        err = r.get("error", "")
        pf = r.get("predicted_files", [])
        if err:
            print(f"  {m:30s} | ERROR: {err}", flush=True)
        else:
            print(f"  {m:30s} | FHR={fhr} | elapsed={el}s | diff={dl} | pred_files={pf}", flush=True)

    out_dir = Path("/home/liuhaotian/Jap/ConcordCoder/Code/results/rq1_concurrent")
    out_file = out_dir / f"{INSTANCE_ID.replace('/', '_')}_retest.json"
    out_file.write_text(json.dumps({
        "instance_id": INSTANCE_ID,
        "models": MODELS,
        "total_time_s": round(total, 2),
        "results": results
    }, ensure_ascii=False, indent=2))
    print(f"\n结果已保存: {out_file}", flush=True)


if __name__ == "__main__":
    main()
