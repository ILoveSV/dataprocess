# 背景接收场理论参考，2026-09-27

本目录是条件性理论预测，不是实验数据，也不是TC检测能力测量。主资料见[背景目标接收场强推演](../../docs/背景目标接收场强_参考理论推演_20260927.md)。

## 输入与输出

主参考为水下平衡电流源汇：I0=1 A、有效间距10 m、源深5 m、水电导率4 S/m。空气接收点高1 m，水中比较点深5 m，水平方向为源轴的侧向中垂面；距离从源中心起算。参数为本轮假设，不是具体目标实测值。

| 文件 | 含义 |
|---|---|
| reference_distance_dc.csv | 无限水体、水面两侧及有限水深的静态距离表 |
| modulation_with_validity.csv | 指定调制与频率的交流峰值/RMS；未通过感应预筛选时不报预测值 |
| frequency_validity.csv | 趋肤深度及L/δ预筛选，不是探测距离 |
| small_source_ideal_reference.csv | 开放水面小源参考，不是实际水桶预测 |
| parameter_sensitivity.csv | 电流、电导率、源深、接收高度的假设参数扫描 |
| net_source_cancellation.csv | 反向共址回路的代数算例，说明总电流不能替代净源矩 |
| 00至03的PNG/SVG | 参考几何、距离边界、调制适用性、参数敏感性 |
| calculation_manifest.json | 假设、输入与输出SHA-256，明确不是COMSOL新解或传感器标定 |
| validation.log | 本轮16项数学与实现测试的运行记录 |

三层海底结果仅是直流敏感性计算。低频复导纳解只应用于两半空间，另外用L/δ≤0.1筛选；通过不是误差保证，未通过不代表物理信号不存在。没有乘经验指数衰减冒充全电磁解。

## 复现

在项目根目录运行：

~~~powershell
& 'D:\Anaconda\python.exe' -X utf8 -m unittest tests.test_background_field_reference_20260927 -v
& 'D:\Anaconda\python.exe' -X utf8 scripts/background_field_reference_20260927.py
~~~

核验包括界面条件、负电位梯度、均匀介质退化、闭式解、缩放与相消、远区极限、镜像收敛及独立Hankel积分。全部4张PNG已检查坐标、单位、图例及标签。真实源幅相、海域参数、浮地/回流及TC传递函数没有由这些测试得到验证。

未改原始数据、旧分析主线、论文正文或已有COMSOL模型。
