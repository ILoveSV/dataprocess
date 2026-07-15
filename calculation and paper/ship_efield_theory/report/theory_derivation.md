# 舰艇低频电场理论估算计算说明

本计算只用于水下潜艇/舰艇低频电场的理论量级估算。所有源项均采用公开文献中常见的等效模型，不代表任何真实型号平台，也不做 COMSOL、有限元、真实几何建模或实验拟合。由于暂未给出 MEMS 标定参数和实测噪声底，接收端与探测距离均保持参数化表达。

## Step 0：坐标系、几何关系与运动模型

### 1. 本步目的

建立匀速直线通过固定接收点时的距离模型。

### 2. 输入参数

`R_0`、`v`、`t`。

### 3. 变量定义

`R(t)` 为源中心到接收点的距离。

### 4. 理论公式

```latex
R(t)=\sqrt{R_0^2+v^2t^2}
```

### 5. 计算流程

对多个最近通过距离和默认速度 `v=5 m/s` 扫描时间序列。

### 6. 输出结果

`geometry_range_vs_time.csv`，`range_vs_time.png`。

### 7. 适用条件与边界

不考虑加速度、转向、姿态变化和海流。

### 8. 本步结论

`R(t)` 关于 `t=0` 对称，并在 `t=0` 取得最小值 `R_0`。

## Step 1：导电海水准静态控制方程

### 1. 本步目的

固定低频/准静态电场计算的控制方程和物理常数。

### 2. 输入参数

`\sigma`、`\rho_I(\mathbf r)`、`\varphi`。

### 3. 变量定义

`\varphi` 为电势，`\mathbf E` 为电场，`\mathbf J` 为导电电流密度。

### 4. 理论公式

```latex
\nabla\cdot(\sigma\nabla\varphi)=-\rho_I
```

```latex
\mathbf E=-\nabla\varphi,\qquad \mathbf J=\sigma\mathbf E
```

均匀各向同性海水中：

```latex
\nabla^2\varphi=-\frac{\rho_I}{\sigma}
```

### 5. 计算流程

输出控制方程表和默认物理常数表。

### 6. 输出结果

`control_equations.csv`，`physical_constants.csv`。

### 7. 适用条件与边界

不处理完整 Maxwell 方程组、高频辐射和真实金属-海水界面非线性极化曲线。

### 8. 本步结论

后续模型均基于低频准静态导电介质近似。

## Step 2：舰艇源项等效模型

### 1. 本步目的

把复杂电化学源项参数化为多点电流源与等效电流偶极矩。

### 2. 输入参数

`I_k`、`\mathbf r_k`。

### 3. 变量定义

`\mathbf P` 为等效电流偶极矩，单位 `A m`。

### 4. 理论公式

```latex
\rho_I(\mathbf r)=\sum_{k=1}^{N}I_k\delta(\mathbf r-\mathbf r_k)
```

```latex
\sum_{k=1}^{N}I_k=0
```

```latex
\mathbf P=\sum_{k=1}^{N}I_k\mathbf r_k
```

### 5. 计算流程

用正负点电流源示例验证 `P=IL` 的量纲关系。

### 6. 输出结果

`source_dipole_examples.csv`，`source_dipole_moment_vs_separation.png`。

### 7. 适用条件与边界

不拟合真实舰艇源分布，不给出真实 ICCP 电流或涂层参数。

### 8. 本步结论

`P` 是理论等效参数，只用于量级扫描。

## Step 3：UEP/ICCP 静态等效电流偶极子场

### 1. 本步目的

估算 UEP/ICCP 类静态低频电场的远场量级。

### 2. 输入参数

`P`、`\sigma`、`R`、`C_\theta`。

### 3. 变量定义

`C_\theta` 表示方向因子；默认取 1 用于保守的量级上界比较。

### 4. 理论公式

```latex
\varphi(\mathbf r)\approx
\frac{\mathbf P\cdot\hat{\mathbf R}}{4\pi\sigma R^2}
```

```latex
E(R)=\frac{C_\theta P}{4\pi\sigma R^3}
```

### 5. 计算流程

扫描多个 `P` 和 `R`。

### 6. 输出结果

`static_dipole_scan.csv`，`E_vs_R_for_P.png`。

### 7. 适用条件与边界

只适用于远场近似和均匀无限海水；不考虑水面、海底、船体边界和涂层细节。

### 8. 本步结论

`E \propto P`，`E \propto R^{-3}`，`E \propto \sigma^{-1}`。

## Step 4：海水电导率敏感性

### 1. 本步目的

评估海水电导率变化对电场估算结果的影响。

### 2. 输入参数

`\sigma\in[3,6] S/m`、`P`、`R`。

### 3. 变量定义

`E_min` 与 `E_max` 分别对应较高和较低电导率下的电场估算。

### 4. 理论公式

```latex
E(R,\sigma)=\frac{C_\theta P}{4\pi\sigma R^3}
```

```latex
\frac{\partial \ln E}{\partial \ln \sigma}=-1
```

### 5. 计算流程

扫描 `sigma=3,4,5,6 S/m` 并绘制区间带。

### 6. 输出结果

`conductivity_sensitivity.csv`，`conductivity_sensitivity_band.png`。

### 7. 适用条件与边界

不使用盐度-温度-压力经验公式，不处理空间非均匀电导率。

### 8. 本步结论

电导率只改变幅值比例，不改变 `R^{-3}` 距离律。

## Step 5：低频皮肤深度与频率衰减

### 1. 本步目的

估算导电海水对不同频率扰动的附加衰减。

### 2. 输入参数

`f`、`\mu`、`\sigma`、`R`。

### 3. 变量定义

`\delta(f)` 为皮肤深度，`A_f` 为工程化衰减因子。

### 4. 理论公式

```latex
\delta(f)=\sqrt{\frac{1}{\pi f\mu\sigma}}
```

```latex
A_f(R,f)=\exp\left(-\frac{R}{\delta(f)}\right)
```

### 5. 计算流程

扫描 `0.1-100 Hz` 频率范围。

### 6. 输出结果

`skin_depth_scan.csv`，`skin_depth_vs_frequency.png`，`attenuation_vs_distance_by_frequency.png`。

### 7. 适用条件与边界

`A_f` 是工程化附加因子，不替代完整边界条件求解。

### 8. 本步结论

频率升高时，皮肤深度按 `f^{-1/2}` 下降。

## Step 6：轴频电场调制模型

### 1. 本步目的

把轴频电场视为 UEP/ICCP 等效偶极矩的周期调制分量。

### 2. 输入参数

`P_0`、`m_n`、`f_s`、`n`、`R`、`\sigma`。

### 3. 变量定义

无实测谐波信息时采用工程化假设：

```latex
m_n=\frac{m_1}{n}
```

### 4. 理论公式

```latex
E_{\mathrm{shaft},n}(R)=
m_n
\frac{C_\theta P_0}{4\pi\sigma R^3}
\exp\left[-\frac{R}{\delta(nf_s)}\right]
```

### 5. 计算流程

默认 `P_0=100 A m`、`f_s=3 Hz`、`m_1=0.03`，扫描 1-5 阶谐波。

### 6. 输出结果

`shaft_rate_scan.csv`，`shaft_rate_amplitude_by_range.png`，`shaft_rate_line_spectrum.png`。

### 7. 适用条件与边界

不模拟真实螺旋桨、轴承、接触电阻；`m_n` 不是实测值。

### 8. 本步结论

轴频模型给出可用于频域 SNR 比较的低频线谱分量。

## Step 7：移动目标时间包络

### 1. 本步目的

计算目标匀速经过固定点时的电场包络。

### 2. 输入参数

`R_0`、`v`、`P`、`\sigma`、`f_s`、`m_n`。

### 3. 变量定义

`E_env(t)` 是慢变包络，`E_shaft(t)` 是调制时间信号。

### 4. 理论公式

```latex
E_{\mathrm{env}}(t)=
\frac{C_\theta P}{4\pi\sigma [R_0^2+v^2t^2]^{3/2}}
```

```latex
E_{\mathrm{shaft}}(t)=
E_{\mathrm{env}}(t)
\sum_{n=1}^{N_h}m_n
\cos(2\pi n f_s t+\phi_n)
```

### 5. 计算流程

默认取 `R_0=300 m`、`v=5 m/s`、`P=100 A m`。

### 6. 输出结果

`moving_target_envelope.csv`，`moving_range_vs_time.png`，`moving_E_env_vs_time.png`，`moving_E_shaft_vs_time.png`。

### 7. 适用条件与边界

不考虑姿态变化、方向因子变化和边界反射。

### 8. 本步结论

包络在最近通过时刻达到最大，且关于 `t=0` 对称。

## Step 8：多通道空间差分与阵列观测模型

### 1. 本步目的

将局部电场转换为小基线电压差估算。

### 2. 输入参数

`\mathbf E`、`\mathbf r_i-\mathbf r_j`。

### 3. 变量定义

`\Delta V_{ij}` 为两个接收点之间的电势差。

### 4. 理论公式

```latex
\Delta V_{ij}(t)\approx
-\mathbf E(\mathbf r_c,t)\cdot(\mathbf r_i-\mathbf r_j)
```

```latex
G_{ij}(t)=\frac{\Delta V_{ij}(t)}{|\mathbf r_i-\mathbf r_j|}
```

### 5. 计算流程

假设电场沿 `x` 方向，比较 `x` 向和 `y` 向基线响应。

### 6. 输出结果

`receiver_array_voltage.csv`，`receiver_array_deltaV_vs_time.png`。

### 7. 适用条件与边界

只对传统电势差阵列的小基线近似严格成立；对 MEMS 芯片只作为外场输入参考。

### 8. 本步结论

基线与电场平行时响应最大，垂直时近似为零。

## Step 9：MEMS 极化带效应接收响应模型

### 1. 本步目的

建立外部电场到芯片输出电压的参数化线性响应。

### 2. 输入参数

`E_i(t)`、`K_i`、`b_i(t)`、`n_i(t)`。

### 3. 变量定义

`K_i` 是待标定传递系数，单位可写作 `V/(V/m)`。

### 4. 理论公式

```latex
V_i(t)=K_iE_i(t)+b_i(t)+n_i(t)
```

```latex
\mathbf V(t)=\mathbf K\mathbf E(t)+\mathbf b(t)+\mathbf n(t)
```

### 5. 计算流程

扫描符号化/参数化 `K`，展示线性响应关系。

### 6. 输出结果

`mems_response_parameterized.csv`，`mems_response_parameterized.png`。

### 7. 适用条件与边界

没有标定参数时，不给出实际芯片输出电压绝对结论。

### 8. 本步结论

MEMS 输出层面的判断必须等待 `K` 和噪声底标定；当前只保留参数化接口。

## Step 10：背景噪声谱模型

### 1. 本步目的

建立可扫描的低频背景噪声谱模型。

### 2. 输入参数

`N_0`、`f_0`、`\alpha`、线谱峰位置和带宽。

### 3. 变量定义

`N_cont` 表示连续噪声，`N_line` 表示窄带线谱干扰。

### 4. 理论公式

```latex
N_{\mathrm{cont}}(f)=N_0\left(\frac{f}{f_0}\right)^{-\alpha}
```

```latex
N_{\mathrm{line}}(f)=\sum_k A_k g(f-kf_{\mathrm{power}})
```

其中 `g` 为窄带峰近似。

### 5. 计算流程

构造连续噪声和 50/60 Hz 线谱峰的示例曲线。

### 6. 输出结果

`noise_spectrum_examples.csv`，`noise_spectrum_examples.png`。

### 7. 适用条件与边界

没有实测噪声底时，本步只作为参数化示意，不给出实际探测结论。

### 8. 本步结论

低频噪声和工频峰会影响 SNR 判据，后续可替换为实测谱。

## Step 11：SNR 与最大可探测距离

### 1. 本步目的

在无 MEMS 标定和实测噪声底时，建立参数化 SNR 与 `R_max` 曲线。

### 2. 输入参数

`E(R,f)`、`E_min`、`M`、`B`、`T`、`L_loss`。

### 3. 变量定义

`E_min` 是等效场强阈值，不是实测芯片噪声。

### 4. 理论公式

```latex
\mathrm{SNR}(R,f)=
20\log_{10}\left[\frac{E(R,f)}{E_{\min}}\right]
```

```latex
R_{\max}\approx
\left[
\frac{C_\theta P m_n}
{4\pi\sigma E_{\min}}
\right]^{1/3}
```

考虑频率衰减时求解：

```latex
\frac{C_\theta P m_n}{4\pi\sigma R^3}
\exp\left(-\frac{R}{\delta(f)}\right)-E_{\min}=0
```

### 5. 计算流程

扫描 `E_min={1e-12,1e-11,1e-10,1e-9} V/m` 和多个 `P`。

### 6. 输出结果

`snr_range_scan.csv`，`SNR_vs_R.png`，`Rmax_vs_P.png`，`Rmax_vs_noise_floor.png`。

### 7. 适用条件与边界

`R_max` 只是参数化理论曲线，不是实际探测距离。

### 8. 本步结论

源强、调制系数和处理增益提高会增大 `R_max`；阈值和损耗提高会降低 `R_max`。

## Step 12：统一源项对比与结论边界

### 1. 本步目的

在同一物理量标准下比较不同距离、不同频率、不同源项的信号强度，为实验与仿真设计提供定量依据。

### 2. 输入参数

各源项的：

- `E_j(R)`：外部电场幅值；
- `f_j`：频率或特征频率；
- `E_min`：参数化等效场强阈值；
- `R`：统一距离网格；
- `Delta V`：1 m 小基线电压差近似。

### 3. 变量定义

同一距离下，以 UEP/ICCP 静态等效偶极子场作为幅值基准：

```latex
D_j(R)=20\log_{10}\frac{E_j(R)}{E_{\mathrm{static}}(R)}
```

### 4. 理论公式

```latex
\mathrm{SNR}_j(R)=20\log_{10}\frac{E_j(R)}{E_{\min}}
```

```latex
\Delta V_{1\mathrm{m}}(R)\approx E(R)\times1\ \mathrm{m}
```

```latex
f_{\mathrm{env}}(R)\approx\frac{v}{2\pi R}
```

### 5. 计算流程

在 `R=50,100,300,500,1000,3000 m` 上，统一计算：

1. UEP/ICCP 静态等效偶极子场；
2. 移动 UEP 包络；
3. 1 m 基线空间梯度可观测量；
4. 轴频 1-5 阶谐波；
5. 尾流局部量级和工频干扰参考。

### 6. 输出结果

`source_comparison_by_range.csv`，`source_comparison_pivot.csv`，`comparable_source_E_vs_R.png`，`source_frequency_strength_map.png`。

### 7. 适用条件与边界

只有 UEP/ICCP 静态场、移动包络、空间梯度和轴频谐波来自同一等效偶极子框架，可按距离直接比较。尾流/流动诱导电场缺少尾流几何和传播模型，工频泄漏是实验干扰项，二者不参与舰艇源项距离排序。

### 8. 本步结论

100 m 内可同时关注静态场、移动包络、空间梯度和轴频线谱；300 m 左右轴频基频仍可作为候选，高阶谐波显著变弱；1000 m 及以上应优先关注静态/慢变分量和低漂移测量能力。
