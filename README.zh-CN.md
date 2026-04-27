# ConcordCoder

**语言 / Languages:** [English](README.md) | **中文** | [日本語](README.ja.md)

> **认知对齐辅助代码生成** — 在生成代码之前，先帮助用户与模型就现有系统形成**共同理解**，再协同完成实现。

## 仓库结构

本目录是**可安装的 Python 包**。克隆后在包含 `pyproject.toml` 的根目录执行 `pip install -e .` 即可安装。

**相关资产（父目录）：**
- `Paper/` — LaTeX 论文源码和编译后的 PDF
- `SWE-bench_Lite/` — 基准测试数据集
- `USAGE.md` — 完整使用指南
- `experiments/` — 实验仓库和结果

## 核心管线

```
用户任务
   ↓
[Phase 1] 上下文提取
  AST + 调用图 + Git 历史 + 测试线索 → ContextBundle
   ↓
[Phase 2] 认知对齐对话
  人–AI 多轮（重建上下文 → 确认约束 → 协同设计）→ AlignmentRecord
   ↓
[Phase 3] 约束驱动代码生成
  带验证的 LLM 代码生成 + 认知摘要
```

## 快速开始

### 1. 安装

```bash
cd /path/to/ConcordCoder/Code
pip install -e ".[dev]"

# 可选：LLM 后端
pip install -e ".[openai]"     # OpenAI (GPT-4o, GPT-5 等)
pip install -e ".[anthropic]"  # Anthropic Claude

# 安装所有可选依赖
pip install -e ".[dev,all]"
```

### 2. 配置 API 密钥

```bash
# OpenAI 或兼容端点
export OPENAI_API_KEY='your-api-key'
export OPENAI_BASE_URL='https://api.openai.com/v1'  # 或使用代理
export CONCORD_OPENAI_MODEL='gpt-4o'  # 或 'gpt-5' 等

# Anthropic
export ANTHROPIC_API_KEY='your-api-key'
```

### 3. 验证配置

```bash
concord doctor --backend openai
# 输出：LLM 客户端已初始化（不发起网络请求）
```

### 4. 运行第一个任务

```bash
concord once /path/to/your/repo \
  -t "为支付处理函数添加指数退避重试" \
  -o /tmp/concord_output \
  --format markdown_plan
```

## 核心命令

### `concord once` — 单任务（推荐用于脚本/CI）

运行完整管线并输出结构化结果。

```bash
# Markdown 计划输出
concord once /path/to/repo -t "你的任务描述" -o /tmp/out --format markdown_plan

# JSON 输出（机器可读）
concord once /path/to/repo -t "..." -o /tmp/out --format json

# 仅 unified diff
concord once /path/to/repo -t "..." -o /tmp/out --format diff

# 快速模式（跳过 Git 历史和测试分析）
concord once /path/to/repo -t "..." -o /tmp/out --fast

# 锚点模式（InlineCoder 风格，针对特定函数）
concord once /path/to/repo -t "..." -o /tmp/out \
  --target-file src/module.py \
  --symbol function_name \
  --use-anchor

# 可选：在锚点草稿上运行探针摘要（需要 --use-anchor）
concord once /path/to/repo -t "..." -o /tmp/out \
  --target-file src/module.py \
  --symbol function_name \
  --use-anchor --with-probe

# 在 OpenAI 下使用真实 chat logprobs（失败时回退到 mock）
# export CONCORD_REAL_LOGPROBS=1
```

### `concord extract` — 仅 Phase 1（不需要 LLM）

提取上下文但不生成代码。

```bash
concord extract /path/to/repo --task "为用户查询添加缓存"
concord extract /path/to/repo --task "..." --json context.json
```

### `concord run` — 完整管线

```bash
# 非交互式（批量对齐）
concord run /path/to/repo --task "..."

# 交互式对话
concord run /path/to/repo --task "..." --interactive

# 指定后端
concord run /path/to/repo --task "..." --backend openai
```

### `concord align` — 仅 Phase 2

仅运行对齐对话（用于调试）。

```bash
concord align /path/to/repo --task "..."
```

## 环境变量

| 变量 | 描述 | 必需 |
|------|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | OpenAI 后端必填 |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | Claude 后端必填 |
| `OPENAI_BASE_URL` | API 端点（用于代理） | 可选 |
| `CONCORD_OPENAI_MODEL` | 模型名称（如 `gpt-4o`） | 默认：`gpt-4o` |
| `CONCORD_REAL_LOGPROBS` | 使用真实 logprobs (1=yes) | 可选 |

## 评估与基准测试

详见 **[docs/EVALUATION.md](docs/EVALUATION.md)**：
- SWE-bench Lite 驱动（`scripts/swe_bench_batch.py`）
- Mini 评估（`scripts/mini_eval.py`）
- 探针/logprobs 超参数
- 可复现性指南

### Mini 评估

对自定义仓库和任务 YAML 进行回归测试：

```bash
cd /path/to/ConcordCoder  # 含 pyproject.toml 的仓库根
export CONCORD_EVAL_REPO_ROOT=/abs/path/to/your/repo
export CONCORD_EVAL_TASKS_DIR=/abs/path/to/your/task_yamls
python3 scripts/mini_eval.py
```

详见 [`examples/mini_eval/README.zh-CN.md`](examples/mini_eval/README.zh-CN.md)。

## 代码结构

```
src/concordcoder/
├── cli.py              # Typer CLI 入口
├── pipeline.py         # 主管道编排
├── schemas.py          # Pydantic 数据结构
├── llm_client.py       # LLM API 客户端
├── extraction/         # Phase 1 模块
│   ├── bundle_builder.py
│   ├── ast_analyzer.py
│   ├── call_graph.py
│   ├── git_historian.py
│   └── test_extractor.py
├── alignment/          # Phase 2 模块
│   ├── dialogue.py
│   ├── llm_dialogue.py
│   └── prompts.py
└── generation/         # Phase 3 模块
    ├── constrained_gen.py
    ├── anchor_pipeline.py
    ├── probing.py
    └── stub.py
```

## 测试

```bash
pytest -v
```

所有测试使用 `StubLLM`（不需要网络）。

## 研究问题

完整的定义、用户研究方案和主张见**随附论文**：
- **RQ1：** 代码生成质量（SWE-bench Lite 自动评估）
- **RQ2：** 用户理解和信任（计划中的用户研究）
- **RQ3：** 对齐对话的成本效益（计划中）

## 文档索引

| 文档 | 描述 |
|------|------|
| **[docs/EVALUATION.md](docs/EVALUATION.md)** | 评估协议和可复现性 |
| **[docs/MINI_EVAL_RUNBOOK.md](docs/MINI_EVAL_RUNBOOK.md)** | Mini 评估指南 |
| **../USAGE.md** | 完整使用指南（多语言） |
| **../Paper/** | LaTeX 论文源码和 PDF |
| **../experiments/results/** | RQ1 实验结果 |