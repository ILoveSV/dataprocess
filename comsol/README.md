# COMSOL 工作目录

本目录集中保存本项目后续所有 COMSOL 建模资料。

2026-09-28同步说明：Git保留建模源程序、说明和轻量导出结果，`.mph`、恢复文件及编译产物仅保留本地。已有模型索引见[研究资料模型清单](../research_materials/existing_comsol_model_index.csv)。最新舰艇背景模型及研究边界见[研究资料入口](../research_materials/README.md)，下列历史模型不等于实物绝对标定。

## 目录结构

- `docs/`：需求、参数和建模说明。
- `models/`：正式 `.mph` 工程。
- `scripts/models/`：用于创建或更新模型的 COMSOL Java 脚本。
- `scripts/utilities/`：只读检查、导出和诊断工具。
- `results/`：图片、CSV、动画和求解结果。
- `references/photos/`：现场照片。
- `references/exported_models/`：从现有工程导出的 Java 建模历史，仅供分析参考。
- `build/`：编译产物、恢复文件和临时诊断模型，不作为正式成果。

## 当前项目

- 三维水循环系统需求文档：`docs/三维水循环系统电场仿真参数汇总.md`
- 双代表源电学模型说明：`docs/双代表源电学模型V14说明.md`
- 双代表源已求解工程：`models/water_system_3d_two_source_v14_solved.mph`
- 已完成的二维阴极保护模型：`models/cathodic_protection_2d.mph`
- 二维模型结果：`results/cathodic_protection_2d/`

## 外部原始工程

以下原始大文件继续保留在 COMSOL 安装数据目录，不移动、不覆盖：

- `D:\COMSOL64\Multiphysics\data\水箱.mph`
- `D:\COMSOL64\Multiphysics\data\水加空气.mph`

后续新建和修改的工程统一写入本目录的 `models/`，不再写入 COMSOL 安装目录。
