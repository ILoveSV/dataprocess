# 三维潜艇外场

| 工程 | 内容 | 入口 |
|---|---|---|
| 通用艇体单位电流 | 50 m通用艇体、规定平衡电流源，计算水中传导场与水面上空气静电场 | [扩域工程](../../../01_vessel_background/comsol/wide.mph)、[数值核验](../../../01_vessel_background/数值结果与核验.md) |
| 三维潜艇 ICCP V1 | 四阳极、钢与青铜极化、浮置金属回流；0、5、10、20 A和数值对照 | [10 A已求解工程](../../../01_vessel_background/iccp_v1/models/submarine_iccp_base_10A.mph)、[工程与结果](../../../01_vessel_background/iccp_v1/README.md) |

ICCP V1求的是水下稳态外场；没有空气场、旋转或轴频调制。单位电流模型的空气场不能直接当作ICCP工程的空气场。[返回总目录](../../README.md)
