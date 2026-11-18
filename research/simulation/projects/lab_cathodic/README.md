# 桶内与水箱阴极放电

| 工程 | 内容 | 入口 |
|---|---|---|
| 方形浅水箱 V2 | 内宽20 cm、石墨正对窗口、20 V恒压与距外壁0.5 m空气场 | [布局、求解工程与对比](rectangular_tank_v2/README.md) |
| 方形浅水箱 V1 | 早期30 cm内宽、10 mA稳态箱内导电，无外场 | [历史工程与结果](rectangular_tank_v1/README.md) |
| 圆桶电极 V1 | 钢管窗口、石墨、支杆与桶盖；纯几何 | [电极组件](../../models/cathodic_protection_electrode_assembly_3d_v1.mph) |
| 圆桶内 V2、V3 | 170 L桶内导电；V3按20 mm净间距计算10、50、100、200 mA | [V2](../../models/cathodic_protection_tank_3d_preliminary_v2.mph)、[V3](../../models/cathodic_protection_tank_3d_current_sweep_v3.mph) |
| 圆桶外 V4 | 近静态单位差模外场，含桶、地板和引线 | [V4](../../models/cathodic_protection_external_field_v4.mph)、[说明](../../docs/阴极保护四档恒流与外部电场V4说明.md)、[补算0.5 m](rectangular_tank_v2/legacy_half_meter/README.md) |
| 全场景 V5 | 圆桶、泵、管路、变频器、门墙及电极；仅几何，无全场景联合解 | [V5](../../models/cathodic_protection_full_scene_geometry_v5.mph) |
| 间隙和外场核验 | 六档间隙、引线、供电边界、网格、外域及解析基准 | [历史核验说明](../../../../analysis/thesis_followup_20260915/COMSOL模型核验说明.md) |
| 二维历史原型 | 独立的铝板与石墨10 mA原型，和已删除的7月7日二维水箱工程不同 | [二维原型](../../models/cathodic_protection_2d.mph) |

[返回总目录](../../README.md)
