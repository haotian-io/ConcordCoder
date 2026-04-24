# 对外试用（CLI）与体验数据收集

当前**发布形态**为：可安装的 Python 包 + `concord` 命令行，**无**内置 Web 与遥测。外测时建议按下述分工准备材料。

## 1. 试用包（最小可交付）

1. 指向本仓库的 **安装说明**：[README.md](../README.md) / [README.zh-CN.md](../README.zh-CN.md)。  
2. 试用者需自备 **OpenAI 或 Anthropic API Key**（及可选的 **OPENAI_BASE_URL** 以对接兼容中转）。  
3. 运行前执行 **`concord doctor`** 确认环境与密钥可初始化客户端（**不**代表 LLM 一定联网成功，以首次实际调用为准）。  
4. 建议提供 **固定练习仓库**（如本仓 `fixtures/repos/tasklab`）与 1–2 条与 [`fixtures/tasks`](../fixtures/tasks) 同风格的任务句，减少变量。

## 2. 仅展示 Phase 1（可免 Key）

- `concord extract <repo> --task "…"` 可在**无 API Key** 下展示静态分析、片段与风险。  
- 全管道 `run` / 单任务 `once` / `align` 与 `scripts/mini_eval.py` **需要** Key，否则按设计**退出**。

## 3. 收集研究数据时建议单独准备（非本仓库内建功能）

- **同意书** / 研究伦理（依你所在机构要求）。  
- **问卷**：信任度、任务难度、对认知摘要/约束的理解等（可对照论文 RQ2 与 ESS-7 类量表）。  
- **可留存产物**（在同意前提下）：`result.json`、`plan.md` 脱敏副本、**可选**录屏。  
- 本系统**不**向作者服务器回传使用数据；需由实验组织者自行通过问卷星/表格/邮件收集。

## 4. 后续可选（需单独立项）

- 与 [claw-code](https://github.com/ultraworkers/claw-code) 等类似：**USAGE 体例**、**容器镜像**、**类 doctor 的更强自检** 已可逐步加在本文档所指的 CLI 上。  
- **Web 或托管** 给非技术用户：需另做鉴权、限流、Key 代理与责任边界，不属当前仓库保证范围。
