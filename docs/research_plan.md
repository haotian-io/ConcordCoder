# ConcordCoder：代码生成中的认知对齐辅助系统

> **研究定位**：Software Engineering × Human-AI Interaction × LLM-based Code Generation  
> **核心假设**：在代码生成前，通过"上下文重建 → 认知对齐对话 → 约束驱动生成"三阶段流程，可以显著提升 AI 辅助代码质量，并帮助用户更好地理解生成结果。

---

## 一、研究动机与问题（Motivation & Problem）

### 1.1 核心痛点

在现实软件开发中，用户使用 LLM 进行"vibe coding"（凭感觉描述需求后直接生成代码）存在三重鸿沟：

| 鸿沟类型 | 具体表现 |
|---------|---------|
| **模型理解 vs. 用户意图** | 模型对需求产生错误解读，生成逻辑偏差的代码 |
| **用户当前记忆 vs. 代码历史** | 长期项目中用户忘记过去的设计决策、约束、边界条件 |
| **表层需求 vs. 隐性约束** | 公开 API 兼容性、数据格式约束、错误处理策略等未被明确表达 |

### 1.2 现有方法的局限性

- **直接提示（Direct Prompting）**：用户一句话描述需求，模型直接生成，无法处理隐性约束
- **测试驱动方法（TDD-like）**：需要用户事先写测试，门槛高，且仍不解决"共同理解"问题  
- **RAG 检索增强**：只是给模型更多上下文，并未帮助用户"认知重建"
- **TraceCoder 等调试框架**：关注生成后的修复，而非生成前的意图对齐

### 1.3 ConcordCoder 的定位

> **目标不是"替用户写代码"，而是"先帮助用户和模型达成对现有系统的共同理解，再协同完成代码生成"。**

```
用户描述任务
     ↓
[Phase 1] 上下文抽取与融合（Context Extraction & Fusion）
  静态分析 + 语义检索 → ContextBundle
     ↓
[Phase 2] 认知对齐对话（Alignment Dialogue）
  人-AI 多轮交互 → 澄清约束、重建上下文 → AlignmentRecord
     ↓
[Phase 3] 约束驱动代码生成（Constrained Generation）
  带验证的代码生成 + 解释性输出
     ↓
生成代码 + 认知摘要（为什么这样实现）
```

---

## 二、研究问题（Research Questions）

### RQ1：ConcordCoder 能否提升 vibe coding 的代码质量？

**核心假设**：认知对齐前置处理能减少因需求误解导致的代码错误，提高最终代码与仓库约束的匹配程度。

**比较对象（Baseline）**：
1. **Direct**：直接将用户需求发给 LLM，单轮生成
2. **RAG-only**：检索相关代码片段注入 prompt，单轮生成
3. **Clarify-then-Code**（消融）：只做意图澄清对话，不做仓库上下文分析
4. **ContextOnly**（消融）：只做上下文抽取，不做对齐对话
5. **ConcordCoder**：完整三阶段流程（上下文抽取 + 对齐对话 + 约束生成）

**评估指标**：
- **Pass@1（测试通过率）**：主要指标，使用 SWE-bench Verified 子集
- **Constraint Violation Rate（约束违背率）**：检测生成代码是否破坏了已知约束
- **Regression Rate（回归率）**：生成代码是否导致原有测试失败
- **Edit Distance to Ground Truth**：与标准答案的编辑距离（补充指标）

### RQ2：ConcordCoder 对用户认知的主客观影响

**核心假设**：认知对齐流程能让用户更好地理解项目现有结构，并在生成后对代码有更准确的认知评估。

#### 主观评价（Subjective）

用户完成任务后填写问卷（7点量表），维度包括：
- **意图准确性感知**（"系统生成的代码是否符合你的意图"）
- **理解深度感知**（"完成后你是否更了解项目现有结构"）
- **信任度**（"你对生成代码的信任程度"）
- **认知负荷**（NASA-TLX 量表）

#### 客观评价（Objective）

使用**理解度测验**：任务完成后向用户提问与项目结构/约束相关的问题：
- "该项目中，为什么 `payment_handler.py` 不能直接调用 `database.commit()`？"
- "如果你修改了 `retry_policy`，哪些其他模块需要更新？"

对比 ConcordCoder 组 vs. Direct 组用户的答题准确率，作为认知理解的客观度量。

### RQ3：交互成本与收益分析

**核心假设**：对齐对话引入了额外的交互轮次成本，但这些成本可以被代码修改次数减少所补偿。

**指标**：
- **对话轮次数**（Task Completion Turns）：完成任务所需的总对话轮数
- **代码修改轮次**（Correction Rounds）：用户收到初始生成后进行修改的次数
- **任务完成时间**（Task Completion Time）：端到端计时
- **认知对齐收益率**（Alignment ROI）：`(代码质量提升) / (额外交互成本)`

---

## 三、系统架构详细设计

### 3.1 Phase 1：上下文抽取与融合（Context Extraction & Fusion）

#### 现有基线实现（已有）

关键词窗口检索（BundleBuilder v0），输出 ContextBundle 包含：task_summary、structural_facts、snippets（≤30个代码片段）、constraints_guess、risks、open_questions

#### 升级目标：多层次分析管道

```
输入: repo_root + task_text
     ↓
Layer 1: 静态结构分析
  · AST 解析 (tree-sitter / ast)
  · 调用图构建 (networkx)
  · 类型签名提取
  · 模块依赖图
     ↓
Layer 2: 语义检索
  · 代码嵌入 (CodeBERT / OpenAI text-embedding)
  · 向量数据库 (ChromaDB / FAISS)
  · 任务相关片段 Top-K 检索
     ↓
Layer 3: 历史痕迹分析
  · Git commit message 分析 (gitpython)
  · 注释/文档设计意图提取
  · TODO/FIXME/HACK 标记收集
  · 测试用例隐性约束识别
     ↓
Layer 4: LLM 融合与摘要
  · 将三层结果融合为 ContextBundle
  · LLM 生成结构性摘要
  · 识别潜在风险与设计约束
     ↓
输出: ContextBundle (enriched)
```

**关键新增 Schema 字段**：
```python
class ContextBundle(BaseModel):
    # 现有字段...
    call_graph: dict[str, list[str]]       # 调用关系图
    entry_points: list[str]                # 关键入口文件
    design_constraints: list[Constraint]   # 从注释/文档推断的约束
    historical_decisions: list[str]        # Git 历史决策痕迹
    test_expectations: list[str]           # 测试文件推断的行为期望
    affected_modules: list[str]            # 本次任务可能影响的模块
```

### 3.2 Phase 2：认知对齐对话（Alignment Dialogue）

对话分为**三个子阶段**，每个子阶段有明确的认知目标：

**子阶段 A：上下文重建（Context Reconstruction）**
> 目标：帮用户重建对项目现有结构的认知

```
系统: "我分析了你的仓库，发现以下与本次任务最相关的模块：
  · payment/handler.py（支付核心逻辑，包含3个公开函数）
  · retry/policy.py（重试策略，目前最大重试3次）
  · tests/test_payment.py（12个测试，均依赖 mock_db 夹具）
  
其中：handler.py 的 process_payment() 被 3 个不同模块调用，
改动签名会影响所有调用方。你对这些模块熟悉吗？"
```

**子阶段 B：约束确认（Constraint Confirmation）**
> 目标：显式确认哪些约束必须遵循

```
系统展示推断的约束清单，要求确认/修改：
✅ 必须遵循（系统推断）
  [C1] process_payment() 的函数签名不可更改（被3处调用）
  [C2] 需兼容现有的 mock_db 测试夹具
⚠️ 需要你确认的
  [C4] 新功能是否需要兼容旧数据格式？[是/否]
  [C5] 失败后应该抛出异常还是返回错误码？[抛/返回]
❓ 发现的潜在风险
  [R1] 现有代码没有事务回滚，新增重试可能导致重复扣款
```

**子阶段 C：实现方案讨论（Solution Co-design）**
> 目标：在约束框架内协同确定实现方案

```
系统提供 2-3 个实现方案（保守/重构），分析利弊，
询问用户偏好，形成最终实现策略。
```

**对话轮次控制**：最少 2 轮（约束确认）→ 标准 3-4 轮 → 详细 5-6 轮；用户明确说"可以生成了"时退出。

### 3.3 Phase 3：约束驱动代码生成（Constrained Generation）

#### 生成流程

```
1. 构建约束感知 System Prompt
   (含 hard constraints + allowlist_paths + 验收标准)
     ↓
2. LLM 生成初始代码
     ↓
3. 约束验证器检测违规
   - 违规 → 自动反馈，重生成（最多3次）
   - 通过 → 继续
     ↓
4. 生成认知摘要（Cognitive Summary）
   - 为什么这样实现
   - 已处理的风险 / 仍需关注的风险
   - 建议的验证步骤
```

#### 认知摘要输出格式示例

```markdown
## 实现摘要

**我这样实现，因为：**
- 遵循约束 C1（process_payment 签名不变）
- 使用项目已有的 RetryPolicy 基类
- 不影响 tests/test_payment.py 中现有的 12 个测试

**注意以下风险点：**
- ⚠️ R1：已添加幂等性检查以避免重复扣款，建议测试验证
- ✅ R2：retry timeout 已与现有 connection_timeout 对齐

**建议验证步骤：**
1. pytest tests/test_payment.py -v
2. 用 mock 模拟网络失败，验证重试行为
```

---

## 四、实验设计

### 4.1 数据集选取

| 数据集 | 用途 | 规模 | 选取理由 |
|--------|------|------|---------|
| **SWE-bench Verified** | RQ1 自动化评估 | 500 tasks | 真实 GitHub Issue，有标准测试验证 |
| **SWE-bench Lite** | 快速迭代测试 | 300 tasks | 资源受限时替代 |
| **CodeChat** | 用户交互行为分析 | 82,845 对话 | 真实用户-LLM 交互，分析对齐模式 |
| **AweAI SCALE-SWE** | 扩展评估 | TBD | 更大规模多语言验证 |

**SWE-bench 子集筛选策略**：
- 涉及 ≥2 文件修改（体现仓库级理解的必要性）
- 有 ≥3 个 fail_to_pass 测试（约束验证更有意义）
- 不是纯算法实现（需要理解现有代码结构）

### 4.2 RQ1 实验设计（自动化评估）

#### 实验条件（5组）

| 条件 | 描述 |
|------|------|
| **Baseline-Direct** | Issue 直接发给 GPT-4o，单轮生成 |
| **Baseline-RAG** | 检索相关代码片段增强 prompt，单轮生成 |
| **Ablation-AlignOnly** | 只做意图澄清，不做仓库上下文抽取 |
| **Ablation-ContextOnly** | 只做上下文抽取，不做对齐对话 |
| **ConcordCoder-Full** | 完整三阶段流程 |

#### 核心指标

- **Pass@1**：fail_to_pass 测试全部通过
- **Constraint Violation Rate**：生成代码破坏已知约束的比例
- **Regression Rate**：pass_to_pass 测试中出现失败的比例

### 4.3 RQ2 用户实验设计

#### 被试设计

- **规模**：N ≥ 20（ConcordCoder 组 10 人，Direct 组 10 人）
- **来源**：有 1 年以上编程经验的开发者（CS 研究生）
- **设计**：组间设计（Between-subject），避免学习效应

#### 实验任务池（3 个）

| 任务 | 描述 | 复杂度 |
|------|------|--------|
| **T1: 支付重试** | 为支付模块增加带指数退避的重试逻辑 | 中 |
| **T2: 日志扩展** | 为现有日志系统增加结构化输出格式 | 低 |
| **T3: 权限管理** | 在 API 路由层增加细粒度权限验证 | 高 |

每个被试完成 1 个任务（减少疲劳），3 个任务在组间均匀分布。

#### 实验流程（约 85 min）

```
1. 简介 & 知情同意（5 min）
2. 熟悉代码仓库（15 min，双组相同）
3. 使用对应工具完成任务（30 min）
   · ConcordCoder 组：全流程辅助
   · Control 组：直接使用 ChatGPT
4. 认知理解测验（10 min，客观题）
5. 主观问卷（NASA-TLX + 感知量表）（10 min）
6. 半结构化访谈（15 min）
```

#### 客观理解度测验题目示例（T1 - 支付重试）

- Q1: process_payment() 由哪些模块调用？（选择题）
- Q2: 修改 payment_logger 格式需要更新哪些测试文件？（简答）
- Q3: 指出以下代码片段中可能导致重复扣款的行（代码阅读）
- Q4: 当前 RetryPolicy 的最大重试次数是多少？（回忆题）

### 4.4 RQ3 交互成本分析

**数据采集**：自动记录对话轮次、时间戳、git diff（代码修改次数）

**核心分析指标**：
```
Alignment ROI =
  (ConcordCoder 组 Pass@1 - Direct 组 Pass@1) /
  (ConcordCoder 对话轮次 - Direct 对话轮次)
```

---

## 五、技术实现路线图

### 阶段 0（现状，已完成）
- [x] 关键词窗口上下文抽取（BundleBuilder v0）
- [x] 基础对话脚本（AlignmentDialogue 草案）
- [x] Pipeline 骨架（extraction → alignment → generation）
- [x] 数据结构定义（ContextBundle, AlignmentRecord, GenerationRequest）

### 阶段 1（第 1-2 周）：上下文抽取升级
- [ ] 集成 `tree-sitter` 进行 AST 解析，提取函数/类定义
- [ ] 构建模块级调用图（`ast` + `networkx`）
- [ ] 集成 `ChromaDB` + 代码嵌入语义检索
- [ ] 实现 Git 历史分析（`gitpython`，commit message）
- [ ] 测试文件约束推断器

### 阶段 2（第 2-3 周）：对齐对话 LLM 集成
- [ ] 对接 OpenAI API / Anthropic Claude API
- [ ] 实现三子阶段对话状态机
- [ ] 约束推断 LLM Prompt（JSON 结构化输出）
- [ ] 命令行交互界面（`rich` 库美化）

### 阶段 3（第 3-4 周）：约束驱动生成
- [ ] 约束感知 System Prompt 模板
- [ ] 生成后约束违背自动检测
- [ ] 再生成反馈循环（最多3次）
- [ ] 认知摘要（Cognitive Summary）生成

### 阶段 4（第 4-6 周）：实验基础设施
- [ ] SWE-bench 测试用例跑通（Docker 环境）
- [ ] 自动化评估脚本
- [ ] 用户实验 Web UI（记录交互日志）
- [ ] 数据分析流水线

### 阶段 5（第 6-10 周）：实验执行 & 论文写作
- [ ] RQ1 自动化实验执行
- [ ] 用户实验招募 & 执行（RQ2/RQ3）
- [ ] 数据分析 & 可视化
- [ ] 论文初稿 & 投稿

---

## 六、目录结构规划

```
ConcordCoder/
├── src/concordcoder/
│   ├── schemas.py               # ✅ 已有，需扩展新字段
│   ├── pipeline.py              # ✅ 已有，需完善
│   ├── cli.py                   # ✅ 已有
│   │
│   ├── extraction/
│   │   ├── bundle_builder.py    # ✅ 基础版已有
│   │   ├── ast_analyzer.py      # 🆕 AST 静态分析
│   │   ├── call_graph.py        # 🆕 调用图构建
│   │   ├── semantic_retriever.py# 🆕 向量语义检索
│   │   ├── git_historian.py     # 🆕 Git 历史分析
│   │   └── test_extractor.py    # 🆕 测试约束推断
│   │
│   ├── alignment/
│   │   ├── dialogue.py          # ✅ 基础版已有
│   │   ├── llm_dialogue.py      # 🆕 LLM 驱动对话
│   │   ├── constraint_infer.py  # 🆕 约束推断
│   │   └── state_machine.py     # 🆕 对话状态管理
│   │
│   ├── generation/
│   │   ├── stub.py              # ✅ 基础版已有
│   │   ├── constrained_gen.py   # 🆕 约束驱动生成
│   │   ├── validator.py         # 🆕 生成后验证
│   │   └── explainer.py         # 🆕 认知摘要生成
│   │
│   └── eval/                    # 🆕 评估工具
│       ├── swebench_runner.py
│       ├── metrics.py
│       └── user_study_logger.py
│
├── experiments/                 # 🆕 实验脚本
│   ├── rq1_automated/
│   ├── rq2_user_study/
│   └── rq3_cost_analysis/
│
├── docs/
│   └── research_plan.md         # 📄 本文件（同步写入仓库）
│
└── tests/                       # ✅ 已有
```

---

## 七、相关工作定位

| 工作 | 方法 | 与本工作区别 |
|------|------|------------|
| **TraceCoder**（arXiv:2602.06875）| 运行时 trace 驱动多智能体调试 | 关注**生成后**调试，本工作关注**生成前**对齐 |
| **SWE-agent** | 自主 Agent 解 GitHub Issue | 全自动化，不关注用户认知；本工作以人为中心 |
| **RAG-based Code Gen** | 检索增强生成 | 只给**模型**更多上下文；本工作同时给**用户**重建认知 |
| **Copilot Chat** | 对话式代码辅助 | 无结构化约束提取，无认知对齐阶段 |
| **CodeChat 分析工作** | 多轮对话代码生成分析 | 分析现象，本工作提出干预方案 |

---

## 八、预期贡献

1. **新问题定义**：首次系统性分析"认知鸿沟"在代码生成场景中的三重来源（模型理解 vs. 用户意图 vs. 历史设计），提出 Cognitive Alignment 作为解决框架

2. **新系统 ConcordCoder**：实现了上下文抽取 → 认知对齐对话 → 约束驱动生成的完整管道，包含可验证的约束机制和解释性认知摘要

3. **新评估框架**：提出结合主观感知、客观理解度测验、代码质量的多维评估体系，特别是**客观理解度测验**作为新颖的认知评估手段

4. **实证发现**：通过自动化实验（RQ1）+ 用户实验（RQ2/RQ3），量化认知对齐对代码质量和用户理解的影响

---

## 附录：初始 Prompt 模板草稿

### A1. 上下文摘要生成

```
你是一个代码库分析助手。给定代码片段和任务描述，
请用简洁的中文总结：
1. 与本次任务最相关的模块（3-5个）和它们的核心职责
2. 你发现的可能存在的设计约束
3. 本次任务的潜在实现风险

输出为结构化 JSON。
```

### A2. 对齐对话引导

```
你是帮助开发者重建项目认知的助手。
基于分析结果，用自然对话方式：
1. 展示最关键的 2-3 个发现（不要一次说太多）
2. 提问用户对这些发现的认知程度
3. 引导用户确认或修正推断的约束

语气：专业但友好，像一位熟悉这个项目的同事。
重点：帮用户"想起来"他们可能遗忘的项目细节。
```

### A3. 约束驱动生成 System Prompt

```
你是一个约束感知的代码生成助手。
在生成代码时必须严格遵守以下约束：
{confirmed_constraints}

可以修改的文件范围：
{allowlist_paths}

生成代码后，请附上认知摘要：
- 为什么这样实现（与约束的关联）
- 哪些风险已处理，哪些仍需用户关注
- 建议的验证步骤
```
