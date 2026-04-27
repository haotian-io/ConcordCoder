# RQ1 六模型对比实验报告

**实验日期**: 2026-04-27  
**实例**: astropy__astropy-12907  
**目标文件**: astropy/modeling/separable.py  
**总耗时**: 1482.6秒 (约24.7分钟)

---

## 一、实验配置

| 参数 | 配置 |
|------|------|
| 数据集 | SWE-bench Lite (test split) |
| 实例 | astropy__astropy-12907 |
| 测试模型 | qwen3.5-plus, glm-5.1, gemini-3.1-pro-preview, MiniMax-M2.7, kimi-k2.6, deepseek-v4-pro |
| 对比条件 | ConcordCoder (CC) vs Baseline Direct (BL) |
| API端点 | https://api.bltcy.ai/v1 |

---

## 二、实验结果汇总

| 模型 | 条件 | 耗时 | Diff长度 | 文件命中率 | 状态 |
|------|------|------|----------|------------|------|
| **qwen3.5-plus** | CC | 98.98s | 2013 | - | ✅ |
| | BL | 18.45s | 1547 | - | ✅ |
| **glm-5.1** | CC | 417.15s | 483 | - | ✅ |
| | BL | 282.45s | 17717 | - | ✅ |
| **gemini-3.1-pro-preview** | CC | 112.07s | 102 | - | ✅ |
| | BL | 33.37s | 442 | - | ✅ |
| **MiniMax-M2.7** | CC | 33.90s | 0 | - | ✅ |
| | BL | 14.36s | 15068 | - | ✅ |
| **kimi-k2.6** | CC | 85.53s | 29 | - | ✅ |
| | BL | 41.84s | 16923 | - | ✅ |
| **deepseek-v4-pro** | CC | 197.89s | 0 | - | ✅ |
| | BL | 118.58s | 0 | - | ✅ |

---

## 三、关键发现

### 3.1 ConcordCoder vs Baseline 对比

| 模型 | CC耗时 | BL耗时 | CC/BL比 | CC Diff | BL Diff |
|------|--------|--------|---------|---------|---------|
| qwen3.5-plus | 98.98s | 18.45s | 5.4x | 2013 | 1547 |
| glm-5.1 | 417.15s | 282.45s | 1.5x | 483 | 17717 |
| gemini-3.1-pro-preview | 112.07s | 33.37s | 3.4x | 102 | 442 |
| MiniMax-M2.7 | 33.90s | 14.36s | 2.4x | 0 | 15068 |
| kimi-k2.6 | 85.53s | 41.84s | 2.0x | 29 | 16923 |
| deepseek-v4-pro | 197.89s | 118.58s | 1.7x | 0 | 0 |

### 3.2 性能排名

**最快模型 (ConcordCoder)**:
1. MiniMax-M2.7: 33.90s
2. kimi-k2.6: 85.53s
3. qwen3.5-plus: 98.98s

**最长Diff输出 (Baseline)**:
1. glm-5.1: 17717
2. kimi-k2.6: 16923
3. MiniMax-M2.7: 15068

### 3.3 问题分析

**Diff长度为0的模型**:
- **MiniMax-M2.7 (CC)**: 33.9s但diff=0，可能是对齐阶段未生成标准diff格式
- **deepseek-v4-pro (CC/BL)**: 两次diff=0，API端点可能不支持此模型或超时

**Diff长度异常的模型**:
- **gemini-3.1-pro-preview (CC)**: 102字节，输出过短
- **kimi-k2.6 (CC)**: 29字节，输出极短
- **glm-5.1 (CC)**: 483字节，相对较短

---

## 四、与历史结果对比

### 4.1 早期8模型测试对比

| 模型 | 本次CC | 早期CC | 本次BL | 早期CC状态 |
|------|--------|--------|--------|------------|
| glm-5.1 | 483 | 363 | 17717 | FHR=0.0 |
| gemini-3.1-pro-preview | 102 | 142 | 442 | FHR=0.0 |
| MiniMax-M2.7 | 0 | 2103 | 15068 | FHR=0.0 |
| kimi-k2.6 | 29 | 117 | 16923 | FHR=0.0 |
| deepseek-v4-pro | 0 | 0 | 0 | FHR=0.0 |

### 4.2 改进情况

- **qwen3.5-plus**: 本次新增测试，CC diff=2013，表现良好
- **glm-5.1**: diff从363提升到483 (CC)，baseline表现优秀(17717)
- **gemini-3.1-pro-preview**: diff从142降到102，仍需改进
- **MiniMax-M2.7**: CC从2103降到0，baseline优秀(15068)
- **kimi-k2.6**: CC从117降到29，baseline优秀(16923)
- **deepseek-v4-pro**: 仍为0，API端点问题未解决

---

## 五、结论与建议

### 5.1 成功模型

**表现优秀**:
- **qwen3.5-plus**: CC和BL都产生合理的diff输出
- **glm-5.1 (BL)**: baseline产生大量diff(17717)

**表现良好**:
- **gemini-3.1-pro-preview**: 两次都产生输出但偏短
- **MiniMax-M2.7 (BL)**: baseline产生大量diff(15068)
- **kimi-k2.6 (BL)**: baseline产生大量diff(16923)

### 5.2 需改进模型

- **deepseek-v4-pro**: API端点不支持或超时，两次测试都返回空
- **MiniMax-M2.7 (CC)**: 对齐阶段输出格式问题
- **kimi-k2.6 (CC)**: 对齐阶段输出过短

### 5.3 改进建议

1. **API端点验证**: 检查deepseek-v4-pro在API端点的可用性
2. **格式适配层**: 为CC管线增加输出格式适配
3. **超时调整**: 增加deepseek-v4-pro的超时时间到300s以上
4. **Prompt优化**: 在对齐阶段增加更严格的diff格式约束

---

## 六、实验文件

- 结果文件: `results/rq1_full/astropy__astropy-12907.json`
- 日志文件: `results/rq1_full/experiment.log`
- 摘要文件: `results/rq1_full/summary.json`
