# ConcordCoder

**语言 / Languages:** [English](README.md) | **中文** | [日本語](README.ja.md)

> **认知对齐辅助代码生成** — 在生成代码之前，先帮助用户与模型就现有系统形成**共同理解**，再协同完成实现。

## 工程根路径

本仓库即为可安装的 Python 包：克隆后请在**仓库根目录**（含 `pyproject.toml` 处）执行 `pip install -e .`。

若你的工作区另有论文仓库、笔记等，那些资产不参与 `concord` 运行。IDE 集成（如 VS Code 扩展）若由项目单独分发，以发布方说明为准；**本仓库不包含**扩展源码。

## 核心思路

```
用户描述任务
   ↓
[Phase 1] 上下文抽取
  AST + 调用图 + Git 历史 + 测试约束推断 → ContextBundle
   ↓
[Phase 2] 认知对齐对话
  人–AI 多轮（重建上下文 → 确认约束 → 协同方案）→ AlignmentRecord
   ↓
[Phase 3] 约束驱动代码生成
  带校验的 LLM 生成 + 认知摘要
```

## 环境

```bash
cd /path/to/ConcordCoder
pip install -e ".[dev]"

# 启用 LLM（二选一或按需）
pip install -e ".[openai]"
pip install -e ".[anthropic]"

# Git 历史分析
pip install -e ".[git]"

pip install -e ".[dev,all]"
```

## 文档

- **[评测与复现](docs/EVALUATION.md)**：SWE-bench Lite 驱动、`mini_eval`、探针 / logprobs 表等（**均在仓库内**，无父目录依赖）。  
- **[复现状态与结果布局](RESULTS.md)**：单元测试、RQ1 输出目录说明，供复现与审稿对照（英文撰写，与 EVALUATION 互补）。  
- 首次检查 API 配置：运行 **`concord doctor`**（只初始化客户端，不发起聊天请求）。

## 环境变量

**`concord run` / `once` / `align` 以及 `scripts/mini_eval.py` 必须能访问 LLM**：需设置 `OPENAI_API_KEY`（或 `ANTHROPIC_API_KEY`），否则进程会**直接退出**；不再提供无 Key 的生成桩。

使用 **OpenAI 兼容中转** 时设置基址（示例，按服务商文档调整是否带 `/v1`）：

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://example.com/v1
# export ANTHROPIC_API_KEY=sk-ant-...
```

## 用法

### 单任务 `concord once`（脚本 / CI 友好）

默认会跑 **LLM 批量认知对齐**（`LLMAlignmentDialogue.run_batch`，与论文 Phase 2 一致）。仅在做回归、脚本降本或 CI 快检时加 **`--no-full-align`**，改为抽取侧约束猜测 + 规则对齐快路径。

```bash
pip install -e ".[dev,openai]"

concord once /path/to/target/repo \
  -t "实现需求描述" \
  -o /tmp/concord_out \
  --format markdown_plan

# 机读 JSON，解析结果写入 files/
concord once /path/to/repo -t "..." -o /tmp/out --format json

# 仅 unified diff → diff.patch
concord once /path/to/repo -t "..." -o /tmp/out --format diff

# 快路径：缩小扫描、跳过 Git/测试轮次
concord once /path/to/repo -t "..." -o /tmp/out --fast
```

**InlineCoder 式锚点路径**（可选）：指定 `target_file` + 符号，生成草稿锚点并组装上下游上下文（`--use-anchor`）。

```bash
concord once /path/to/repo -t "..." -o /tmp/out --format markdown_plan \
  --target-file src/my_module.py \
  --symbol my_function \
  --use-anchor

# 可选：在锚点草稿上跑探针摘要（无 logprobs 时可用 mock；需同时 --use-anchor）
concord once /path/to/repo -t "..." -o /tmp/out --format markdown_plan \
  --target-file src/my_module.py \
  --symbol my_function \
  --use-anchor --with-probe

# OpenAI 下使用真实 chat logprobs（失败则回退 mock；见 docs/EVALUATION.md 与 experiments/probing_hyperparams*.md）
# export CONCORD_REAL_LOGPROBS=1
```

**机评脚本 `mini_eval.py`（artifact / 回归）**：对你**自备的真实仓库**与**自备任务 YAML 目录**跑三个变体，向 stdout 打印 JSON。仓库内不再附带示例项目；说明见 [`examples/mini_eval/README.zh-CN.md`](examples/mini_eval/README.zh-CN.md)（[en](examples/mini_eval/README.md) / [ja](examples/mini_eval/README.ja.md)）。

```bash
cd /path/to/ConcordCoder   # 含 pyproject.toml 的仓库根
export CONCORD_EVAL_REPO_ROOT=/abs/path/to/your/repo
export CONCORD_EVAL_TASKS_DIR=/abs/path/to/your/task_yamls
python3 scripts/mini_eval.py
```

`--format`：`markdown_plan` | `md` | `json` / `json_files` | `diff` / `unified_diff`。

### Phase 1：`extract`

```bash
concord extract /path/to/repo --task "为支付流程增加指数退避重试"
concord extract /path/to/repo --task "..." --json context.json
```

### 全流程：`run`

```bash
concord run /path/to/repo --task "..."
concord run /path/to/repo --task "..." --interactive
concord run /path/to/repo --task "..." --backend openai
```

### 仅对齐：`align`

```bash
concord align /path/to/repo --task "..."
```

## 代码结构

与英文版一致，见 [README.md](README.md) 中 `src/concordcoder/` 树状说明。

## 测试

```bash
pytest -v
```

## 研究问题（摘要）

**RQ1–RQ3** 的正式定义、用户研究方案与完整主张见**随附论文**。本仓库提供自动化评测轨道的**可复现驱动**，见 [docs/EVALUATION.md](docs/EVALUATION.md)。

---

英文主文档见 [README.md](README.md)，日文见 [README.ja.md](README.ja.md)。
