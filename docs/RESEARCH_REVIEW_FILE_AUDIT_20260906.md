# 全目录与研究材料核查清单
> 历史文件审计，非当前总纲（2026-09-26标注）。本文件引用的9月6日旧全局复审已归入[规划清理快照](../archive/snapshots/thesis_planning_20260926/README.md)，按ZIP内原路径查阅；当前方向见[论文总体判断与写作主线](论文总体判断与写作主线.md)。
日期：2026年9月6日

本清单记录材料覆盖范围和版本问题。全目录清点不等于逐个阅读原始波形、每张图片和每个依赖文件。主汇报只使用可追溯的关键证据。

## 根目录各目录

| 目录 | 文件数 | 研究作用与核查范围 |
|---|---:|---|
| [$build](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/$build>) | 16 | LaTeX/PDF构建副本，非独立研究成果。 |
| [.git](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/.git>) | 11381 | 版本存储；不作研究内容逐对象读取。 |
| [.pytest_cache](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/local/test_cache/pre_migration>) | 6 | 测试缓存。 |
| [26.8.12汇报_加图_PSD对比_颜色还原](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/26.8.12汇报_加图_PSD对比_颜色还原>) | 47 | 旧PPT渲染页，不能仅凭页图日期判断所对应最新版本。 |
| [26.8.12汇报_阴极保护实验补充](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/26.8.12汇报_阴极保护实验补充>) | 6 | 阴极补充PPT渲染页。 |
| [analysis_out](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/analysis/legacy_pipeline>) | 7424 | 早期特征、QC、背景和大量图表；阅读总报告，抽查与最新结论的差异。 |
| [analysis_package_44_6_9_non_vac_minimal](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/analysis_package_44_6_9_non_vac_minimal>) | 192 | 非真空脉冲早期可交付包；目录/说明索引，不能替代后期完整复核。 |
| [analysis_package_44_6_9_vac_first3_minimal](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/analysis_package_44_6_9_vac_first3_minimal>) | 410 | 真空脉冲早期包；first3代表早期范围，不能当全部数据。 |
| [calculation and paper](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/archive/legacy_theory>) | 219 | 论文Word/LaTeX、源项理论包与PDF；检查章节实质完成度与理论边界。 |
| [comsol](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/simulation>) | 374 | 模型、建模脚本、参数说明、CSV/图片及现场照片；重点V10/V13/V14与阴极V4。未重新求解mph。 |
| [config](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/config>) | 4 | 运行参数与路径配置；属于复现基础，不直接提供研究结论。 |
| [docs](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/docs>) | 23 | 上下文、方法、计划与交接；今天交接并非所有数值的最终依据。 |
| [logs](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/local/logs>) | 45 | 运行记录，不当科学结果。 |
| [results](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/analysis>) | 2081 | 主要专题证据区；重点核对原始补全v3、旧阴极、8月6日数表、历史与近似报告。 |
| [scripts](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/scripts>) | 84 | 专题精确归档、原始补全及阴极方法；核对关键相干采样与识别逻辑。 |
| [src](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/src>) | 201 | 通用采集转换、特征、质检、流水线与导出；检查结构及入口，未逐行审计全部代码。 |
| [tests](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/tests>) | 52 | 单元/冒烟测试；仅清点，本轮未重跑。 |
| [__pycache__](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/local/python_cache/pre_migration>) | 1 | Python缓存。 |
| [.codex_tmp](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/local/workbench>) | 17844 | 工具运行缓存。 |
| [articles](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/research/literature>) | 22 | 11篇PDF与11份逐段摘要；属于文献基础，未将文献结果作为本人实验成果。 |
| [third_party](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/local/third_party>) | 351 | 第三方UVM代码等，未发现其直接支持本课题物理结论。 |
| [tmp](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/local/tmp>) | 47970 | 历史PPT修改、渲染、依赖及本轮审阅中间件；大量文件为重复产物。 |

计数来自本轮开始时的递归清点，包含构建/依赖/缓存；不能用文件数量衡量工作量。

## 根目录独立文件

7份PPT全部进行文本抽取与版本比较；`information.md`属于开题背景材料，`PROJECT_STATE.md`为6月历史状态，`AGENT.md`为项目操作约束。两份VD230说明书为设备资料，本轮未重新逐页审核参数。其他日志、JSON与inspect文件为运行或渲染记录。

## 外部相关目录

- [汇报ppt](<C:/Users/17584/Documents/ALearning/Project/汇报ppt>)：31份PPT，包含模板、论证性实验框架和多次汇报。
- [paper](<C:/Users/17584/Documents/ALearning/Project/paper>)：7份Word，已抽取文本；两个同名论文稿与工作区副本SHA-256一致。开题和周报用于恢复原研究目标与计划。
- [Notebook](<C:/Users/17584/Documents/ALearning/Project/Notebook>)：已做相关文档类型搜索，本轮未发现需取代当前结论的对应文档。
- [硕士研究生学位论文.pdf](<C:/Users/17584/Documents/ALearning/Project/硕士研究生学位论文.pdf>)：98页，属于管颖添的等离子体课题；检查摘要、总结和相关分类内容，定位为参考研究。
- `D:/Lab/raw/raw`：今天交接指明的原始数据位置；检查了D:/Lab目录及相关文档路径，本轮未读取全量TDMS。历史E盘路径不能默认可用。

## PPT清单

| 文件 | 页数 | 核查定位 |
|---|---:|---|
| [25.12.15汇报-水下仿真论文总结.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/25.12.15汇报-水下仿真论文总结.pptx>) | 34 | 历次研究汇报；文本纳入研究历程核对。 |
| [25.12.1汇报-阶段总结报告.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/25.12.1汇报-阶段总结报告.pptx>) | 42 | 历次研究汇报；文本纳入研究历程核对。 |
| [25.12.1汇报v0.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/25.12.1汇报v0.pptx>) | 38 | 历次研究汇报；文本纳入研究历程核对。 |
| [25.12.8汇报-COMSOL仿真.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/25.12.8汇报-COMSOL仿真.pptx>) | 35 | 历次研究汇报；文本纳入研究历程核对。 |
| [25.3.4汇报.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/25.3.4汇报.pptx>) | 14 | 历次研究汇报；文本纳入研究历程核对。 |
| [25.3.7汇报.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/25.3.7汇报.pptx>) | 13 | 历次研究汇报；文本纳入研究历程核对。 |
| [25.5.16汇报.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/25.5.16汇报.pptx>) | 22 | 历次研究汇报；文本纳入研究历程核对。 |
| [25.5.23汇报.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/25.5.23汇报.pptx>) | 20 | 历次研究汇报；文本纳入研究历程核对。 |
| [25.7.19汇报.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/25.7.19汇报.pptx>) | 16 | 历次研究汇报；文本纳入研究历程核对。 |
| [25.7.24汇报.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/25.7.24汇报.pptx>) | 18 | 历次研究汇报；文本纳入研究历程核对。 |
| [25.8.25汇报.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/25.8.25汇报.pptx>) | 20 | 历次研究汇报；文本纳入研究历程核对。 |
| [25.8.31汇报.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/25.8.31汇报.pptx>) | 24 | 历次研究汇报；文本纳入研究历程核对。 |
| [26.1.12汇报-计划.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.1.12汇报-计划.pptx>) | 11 | 历次研究汇报；文本纳入研究历程核对。 |
| [26.1.20汇报-光谱分析.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.1.20汇报-光谱分析.pptx>) | 15 | OES/等离子体诊断支线调研，不并入水流检出证据。 |
| [26.3.27汇报-进展 .pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.3.27汇报-进展 .pptx>) | 18 | 历次研究汇报；文本纳入研究历程核对。 |
| [26.4.13汇报-信号处理.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.4.13汇报-信号处理.pptx>) | 25 | 历次研究汇报；文本纳入研究历程核对。 |
| [26.5.12实验计划.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.5.12实验计划.pptx>) | 13 | 历次研究汇报；文本纳入研究历程核对。 |
| [26.5.12汇报-毕业设计总计划.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.5.12汇报-毕业设计总计划.pptx>) | 22 | 历次研究汇报；文本纳入研究历程核对。 |
| [26.5.18汇报-进展.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.5.18汇报-进展.pptx>) | 15 | 历次研究汇报；文本纳入研究历程核对。 |
| [26.5.27汇报-背景组信号分析.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.5.27汇报-背景组信号分析.pptx>) | 23 | 历次研究汇报；文本纳入研究历程核对。 |
| [26.5.7汇报-ANSYS .pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.5.7汇报-ANSYS .pptx>) | 15 | 工具与算例学习，不能等同正式多物理场验证。 |
| [26.6.17汇报-放电实验信号分析.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.6.17汇报-放电实验信号分析.pptx>) | 22 | 历次研究汇报；文本纳入研究历程核对。 |
| [26.6.8汇报-实验组信号分析.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.6.8汇报-实验组信号分析.pptx>) | 14 | 历次研究汇报；文本纳入研究历程核对。 |
| [26.7.15汇报-实验设计.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.7.15汇报-实验设计.pptx>) | 8 | 历次研究汇报；文本纳入研究历程核对。 |
| [26.7.22汇报.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.7.22汇报.pptx>) | 8 | 历次研究汇报；文本纳入研究历程核对。 |
| [26.7.31汇报.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.7.31汇报.pptx>) | 12 | 历次研究汇报；文本纳入研究历程核对。 |
| [26.8.12汇报.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.8.12汇报.pptx>) | 29 | 历次研究汇报；文本纳入研究历程核对。 |
| [26.99.99汇报-信号处理.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/26.99.99汇报-信号处理.pptx>) | 29 | 信号处理工作稿，文件名不是有效实验日期。 |
| [上海交通大学16：9模板.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/上海交通大学16：9模板.pptx>) | 29 | 模板材料，排除为独立研究成果。 |
| [探测感知通用模板.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/探测感知通用模板.pptx>) | 11 | 模板材料，排除为独立研究成果。 |
| [论证性实验.pptx](<C:/Users/17584/Documents/ALearning/Project/汇报ppt/论证性实验.pptx>) | 17 | 大量实验照片/结论占位，属于论证框架，不能视为已验证实验。 |
| [26.8.12汇报.pptx](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/26.8.12汇报.pptx>) | 29 | 同次8月汇报的版本/补充，比较文本变化，不重复计为实验。 |
| [26.8.12汇报_加图.pptx](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/26.8.12汇报_加图.pptx>) | 45 | 同次8月汇报的版本/补充，比较文本变化，不重复计为实验。 |
| [26.8.12汇报_加图_PSD对比.pptx](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/26.8.12汇报_加图_PSD对比.pptx>) | 47 | 同次8月汇报的版本/补充，比较文本变化，不重复计为实验。 |
| [26.8.12汇报_加图_PSD对比_颜色还原.pptx](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/26.8.12汇报_加图_PSD对比_颜色还原.pptx>) | 52 | 同次8月汇报的版本/补充，比较文本变化，不重复计为实验。 |
| [26.8.12汇报_加图_PSD对比_颜色还原_三图更新.pptx](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/26.8.12汇报_加图_PSD对比_颜色还原_三图更新.pptx>) | 64 | 64页综合材料；当前关键PPT，核对数值/模型/阴极几何。 |
| [26.8.12汇报_加图_局部峰对比.pptx](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/26.8.12汇报_加图_局部峰对比.pptx>) | 47 | 同次8月汇报的版本/补充，比较文本变化，不重复计为实验。 |
| [26.8.12汇报_阴极保护实验补充.pptx](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/26.8.12汇报_阴极保护实验补充.pptx>) | 5 | 同次8月汇报的版本/补充，比较文本变化，不重复计为实验。 |

38份PPT共921页，存在大量重复；进行了全部可提取文本的索引和重点内容复核，未逐页视觉检查全部PPT。

## 本次最重要的版本问题

1. 今天交接、8月6日专题文字和旧能力报告仍含2–4.5 dB探测器差异；当前换位CSV和更新PPT为高频约−0.25至−0.49 dB。已在新汇报标明，不覆盖旧文件。
2. 同一个实验结果目录里的文字报告与CSV、manifest可能属于不同处理阶段；不能只按目录判断版本一致。
3. V10已完成2%–50%扫描；V13/V14已使用单位源传递，今天交接仍主要展示早期模型结果。
4. 阴极模型V4使用20 mm表面间隙与较早I–V点；实验总结为约10 mm，拟改300 mm。应按批次确认几何与实际工作点。
5. 64页PPT中的载波最强峰2/12与原始补全的梳状模板5/12不是同一检验。
6. “全记录相干”为全程分布窗口，不是连续所有采样点；全段PSD与它应分开描述。
7. 8个分析层级包含同场探测器，独立性需要按真实批次复核；现有p值按原定义引用。
8. 今日交接末尾“已经可靠证明”比正文探索性识别更强；新汇报采用限定批次与候选的表述。

## 本轮执行与产物

执行了rg文件搜索、递归目录/类型清点、OOXML文本抽取、PDF文本提取及关键页面渲染、局部图像查看、同名稿哈希比对、CSV与脚本核对。未重跑全量分析、未重求COMSOL、未修改论文/PPT/旧报告/原始数据。
- 新书面汇报：[RESEARCH_PROGRESS_REVIEW_20260906.md](<C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/docs/RESEARCH_PROGRESS_REVIEW_20260906.md>)
- 本核查清单：`RESEARCH_REVIEW_FILE_AUDIT_20260906.md`。
- 审阅脚本、文本索引与中间图片在`local/tmp/research_review_20260906/`，不作为研究新数据。
- 尚待解决：外场标定、真实采集独立性、不同模型几何/I–V一致性、新间隙数据、论文结果章节补写。
