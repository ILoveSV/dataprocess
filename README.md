# DataProcess

水下弱电目标研究的数据处理、实验归因、理论计算与 COMSOL 建模仓库。

**当前进展先看 [PROJECT_STATE.md](PROJECT_STATE.md)，研究依据先看 [研究资料汇总](research/README.md)。** 历史报告按日期保留，不代表每份旧结论仍有效。设备状态识别不等于水流/舰艇目标检出，条件模型不等于探测器绝对标定。

## 项目导航

| 内容 | 位置 | 使用方式 |
|---|---|---|
| 当前方向、导师要求、论文定位 | [docs](docs/README.md) | 先读当前主线，再查历史方法说明 |
| 文献、理论计算、COMSOL 与实验映射 | [research](research/README.md) | 理论和仿真的统一入口，与数据分析分开 |
| 按日期组织的实验批次 | [experiments](experiments/README.md) | 工况、批次报告与批次级结果 |
| 跨实验分析与验证证据 | [analysis](analysis/README.md) | 精简报告、表、图；大缓存保留本地 |
| 数据处理基础模块 | [src](src) | 保持原有模块和流水线结构 |
| 分批分析、归档、建模与报告脚本 | [scripts](scripts/README.md) | 按任务选择，不全量自动执行 |
| 单元测试和轻量验证 | [tests](tests) | 不替代真实实验有效性验证 |
| COMSOL 建模与轻量结果 | [research/simulation](research/simulation/README.md) | Java 源程序、说明、导出表；MPH 留本地 |
| 文献及阅读笔记 | [research/literature](research/literature/README.md) | 来源材料与本文结论分开 |
| 论文工程 | [thesis](thesis/README.md) | 当前写作在 `论文终稿/`，旧工程与章节稿在 `history/` |
| 历史分析汇总 | [analysis/legacy_pipeline](analysis/legacy_pipeline/README.md) | 小型报告与表；不上传全量特征矩阵 |
| 汇报与交付文件 | [deliverables](deliverables/README.md) | Office 原稿和渲染产物默认仅保留本地 |
| 冻结历史与快照 | [archive](archive/README.md) | 追溯用，不作为当前结论入口 |
| 本机缓存、日志和依赖 | [local](local/README.md) | 不纳入 Git，不作为研究证据 |

## 环境与检查

建议 Python 3.10+。`requirements.txt` 列出基础分析与测试依赖，`requirements-research.txt` 是波形分解及文档生成等可选依赖；这是依赖清单，不是已验证的精确环境锁文件。COMSOL、FFmpeg 和 LaTeX 等外部程序按对应任务单独配置。

```powershell
python -m pip install -r requirements.txt
python -m pytest tests -q
python tools/repository_audit.py
```

部分研究方法需要额外依赖、原始数据或本地模型，不能假设一次安装就能完整重现全部历史处理。读取原始 TDMS 前检查 `config/` 及目标脚本里的数据路径、通道和工况定义。不要直接启动 `run.py` 代替上述检查。

2026-09-29目录迁移后检查：根目录测试113通过、2项原有背景对照测试失败；目录审计规则另行复核。详见[迁移说明](docs/repository/本地目录归档整理_20260929.md)。

无需原始数据的最新理论核验：

```powershell
python -m unittest tests.test_source_constraints_20260928 tests.test_chain_audit_20260928 tests.test_background_field_reference_20260927 -q
python research/00_chain_review/chain_audit.py
python research/01_vessel_background/source_constraints/audit_source_constraints.py
```

## Git 与数据边界

- 本次同步分支为 **`part1`**；远端默认分支 `main` 不在本次自动合并范围内。
- Git 保存代码、研究报告、精简结果表/图、参数和来源信息，不是原始实验数据备份。
- 原始采集文件、录音录像、大型数组、求解后的 MPH、Office 原稿、临时渲染和本地依赖不上传。
- `.gitignore` 不会删除本地文件；已上传过的旧文件即使停止跟踪，仍在 Git 历史中。本次不重写历史。
- 研究现状和使用边界见 [PROJECT_STATE.md](PROJECT_STATE.md)，目录迁移见 [迁移说明](docs/repository/本地目录归档整理_20260929.md)。
