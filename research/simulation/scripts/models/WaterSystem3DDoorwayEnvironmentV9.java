import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class WaterSystem3DDoorwayEnvironmentV9 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\research\\simulation";
  private static final String INPUT_FILE =
      ROOT + "\\models\\water_system_3d_integrated_sources_v8.mph";
  private static final String MODEL_FILE =
      ROOT + "\\models\\water_system_3d_doorway_environment_v9.mph";

  private static void color(Model model, String tag, double r, double g, double b) {
    model.component("comp2").geom("geom2").feature(tag).set("selresult", true);
    model.component("comp2").geom("geom2").feature(tag).set("selresultshow", "all");
    model.component("comp2").geom("geom2").feature(tag).set("color", "custom");
    model.component("comp2").geom("geom2").feature(tag)
        .set("customcolor", new double[] {r, g, b});
  }

  private static void block(
      Model model, String tag, String label, String[] size, String[] pos,
      double r, double g, double b) {
    model.component("comp2").geom("geom2").create(tag, "Block");
    model.component("comp2").geom("geom2").feature(tag).label(label);
    model.component("comp2").geom("geom2").feature(tag).set("size", size);
    model.component("comp2").geom("geom2").feature(tag).set("pos", pos);
    color(model, tag, r, g, b);
  }

  private static void material(
      Model model, String tag, String label, String selection,
      String conductivity, String relPermittivity) {
    model.component("comp2").material().create(tag, "Common");
    model.component("comp2").material(tag).label(label);
    model.component("comp2").material(tag).selection().named(selection);
    model.component("comp2").material(tag).propertyGroup("def")
        .set("electricconductivity", new String[] {conductivity});
    model.component("comp2").material(tag).propertyGroup("def")
        .set("relpermittivity", new String[] {relPermittivity});
  }

  private static void visualColor(Model model, String tag, double r, double g, double b) {
    model.component("comp1").geom("geom1").feature(tag).set("selresult", true);
    model.component("comp1").geom("geom1").feature(tag).set("color", "custom");
    model.component("comp1").geom("geom1").feature(tag)
        .set("customcolor", new double[] {r, g, b});
  }

  private static void visualBlock(
      Model model, String tag, String label, String[] size, String[] pos,
      double r, double g, double b) {
    model.component("comp1").geom("geom1").create(tag, "Block");
    model.component("comp1").geom("geom1").feature(tag).label(label);
    model.component("comp1").geom("geom1").feature(tag).set("size", size);
    model.component("comp1").geom("geom1").feature(tag).set("pos", pos);
    visualColor(model, tag, r, g, b);
  }

  private static void visualSphere(
      Model model, String tag, String label, String[] pos, double r, double g, double b) {
    model.component("comp1").geom("geom1").create(tag, "Sphere");
    model.component("comp1").geom("geom1").feature(tag).label(label);
    model.component("comp1").geom("geom1").feature(tag).set("r", "35[mm]");
    model.component("comp1").geom("geom1").feature(tag).set("pos", pos);
    visualColor(model, tag, r, g, b);
  }

  public static Model run() throws Exception {
    Model model = ModelUtil.load("Model", INPUT_FILE);
    model.modelPath(ROOT + "\\models");
    model.label("water_system_3d_doorway_environment_v9.mph");
    model.title("3D Water Circulation System - Doorway Environment V9");
    model.description(
        "V8 integrated sources with corrected observation distances measured from the tank wall, "
            + "an open personnel doorway 1.5 m from the near tank wall, and a grounded metal-frame "
            + "glass partition surrounding the doorway.");

    model.param().set("door_from_tank_wall", "1.5[m]",
        "Near tank wall to doorway and glass-wall plane");
    model.param().set("wall_y", "-(tank_diam/2+door_from_tank_wall)",
        "Doorway and glass-wall center plane");
    model.param().set("door_width", "0.9[m]", "Assumed one-person doorway width");
    model.param().set("door_height", "2.1[m]", "Assumed doorway clear height");
    model.param().set("partition_width", "6[m]", "Assumed modeled glass-partition width");
    model.param().set("partition_height", "3[m]", "Glass partition height equals air domain");
    model.param().set("glass_thickness", "20[mm]", "Equivalent glass thickness");
    model.param().set("frame_thickness", "40[mm]", "Equivalent metal-frame depth");
    model.param().set("frame_width", "50[mm]", "Equivalent visible frame width");
    model.param().set("epsr_glass", "6.5", "Representative architectural glass permittivity");
    model.param().set("sigma_glass", "1e-12[S/m]", "Dry glass effective conductivity");
    model.param().set("sigma_frame", "3.5e7[S/m]", "Representative aluminum frame conductivity");
    model.param().set("obs_z", "0.5[m]", "Corrected MEMS observation height above floor");

    model.component("comp1").geom("geom1").feature("floor")
        .label("Symmetric floor spanning full glass partition");
    model.component("comp1").geom("geom1").feature("floor")
        .set("size", new String[] {"partition_width", "5.2[m]", "0.05[m]"});
    model.component("comp1").geom("geom1").feature("floor")
        .set("pos", new String[] {"-partition_width/2", "-4.35[m]", "-0.05[m]"});

    String[][] glass = {
        {"-2.95[m]", "0.05[m]", "1.425[m]", "1.425[m]"},
        {"-2.95[m]", "1.525[m]", "1.425[m]", "1.425[m]"},
        {"-1.475[m]", "0.05[m]", "1.0[m]", "1.425[m]"},
        {"-1.475[m]", "1.525[m]", "1.0[m]", "1.425[m]"},
        {"0.475[m]", "0.05[m]", "1.0[m]", "1.425[m]"},
        {"0.475[m]", "1.525[m]", "1.0[m]", "1.425[m]"},
        {"1.525[m]", "0.05[m]", "1.425[m]", "1.425[m]"},
        {"1.525[m]", "1.525[m]", "1.425[m]", "1.425[m]"},
        {"-0.425[m]", "2.15[m]", "0.85[m]", "0.80[m]"}
    };
    String[] glassTags = new String[glass.length];
    for (int index = 0; index < glass.length; index++) {
      String tag = "glass" + (index + 1);
      glassTags[index] = tag;
      block(model, tag, "Glass partition panel " + (index + 1),
          new String[] {glass[index][2], "glass_thickness", glass[index][3]},
          new String[] {glass[index][0], "wall_y-glass_thickness/2", glass[index][1]},
          0.62, 0.84, 0.90);
    }
    model.component("comp2").geom("geom2").create("glassWall", "Union");
    model.component("comp2").geom("geom2").feature("glassWall")
        .label("Glass panels around open doorway");
    model.component("comp2").geom("geom2").feature("glassWall").selection("input")
        .set(glassTags);
    color(model, "glassWall", 0.62, 0.84, 0.90);

    String[] verticalX = {"-3[m]", "-1.525[m]", "-0.475[m]", "0.425[m]", "1.475[m]", "2.95[m]"};
    String[] frameTags = new String[15];
    int frameIndex = 0;
    for (int index = 0; index < verticalX.length; index++) {
      String tag = "frameV" + (index + 1);
      frameTags[frameIndex++] = tag;
      block(model, tag, "Grounded vertical metal frame " + (index + 1),
          new String[] {"frame_width", "frame_thickness", "partition_height"},
          new String[] {verticalX[index], "wall_y-frame_thickness/2", "0"},
          0.18, 0.22, 0.26);
    }

    String[][] horizontal = {
        {"-3[m]", "0", "2.55[m]"}, {"0.45[m]", "0", "2.55[m]"},
        {"-3[m]", "1.475[m]", "2.55[m]"}, {"0.45[m]", "1.475[m]", "2.55[m]"},
        {"-3[m]", "2.95[m]", "6[m]"}, {"-0.45[m]", "2.10[m]", "0.9[m]"},
        {"-0.45[m]", "0", "frame_width"}, {"0.40[m]", "0", "frame_width"},
        {"-0.45[m]", "door_height", "0.9[m]"}
    };
    for (int index = 0; index < horizontal.length; index++) {
      String tag = "frameH" + (index + 1);
      frameTags[frameIndex++] = tag;
      block(model, tag, "Grounded horizontal metal frame " + (index + 1),
          new String[] {horizontal[index][2], "frame_thickness", "frame_width"},
          new String[] {horizontal[index][0], "wall_y-frame_thickness/2", horizontal[index][1]},
          0.18, 0.22, 0.26);
    }
    model.component("comp2").geom("geom2").create("metalFrames", "Union");
    model.component("comp2").geom("geom2").feature("metalFrames")
        .label("Grounded metal frame surrounding doorway");
    model.component("comp2").geom("geom2").feature("metalFrames").selection("input")
        .set(frameTags);
    color(model, "metalFrames", 0.18, 0.22, 0.26);

    for (int index = 0; index < glass.length; index++) {
      visualBlock(model, "v9Glass" + (index + 1), "Visible glass panel " + (index + 1),
          new String[] {glass[index][2], "glass_thickness", glass[index][3]},
          new String[] {glass[index][0], "wall_y-glass_thickness/2", glass[index][1]},
          0.62, 0.84, 0.90);
    }
    for (int index = 0; index < verticalX.length; index++) {
      visualBlock(model, "v9FrameV" + (index + 1), "Visible vertical metal frame " + (index + 1),
          new String[] {"frame_width", "frame_thickness", "partition_height"},
          new String[] {verticalX[index], "wall_y-frame_thickness/2", "0"},
          0.18, 0.22, 0.26);
    }
    for (int index = 0; index < horizontal.length; index++) {
      visualBlock(model, "v9FrameH" + (index + 1), "Visible horizontal metal frame " + (index + 1),
          new String[] {horizontal[index][2], "frame_thickness", "frame_width"},
          new String[] {horizontal[index][0], "wall_y-frame_thickness/2", horizontal[index][1]},
          0.18, 0.22, 0.26);
    }

    for (int distance = 2; distance <= 4; distance++) {
      String tag = "obs" + distance;
      model.component("comp1").geom("geom1").feature().remove(tag);
      visualSphere(model, tag, "Observation point " + distance + " m from tank wall at 0.5 m height",
          new String[] {"0", "-(tank_diam/2+" + distance + "[m])", "obs_z"},
          0.92, 0.14, 0.12);
    }
    model.component("comp1").geom("geom1").run();

    for (int distance = 2; distance <= 4; distance++) {
      String tag = "obs" + distance;
      model.component("comp2").geom("geom2").feature().remove(tag);
      model.component("comp2").geom("geom2").create(tag, "Point");
      model.component("comp2").geom("geom2").feature(tag)
          .label("Observation point " + distance + " m from tank wall");
      model.component("comp2").geom("geom2").feature(tag).set("p",
          new String[] {"0", "-(tank_diam/2+" + distance + "[m])", "obs_z"});
      model.component("comp2").geom("geom2").feature(tag).set("selresult", true);
    }
    model.component("comp2").geom("geom2").run();

    material(model, "matGlassWall", "Architectural glass", "geom2_glassWall_dom",
        "sigma_glass", "epsr_glass");
    material(model, "matMetalFrames", "Grounded aluminum window and door frame",
        "geom2_metalFrames_dom", "sigma_frame", "1");

    model.component("comp2").physics("ec").create("gndFrames", "Ground", 2);
    model.component("comp2").physics("ec").feature("gndFrames")
        .label("Conventionally grounded metal window and door frames");
    model.component("comp2").physics("ec").feature("gndFrames").selection()
        .named("geom2_metalFrames_bnd");

    model.component("comp2").physics("ec").prop("ShapeProperty")
        .set("order_electricpotential", 1);
    model.component("comp2").mesh("mesh2").feature("size").set("hauto", 3);
    model.component("comp2").mesh("mesh2").feature("size").set("hmax", "0.65[m]");
    model.component("comp2").mesh("mesh2").feature("size").set("hmin", "8[mm]");

    double tankRadius = 0.28;
    for (int distance = 2; distance <= 4; distance++) {
      double y = -(tankRadius + distance);
      model.result().dataset("cp" + distance)
          .label("Observation point " + distance + " m from tank wall");
      model.result().dataset("cp" + distance).set("pointx", new double[] {0});
      model.result().dataset("cp" + distance).set("pointy", new double[] {y});
      model.result().dataset("cp" + distance).set("pointz", new double[] {0.5});
      model.result().numerical("eval" + distance)
          .label("Electric field " + distance + " m from tank wall");
    }

    model.study("stdField").label("Doorway environment independent and combined source cases");
    model.save(MODEL_FILE);
    return model;
  }

  public static void main(String[] args) throws Exception {
    run();
  }
}
