# 研究路线与实验待办

与 **论文主稿** `Paper/main.tex`（Overleaf 同步稿同内容）中 **Future Work、Evaluation、RQ1–RQ3** 的 **planned** 表述对齐。若工作区为仅含 `Code/` 的克隆，以单独检出的 `Paper` 仓或 arXiv/期刊 PDF 为准。完成项可在此打勾，不必与代码发版同序。

## 1. 模型与 Probing

- [ ] 在**真实** OpenAI/兼容 API 上稳定取得 **logprobs**（或等价置信度）并接 [`probing.py`](../src/concordcoder/generation/probing.py) 的既有管线。
- [ ] 标定探针阈值、churn 权重、每任务最大探针数等超参，并记录实验配置（可进附录）。

## 2. 自动化评测（与 artifact 机评并列）

- [ ] **保留** 当前 [TaskLab + `scripts/mini_eval.py`](../scripts/mini_eval.py) 作为**可复现、回归**用 driver（**不**替代大基准结论）。
- [ ] 另起**大规模 RQ1**（如 SWE-bench 子集）：Pass@k、约束违反率、回归率等，与机评**并行汇报**，不互相替代。

## 3. 用户与探针金标准

- [ ] **RQ2**：按论文协议招募、任务、前测/后测（如 ESS-7、客观题）、访谈同意与伦理审查（依机构要求）。
- [ ] **RQ3**：小集合**注入错误**或人工标注**错误相关 AST 节点**，计算探针精度/召回，与 `mini_eval` 的 metadata **区分**表。

## 4. 工程扩展（非短期必做）

- [ ] 多语言 Phase 1：如 **tree-sitter** 替代/补充单语言 AST。

## 5. 论文定稿

- [ ] 关闭 `showcomments`、清理合著者批注、核对 `\cite` 与 `ref.bib`。
- [ ] 若仓库旁维护 Springer 模板稿，与主稿**定期合并**，以 `Paper/main.tex` 为唯一真源。
