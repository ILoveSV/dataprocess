# 三维潜艇 ICCP 初版

本目录独立保存参数、曲线、建模脚本、COMSOL工程与结果，不修改旧的单位电流传递模型。

优先打开：

- `models/submarine_iccp_base_10A.mph`：10A三维算例，带艇体极化电位和水下场图。
- [初版模型说明与结果](初版模型说明与结果.md)：回路、电位、距离表与数值检查。
- [参数与来源](PARAMETER_SOURCES.md)：哪些取自论文，哪些为通用几何假设。
- [集中参数](parameters.properties)：后续脚本重算的参数入口。
- `results/submarine_iccp_3d.png`：COMSOL原生三维艇表极化电位图。
- `results/external_field_plane.png`：艇下平面外场。
- `results/current_and_distance_comparison.png`：供电工况与距离响应对比。
- `results/field_distance_comparison.csv`：整理后的分量与场强表。
- `results/iccp_induced_field_change.csv`：相对ICCP关闭状态的电场矢量变化。
- `results/manifest.json`、`results/validation.json`：来源哈希、回路与数值核验记录。

## 修改与重算

可在COMSOL中直接修改全局参数并重新构建/求解。脚本重算时，先编辑`parameters.properties`，再在PowerShell中运行：

```powershell
.\run_model.ps1
```

默认扫描0、0.5倍、1倍、2倍`I_total`，初版对应0、5、10、20A；另对标称电流计算0.75倍网格尺寸和1.5倍水域尺寸的对照。运行会覆盖本目录自己生成的同名工程和结果。

`extract_polarization.py`使用Bundled Python读取本地论文矢量曲线，生成CSV和`ICCPInputs.java`。后者是自动生成文件，手工修改应放在参数文件或提取程序中。`SubmarineICCP.java`使用COMSOL模型API完成几何、网格、非线性边界、浮动金属电位约束、求解和导出；`summarize_results.py`使用Anaconda的NumPy/Matplotlib整理结果；`validate_results.py`检查电流平衡、采样位置和场分量一致性。

本轮采用阳极湿表面的均匀给定电流密度近似，未求阳极反应过电位、电源输出电压或反馈控制动态。钢/螺旋桨界面使用非线性极化关系，艇体和螺旋桨按理想金属连接共同回流。模型只求水下稳态场。
