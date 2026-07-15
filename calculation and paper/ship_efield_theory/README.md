# 舰艇低频电场理论估算计算包

本目录只做公开参数范围下的理论量级估算，不做 COMSOL、FEM/BEM/FDTD、真实潜艇几何建模或实验数据拟合。

## 已实现的完整计算链

- Step 0：几何关系与最近通过距离 `R(t)`。
- Step 1：导电海水准静态控制方程与常数表。
- Step 2：多点电流源到等效电流偶极矩。
- Step 3：UEP/ICCP 等效静态电流偶极子场 `E(R)`。
- Step 4：海水电导率敏感性。
- Step 5：导电海水低频皮肤深度与工程化频率衰减。
- Step 6：轴频电场调制分量估算。
- Step 7：移动目标时间包络。
- Step 8：多通道空间差分与小基线电压。
- Step 9：MEMS 线性参数化响应。
- Step 10：背景噪声谱参数化模型。
- Step 11：参数化 SNR 与最大可探测距离。
- Step 12：源项理论研究优先级排序。

## 运行

```powershell
python scripts/run_all.py
python -m pytest tests
```

输出位于：

- `outputs/tables/`
- `outputs/figures/`

## 参数边界

当前默认参数只用于理论扫描。等效偶极矩、调制系数、噪声底和探测阈值都不是任何真实潜艇或真实 MEMS 芯片的标定值。
