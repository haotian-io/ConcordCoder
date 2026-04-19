# ConcordCoder：代码生成中的可解释认知对齐系统

> **投稿目标**：Automated Software Engineering (ASEJ) — Explainability in Automated Software Engineering (Ex-ASE) Special Issue  
> **截稿时间**：2026 年 6 月 30 日  
> **研究定位**：Software Engineering × Human-AI Interaction × Explainable LLM-based Code Generation  
> **核心主张**：传统 LLM 代码生成对开发者而言是不可解释的黑盒。ConcordCoder 通过三个可解释机制解决这一问题：结构可解释性（Context Transparency）、约束可解释性（Constraint Grounding）、决策可解释性（Decision Traceability）。

---

## 一、研究动机与问题（Motivation & Problem）

### 1.1 核心痛点：三重认知鸿沟

在现实软件开发中，用户使用 LLM 进行"vibe coding"（凭感觉描述需求后直接生成代码）存在三重认知鸿沟（Cognitive Gap）：

| 鸿沟类型 | 具体表现 | 对可解释性的影响 |
|---------|---------|----------------|
| **模型理解 vs. 用户意图** | 模型对需求产生错误解读，生成逻辑偏差的代码 | 用户不知道模型"理解了什么" |
| **用户当前记忆 vs. 代码历史** | 长期项目中用户忘记过去的设计决策、约束、边界条件 | 用户无法判断生成代码是否符合历史约定 |
| **表层需求 vs. 隐性约束** | 公开 API 兼容性、数据格式约束、错误处理策略等未被明确表达 | 生成代码违反约束但无人能察觉 |

### 1.2 Post-hoc Feedback 的根本局限

现有代码生成工具（包括 GitHub Copilot、ChatGPT 等）本质上采用 **Post-hoc Feedback** 模式：

```
[全局上下文 One-Shot Prompt] → LLM 生成代码
         ↓
编译出错 / 测试失败 / 用户否定
         ↓
用户反馈 → [重新生成] → 循环往复（试错）
```

**根本弱点**：每轮迭代都是"上帝视角"的重试，模型不知道哪里错了、为什么错了。用户也不知道下一次生成是否会更好。这是典型的**不可解释的黑盒循环**。

ConvCodeWorld（2502.19852）已经系统性地研究了 Compilation / Execution / Verbal 三种 Feedback 的组合效果，发现即使有足够反馈，LLM 的 post-hoc 纠错能力也存在天花板。

### 1.3 ConcordCoder 的核心思路：事后调试 → 事前规划

> **目标**：在代码生成前，通过结构化对话让用户和系统就「做什么」「受什么约束」「为什么这样实现」达成可验证的共识，再进行约束感知的一次性生成。

```
用户描述任务
     ↓
[Phase 1] 多层上下文抽取（Context Extraction）
  AST 静态分析 + 调用图 + Git 历史 + 测试约束推断 → ContextBundle
  → 提供「结构可解释性」：LLM 依赖哪些上下文，用户可见
     ↓
[Phase 2] 约束基础的对齐对话（Constraint-Grounded Alignment Dialogue）
  State Machine × Action Space × Constraint 前向验证 → AlignmentRecord
  → 提供「约束可解释性」：所有约束有来源（AST/Git/Test/User），可追溯
     ↓
[Phase 3] 约束驱动代码生成 + Cognitive Summary
  带 Confidence-Guided Probing 的生成 → 代码 + 决策追踪表
  → 提供「决策可解释性」：每个关键决策 traceback 到具体约束节点
```

---

## 二、三项技术贡献（Technical Contributions）

### Contribution 1：Constraint-Grounded Alignment Dialogue（约束基础对齐对话）

#### 对话状态机（Dialogue State Machine）

对话不再是流水账，而是有严格的状态定义和 Action Space：

```python
@dataclass
class DialogueState:
    phase: DialoguePhase                          # 当前子阶段
    confirmed_constraints: List[Constraint]       # 已确认的硬约束（带来源）
    open_questions: List[QuestionSpec]            # 待解答问题队列
    implementation_sketch: SketchNode | None      # 方案雏形
    user_confidence: Dict[ConstraintId, float]    # 用户对每条约束的置信度

# 每条约束都有来源，确保可追溯性
@dataclass
class Constraint:
    id: str
    description: str
    hard: bool
    source: Literal["ast", "git_history", "test_inference", "user_stated"]
    evidence: str   # 具体证据（如：「被 payment/checkout.py:L42 调用」）
```

**Action Space (𝒜)**：

| Action | 触发条件 | 对 State 的影响 |
|--------|---------|----------------|
| `CONFIRM_CONSTRAINT(id)` | 用户确认 | 约束加入 hard_constraints |
| `REJECT_CONSTRAINT(id)` | 用户否定 | 从候选列表移除 |
| `ADD_CONSTRAINT(desc)` | 用户补充 | 新建 source=user_stated 约束 |
| `REQUEST_CLARIFICATION(q)` | 用户提问 | 系统用 LLM 解答，更新上下文 |
| `SKETCH_PREFERENCE(option)` | 用户选方案 | 更新 implementation_sketch |
| `COMMIT_TO_GENERATE` | 用户确认完毕 | 终止对话，触发 Phase 3 |

**对话三子阶段**：

- **Phase A：Context Reconstruction**  
  系统展示 ContextBundle 中最相关的 2-3 个发现，帮用户"想起来"遗忘的项目细节，询问认知程度
- **Phase B：Constraint Confirmation**  
  展示推断出的约束清单（含来源证据），用户逐条确认/否定/补充；收集验收标准
- **Phase C：Solution Co-design**  
  提供 2-3 个实现方案（含利弊分析），用户选择偏好，系统形成最终实现策略

**与 Post-hoc 的核心对比**：

| | Post-hoc Feedback | ConcordCoder |
|---|---|---|
| 干预时机 | 生成后，看到错误再改 | 生成前，共识达成后再生成 |
| 约束处理 | 隐式（模型猜测） | 显式（用户确认，有来源） |
| 可解释性 | 模型为什么这样改？不透明 | 每条约束可追溯到 AST/Git/User |
| 轮次收敛 | 随机，依赖反馈质量 | 收敛到所有 open_questions 解答 |

---

### Contribution 2：Confidence-Guided Probing（置信度引导探针干预）

#### 核心思路

这是 ConcordCoder 独特的**早期干预机制**：在 Draft Generation 阶段，系统不仅关注输出 Token，还追踪关键 AST 节点区间的生成置信度。当检测到低置信度 + 高历史修改频率的代码区域，系统主动向用户抛出探针问题，再精准重生成，而不是整体重来。

```
Draft Generation（使用 logprobs）
         ↓
Perplexity 估计：提取每个 Token 的 log-probability
         ↓
AST 节点映射：将 token 序列映射到 AST 节点（函数/类/跨文件调用）
         ↓
热点权重叠加：
  hotspot_score(node) = (1 - confidence(node)) × git_churn_rate(node)
         ↓
阈值判断：hotspot_score > θ AND node 涉及历史技术债
         ↓ 是
生成探针问题：「我在 payment/handler.py:L156-172 的处理逻辑置信度较低
              （该区域有 3 次近期修改记录）。请问这里期望的错误处理行为是？」
         ↓
用户回答 → 更新 AlignmentRecord → 精准重生成该区间
```

#### 与 InlineCoder（2601.00376）的区别

InlineCoder 也使用 Perplexity 估计，但其目的是**生成 anchor 以驱动上下文检索**（内联上下游调用），属于单轮生成优化。  
ConcordCoder 将 Perplexity 用作**人机对话的触发机制**：
- InlineCoder：低置信度 → 自动检索更多上下文 → 继续生成（无人介入）
- ConcordCoder：低置信度 + 历史热点 → 向用户抛出探针问题 → 人机协同精修

#### 工程实现

```python
# OpenAI API 支持返回 token 级 log-probability
response = client.chat.completions.create(
    model="gpt-4o",
    messages=constrained_generation_messages,
    logprobs=True,
    top_logprobs=5,
)

def compute_node_confidence(logprobs, ast_node_spans):
    """将 token logprobs 聚合到 AST 节点级别。"""
    node_confidences = {}
    for node_id, (start_tok, end_tok) in ast_node_spans.items():
        node_logprobs = [lp.logprob for lp in logprobs[start_tok:end_tok]]
        node_confidences[node_id] = math.exp(sum(node_logprobs) / len(node_logprobs))
    return node_confidences

def detect_probe_targets(node_confidences, git_churn, theta=0.4, alpha=0.5):
    """识别需要探针干预的节点。"""
    probes = []
    for node_id, conf in node_confidences.items():
        churn = git_churn.get(node_id, 0.0)
        score = (1 - conf) * (1 + alpha * churn)
        if score > theta:
            probes.append(ProbeTarget(node_id=node_id, confidence=conf, churn=churn))
    return sorted(probes, key=lambda p: -p.score)
```

---

### Contribution 3：Cognitive Summary as Explainability Artifact（认知摘要作为可解释性产出）

#### 增强格式（v2）

认知摘要不再是自由文本，而是**结构化的决策追踪表**，每条决策 traceback 到具体的来源约束：

```markdown
## 认知摘要（Cognitive Summary）

### 决策追踪表
| 代码位置 | 实现决策 | 依据约束 | 约束来源 | 置信度 |
|---------|---------|---------|---------|------|
| payment_handler.py:L42 | 保持函数签名不变 | C1: 签名稳定性 | AST（被3处调用） | 🟢 高 |
| retry_policy.py:L89 | 指数退避，最大3次 | C3（用户确认） | 对话 Phase B | 🟢 高 |
| transaction.py:L156 | 幂等性校验 | R1: 重复扣款风险 | Git历史分析 | 🟡 中 |

### 低置信度警告区域（需人工复核）
- ⚠️ payment/transaction.py:L156-172【置信度: 0.43】
  原因：该函数在最近 30 天内有 3 次修改，涉及跨文件依赖
  建议：重点检查此段逻辑，尤其与 checkout.py 的接口一致性

### 验证建议
1. `pytest tests/test_payment.py -v`（验证无回归）
2. 用 mock 模拟网络失败，验证重试次数上限
3. 人工检查 transaction.py:L156-172
```

#### 可解释性评估

使用 **Explanation Satisfaction Scale（ESS，Hoffman et al. 2023）** 的 7 点量表维度（中文本地化）：
- 认知充分性：「我理解系统为什么这样实现」
- 决策可追溯性：「我知道哪些因素影响了这段代码的生成」
- 信任标定：「我知道哪些地方需要重点检查」
- 行动支持：「这个摘要帮助我决定下一步怎么验证」

---

## 三、研究问题（Research Questions）

### RQ1：约束基础生成是否优于无约束生成？
**指标**：Pass@1（SWE-bench 子集）、Constraint Violation Rate、Regression Rate  
**实验组**：Direct / RAG-only / Ablation-AlignOnly / Ablation-ContextOnly / ConcordCoder-Full

### RQ2：Cognitive Summary 对开发者可解释性的影响
**主观**：ESS 量表（4 维度，7 点），NASA-TLX 认知负荷  
**客观**：Bug 定位速度（引入隐性 bug 后的发现时间）、项目结构理解度测验  

### RQ3：Confidence-Guided Probing 有效性分析
**指标**：Probe Precision（触发探针的区域与实际错误区域的重叠率）、额外对话轮次代价、生成质量提升（与无 Probing 的对比）

---

## 四、实验设计

### 4.1 数据集

| 数据集 | 用途 | 规模 | 筛选标准 |
|--------|------|------|---------|
| **SWE-bench Verified** | RQ1 主评估 | 500 → 约 150 个子集 | ≥2 文件修改，≥3 fail-to-pass 测试 |
| **CoderEval（2302.00288）** | RQ1 补充评估 | 230 Python + 230 Java | 真实仓库级任务，6 级 context dependency |
| **用户实验仓库（自制）** | RQ2/RQ3 | 3 个小型 Python 项目 | 含 ≥10 模块，有 API 兼容约束，有 Git 历史 |

### 4.2 RQ1 实验（自动化）

五组条件对比：

| 条件 | 描述 |
|------|------|
| Baseline-Direct | Issue 直接 One-Shot 发给 GPT-4o |
| Baseline-RAG | 检索增强 prompt，单轮生成 |
| Ablation-AlignOnly | 只做意图澄清，不做上下文抽取 |
| Ablation-ContextOnly | 只做上下文抽取，不做对齐对话 |
| **ConcordCoder-Full** | 完整三阶段 + Probing |

### 4.3 RQ2/RQ3 用户实验（N ≥ 16）

- **设计**：组间设计（Between-subject），ConcordCoder 组 vs. Direct 组
- **任务池**：3 个仓库任务（支付重试 / 日志扩展 / 权限管理），复杂度低/中/高
- **流程**：5 min 简介 → 15 min 熟悉仓库 → 30 min 完成任务 → 10 min 理解度测验 → 10 min ESS + NASA-TLX → 15 min 访谈

**理解度测验题示例（T1：支付重试）**：
- Q1：`process_payment()` 被哪些模块调用？（选择题）
- Q2：为什么不能直接修改 `transaction.py` 的函数签名？（简答）
- Q3：当前 RetryPolicy 的最大重试次数是多少？（回忆题）
- Q4：指出以下代码片段中可能导致重复扣款的行（代码阅读）

---

## 五、与相关工作的定位

| 工作 | 方法 | 与 ConcordCoder 的区别 |
|------|------|----------------------|
| **InlineCoder（2601.00376）** | Perplexity → anchor → 上下游 inlining | 用 perplexity 做检索；我们用它做**人机探针触发** |
| **A³-CodGen（2312.05772）** | Local + Global + 3rd-party 三层融合，单轮 | 无对话、无约束共识、无解释性输出 |
| **ConvCodeWorld（2502.19852）** | Post-hoc feedback 的 benchmark 分析 | 研究什么反馈有效；我们研究**如何事前避免需要反馈** |
| **CoderEval（2302.00288）** | 6 级 context dependency benchmark | 用于我们的 **RQ1 补充评估数据集** |
| **In-IDE HAX SLR（2503.06195）** | "surface context, provide explanations, support user control" | 我们的设计恰好满足三点，引用作 design motivation |
| **Human-Centered XAI（2110.10790）** | XAI 是 human-centered property | 引用作 explainability 理论基础 |
| **SWE-agent** | 全自动 Agent，无用户认知关注 | 全自动化；我们以 human-in-the-loop 为核心 |

---

## 六、论文结构（ASEJ，预计 20-25 页）

```
1. Introduction
   1.1 三重认知鸿沟与 LLM 代码生成的不可解释性
   1.2 Post-hoc vs. Pre-hoc 干预
   1.3 三项贡献（明确列出）

2. Background & Related Work
   2.1 LLM-based Code Generation（RAG, Direct, Agentic）
   2.2 Explainability in SE（引用 XAI SLR, In-IDE HAX）
   2.3 Human-in-the-loop Code Generation（ConvCodeWorld, InlineCoder, A³-CodGen）

3. ConcordCoder Architecture
   3.1 Phase 1: Multi-layer Context Extraction
   3.2 Phase 2: Constraint-Grounded Alignment Dialogue
        - Dialogue State Machine
        - Action Space
        - 三子阶段实现
   3.3 Phase 3: Constrained Generation + Cognitive Summary

4. Confidence-Guided Probing
   4.1 动机：何时应当干预
   4.2 Token Perplexity → AST Node Confidence
   4.3 热点权重（Git Churn）
   4.4 探针问题生成与精准重生成

5. Evaluation
   5.1 RQ1: Code Quality（SWE-bench + CoderEval）
   5.2 RQ2: Explanation Quality（ESS + 理解度测验）
   5.3 RQ3: Probing Effectiveness

6. Discussion
   6.1 三项贡献的互补性
   6.2 局限性与泛化性
   6.3 对 Explainable AI-SE 的启示

7. Conclusion
```

---

## 七、近期行动计划（～6 月 30 日）

| 周次 | 重点任务 | 产出 |
|------|---------|------|
| **W1-2**（当前）| Intro + Related Work 骨架，Perplexity PoC 验证 | `paper/1_intro.tex`，`experiments/perplexity_poc.py` |
| **W3-4** | Probing 模块完整实现，SWE-bench 环境搭建 | `src/concordcoder/generation/probing.py` |
| **W5-6** | RQ1：50+ SWE-bench tasks，5 条件自动化实验 | `experiments/rq1_results.csv` |
| **W7-8** | 用户实验招募（N≥16）+ 执行，收集 RQ2/RQ3 数据 | 原始问卷数据 + 交互日志 |
| **W9-10** | 数据分析 + 论文全文起草 + 润色 + 投稿 | `paper/main.tex` 完稿 |

> **关键里程碑**：W4 结束前需要有一个能运行的端到端 demo（最少 3 个完整 case），以便在 W5 开始系统性实验。
