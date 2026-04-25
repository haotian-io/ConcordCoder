# Phase 1 多语言（tree-sitter）— 已推迟

**范围说明（推迟项）**：仅在审稿意见要求多语言外效度，或消融明确需要**非 Python** Phase 1 时再立项实现。

## 未在本周期实现的原因

- 当前 AST/调用图路径以 CPython `ast` 与仓库内 [bundle_builder](https://github.com/haotian-io/ConcordCoder) 为主；接 tree-sitter 需**并行**图模型与测试矩阵，与短稿截稿期冲突。  
- 论文 **Limitations / Future Work** 已将多语言 Phase 1 列为威胁与后续方向时，不必为单次投稿强行合并 tree-sitter 后端。

## 若将来要做

- 在 `extraction/` 下新增可选后端，以「文件扩展名 → 解析器」表驱动；对回归任务保留 Python 基线对照。  
- 依赖与 CI：固定 `tree-sitter` 语言包版本，避免可重复性漂。

**状态**：`opt-tree-sitter` 关闭；见论文 Limitations 表述即可。
