# SWE-bench Lite demo（ConcordCoder RQ1）

本 demo 与论文 **RQ1** 主轨一致：在 [SWE-bench Lite](https://www.swebench.com/lite.html) 的公开实例上，用 [`scripts/swe_bench_batch.py`](../scripts/swe_bench_batch.py) 驱动 [`run_single_task`](../src/concordcoder/pipeline.py)。**不**包含官方 Docker harness 的 Resolved% 自动评测；若需 leaderboard 口径，见下文「官方 harness（可选）」。

## 前置条件

- Python 3.10+，在 `Code/` 根目录：`pip install -e ".[eval,openai]"`（或 `anthropic`）。
- `git`、可写磁盘（每条 instance 需单独克隆上游仓库）。
- `OPENAI_API_KEY`（或 `ANTHROPIC_API_KEY`）；可选 `OPENAI_BASE_URL`。
- 默认数据集：`SWE-bench/SWE-bench_Lite`（[HF](https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite)）。若需旧镜像：`export CONCORD_SWE_DATASET=princeton-nlp/SWE-bench_Lite`。

## 固定 5 条子集

见 [`swe_tiny_config.yaml`](swe_tiny_config.yaml) 中 `instance_ids`。任选**一条**按下列步骤跑通。

## 逐步复现（单条 instance）

1. **查看元数据与建议 checkout**

   ```bash
   cd /path/to/ConcordCoder/Code
   python3 scripts/swe_bench_batch.py --instance-id "astropy__astropy-12907" --print-meta
   ```

   按输出在临时目录执行 `git clone` + `git checkout <base_commit>`（或对你已有克隆 checkout 到该 commit）。

2. **指向克隆根目录**

   ```bash
   export CONCORD_SWE_REPO_ROOT=/abs/path/to/astropy
   ```

3. **干跑（不调 LLM，校验 spec）**

   ```bash
   python3 scripts/swe_bench_batch.py --instance-id "astropy__astropy-12907" --dry-run
   ```

4. **真跑（调 LLM，写 JSON）**

   ```bash
   python3 scripts/swe_bench_batch.py --instance-id "astropy__astropy-12907" --out-row /tmp/swe_lite_row.json
   ```

5. **下一条**：对下一个 `instance_id` 重复步骤 1–4（**每条**对应不同 `base_commit`，必须重新 checkout 或单独克隆）。

## 论文中可报告的 MVP 指标

当前 `swe_bench_batch` 写出 JSON 含：`code_plan_len`、`warnings_n`、`n_parsed_files`、`probe`（若启用路径）、以及 `repo` / `base_commit` / `instance_id`。**不**等同于 SWE-bench 官方 **% Resolved**（需补丁级 predictions + `run_evaluation`）。

## 官方 harness（可选 / 附录）

要在 [SWE-bench](https://github.com/swe-bench/SWE-bench) 上得到与 leaderboard 一致的 Resolved 指标，需要：

1. 按官方文档安装 `swebench` 与 Docker（资源要求高，见上游 README）。
2. 将系统生成的补丁整理为 **predictions** JSONL（每行含 `instance_id` 与 `model_patch` 等字段，格式以 `swebench.harness.run_evaluation --help` 为准）。
3. 运行 `python -m swebench.harness.run_evaluation --dataset_name SWE-bench/SWE-bench_Lite ...`。

Concord 当前主路径产出为 **pipeline JSON / code_plan**，与官方 `model_patch` 字段对齐需额外转换脚本；建议在论文中如实写为 *future work* 或附录脚本占位。详见仓库内 [`SWE_HARNESS_APPENDIX.md`](SWE_HARNESS_APPENDIX.md)。

## 列出数据集中前 N 个 id

```bash
python3 scripts/swe_bench_batch.py --list-ids 10
```

可选：加 `--config experiments/swe_tiny_config.yaml` 时，`--list-ids` 使用 yaml 中的 `dataset` / `split` 拉取数据，**仍返回该 split 中按行号顺序的前 N 个** `instance_id`（不是 yaml 里 `instance_ids` 列表的子集）。
