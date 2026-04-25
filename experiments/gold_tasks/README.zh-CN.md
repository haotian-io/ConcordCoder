# 黄金任务 YAML 模板集（10 条）

**语言 / Languages:** [English](README.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

本目录**不**随仓附带任何真实应用仓库，仅提供 **10 个** 与 `examples/mini_eval/sample_task.template.yaml` 同构的任务模板，用于：

- 你在本机为每条模板填写 **真实** `id`、`task`、`target_file` / `target_symbol` 与可选 `alignment_answers`；  
- 将填好的文件复制到 `CONCORD_EVAL_TASKS_DIR` 指向的目录，再设 `CONCORD_EVAL_REPO_ROOT` 跑 [`scripts/mini_eval.py`](../scripts/mini_eval.py)；  
- 论文/回归中把「10 条黄金集」的**元数据**（无秘密路径）写进附录或实验说明。

## 使用步骤

1. 克隆并固定提交：在与任务描述匹配的代码版本上建一条分支或打 tag。  
2. 将 `task_01.template.yaml` 复制为 `myrepo_task01.yaml`（可任意命名），把占位符换成真实相对路径与符号。  
3. 若某条与某仓库不相关，**跳过**该条即可；不必十处全填。  
4. 记录你最终选用的任务 ID 列表，与 [`probing_hyperparams.zh-CN.md`](../probing_hyperparams.zh-CN.md) 中的超参表一并存档。

## 与 `dependency_level` 的对应（可选字段）

`dependency_level` 为自由标注（CoderEval 6 级风格，见 `schemas.ContextDependencyLevel`），便于论文表格分层汇报；不填则不影响 `concord` 运行。

## 文件列表

| 文件 | 建议场景（仅命名提示） |
|------|------------------------|
| `task_01` … `task_03` | 偏 `slib` / 单文件 |
| `task_04` … `task_06` | 同类内多符号 / `file-runnable` |
| `task_07` … `task_10` | 跨模块 / `project-runnable` 倾向 |

## 清单（模板）

- [ ] task_01 — 已填真实路径并纳入 mini_eval 或论文  
- [ ] task_02  
- [ ] task_03  
- [ ] task_04  
- [ ] task_05  
- [ ] task_06  
- [ ] task_07  
- [ ] task_08  
- [ ] task_09  
- [ ] task_10  
