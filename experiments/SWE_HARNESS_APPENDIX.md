# SWE-bench 官方 harness 与 Concord 产出对齐（附录占位）

## 目标

[SWE-bench 评测 harness](https://github.com/swe-bench/SWE-bench) 期望每条预测为带 `instance_id` 的补丁（`model_patch` 等，以 `run_evaluation --help` 为准）。Leaderboard 上的 **% Resolved** 来自该流水线 + Docker 内执行测试。

## 当前 Concord 路径

- [`swe_bench_batch.py`](../scripts/swe_bench_batch.py) 调用 `run_single_task`，JSON 行里主要为 **过程型指标**（如 `code_plan_len`、解析文件数等），以及（若 pipeline 配置为输出 diff）工作区内的 **unified diff** 产物；**未**自动写成官方 predictions JSONL。

## 对接步骤（实现时 checklist）

1. 从 `run_single_task` 结果或输出目录读取 `unified_diff_text` / `diff.patch`。
2. 映射为每条 `instance_id` 一行 JSON（字段名与 SWE-bench 版本一致）。
3. 在 x86_64 + Docker + 足够磁盘的环境下运行：

   ```text
   python -m swebench.harness.run_evaluation \
     --dataset_name SWE-bench/SWE-bench_Lite \
     --predictions_path <predictions.jsonl> \
     --max_workers <n> \
     --run_id concord-demo
   ```

4. 将 `evaluation_results` 中的 Resolved 数字写入论文表，并与 MVP 管道指标区分汇报。

## 风险提示

补丁格式不完整、路径前缀或换行与 gold 不一致会导致 harness 判失败。建议先在单条 instance 上用 `--predictions_path gold` 验证环境，再接入模型补丁。
