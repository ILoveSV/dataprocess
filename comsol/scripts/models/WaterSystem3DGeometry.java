import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class WaterSystem3DGeometry {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\comsol";
  private static final String MODEL_FILE = ROOT + "\\models\\water_system_3d_geometry_v2.mph";

  private static void color(Model model, String tag, double r, double g, double b) {
    model.component("comp1").geom("geom1").feature(tag).set("selresult", true);
    model.component("comp1").geom("geom1").feature(tag).set("color", "custom");
    model.component("comp1").geom("geom1").feature(tag)
        .set("customcolor", new double[] {r, g, b});
  }

  private static void cylinder(
      Model model, String tag, String label, double radius, double[] from, double[] to,
      double r, double g, double b) {
    double dx = to[0] - from[0];
    double dy = to[1] - from[1];
    double dz = to[2] - from[2];
    double length = Math.sqrt(dx * dx + dy * dy + dz * dz);
    model.component("comp1").geom("geom1").create(tag, "Cylinder");
    model.component("comp1").geom("geom1").feature(tag).label(label);
    model.component("comp1").geom("geom1").feature(tag).set("r", radius);
    model.component("comp1").geom("geom1").feature(tag).set("h", length);
    model.component("comp1").geom("geom1").feature(tag).set("pos", from);
    model.component("comp1").geom("geom1").feature(tag)
        .set("axis", new double[] {dx, dy, dz});
    color(model, tag, r, g, b);
  }

  private static void sphere(
      Model model, String tag, String label, double radius, double[] pos,
      double r, double g, double b) {
    model.component("comp1").geom("geom1").create(tag, "Sphere");
    model.component("comp1").geom("geom1").feature(tag).label(label);
    model.component("comp1").geom("geom1").feature(tag).set("r", radius);
    model.component("comp1").geom("geom1").feature(tag).set("pos", pos);
    color(model, tag, r, g, b);
  }

  private static void block(
      Model model, String tag, String label, double[] size, double[] pos,
      double r, double g, double b) {
    model.component("comp1").geom("geom1").create(tag, "Block");
    model.component("comp1").geom("geom1").feature(tag).label(label);
    model.component("comp1").geom("geom1").feature(tag).set("size", size);
    model.component("comp1").geom("geom1").feature(tag).set("pos", pos);
    color(model, tag, r, g, b);
  }

  public static Model run() throws Exception {
    Model model = ModelUtil.create("Model");
    model.modelPath(ROOT + "\\models");
    model.label("water_system_3d_geometry_v2.mph");
    model.title("3D Water Circulation System - Geometry V2");
    model.description(
        "Pure geometry model for the 200 L PE tank, 170 L water, DN40 hoses, vertical pump, "
            + "VFD, wall 380 V supply, floor, and observation points at 2 m, 3 m, and 4 m.");

    model.param().set("tank_diam", "0.56[m]", "PE tank outer diameter");
    model.param().set("tank_total_h", "0.87[m]", "Tank total height excluding lid");
    model.param().set("tank_straight_h", "0.72[m]", "Tank straight wall height");
    model.param().set("tank_wall", "5[mm]", "Assumed PE wall thickness");
    model.param().set("water_volume", "170[L]", "Baseline water volume; later sweep 160-180 L");
    model.param().set("sigma_water", "0.05[S/m]", "Confirmed 500 uS/cm water conductivity");
    model.param().set("pipe_nominal", "DN40", "Nominal hose and flange size");
    model.param().set("lower_hose_len", "0.50[m]", "Straight lower suction hose length");
    model.param().set("upper_hose_len", "2.0[m]", "Approximate curved upper return hose length");
    model.param().set("flow_rate", "6.3[m^3/h]", "Rated pump flow");
    model.param().set("pump_head", "32[m]", "Rated pump head");
    model.param().set("pump_power", "2.2[kW]", "Motor rated power");
    model.param().set("pump_speed", "2800[rpm]", "Motor rated speed");
    model.param().set("vfd_power", "3.7[kW]", "VFD rated power");
    model.param().set("obs_z", "1[m]", "Observation height above floor");
    model.param().set("air_radius", "5[m]", "Future open-air computational radius");

    model.component().create("comp1", true);
    model.component("comp1").geom().create("geom1", 3);
    model.component("comp1").geom("geom1").lengthUnit("m");

    block(model, "floor", "Concrete floor reference", new double[] {3.6, 5.2, 0.05},
        new double[] {-0.65, -4.35, -0.05}, 0.55, 0.55, 0.55);

    model.component("comp1").geom("geom1").create("tankOuter", "Cylinder");
    model.component("comp1").geom("geom1").feature("tankOuter").label("PE tank outer body");
    model.component("comp1").geom("geom1").feature("tankOuter").set("r", "tank_diam/2");
    model.component("comp1").geom("geom1").feature("tankOuter").set("h", "tank_total_h");
    color(model, "tankOuter", 0.92, 0.94, 0.89);

    model.component("comp1").geom("geom1").create("tankCavityTool", "Cylinder");
    model.component("comp1").geom("geom1").feature("tankCavityTool").label("Tank cavity tool");
    model.component("comp1").geom("geom1").feature("tankCavityTool")
        .set("r", "tank_diam/2-tank_wall");
    model.component("comp1").geom("geom1").feature("tankCavityTool")
        .set("h", "tank_total_h-tank_wall");
    model.component("comp1").geom("geom1").feature("tankCavityTool")
        .set("pos", new String[] {"0", "0", "tank_wall"});

    model.component("comp1").geom("geom1").create("tankShell", "Difference");
    model.component("comp1").geom("geom1").feature("tankShell").label("PE hollow tank shell");
    model.component("comp1").geom("geom1").feature("tankShell").selection("input")
        .set("tankOuter");
    model.component("comp1").geom("geom1").feature("tankShell").selection("input2")
        .set("tankCavityTool");
    color(model, "tankShell", 0.92, 0.94, 0.89);

    model.component("comp1").geom("geom1").create("water", "Cylinder");
    model.component("comp1").geom("geom1").feature("water").label("Water - baseline 170 L");
    model.component("comp1").geom("geom1").feature("water")
        .set("r", "tank_diam/2-tank_wall");
    model.component("comp1").geom("geom1").feature("water")
        .set("h", "water_volume/(pi*(tank_diam/2-tank_wall)^2)");
    model.component("comp1").geom("geom1").feature("water")
        .set("pos", new String[] {"0", "0", "tank_wall"});
    color(model, "water", 0.18, 0.55, 0.88);

    cylinder(model, "lowerAdapter", "Lower tank DN40 adapter", 0.032,
        new double[] {0.275, 0, 0.10}, new double[] {0.36, 0, 0.10}, 0.42, 0.43, 0.45);
    cylinder(model, "lowerTankFlange", "Lower tank flange", 0.070,
        new double[] {0.34, 0, 0.10}, new double[] {0.37, 0, 0.10}, 0.20, 0.30, 0.58);
    cylinder(model, "lowerHose", "Lower 0.5 m steel-wire rubber hose", 0.033,
        new double[] {0.37, 0, 0.10}, new double[] {0.87, 0, 0.10}, 0.12, 0.38, 0.72);

    block(model, "pumpBase", "Pump wooden base", new double[] {0.48, 0.38, 0.08},
        new double[] {0.78, -0.19, 0}, 0.58, 0.42, 0.24);
    cylinder(model, "pumpBody", "Pump hydraulic body", 0.12,
        new double[] {0.87, 0, 0.14}, new double[] {1.17, 0, 0.14}, 0.08, 0.30, 0.58);
    cylinder(model, "pumpLeftFlange", "Pump left suction flange", 0.075,
        new double[] {0.85, 0, 0.14}, new double[] {0.89, 0, 0.14}, 0.12, 0.30, 0.56);
    cylinder(model, "pumpRightFlange", "Pump right discharge flange", 0.075,
        new double[] {1.15, 0, 0.14}, new double[] {1.19, 0, 0.14}, 0.12, 0.30, 0.56);
    cylinder(model, "motorLower", "Vertical motor lower housing", 0.12,
        new double[] {1.02, 0, 0.14}, new double[] {1.02, 0, 0.29}, 0.08, 0.30, 0.58);
    cylinder(model, "motor", "2.2 kW vertical motor", 0.095,
        new double[] {1.02, 0, 0.27}, new double[] {1.02, 0, 0.5775}, 0.08, 0.30, 0.58);
    cylinder(model, "motorCap", "Motor fan cover", 0.10,
        new double[] {1.02, 0, 0.5775}, new double[] {1.02, 0, 0.6275}, 0.06, 0.22, 0.46);

    cylinder(model, "topAdapter", "Top tank threaded adapter", 0.028,
        new double[] {0.187, 0, 0.87}, new double[] {0.187, 0, 0.98}, 0.42, 0.43, 0.45);
    cylinder(model, "topTankFlange", "Top DN40 flange", 0.068,
        new double[] {0.187, 0, 0.96}, new double[] {0.187, 0, 0.99}, 0.20, 0.30, 0.58);

    double[][] upperPath = new double[][] {
        {1.19, 0, 0.14}, {1.30, 0, 0.14}, {1.30, 0, 0.95},
        {0.38, 0, 1.04}, {0.187, 0, 0.99}
    };
    for (int i = 0; i < upperPath.length - 1; i++) {
      cylinder(model, "upperHose" + (i + 1), "Upper return hose segment " + (i + 1), 0.033,
          upperPath[i], upperPath[i + 1], 0.12, 0.38, 0.72);
    }
    for (int i = 1; i < upperPath.length - 1; i++) {
      sphere(model, "upperElbow" + i, "Upper hose smooth bend " + i, 0.034,
          upperPath[i], 0.12, 0.38, 0.72);
    }

    block(model, "vfd", "3.7 kW variable-frequency drive", new double[] {0.34, 0.20, 0.55},
        new double[] {2.34, -0.10, 0.52}, 0.18, 0.18, 0.20);
    block(model, "wallSupply", "Wall 3-phase 380 V supply box", new double[] {0.22, 0.16, 0.30},
        new double[] {2.72, -0.08, 0.72}, 0.80, 0.80, 0.76);
    cylinder(model, "supplyCable", "Wall supply to VFD cable bundle", 0.018,
        new double[] {2.72, 0, 0.82}, new double[] {2.68, 0, 0.72}, 0.08, 0.08, 0.08);

    double[][] motorCable = new double[][] {
        {2.34, 0, 0.58}, {2.20, 0, 0.18}, {1.32, 0, 0.18}, {1.10, 0, 0.42}
    };
    for (int i = 0; i < motorCable.length - 1; i++) {
      cylinder(model, "motorCable" + (i + 1), "VFD-to-pump motor cable " + (i + 1), 0.014,
          motorCable[i], motorCable[i + 1], 0.05, 0.05, 0.05);
    }

    sphere(model, "obs2", "Observation point 2 m", 0.035,
        new double[] {0, -2, 1}, 0.92, 0.14, 0.12);
    sphere(model, "obs3", "Observation point 3 m", 0.035,
        new double[] {0, -3, 1}, 0.92, 0.14, 0.12);
    sphere(model, "obs4", "Observation point 4 m", 0.035,
        new double[] {0, -4, 1}, 0.92, 0.14, 0.12);

    model.component("comp1").geom("geom1").feature("fin").set("action", "assembly");
    model.component("comp1").geom("geom1").run();

    model.component("comp1").view("view1").set("showgrid", true);
    model.component("comp1").view("view1").set("renderwireframe", false);
    model.component("comp1").view("view1").set("scenelight", true);

    model.save(MODEL_FILE);
    return model;
  }

  public static void main(String[] args) throws Exception {
    run();
  }
}
