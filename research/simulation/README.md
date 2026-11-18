# COMSOL 工作目录

从下面三类进入项目。每类索引标明纯几何、已求解工程和用于核验的变体。

| 分类 | 主要内容 | 先打开 |
|---|---|---|
| [三维水循环实验](projects/water_circulation/README.md) | 实验场景、流动电势、水力脉动、电缆和泵壳外场 | [完整场景 V9](models/water_system_3d_doorway_environment_v9_solved_floor_fixed.mph)、[代表源 V14](models/water_system_3d_two_source_v14_solved.mph) |
| [桶内与水箱阴极放电](projects/lab_cathodic/README.md) | 原圆桶、方形浅水箱、电极间隙和桶外场 | [方形水箱 20 V 外场 V2](projects/lab_cathodic/rectangular_tank_v2/README.md)、[圆桶外场 V4](models/cathodic_protection_external_field_v4.mph) |
| [三维潜艇外场](projects/submarine_fields/README.md) | 单位电流传递、ICCP非线性极化与水下外场 | [潜艇 ICCP 10 A](../01_vessel_background/iccp_v1/models/submarine_iccp_base_10A.mph) |

Git保留建模源程序、说明和轻量导出结果，`.mph`、恢复文件及编译产物仅保留本地。[旧模型清单](../existing_comsol_model_index.csv)是迁移前的历史索引，打开模型时以上表各项目入口为准。[研究资料入口](../README.md)同时索引理论计算和 COMSOL。

## 目录结构

- `docs/`：需求、参数和建模说明。
- `models/`：正式 `.mph` 工程。
- `scripts/models/`：用于创建或更新模型的 COMSOL Java 脚本。
- `scripts/utilities/`：只读检查、导出和诊断工具。
- `results/`：图片、CSV、动画和求解结果。
- `references/photos/`：现场照片。
- `references/exported_models/`：从现有工程导出的 Java 建模历史，仅供分析参考。
- `build/`：编译产物、恢复文件和临时诊断模型，不作为正式成果。

## 工程位置

2026-11-12：原顶层 `simulation/` 整体移至 `research/simulation/`，内部结构不变。已有 Java 源码中的本机路径已更新；迁移前编译的 `.class` 仅作历史产物，运行前应由新路径的源码重新编译。仿真说明及计算结果留在本目录，实测分析仍在仓库顶层 `analysis/`。

7月7日的两个原始二维工程此前已移除，不列入工作入口。另建的铝板与石墨二维原型归入阴极放电的历史参考。
