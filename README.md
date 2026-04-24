# ConcordCoder

> **认知对齐辅助代码生成系统** — 先帮助用户和模型达成对现有系统的共同理解，再协同完成代码生成。

## 工程根路径（本工作区）

持续迭代与 `pip install -e` 的**唯一正式代码根**为：

`ConcordCoder/ConcordCoder/Code/`

（仓库中 `Paper/`、`ConcordCoder_Full_Session_History/`、上级目录的论文与笔记等为研究资产，不参与 `concord` 运行时。）

## 核心思路

```
用户描述任务
     ↓
[Phase 1] 上下文抽取（Context Extraction）
  AST 静态分析 + 调用图 + Git 历史 + 测试约束推断 → ContextBundle
     ↓
[Phase 2] 认知对齐对话（Alignment Dialogue）
  人-AI 多轮交互（重建上下文 → 确认约束 → 协同设计方案）→ AlignmentRecord
     ↓
[Phase 3] 约束驱动代码生成（Constrained Generation）
  带验证的 LLM 代码生成 + 认知摘要输出
```

## 环境

使用 Anaconda 虚拟环境（推荐 base 或新建环境）：

```bash
cd ConcordCoder/ConcordCoder/Code
# 基础安装（规则模式，无需 API Key）
pip install -e ".[dev]"

# 启用 LLM（选择其一）
pip install -e ".[openai]"     # OpenAI GPT-4o
pip install -e ".[anthropic]"  # Anthropic Claude

# 启用 Git 历史分析
pip install -e ".[git]"

# 安装全部
pip install -e ".[dev,all]"
```

## 环境变量

```bash
export OPENAI_API_KEY=sk-...        # 使用 OpenAI
export ANTHROPIC_API_KEY=sk-ant-... # 使用 Anthropic Claude
```

## 用法

### 单任务一次跑通（推荐用于脚本 / CI）

默认**不**跑多轮 LLM 对齐，仅使用抽取阶段得到的约束猜测 + 规则对齐，低延迟；需要完整「批量对齐」时加 `--full-align`。

```bash
cd /path/to/ConcordCoder/ConcordCoder/Code
pip install -e ".[dev,openai]"   # 或 anthropic

# 输出目录写入 result.json；markdown 时另有 plan.md；json_files 时另有 files/ 与 raw_model_output.txt
concord once /path/to/target/repo \
  -t "实现需求描述" \
  -o /tmp/concord_out \
  --format markdown_plan

# 机读 JSON：{"files":[{"path","content"}]}，并解析写入 files/
concord once /path/to/repo -t "..." -o /tmp/out --format json

# 仅生成 unified diff 文本 → diff.patch
concord once /path/to/repo -t "..." -o /tmp/out --format diff

# 快路径 + 不跑 LLM 对齐（默认已是快路径；--full-align 才启用 LLM 批量对齐）
concord once /path/to/repo -t "..." -o /tmp/out --fast
```

`--format` 可写：`markdown_plan` | `md` | `json` / `json_files` | `diff` / `unified_diff`。

### Phase 1：仓库上下文抽取

```bash
# 分析仓库，抽取与任务相关的上下文
concord extract /path/to/repo --task "为支付流程新增指数退避重试逻辑"

# 保存 ContextBundle 为 JSON
concord extract /path/to/repo --task "..." --json context.json
```

### 全流程（Phase 1 → 2 → 3）

```bash
# 批量模式（自动化，无交互）
concord run /path/to/repo --task "为支付流程新增指数退避重试逻辑"

# 交互模式（认知对齐对话）
concord run /path/to/repo --task "..." --interactive

# 指定 LLM 后端
concord run /path/to/repo --task "..." --backend openai
concord run /path/to/repo --task "..." --backend anthropic
```

### 只运行对齐对话（调试用）

```bash
concord align /path/to/repo --task "..."
```

## 代码结构

```
src/concordcoder/
├── schemas.py                  # 数据结构：ContextBundle, AlignmentRecord, GenerationResult
├── pipeline.py                 # 主流程编排
├── cli.py                      # CLI 入口（typer + rich）
├── llm_client.py               # LLM 客户端（OpenAI / Anthropic）
│
├── extraction/
│   ├── bundle_builder.py       # 多层次上下文抽取（主入口）
│   ├── ast_analyzer.py         # AST 静态分析（函数/类/导入/TODO）
│   ├── call_graph.py           # 模块依赖图（传播分析）
│   ├── git_historian.py        # Git 历史设计决策提取
│   └── test_extractor.py       # 测试文件约束推断
│
├── alignment/
│   ├── dialogue.py             # 规则模式基础对话（无 LLM）
│   ├── llm_dialogue.py         # LLM 驱动三阶段对话状态机
│   └── prompts.py              # Prompt 模板（三阶段）
│
└── generation/
    ├── stub.py                 # 基础桩（write_plan 工具函数）
    ├── json_output.py          # json_files / diff 输出解析
    ├── anchor_pipeline.py      # InlineCoder 风格锚点 + 片段组装（可选）
    └── constrained_gen.py      # 约束驱动生成 + 多输出格式
```

## 测试

```bash
pytest -v
```

目前测试覆盖：
- AST 分析器（函数/类/导入/TODO提取，语法错误处理）
- 调用图（依赖关系、传播分析）
- 测试约束推断（fixture、断言模式）
- BundleBuilder 升级功能（调用图、受影响模块、元数据）
- 对齐对话（规则模式）
- 约束生成器（stub 模式）
- 端到端 pipeline

## 研究方案

详见 [`docs/research_plan.md`](docs/research_plan.md)

三个研究问题：
- **RQ1**：ConcordCoder 能否提升 vibe coding 的代码质量？（SWE-bench 自动化评估）
- **RQ2**：对用户认知的主客观影响？（主观问卷 + 客观理解度测验）
- **RQ3**：交互成本与收益如何权衡？（对话轮次 vs. 代码修改次数）
