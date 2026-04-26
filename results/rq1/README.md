# RQ1 结果目录（`rq1_runner.py` 输出）

## 本环境抽样状态

| 检查项 | 状态 |
|--------|------|
| `pytest`（Code/） | 49 passed |
| `python3 scripts/rq1_runner.py --print-meta / --dry-run` | 通过；实例 `pallets__flask-4045` 可用 |
| 本地 Parquet | `../SWE-bench_Lite/data/test-00000-of-00001.parquet` |
| Flask 仓库 @ base_commit | `Code/.rq1_repos/flask`（已本地准备；`.gitignore` 忽略） |
| 需 `OPENAI_API_KEY` 的完整 run | 未在 CI/无 key 环境执行；设置 key 后运行下方命令 |

## 生成一条完整 JSON

```bash
cd /path/to/ConcordCoder/Code
export CONCORD_SWE_REPO_ROOT=/path/to/ConcordCoder/Code/.rq1_repos/flask
export OPENAI_API_KEY=...   # 或 ANTHROPIC_API_KEY；DeepSeek: 设 OPENAI_BASE_URL=https://api.deepseek.com
./scripts/run_rq1_sample.sh
```

产出文件：`pallets__flask-4045.json`（instance id 中 `/` 会替换为 `_`）。

## 分析 / 出图

在已有至少一个 `*.json` 结果后：

```bash
python3 scripts/rq1_analyze.py --results-dir results/rq1 --out-dir results/rq1/plots
```
