# RQ1 多模型测试失败根因分析报告

## 测试概述

- **实例**: astropy__astropy-12907
- **目标文件**: astropy/modeling/separable.py
- **测试时间**: 2026-04-27
- **总耗时**: 312.89秒（5模型并发）

## 测试结果摘要

| 模型 | FHR | 耗时 | Diff长度 | 约束数 | Predicted Files | 状态 |
|------|-----|------|----------|--------|-----------------|------|
| gpt-5.5 | 1.00 | 68.9s | 1623 | 12 | 2 files | 成功 |
| glm-5.1 | 1.00 | 205.6s | 628 | 3 | 1 file | 成功 |
| gemini-3.1-pro-preview | 0.00 | 97.8s | 572 | 3 | [] | 失败 |
| deepseek-v4-flash | 0.00 | 118.6s | 0 | 5 | [] | 失败 |
| deepseek-v4-pro | 0.00 | 310.3s | 0 | 6 | [] | 失败 |

## 失败根因分析

### 1. DeepSeek 系列模型（v4-flash / v4-pro）

**现象**: `unified_diff_len = 0`，完全没有生成 diff 格式的输出。

**根因假设**:

1. **模型名称映射问题**: API 端点 `https://api.bltcy.ai/v1` 可能不支持 `deepseek-v4-flash` 或 `deepseek-v4-pro` 这些模型名称，实际调用时可能 fallback 到了默认模型或返回了空响应。

2. **输出格式不遵循**: DeepSeek 模型可能没有遵循 ConcordCoder 管线中要求的 `OutputFormat.UNIFIED_DIFF` 格式。对齐对话后，模型返回了自然语言解释而非标准 unified diff。

3. **约束提取差异**: DeepSeek 模型的约束数（5-6个）显著低于 gpt-5.5（12个），说明对齐阶段提取的上下文约束较少，可能导致生成阶段缺乏足够指导。

**验证建议**:
- 直接调用 API 测试 DeepSeek 模型是否支持 unified diff 格式
- 检查 API 返回的原始响应内容
- 尝试使用 `deepseek-chat` 或 `deepseek-coder` 等标准模型名称

### 2. Gemini 3.1 Pro Preview

**现象**: `unified_diff_len = 572`（有内容输出），但 `predicted_files = []`（无法提取文件路径）。

**根因假设**:

1. **Diff 格式非标准**: Gemini 模型生成了代码修改内容，但格式不是标准的 unified diff（`--- a/file` / `+++ b/file` 格式），导致 `paths_from_unified_diff()` 解析器无法提取文件路径。

2. **Markdown 代码块包裹**: Gemini 可能将 diff 包裹在 markdown 代码块（```diff）中，而解析器期望纯 diff 文本。

3. **约束类型差异**: Gemini 的约束只有3个且全部是 docstring 级别（`docstring_test_kernel_normalization`, `docstring_transform_to`, `docstring_get_from_registry`），缺少代码结构约束（c1-c7, s1-s5），导致生成质量不足。

**验证建议**:
- 检查 Gemini 原始输出的格式
- 增强 `paths_from_unified_diff()` 的鲁棒性，支持更多格式变体
- 在对齐阶段增加格式约束提示

## 成功模型对比分析

### gpt-5.5（最佳表现）
- 12个约束全部满足（c1-c7, s1-s5）
- 预测了目标文件和测试文件
- Diff 长度 1623，内容完整
- 耗时最短（68.9秒）

### glm-5.1
- 3个约束满足（docstring级别）
- 正确预测目标文件
- Diff 长度 628
- 耗时较长（205.6秒）

## 改进建议

1. **模型适配层**: 为不同模型添加输出格式适配器，处理非标准 diff 格式
2. **格式强制**: 在 prompt 中增加更严格的格式示例和约束
3. **模型名称验证**: 测试 API 端点实际支持的模型名称列表
4. **回退策略**: 当 diff 解析失败时，尝试从代码块或自然语言中提取修改内容
5. **约束增强**: 对齐阶段增加格式相关的显式约束（如 "输出必须是标准 unified diff 格式"）

## 结论

失败主要原因是 **输出格式不兼容**，而非模型能力不足。DeepSeek 模型可能没有生成 diff 格式输出，Gemini 生成的 diff 格式非标准。建议增加输出格式适配层和更严格的格式约束来提升多模型兼容性。
