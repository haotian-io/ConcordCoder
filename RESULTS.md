# ConcordCoder — 可复现状态与 RQ1 抽样

本文档记录「Plan 199-312」对接执行后的**验收型结果**；**全量** SWE 跑批请在本地配置 API key 后按 [docs/EVALUATION.md](docs/EVALUATION.md) 与 [results/rq1/README.md](results/rq1/README.md) 进行。

## 自动化测试

- **路径**：本目录（`Code/`）
- **命令**：`python3 -m pytest -q`
- **结果**：**49 passed**（以你本机实跑为准）

## RQ1 驱动器（无 API 部分）

- `python3 scripts/rq1_runner.py --instance-id pallets__flask-4045 --print-meta`：通过
- `python3 scripts/rq1_runner.py --instance-id pallets__flask-4045 --dry-run`：通过
- 本地数据：上级目录 `../SWE-bench_Lite/data/test-00000-of-00001.parquet` 已存在
- 示例仓库：可在 `.rq1_repos/flask` 使用，**不纳入 git**（见 `.gitignore` 中 `.rq1_repos/`）

## 有 API 时的一条完整抽样

```bash
cd /path/to/this/Code
export CONCORD_SWE_REPO_ROOT="$PWD/.rq1_repos/flask"
export OPENAI_API_KEY=...   # 或 ANTHROPIC_API_KEY；OpenAI 兼容：另设 OPENAI_BASE_URL
./scripts/run_rq1_sample.sh
python3 scripts/rq1_analyze.py --results-dir results/rq1 --out-dir results/rq1/plots
```

当前环境未设置 `OPENAI_API_KEY` 时，驱动器会在初始化 LLM 前退出；属预期，**不是**数据或路径错误。

## 全量与论文数字

在你确认**抽样 JSON / 图**与预期一致后，再扩大 `instance_id` 列表或 `experiments` 配置批量运行，并将最终 `results/rq1/` 与文内表图对齐。此处不预先写入占位数字，以免与真实跑批不一致。

## 论文主图

- 论文仓库中 `Paper/main.tex` 的 pipeline 图已改为使用已有资产 `fig/overview_gpt.png`（原 `overview.pdf` 在仓库中不存在）。
- 本地完整编译需完整 TeX 环境；若报缺 `algorithmicx.sty` 等，请用发行版包管理器补装或改用 **Overleaf** 编译 `main.tex`。

## 安全

若曾在笔记中误贴 API 密钥，请已在提供商控制台**轮换**；仓库内不应再出现明文 key。
