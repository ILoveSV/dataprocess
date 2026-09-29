import com.comsol.model.Model;
import com.comsol.model.ModelEntityImage;
import com.comsol.model.util.ModelUtil;

public class CathodicProtectionFullSceneV5 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\simulation";
  private static final String INPUT_FILE =
      ROOT + "\\models\\water_system_3d_doorway_environment_v9.mph";
  private static final String MODEL_FILE =
      ROOT + "\\models\\cathodic_protection_full_scene_geometry_v5.mph";
  private static final String OUTPUT_DIR =
      ROOT + "\\results\\cathodic_protection_full_scene_v5";

  private static void color(Model model, String tag, double r, double g, double b) {
    model.component("comp1").geom("geom1").feature(tag).set("selresult", true);
    model.component("comp1").geom("geom1").feature(tag).set("selresultshow", "all");
    model.component("comp1").geom("geom1").feature(tag).set("color", "custom");
    model.component("comp1").geom("geom1").feature(tag)
        .set("customcolor", new double[] {r, g, b});
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

  private static void cylinder(
      Model model, String tag, String label, double radius, double height,
      double[] pos, double[] axis, double r, double g, double b) {
    model.component("comp1").geom("geom1").create(tag, "Cylinder");
    model.component("comp1").geom("geom1").feature(tag).label(label);
    model.component("comp1").geom("geom1").feature(tag).set("r", radius);
    model.component("comp1").geom("geom1").feature(tag).set("h", height);
    model.component("comp1").geom("geom1").feature(tag).set("pos", pos);
    model.component("comp1").geom("geom1").feature(tag).set("axis", axis);
    color(model, tag, r, g, b);
  }

  private static void cylinderBetween(
      Model model, String tag, String label, double radius,
      double[] from, double[] to, double r, double g, double b) {
    double dx = to[0] - from[0];
    double dy = to[1] - from[1];
    double dz = to[2] - from[2];
    double length = Math.sqrt(dx * dx + dy * dy + dz * dz);
    cylinder(model, tag, label, radius, length, from,
        new double[] {dx / length, dy / length, dz / length}, r, g, b);
  }

  private static void difference(
      Model model, String tag, String label, String input, String tool,
      double r, double g, double b) {
    model.component("comp1").geom("geom1").create(tag, "Difference");
    model.component("comp1").geom("geom1").feature(tag).label(label);
    model.component("comp1").geom("geom1").feature(tag).selection("input").set(input);
    model.component("comp1").geom("geom1").feature(tag).selection("input2").set(tool);
    color(model, tag, r, g, b);
  }

  private static void exportGeometry(
      Model model, String filename, double[] position, double[] target,
      double orthoscale, int width, int height) throws Exception {
    model.component("comp1").view("view1").camera().set("projection", "orthographic");
    model.component("comp1").view("view1").camera().set("position", position);
    model.component("comp1").view("view1").camera().set("target", target);
    model.component("comp1").view("view1").camera().set("up", new double[] {0, 0, 1});
    model.component("comp1").view("view1").camera().set("orthoscale", orthoscale);
    model.component("comp1").view("view1").set("showgrid", false);
    model.component("comp1").view("view1").set("renderwireframe", false);
    model.component("comp1").view("view1").set("scenelight", true);

    ModelEntityImage image = model.component("comp1").geom("geom1").image();
    image.set("view", "view1");
    image.set("zoomextents", false);
    image.set("showselection", false);
    image.set("showmaterial", false);
    image.set("drawmode", "on");
    image.set("showgrid", false);
    image.set("grid", false);
    image.set("background", "color");
    image.set("customcolor", new double[] {1, 1, 1});
    image.set("size", "manualweb");
    image.set("widthpx", Integer.toString(width));
    image.set("heightpx", Integer.toString(height));
    image.set("pngfilename", filename);
    image.export();
  }

  public static Model run() throws Exception {
    Model model = ModelUtil.load("Model", INPUT_FILE);
    model.modelPath(ROOT + "\\models");
    model.label("cathodic_protection_full_scene_geometry_v5.mph");
    model.title("Cathodic Protection Assembly in Full Laboratory Scene V5");
    model.description(
        "Geometry-only integration of the cathodic-protection lid, immersed carbon-steel and "
            + "graphite electrodes, floating DC supply and paired output leads into the established "
            + "tank, pump, VFD, doorway, glass partition, floor and 2/3/4 m observation-point scene. "
            + "This model is intended for whole-scene visualization and does not add a new coupled solve.");

    // Remove the +x,+y quarter of the visual tank and water so the immersed assembly
    // remains visible from the equipment-side camera. The solved V9/V14 geometries are untouched.
    block(model, "cpTankCutToolV5", "Tank cutaway tool",
        new double[] {0.55, 0.65, 1.00}, new double[] {-0.15, -0.25, 0.00},
        0.92, 0.94, 0.89);
    difference(model, "cpTankCutV5", "Quarter-cut PE tank shell",
        "tankShell", "cpTankCutToolV5", 0.92, 0.94, 0.89);
    block(model, "cpWaterCutToolV5", "Water cutaway tool",
        new double[] {0.55, 0.65, 1.00}, new double[] {-0.15, -0.25, 0.00},
        0.18, 0.55, 0.88);
    difference(model, "cpWaterCutV5", "Quarter-cut 170 L water volume",
        "water", "cpWaterCutToolV5", 0.18, 0.55, 0.88);

    // Lid and support plate at the established 0.87 m tank height.
    cylinder(model, "cpLidV5", "Cathodic-protection circular PE lid", 0.28, 0.018,
        new double[] {0, 0, 0.87}, new double[] {0, 0, 1}, 0.84, 0.88, 0.80);
    block(model, "cpPlateV5", "Square PE support plate", new double[] {0.62, 0.62, 0.012},
        new double[] {-0.31, -0.31, 0.888}, 0.90, 0.92, 0.88);

    // The doorway is on the -Y side of the tank. The steel pipe is nearer the doorway and
    // the graphite is farther away, so doorway -> steel center -> graphite center is collinear.
    // The 82.5 mm axis spacing preserves the confirmed 20 mm surface gap for a 50 mm
    // steel radius and a 12.5 mm graphite radius. The pipe axis is transverse to that line.
    double steelY = -0.04125;
    double graphiteY = 0.04125;
    double steelCenterZ = 0.46;
    cylinder(model, "cpSteelV5", "20# sealed carbon-steel pipe", 0.050, 0.400,
        new double[] {-0.200, steelY, steelCenterZ}, new double[] {1, 0, 0},
        0.48, 0.50, 0.53);
    cylinder(model, "cpTapeV5", "Waterproof tape envelope", 0.052, 0.400,
        new double[] {-0.200, steelY, steelCenterZ}, new double[] {1, 0, 0},
        0.06, 0.42, 0.30);
    block(model, "cpWindowV5", "Exposed 200 mm by 120 mm steel window",
        new double[] {0.200, 0.006, 0.100},
        new double[] {-0.100, steelY + 0.047, steelCenterZ - 0.050},
        0.58, 0.60, 0.63);
    cylinder(model, "cpGraphiteV5", "Graphite anode", 0.0125, 0.200,
        new double[] {0, graphiteY, 0.300}, new double[] {0, 0, 1},
        0.10, 0.10, 0.11);
    cylinder(model, "cpSteelSupportV5", "Steel-electrode support tube", 0.016, 0.360,
        new double[] {0, steelY, 0.510}, new double[] {0, 0, 1},
        0.62, 0.64, 0.66);
    cylinder(model, "cpGraphiteSupportV5", "Graphite-electrode support tube", 0.016, 0.370,
        new double[] {0, graphiteY, 0.500}, new double[] {0, 0, 1},
        0.20, 0.20, 0.22);

    // DC supply placed beside the pump on the doorway side, with a paired lead route to the lid.
    block(model, "cpSupplyBoardV5", "Extended wooden board for DC supply",
        new double[] {0.55, 0.34, 0.06}, new double[] {0.78, -0.56, 0.00},
        0.58, 0.42, 0.24);
    block(model, "cpSupplyV5", "Floating DC constant-current supply",
        new double[] {0.30, 0.20, 0.20}, new double[] {0.90, -0.49, 0.06},
        0.32, 0.34, 0.37);
    block(model, "cpSupplyDisplayV5", "DC supply front panel",
        new double[] {0.16, 0.008, 0.075}, new double[] {0.97, -0.498, 0.135},
        0.08, 0.15, 0.19);

    double[][] negPath = {
        {0.98, -0.49, 0.24}, {0.82, -0.44, 0.34}, {0.42, -0.30, 0.72},
        {0, steelY, 0.94}
    };
    double[][] posPath = {
        {1.08, -0.49, 0.24}, {0.90, -0.42, 0.36}, {0.48, -0.25, 0.75},
        {0, graphiteY, 0.94}
    };
    for (int index = 0; index < negPath.length - 1; index++) {
      cylinderBetween(model, "cpNegLeadV5_" + index, "Negative cathodic lead segment " + index,
          0.003, negPath[index], negPath[index + 1], 0.08, 0.16, 0.28);
      cylinderBetween(model, "cpPosLeadV5_" + index, "Positive graphite lead segment " + index,
          0.003, posPath[index], posPath[index + 1], 0.82, 0.10, 0.08);
    }

    model.component("comp1").geom("geom1").feature("fin").set("action", "assembly");
    model.component("comp1").geom("geom1").run();

    // The wide image includes the observation points and full doorway partition.
    exportGeometry(model, OUTPUT_DIR + "\\cathodic_protection_full_scene_v5.png",
        new double[] {6.2, 5.8, 4.6}, new double[] {0.0, -1.45, 0.85},
        4.9, 2000, 1250);

    // The second image keeps the doorway context while making the tank, pump, VFD and DC source legible.
    exportGeometry(model, OUTPUT_DIR + "\\cathodic_protection_equipment_scene_v5.png",
        new double[] {4.6, 3.8, 3.1}, new double[] {0.85, -0.45, 0.65},
        2.65, 2000, 1300);

    // High oblique overview: observation points, doorway and equipment remain visible together.
    exportGeometry(model, OUTPUT_DIR + "\\cathodic_protection_scene_overview_v5.png",
        new double[] {6.2, 6.0, 10.0}, new double[] {0.0, -1.75, 0.45},
        5.25, 2000, 1250);

    // Far-side oblique detail: the graphite and the steel window facing it are visible;
    // the doorway lies behind the nearer steel pipe along -Y.
    exportGeometry(model, OUTPUT_DIR + "\\cathodic_protection_electrode_direction_v5.png",
        new double[] {1.15, 1.20, 1.02}, new double[] {0.0, 0.0, 0.46},
        0.78, 2000, 1400);

    model.save(MODEL_FILE);
    System.out.println("MODEL_FILE=" + MODEL_FILE);
    System.out.println("FULL_SCENE=" + OUTPUT_DIR + "\\cathodic_protection_full_scene_v5.png");
    System.out.println("EQUIPMENT_SCENE=" + OUTPUT_DIR
        + "\\cathodic_protection_equipment_scene_v5.png");
    System.out.println("SCENE_OVERVIEW=" + OUTPUT_DIR
        + "\\cathodic_protection_scene_overview_v5.png");
    System.out.println("ELECTRODE_DIRECTION=" + OUTPUT_DIR
        + "\\cathodic_protection_electrode_direction_v5.png");
    ModelUtil.remove("Model");
    return null;
  }

  public static void main(String[] args) throws Exception {
    run();
  }
}
