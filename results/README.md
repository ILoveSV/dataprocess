# 实验与理论结果索引

更新：2026-09-28。本目录现纳入Git的内容是报告、结果表、图和审计元数据；原始记录、数组缓存、求解模型及音视频仍留在本地或外部备份。

**克隆仓库不等于取得完整精简归档。** `exact_archive`等目录仅有部分元数据/表；不上传`COMPLETE`标记，不能据此跳过原始归档的完整性检查。历史报告引用的本机路径和未上传缓存可能不可用。

## 按研究环节阅读

| 环节 | 结果入口 | 解释边界 |
|---|---|---|
| 工况拆分，7月31日 | [实验报告](experiment_20260731/EXPERIMENT_ANALYSIS_REPORT.md) | 两探测器应各对本机背景，结合后续完整分析修正 |
| 交叉校准与载波扫描，8月6日 | [实验报告](experiment_20260806/EXPERIMENT_ANALYSIS_REPORT.md) | 相对比较不等于绝对场强标定 |
| 阴极保护，8月11日 | [第一组](experiment_20260811/EXPERIMENT_ANALYSIS_REPORT.md)、[高电流组](experiment_20260811_2/EXPERIMENT_ANALYSIS_REPORT.md) | 旧小间距实验，不能擅自作为修正后间距数据 |
| 导师建议的时域/多尺度/动力学方法 | [第一轮](mentor_aligned_pre_electrochemical_v1/MENTOR_ALIGNED_EVIDENCE_REPORT.md)、[扩展轮](mentor_aligned_methods_v2/MENTOR_METHOD_EXPLORATION_REPORT.md) | 方法探索不等于已证实某种物理源 |
| 补齐原始数据后的核验 | [完整数据复核](mentor_aligned_raw_completion_v3/RAW_COMPLETION_REPORT.md) | 区分文件内统计、跨文件复现与独立检验 |
| 阴极实验新增方法复核 | [报告](cathodic_mentor_methods_v1/CATHODIC_MENTOR_METHODS_REPORT.md) | 不把探索结果改写为稳定检出 |
| 相干、检测能力与误差审计 | [相干审计](coherence_precision_audit_20260908/AUDIT_REPORT.md)、[结果及漏判](thesis_completion_20260908/RESULTS_AND_MISSES.md) | 结果阈值依赖背景和验证方案 |
| 电极间距及背景阈值后续 | [9月18日报告](thesis_followup_20260915/研究进展与间隙检出分析报告_20260918.md) | 绝对输入解释还须结合9月28日源端口核验 |
| 9月21日连续启停 | [新数据报告](20260921_switching/9月21日新数据分析报告.md) | 设备运行变化不等于水流独立归因 |
| 通道诊断 | [逐通道报告](20260922_channel_diagnosis/逐通道贡献与漏判诊断.md) | 通道状态按记录/时段判断 |
| 状态识别候选 | [基础版](20260922_recognizer/使用说明与验证.md)、[健康通道融合](20260922_health_fusion/候选版说明.md) | 开发集探索结果，不是新批次目标识别保证 |
| 背景与实验映射理论 | [参考计算](background_field_reference_20260927/README.md)、[最新链条审查](../research_materials/00_chain_review/研究链条审查与推进依据_20260928.md) | 条件模型，尚缺实物输入/接收标定 |

早期根目录监测能力报告和`legacy_approximation_snapshot`为历史材料，不覆盖较新的审计和修订。原始数据保留状态见`preservation_20260808`；本次Git整理未删除任何原始数据，也不是新的删除授权。
