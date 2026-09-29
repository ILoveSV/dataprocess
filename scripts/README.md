# 分析脚本导航

本目录保留原有文件名和导入关系。本次整理不改算法、阈值、实验标签或输出路径。

| 环节 | 入口/命名 | 数据需求 |
|---|---|---|
| 动态通道质量与完整归档 | `channel_quality.py`、`exact_tdms_archive.py`、`exact_analysis_metrics.py` | 原始 TDMS；按文件/时间判断坏道 |
| 早期实验与工况/载波扫描 | `analyze_20260512_*`、`analyze_20260731_*`、`analyze_20260806_*` | 对应批次原始数据或归档 |
| 旧阴极保护实验 | `analyze_20260811*`、`analyze_cathodic_*` | 对应批次；不擅自修改间距标签 |
| 导师建议的时域、多尺度与统计探索 | `analyze_mentor_*`、`analyze_pre_electrochemical_dynamics.py`、`analyze_raw_completion_identifiability.py` | 按脚本读取原始/精简归档 |
| 连续启停与通道诊断 | `analyze_20260921_*`、`audit_20260921_switching.py`、`diagnose_20260922_channels.py` | 9月连续记录及其缓存 |
| 状态识别候选 | `state_recognizer.py`、`health_fusion_recognizer.py` | 训练/验证和分组必须保留，不代表目标源检出 |
| 理论推演 | `background_field_reference_20260927.py`、`source_scale_groundwork_20260925.py` | 规定参数情景；最新限制见研究资料入口 |
| COMSOL 补充与核验 | `External*.java`、`Cathodic*.java`、`prepare_*`、`summarize_*` | COMSOL 及规定模型；MPH 未随 Git 发布 |
| 报告与结果检查 | `build_*`、`report_*`、`validate_*`、`verify_*` | 先检查各自输入文件和本机路径 |
| 资料保存 | `archive_tdms_tree.py`、`build_preservation_manifest.py`、`collect_research_materials_20260927.ps1` | 不与 Git 同步混同，不自动删除原始数据 |

最新源强/输入一致性程序在 [source_constraints](../research_materials/01_vessel_background/source_constraints/)，链条核验在 [00_chain_review](../research_materials/00_chain_review/)。

部分旧脚本含 `D:/Lab`、`E:/Lab` 或本地依赖路径。新机器应先核对路径、依赖和数据版本。此轮只整理和同步，未重新运行全量分析。
