# 公开来源与采用方式

本文档只记录用于计算边界的公开资料来源，不引入真实舰艇型号参数。

1. NOAA World Ocean Atlas 说明其数据包含温度、盐度等海洋气候态数据，可作为海水物性背景来源：<https://www.ncei.noaa.gov/products/world-ocean-atlas>
2. NOAA Sea Water 页面给出典型海水盐度接近 35 ppt，常见范围约 33-37 ppt：<https://www.noaa.gov/jetstream/ocean/sea-water>
3. Manoj et al., Electrical conductivity of the global ocean，给出全球海洋体积加权平均电导率 `3.31 ± 0.23 S/m`：<https://pmc.ncbi.nlm.nih.gov/articles/PMC6959386/>
4. Electromagnetic Geophysics, Attenuation and Skin Depth，列出海水电导率示例 `3.3 S/m`，并给出皮肤深度随频率、电导率变化的标准关系：<https://em.geosci.xyz/content/maxwell1_fundamentals/harmonic_planewaves_homogeneous/skindepth.html>
5. US EPA, Electromagnetic Signal Attenuation (Skin Depth)，说明皮肤深度是信号衰减到 `1/e` 的距离，并与频率和介质电导率有关：<https://www.epa.gov/environmental-geophysics/electromagnetic-signal-attenuation-skin-depth>
6. An analytical four-layer horizontal electric current dipole model for underwater electric potential，说明水平电流偶极子模型可用于船体腐蚀监测和 UEP 估算：<https://pmc.ncbi.nlm.nih.gov/articles/PMC9130128/>
7. Simulating Underwater Electric Field Signal of Ship Using the 3-D BEM，文中讨论舰船腐蚀电场的等效电偶极模型，并指出电偶极矩通常来自经验和文献，且会随损伤面积/位置变化：<https://www.jpier.org/ac_api/download.php?id=18092706>
8. Ship Shaft-Rate Electric Field Signal Denoising Method Based on MHA-VMD，说明轴频电场是 ELF 信号，基频与螺旋桨/轴转频相关：<https://www.mdpi.com/2077-1312/12/4/544>
9. Mixed Electric Field of Multi-Shaft Ship Based on Oxygen Mass Transfer，说明混合电场包含静电场与轴频电场，轴频分量来自腐蚀电流受轴系机械结构调制：<https://www.mdpi.com/2079-9292/11/22/3684>
10. Analysis and Measurement of Ship Shaft-Rate Magnetic Field in Air，公开摘要中给出轴频电磁场基频等于轴转频，典型范围 `1-7 Hz`：<https://www.jpier.org/ac_api/download.php?id=16091604>
11. Mixed Electric Field of Multi-Shaft Ship Based on Oxygen Mass Transfer Process under Turbulent Conditions，用于说明多轴舰船混合电场、腐蚀电场、轴系/湍流/氧传质耦合：<https://www.mdpi.com/2079-9292/11/22/3684>
12. Induced electromagnetic fields associated with large ship wakes，用于说明导电海水尾流穿越地磁场会产生诱导电磁信号：<https://www.sciencedirect.com/science/article/pii/0165212594900531>
13. Detection of the electromagnetic field induced by the wake of a ship moving in a random sea of finite depth，用于说明船舶尾流电磁场的可探测性依赖海况、谱特征和尾流模型：<https://link.springer.com/article/10.1007/s10665-010-9410-z>
14. Characteristics of Electric Field Induced by Oscillating Metal Cylinder in Seawater，用于补充水下电场测量/振荡金属体/50 Hz 相关实验背景：<https://www.mdpi.com/2076-3417/14/7/2873>

## 在本计算中的取值

- 海水电导率：采用 `3-6 S/m` 扫描，默认 `4 S/m`。该范围覆盖公开全球均值 `3.31 S/m` 附近，并保留温盐变化余量。
- 轴频基频：采用 `1-7 Hz` 扫描，默认 `3 Hz`。
- UEP 等效电流偶极矩：默认 `100 A m`，只作为公开理论估算参数。
- ICCP 等效电流偶极矩：默认 `300 A m`，只作为“较强外加保护电流源”的参数化参考。
- 尾流/流动诱导电场：采用 `E_wake0=3e-6 V/m`、`L_wake=300 m` 的工程参考模型，用于提示后续需要流体-电磁耦合仿真，不作为最终定论。
- 工频泄漏：采用 `50 Hz`、`1 m 处 1e-6 V/m` 的实验干扰参考，并加入皮肤深度衰减；不作为真实舰艇源项。
- 噪声底与 MEMS 灵敏度：暂未给定实测或标定数据，因此只做 `E_min` 参数化扫描。
