# 三维水循环实验

| 版本 | 内容 | 工程或说明 |
|---|---|---|
| V1、V2 | 水桶、管路、泵、变频器、测点的纯几何；V2简化桶和泵 | [V1](../../models/water_system_3d_geometry_v1.mph)、[V2](../../models/water_system_3d_geometry_v2.mph) |
| V3、V4 | 三维外场；分开电机电缆、墙内供电和组合工况 | [V3已求解](../../models/water_system_3d_electric_field_v3_solved.mph)、[V4已求解](../../models/water_system_3d_source_decomposition_v4_solved.mph) |
| V5、V6 | 变频器30/50 Hz基波及4/8/12 kHz等效载波；独立泵壳共模 | [V5已求解](../../models/water_system_3d_vfd_spectrum_v5_solved.mph)、[V6已求解](../../models/water_system_3d_pump_source_v6_solved.mph) |
| V7 | 等效水路SST稳态压降与薄双电层流动电势 | [V7已求解](../../models/water_loop_streaming_potential_v7_solved.mph) |
| V8、V9 | 四源外场与时域重建；V9加入门洞、玻璃和金属框，地板修正版覆盖玻璃长度 | [V8已求解](../../models/water_system_3d_integrated_sources_v8_solved.mph)、[V9地板修正版](../../models/water_system_3d_doorway_environment_v9_solved_floor_fixed.mph) |
| V10 | 3.1 s水力脉动、幅值参数扫描与外场换算 | [末工况求解工程](../../models/water_loop_pulsation_v10_last_solution.mph)、[扫描说明](../../docs/水流脉动3.1s参数扫描V10说明.md) |
| V11、V12 | 源假设审计与实验频段对照，无独立新工程 | [V11](../../docs/nonwater_source_audit_v11.md)、[V12](../../docs/nonwater_model_experiment_comparison_v12.md) |
| V13、V14 | 电缆差模、单位共模；V14增加机壳及PE回流磁场、感应场 | [V13已求解](../../models/water_system_3d_minimal_electric_v13_solved.mph)、[V14已求解](../../models/water_system_3d_two_source_v14_solved.mph) |
| V13、V14补算 | 保持激励与观测方向，增加距桶外壁0.5 m的空气点 | [带新测点的工程与全频段结果](../lab_cathodic/rectangular_tank_v2/legacy_half_meter/README.md) |

V9用于查看完整布置；V10用于水流脉动；V14用于代表性电学源。高频单位传递需要实测激励才可换算现场绝对场强。[返回总目录](../../README.md)
