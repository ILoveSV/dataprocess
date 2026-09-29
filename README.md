# DataProcess

水下弱电目标研究的数据处理、实验归因、理论计算与 COMSOL 建模仓库。

**当前进展先看 [PROJECT_STATE.md](PROJECT_STATE.md)，研究依据先看 [研究资料汇总](research_materials/README.md)。** 历史报告按日期保留，不代表每份旧结论仍有效。设备状态识别不等于水流/舰艇目标检出，条件模型不等于探测器绝对标定。

## 项目导航

| 内容 | 位置 | 使用方式 |
|---|---|---|
| 当前方向、导师要求、论文定位 | [docs](docs/README.md) | 先读当前主线，再查历史方法说明 |
| 背景源、传播、实验输入与接收链核验 | [research_materials](research_materials/README.md) | 当前研究主入口 |
| 实验结果与验证证据 | [results](results/README.md) | 精简报告、表、图；大缓存保留本地 |
| 数据处理基础模块 | [src](src/) | 保持原有模块和流水线结构 |
| 分批分析、归档、建模与报告脚本 | [scripts](scripts/README.md) | 按任务选择，不全量自动执行 |
| 单元测试和轻量验证 | [tests](tests/) | 不替代真实实验有效性验证 |
| COMSOL 实验场景 | [comsol](comsol/README.md) | Java 源程序、说明、导出表；MPH 留本地 |
| 文献及阅读笔记 | [articles](articles/README.md) | 来源材料与本文结论分开 |
| 论文与早期理论工程 | [calculation and paper](calculation%20and%20paper/README.md) | 保留原路径；当前章节状态见子目录说明 |
| 历史分析汇总 | [analysis_out](analysis_out/README.md) | 小型报告与表；不上传全量特征矩阵 |
| 本地汇报、说明书与旧包位置 | [文件整理说明](docs/repository/整理与同步说明_20260928.md) | 查搬移清单，不修改文件内容 |

## 环境与检查

建议 Python 3.10+。`requirements.txt` 列出基础分析与测试依赖，`requirements-research.txt` 是波形分解及文档生成等可选依赖；这是依赖清单，不是已验证的精确环境锁文件。COMSOL、FFmpeg 和 LaTeX 等外部程序按对应任务单独配置。

```powershell
python -m pip install -r requirements.txt
python -m pytest tests -q
python tools/repository_audit.py
```

部分研究方法需要额外依赖、原始数据或本地模型，不能假设一次安装就能完整重现全部历史处理。读取原始 TDMS 前检查 `config/` 及目标脚本里的数据路径、通道和工况定义。不要直接启动 `run.py` 代替上述检查。

2026-09-29检查：根目录测试115通过、2项原有背景对照测试失败，尚不是全绿测试集；详见[同步说明](docs/repository/整理与同步说明_20260928.md)。

无需原始数据的最新理论核验：

```powershell
python -m unittest tests.test_source_constraints_20260928 tests.test_chain_audit_20260928 tests.test_background_field_reference_20260927 -q
python research_materials/00_chain_review/chain_audit.py
python research_materials/01_vessel_background/source_constraints/audit_source_constraints.py
```

## Git 与数据边界

- 本次同步分支为 **`part1`**；远端默认分支 `main` 不在本次自动合并范围内。
- Git 保存代码、研究报告、精简结果表/图、参数和来源信息，不是原始实验数据备份。
- 原始采集文件、录音录像、大型数组、求解后的 MPH、Office 原稿、临时渲染和本地依赖不上传。
- `.gitignore` 不会删除本地文件；已上传过的旧文件即使停止跟踪，仍在 Git 历史中。本次不重写历史。
- 研究现状和使用边界见 [PROJECT_STATE.md](PROJECT_STATE.md)，上传检查见 [同步说明](docs/repository/整理与同步说明_20260928.md)。
