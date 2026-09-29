import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class CathodicProtectionElectrodeAssembly3DV1 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\simulation";
  private static final String MODEL_FILE =
      ROOT + "\\models\\cathodic_protection_electrode_assembly_3d_v1.mph";

  private static void color(Model model, String tag, double r, double g, double b) {
    model.component("comp1").geom("geom1").feature(tag).set("selresult", true);
    model.component("comp1").geom("geom1").feature(tag).set("selresultshow", "all");
    model.component("comp1").geom("geom1").feature(tag).set("color", "custom");
    model.component("comp1").geom("geom1").feature(tag)
        .set("customcolor", new double[] {r, g, b});
  }

  private static void cylinder(
      Model model, String tag, String label, String radius, String height,
      String[] position, double r, double g, double b) {
    model.component("comp1").geom("geom1").create(tag, "Cylinder");
    model.component("comp1").geom("geom1").feature(tag).label(label);
    model.component("comp1").geom("geom1").feature(tag).set("r", radius);
    model.component("comp1").geom("geom1").feature(tag).set("h", height);
    model.component("comp1").geom("geom1").feature(tag).set("pos", position);
    color(model, tag, r, g, b);
  }

  private static void block(
      Model model, String tag, String label, String[] size, String[] position,
      double r, double g, double b) {
    model.component("comp1").geom("geom1").create(tag, "Block");
    model.component("comp1").geom("geom1").feature(tag).label(label);
    model.component("comp1").geom("geom1").feature(tag).set("size", size);
    model.component("comp1").geom("geom1").feature(tag).set("pos", position);
    color(model, tag, r, g, b);
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

  private static void material(
      Model model, String tag, String label, String selection,
      String conductivity, String relativePermittivity) {
    model.component("comp1").material().create(tag, "Common");
    model.component("comp1").material(tag).label(label);
    model.component("comp1").material(tag).selection().named(selection);
    model.component("comp1").material(tag).propertyGroup("def")
        .set("electricconductivity", new String[] {conductivity});
    model.component("comp1").material(tag).propertyGroup("def")
        .set("relpermittivity", new String[] {relativePermittivity});
  }

  public static Model run() throws Exception {
    Model model = ModelUtil.create("Model");
    model.modelPath(ROOT + "\\models");
    model.label("cathodic_protection_electrode_assembly_3d_v1.mph");
    model.title("3D Cathodic-Protection Electrode Lid Assembly V1");
    model.description(
        "Standalone parameterized geometry reconstructed from the 2026-08-11 photographs. "
            + "It contains the lid, a sealed 20# carbon-steel pipe with waterproof tape and "
            + "a 200 mm by 120 mm exposed side window facing a vertical graphite rod, simplified "
            + "feedthroughs, a single steel-pipe support rod, and lead stubs. The steel-pipe axis is "
            + "horizontal and perpendicular to the graphite axis. No water domain, power supply, "
            + "or physics is added yet.");

    model.param().set("lid_diam", "0.56[m]", "Circular lid diameter matched to the tank");
    model.param().set("lid_thickness", "18[mm]", "Assumed circular lid thickness from photographs");
    model.param().set("back_plate_size", "0.62[m]", "Assumed square support plate side length");
    model.param().set("back_plate_thickness", "12[mm]", "Assumed square support plate thickness");
    model.param().set("electrode_spacing", "0.30[m]", "Steel-pipe to graphite center spacing");
    model.param().set("steel_pipe_length", "0.40[m]", "Provided 20# steel specimen length");
    model.param().set("steel_pipe_od", "0.10[m]", "Provided steel specimen outside diameter");
    model.param().set("steel_pipe_wall", "3[mm]", "Provided steel specimen wall thickness");
    model.param().set("steel_pipe_r", "steel_pipe_od/2", "Steel specimen outside radius");
    model.param().set("steel_pipe_inner_r", "steel_pipe_r-steel_pipe_wall",
        "Steel specimen inside radius");
    model.param().set("steel_pipe_center_z", "-0.30[m]",
        "Center elevation shared by the steel window and graphite electrode");
    model.param().set("window_length", "0.20[m]", "Provided exposed-window axial length");
    model.param().set("window_arc_width", "0.12[m]", "Provided exposed-window circumferential width");
    model.param().set("window_chord", "2*steel_pipe_r*sin(window_arc_width/(2*steel_pipe_r))",
        "Chord corresponding to the 120 mm developed window width");
    model.param().set("tape_thickness", "1.5[mm]", "Assumed waterproof tape thickness");
    model.param().set("graphite_diam", "25[mm]", "Provided approximate graphite diameter");
    model.param().set("graphite_length", "0.20[m]", "Provided approximate graphite length");
    model.param().set("holder_diam", "32[mm]", "Equivalent stainless holder diameter");
    model.param().set("lead_diam", "3[mm]", "Equivalent external DC lead diameter");

    model.component().create("comp1", true);
    model.component("comp1").label("Cathodic-protection electrode lid assembly");
    model.component("comp1").geom().create("geom1", 3);
    model.component("comp1").geom("geom1").lengthUnit("m");

    block(model, "backPlate", "Square PE support plate",
        new String[] {"back_plate_size", "back_plate_size", "back_plate_thickness"},
        new String[] {"-back_plate_size/2", "-back_plate_size/2", "0"},
        0.92, 0.94, 0.90);
    cylinder(model, "roundLid", "Circular PE tank lid", "lid_diam/2", "lid_thickness",
        new String[] {"0", "0", "-lid_thickness"}, 0.84, 0.88, 0.80);

    String[] electrodeX = {"-electrode_spacing/2", "electrode_spacing/2"};
    for (int i = 0; i < 2; i++) {
      String suffix = Integer.toString(i + 1);
      cylinder(model, "gland" + suffix, "Stainless feedthrough gland " + suffix,
          "28[mm]", "30[mm]",
          new String[] {electrodeX[i], "0", "-lid_thickness-6[mm]"},
          0.55, 0.57, 0.59);
      cylinder(model, "glandNut" + suffix, "Feedthrough hex-nut equivalent " + suffix,
          "35[mm]", "8[mm]",
          new String[] {electrodeX[i], "0", "back_plate_thickness"},
          0.38, 0.40, 0.42);
    }

    cylinder(model, "steelSupport", "Stainless support and current-feed tube for steel specimen",
        "holder_diam/2",
        "-lid_thickness-(steel_pipe_center_z+steel_pipe_r+tape_thickness)",
        new String[] {"-electrode_spacing/2", "0",
            "steel_pipe_center_z+steel_pipe_r+tape_thickness"},
        0.62, 0.64, 0.66);

    cylinder(model, "pipeOuter", "20# seamless carbon-steel pipe outer body",
        "steel_pipe_r", "steel_pipe_length",
        new String[] {"-electrode_spacing/2", "-steel_pipe_length/2", "steel_pipe_center_z"},
        0.50, 0.52, 0.54);
    model.component("comp1").geom("geom1").feature("pipeOuter")
        .set("axis", new double[] {0, 1, 0});
    cylinder(model, "pipeCavity", "Pipe cavity tool preserving 3 mm sealed end caps",
        "steel_pipe_inner_r", "steel_pipe_length-2*steel_pipe_wall",
        new String[] {"-electrode_spacing/2", "-steel_pipe_length/2+steel_pipe_wall",
            "steel_pipe_center_z"},
        0.15, 0.15, 0.15);
    model.component("comp1").geom("geom1").feature("pipeCavity")
        .set("axis", new double[] {0, 1, 0});
    difference(model, "pipeSteel", "Sealed 20# carbon-steel pipe specimen",
        "pipeOuter", "pipeCavity", 0.47, 0.49, 0.51);

    cylinder(model, "tapeOuter", "Waterproof tape outer cylinder",
        "steel_pipe_r+tape_thickness", "steel_pipe_length",
        new String[] {"-electrode_spacing/2", "-steel_pipe_length/2", "steel_pipe_center_z"},
        0.08, 0.45, 0.33);
    model.component("comp1").geom("geom1").feature("tapeOuter")
        .set("axis", new double[] {0, 1, 0});
    cylinder(model, "tapeInner", "Waterproof tape inner tool",
        "steel_pipe_r+0.1[mm]", "steel_pipe_length+0.4[mm]",
        new String[] {"-electrode_spacing/2", "-steel_pipe_length/2-0.2[mm]",
            "steel_pipe_center_z"},
        0.08, 0.45, 0.33);
    model.component("comp1").geom("geom1").feature("tapeInner")
        .set("axis", new double[] {0, 1, 0});
    difference(model, "tapeShell", "Waterproof tape cylindrical insulation",
        "tapeOuter", "tapeInner", 0.05, 0.47, 0.34);

    block(model, "windowTool", "200 mm by 120 mm developed exposed-window tool",
        new String[] {"steel_pipe_r+2*tape_thickness", "window_length", "window_chord"},
        new String[] {"-electrode_spacing/2", "-window_length/2",
            "steel_pipe_center_z-window_chord/2"},
        0.78, 0.30, 0.24);
    difference(model, "pipeTape", "Waterproof tape with exposed steel window",
        "tapeShell", "windowTool", 0.05, 0.47, 0.34);
    cylinder(model, "tapeBottomCap", "Waterproof tape negative-y end seal",
        "steel_pipe_r+tape_thickness", "tape_thickness",
        new String[] {"-electrode_spacing/2",
            "-steel_pipe_length/2-tape_thickness", "steel_pipe_center_z"},
        0.05, 0.47, 0.34);
    model.component("comp1").geom("geom1").feature("tapeBottomCap")
        .set("axis", new double[] {0, 1, 0});
    cylinder(model, "tapeTopCap", "Waterproof tape positive-y end seal",
        "steel_pipe_r+tape_thickness", "tape_thickness",
        new String[] {"-electrode_spacing/2", "steel_pipe_length/2", "steel_pipe_center_z"},
        0.05, 0.47, 0.34);
    model.component("comp1").geom("geom1").feature("tapeTopCap")
        .set("axis", new double[] {0, 1, 0});

    cylinder(model, "graphiteHolder", "Insulated graphite holder",
        "holder_diam/2", "0.18[m]",
        new String[] {"electrode_spacing/2", "0", "-0.20[m]"},
        0.08, 0.09, 0.10);
    cylinder(model, "graphite", "Graphite counter electrode",
        "graphite_diam/2", "graphite_length",
        new String[] {"electrode_spacing/2", "0", "-0.20[m]-graphite_length"},
        0.12, 0.12, 0.13);

    cylinder(model, "steelLead", "DC lead stub to carbon-steel specimen",
        "lead_diam/2", "90[mm]",
        new String[] {"-electrode_spacing/2", "0", "back_plate_thickness+8[mm]"},
        0.82, 0.10, 0.08);
    cylinder(model, "graphiteLead", "DC lead stub to graphite electrode",
        "lead_diam/2", "90[mm]",
        new String[] {"electrode_spacing/2", "0", "back_plate_thickness+8[mm]"},
        0.05, 0.05, 0.05);

    for (int i = 0; i < 8; i++) {
      double angle = 2.0 * Math.PI * i / 8.0;
      String x = Double.toString(0.225 * Math.cos(angle));
      String y = Double.toString(0.225 * Math.sin(angle));
      cylinder(model, "lidBolt" + (i + 1), "Lid fastener " + (i + 1),
          "5[mm]", "back_plate_thickness+lid_thickness",
          new String[] {x, y, "-lid_thickness"}, 0.32, 0.34, 0.36);
    }

    model.component("comp1").geom("geom1").feature("fin").set("action", "assembly");
    model.component("comp1").geom("geom1").run();

    material(model, "matCarbonSteel", "20# seamless carbon steel",
        "geom1_pipeSteel_dom", "6.0e6[S/m]", "1");
    material(model, "matGraphite", "Graphite counter electrode",
        "geom1_graphite_dom", "1.0e5[S/m]", "1");
    material(model, "matPipeTape", "Waterproof insulating tape",
        "geom1_pipeTape_dom", "1e-13[S/m]", "3.2");
    material(model, "matCircularLid", "PE circular tank lid",
        "geom1_roundLid_dom", "1e-15[S/m]", "2.3");
    material(model, "matBackPlate", "PE square support plate",
        "geom1_backPlate_dom", "1e-15[S/m]", "2.3");

    model.component("comp1").view("view1").set("showgrid", true);
    model.component("comp1").view("view1").set("renderwireframe", false);
    model.component("comp1").view("view1").set("scenelight", true);
    model.component("comp1").view("view1").set("transparency", false);
    model.component("comp1").view("view1").camera().set("projection", "orthographic");
    model.component("comp1").view("view1").camera()
        .set("position", new double[] {1.2, -1.4, -0.05});
    model.component("comp1").view("view1").camera()
        .set("target", new double[] {0, 0, -0.25});
    model.component("comp1").view("view1").camera()
        .set("up", new double[] {0, 0, 1});
    model.component("comp1").view("view1").camera().set("orthoscale", 0.75);

    model.save(MODEL_FILE);
    return model;
  }

  public static void main(String[] args) throws Exception {
    run();
  }
}
