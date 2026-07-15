# COMSOL 工作目录

本目录集中保存本项目后续所有 COMSOL 建模资料。

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
- 已完成的二维阴极保护模型：`models/cathodic_protection_2d.mph`
- 二维模型结果：`results/cathodic_protection_2d/`

## 外部原始工程

以下原始大文件继续保留在 COMSOL 安装数据目录，不移动、不覆盖：

- `D:\COMSOL64\Multiphysics\data\水箱.mph`
- `D:\COMSOL64\Multiphysics\data\水加空气.mph`

后续新建和修改的工程统一写入本目录的 `models/`，不再写入 COMSOL 安装目录。
