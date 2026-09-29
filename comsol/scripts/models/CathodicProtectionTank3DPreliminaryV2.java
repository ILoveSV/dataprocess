import com.comsol.model.Model;
import com.comsol.model.ModelEntityImage;
import com.comsol.model.util.ModelUtil;
import java.util.Arrays;

public class CathodicProtectionTank3DPreliminaryV2 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\comsol";
  private static final String MODEL_FILE =
      ROOT + "\\models\\cathodic_protection_tank_3d_preliminary_v2.mph";
  private static final String OUTPUT_DIR =
      ROOT + "\\results\\cathodic_protection_tank_3d_preliminary_v2";

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

  private static void setAxisY(Model model, String tag) {
    model.component("comp1").geom("geom1").feature(tag)
        .set("axis", new double[] {0, 1, 0});
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
    model.label("cathodic_protection_tank_3d_preliminary_v2.mph");
    model.title("Preliminary 3D Cathodic Discharge in 170 L Water Tank");
    model.description(
        "Preliminary ohmic-conduction baseline using the confirmed lid-electrode geometry. "
            + "The horizontal sealed 20# steel pipe has a 200 mm by 120 mm exposed window "
            + "facing a vertical graphite electrode. A 10 mA DC current is injected at graphite "
            + "and the exposed steel is the cathodic reference. Water conductivity is 0.05 S/m, "
            + "equivalent to 500 uS/cm. Electrode polarization and electrochemical kinetics are "
            + "intentionally deferred until measured operating data are provided.");

    model.param().set("tank_diam", "0.56[m]", "PE tank outside diameter");
    model.param().set("tank_h", "0.87[m]", "Tank height");
    model.param().set("tank_wall", "5[mm]", "Assumed PE tank wall thickness");
    model.param().set("tank_inner_r", "tank_diam/2-tank_wall", "Tank inside radius");
    model.param().set("water_volume", "170[L]", "Preliminary water volume");
    model.param().set("water_h", "water_volume/(pi*tank_inner_r^2)", "Calculated water depth");
    model.param().set("water_bottom_z", "-tank_h+tank_wall", "Water-domain bottom elevation");
    model.param().set("water_top_z", "water_bottom_z+water_h", "Calculated water-surface elevation");
    model.param().set("sigma_water", "0.05[S/m]", "500 uS/cm water conductivity");
    model.param().set("epsr_water", "80", "Preliminary relative permittivity of water");
    model.param().set("I_total", "10[mA]", "Preliminary constant discharge current");

    model.param().set("lid_diam", "0.56[m]", "Circular lid diameter");
    model.param().set("lid_thickness", "18[mm]", "Assumed circular lid thickness");
    model.param().set("back_plate_size", "0.62[m]", "Square support plate side length");
    model.param().set("back_plate_thickness", "12[mm]", "Square support plate thickness");
    model.param().set("electrode_spacing", "0.30[m]", "Steel-to-graphite center spacing");
    model.param().set("steel_pipe_length", "0.40[m]", "20# steel pipe length");
    model.param().set("steel_pipe_od", "0.10[m]", "Steel pipe outside diameter");
    model.param().set("steel_pipe_wall", "3[mm]", "Steel pipe wall thickness");
    model.param().set("steel_pipe_r", "steel_pipe_od/2", "Steel pipe outside radius");
    model.param().set("steel_pipe_inner_r", "steel_pipe_r-steel_pipe_wall",
        "Steel pipe inside radius");
    model.param().set("steel_pipe_center_z", "-0.30[m]", "Horizontal steel-pipe center elevation");
    model.param().set("window_length", "0.20[m]", "Exposed-window length along pipe axis");
    model.param().set("window_arc_width", "0.12[m]", "Exposed-window developed width");
    model.param().set("window_chord", "2*steel_pipe_r*sin(window_arc_width/(2*steel_pipe_r))",
        "Chord corresponding to the developed window width");
    model.param().set("tape_thickness", "1.5[mm]", "Assumed waterproof tape thickness");
    model.param().set("graphite_diam", "25[mm]", "Approximate graphite diameter");
    model.param().set("graphite_length", "0.20[m]", "Preliminary graphite active length");
    model.param().set("graphite_top_z", "-0.20[m]", "Graphite active-section top elevation");
    model.param().set("holder_diam", "32[mm]", "Equivalent holder diameter");
    model.param().set("lead_diam", "3[mm]", "Equivalent external DC lead diameter");
    model.param().set("support_embed", "5[mm]", "Small overlap ensuring rod-to-pipe contact");
    model.param().set("support_bottom_z",
        "steel_pipe_center_z+steel_pipe_r+tape_thickness-support_embed",
        "Bottom of simplified steel support rod");

    model.component().create("comp1", true);
    model.component("comp1").label("Tank and submerged cathodic-protection electrodes");
    model.component("comp1").geom().create("geom1", 3);
    model.component("comp1").geom("geom1").lengthUnit("m");
    model.component("comp1").mesh().create("mesh1");

    cylinder(model, "tankOuter", "PE tank outer body", "tank_diam/2", "tank_h",
        new String[] {"0", "0", "-tank_h"}, 0.92, 0.94, 0.89);
    cylinder(model, "tankCavity", "Tank cavity tool", "tank_inner_r", "tank_h-tank_wall",
        new String[] {"0", "0", "-tank_h+tank_wall"}, 0.92, 0.94, 0.89);
    difference(model, "tankShell", "PE hollow tank shell", "tankOuter", "tankCavity",
        0.92, 0.94, 0.89);

    cylinder(model, "waterBase", "170 L water before electrode cutouts", "tank_inner_r", "water_h",
        new String[] {"0", "0", "water_bottom_z"}, 0.20, 0.58, 0.90);

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
      cylinder(model, "glandNut" + suffix, "Feedthrough nut equivalent " + suffix,
          "35[mm]", "8[mm]",
          new String[] {electrodeX[i], "0", "back_plate_thickness"},
          0.38, 0.40, 0.42);
    }

    cylinder(model, "steelSupport", "Single stainless support rod for steel specimen",
        "holder_diam/2", "-lid_thickness-support_bottom_z",
        new String[] {"-electrode_spacing/2", "0", "support_bottom_z"},
        0.62, 0.64, 0.66);

    cylinder(model, "pipeOuter", "20# seamless carbon-steel pipe outer body",
        "steel_pipe_r", "steel_pipe_length",
        new String[] {"-electrode_spacing/2", "-steel_pipe_length/2", "steel_pipe_center_z"},
        0.50, 0.52, 0.54);
    setAxisY(model, "pipeOuter");
    cylinder(model, "pipeCavity", "Sealed-pipe cavity tool",
        "steel_pipe_inner_r", "steel_pipe_length-2*steel_pipe_wall",
        new String[] {"-electrode_spacing/2", "-steel_pipe_length/2+steel_pipe_wall",
            "steel_pipe_center_z"},
        0.15, 0.15, 0.15);
    setAxisY(model, "pipeCavity");
    difference(model, "pipeSteel", "Sealed 20# carbon-steel pipe specimen",
        "pipeOuter", "pipeCavity", 0.47, 0.49, 0.51);

    cylinder(model, "tapeOuter", "Waterproof tape outer cylinder",
        "steel_pipe_r+tape_thickness", "steel_pipe_length",
        new String[] {"-electrode_spacing/2", "-steel_pipe_length/2", "steel_pipe_center_z"},
        0.08, 0.45, 0.33);
    setAxisY(model, "tapeOuter");
    cylinder(model, "tapeInner", "Waterproof tape inner tool",
        "steel_pipe_r+0.1[mm]", "steel_pipe_length+0.4[mm]",
        new String[] {"-electrode_spacing/2", "-steel_pipe_length/2-0.2[mm]",
            "steel_pipe_center_z"},
        0.08, 0.45, 0.33);
    setAxisY(model, "tapeInner");
    difference(model, "tapeShell", "Waterproof tape cylindrical insulation",
        "tapeOuter", "tapeInner", 0.05, 0.47, 0.34);
    block(model, "windowTool", "Exposed-window tool facing graphite",
        new String[] {"steel_pipe_r+2*tape_thickness", "window_length", "window_chord"},
        new String[] {"-electrode_spacing/2", "-window_length/2",
            "steel_pipe_center_z-window_chord/2"},
        0.78, 0.30, 0.24);
    difference(model, "pipeTape", "Waterproof tape with exposed steel window",
        "tapeShell", "windowTool", 0.05, 0.47, 0.34);
    cylinder(model, "tapeEnd1", "Waterproof tape negative-y end seal",
        "steel_pipe_r+tape_thickness", "tape_thickness",
        new String[] {"-electrode_spacing/2", "-steel_pipe_length/2-tape_thickness",
            "steel_pipe_center_z"},
        0.05, 0.47, 0.34);
    setAxisY(model, "tapeEnd1");
    cylinder(model, "tapeEnd2", "Waterproof tape positive-y end seal",
        "steel_pipe_r+tape_thickness", "tape_thickness",
        new String[] {"-electrode_spacing/2", "steel_pipe_length/2", "steel_pipe_center_z"},
        0.05, 0.47, 0.34);
    setAxisY(model, "tapeEnd2");

    cylinder(model, "graphiteHolder", "Insulated graphite holder",
        "holder_diam/2", "0.18[m]",
        new String[] {"electrode_spacing/2", "0", "graphite_top_z"},
        0.08, 0.09, 0.10);
    cylinder(model, "graphite", "Graphite counter electrode",
        "graphite_diam/2", "graphite_length",
        new String[] {"electrode_spacing/2", "0", "graphite_top_z-graphite_length"},
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
      cylinder(model, "lidBolt" + (i + 1), "Lid fastener " + (i + 1),
          "5[mm]", "back_plate_thickness+lid_thickness",
          new String[] {Double.toString(0.225 * Math.cos(angle)),
              Double.toString(0.225 * Math.sin(angle)), "-lid_thickness"},
          0.32, 0.34, 0.36);
    }

    // Duplicate immersed volumes used only to subtract the electrodes from the water domain.
    cylinder(model, "wetPipeVolume", "Water cutout: sealed steel-pipe volume",
        "steel_pipe_r", "steel_pipe_length",
        new String[] {"-electrode_spacing/2", "-steel_pipe_length/2", "steel_pipe_center_z"},
        0.20, 0.58, 0.90);
    setAxisY(model, "wetPipeVolume");
    cylinder(model, "wetTapeOuter", "Water cutout: tape outer volume",
        "steel_pipe_r+tape_thickness", "steel_pipe_length",
        new String[] {"-electrode_spacing/2", "-steel_pipe_length/2", "steel_pipe_center_z"},
        0.20, 0.58, 0.90);
    setAxisY(model, "wetTapeOuter");
    block(model, "wetWindowTool", "Water cutout: exposed-window opening",
        new String[] {"steel_pipe_r+2*tape_thickness", "window_length", "window_chord"},
        new String[] {"-electrode_spacing/2", "-window_length/2",
            "steel_pipe_center_z-window_chord/2"},
        0.20, 0.58, 0.90);
    difference(model, "wetTapeBody", "Water cutout: tape volume excluding window",
        "wetTapeOuter", "wetWindowTool", 0.20, 0.58, 0.90);
    cylinder(model, "wetTapeEnd1", "Water cutout: negative-y tape seal",
        "steel_pipe_r+tape_thickness", "tape_thickness",
        new String[] {"-electrode_spacing/2", "-steel_pipe_length/2-tape_thickness",
            "steel_pipe_center_z"},
        0.20, 0.58, 0.90);
    setAxisY(model, "wetTapeEnd1");
    cylinder(model, "wetTapeEnd2", "Water cutout: positive-y tape seal",
        "steel_pipe_r+tape_thickness", "tape_thickness",
        new String[] {"-electrode_spacing/2", "steel_pipe_length/2", "steel_pipe_center_z"},
        0.20, 0.58, 0.90);
    setAxisY(model, "wetTapeEnd2");
    cylinder(model, "wetSteelSupport", "Water cutout: steel support rod",
        "holder_diam/2", "-lid_thickness-support_bottom_z",
        new String[] {"-electrode_spacing/2", "0", "support_bottom_z"},
        0.20, 0.58, 0.90);
    cylinder(model, "wetGraphiteHolder", "Water cutout: graphite holder",
        "holder_diam/2", "0.18[m]",
        new String[] {"electrode_spacing/2", "0", "graphite_top_z"},
        0.20, 0.58, 0.90);
    cylinder(model, "wetGraphite", "Water cutout: graphite active volume",
        "graphite_diam/2", "graphite_length",
        new String[] {"electrode_spacing/2", "0", "graphite_top_z-graphite_length"},
        0.20, 0.58, 0.90);

    model.component("comp1").geom("geom1").create("immersedTools", "Union");
    model.component("comp1").geom("geom1").feature("immersedTools")
        .label("All immersed solid cutout volumes");
    model.component("comp1").geom("geom1").feature("immersedTools").selection("input")
        .set(new String[] {"wetPipeVolume", "wetTapeBody", "wetTapeEnd1", "wetTapeEnd2",
            "wetSteelSupport", "wetGraphiteHolder", "wetGraphite"});
    model.component("comp1").geom("geom1").feature("immersedTools").set("intbnd", false);

    difference(model, "waterFluid", "Conductive water with immersed solids removed",
        "waterBase", "immersedTools", 0.20, 0.58, 0.90);

    model.component("comp1").geom("geom1").feature("fin").set("action", "union");
    model.component("comp1").geom("geom1").run();

    material(model, "matWater", "Water at 500 uS/cm",
        "geom1_waterFluid_dom", "sigma_water", "epsr_water");
    material(model, "matSteel", "20# seamless carbon steel",
        "geom1_pipeSteel_dom", "6.0e6[S/m]", "1");
    material(model, "matGraphite", "Graphite counter electrode",
        "geom1_graphite_dom", "1.0e5[S/m]", "1");

    model.component("comp1").physics().create("ec", "ConductiveMedia", "geom1");
    model.component("comp1").physics("ec").selection().named("geom1_waterFluid_dom");
    model.component("comp1").physics("ec").create("term1", "Terminal", 2);
    model.component("comp1").physics("ec").feature("term1")
        .selection().named("geom1_graphite_bnd");
    model.component("comp1").physics("ec").feature("term1").set("I0", "I_total");
    model.component("comp1").physics("ec").feature("term1")
        .label("10 mA graphite current terminal");
    model.component("comp1").physics("ec").create("gnd1", "Ground", 2);
    model.component("comp1").physics("ec").feature("gnd1")
        .selection().named("geom1_pipeSteel_bnd");
    model.component("comp1").physics("ec").feature("gnd1")
        .label("Grounded cathodic steel exposed window");

    System.out.println("WATER_DOMAINS=" + Arrays.toString(
        model.component("comp1").physics("ec").selection().entities()));
    System.out.println("GRAPHITE_TERMINAL_BOUNDARIES=" + Arrays.toString(
        model.component("comp1").physics("ec").feature("term1").selection().entities()));
    System.out.println("STEEL_GROUND_BOUNDARIES=" + Arrays.toString(
        model.component("comp1").physics("ec").feature("gnd1").selection().entities()));

    model.component("comp1").mesh("mesh1").autoMeshSize(3);
    model.component("comp1").mesh("mesh1").run();

    model.study().create("std1");
    model.study("std1").label("Stationary 10 mA cathodic discharge");
    model.study("std1").create("stat", "Stationary");
    model.study("std1").createAutoSequences("all");
    model.sol("sol1").runAll();

    model.result().numerical().create("terminalSummary", "EvalGlobal");
    model.result().numerical("terminalSummary").set("expr", new String[] {
        "ec.term1.V0_ode", "abs(ec.term1.V0_ode/I_total)",
        "abs(ec.term1.V0_ode*I_total)", "water_h", "water_top_z"});
    model.result().numerical("terminalSummary").set("descr", new String[] {
        "Graphite terminal voltage", "Equivalent water-path resistance",
        "Ohmic power", "Water depth", "Water-surface elevation"});
    model.result().table().create("tblTerminal", "Table");
    model.result().table("tblTerminal").label("Preliminary cathodic-discharge terminal summary");
    model.result().numerical("terminalSummary").set("table", "tblTerminal");
    model.result().numerical("terminalSummary").setResult();
    model.result().table("tblTerminal").save(OUTPUT_DIR + "\\terminal_summary.csv");

    model.result().numerical().create("maxField", "MaxVolume");
    model.result().numerical("maxField").selection().named("geom1_waterFluid_dom");
    model.result().numerical("maxField").set("expr",
        new String[] {"V", "ec.normE", "ec.normJ"});
    model.result().numerical("maxField").set("descr",
        new String[] {"Maximum water potential", "Maximum water electric field",
            "Maximum water current density"});
    model.result().table().create("tblMax", "Table");
    model.result().table("tblMax").label("Maximum water-domain values");
    model.result().numerical("maxField").set("table", "tblMax");
    model.result().numerical("maxField").setResult();
    model.result().table("tblMax").save(OUTPUT_DIR + "\\water_field_maximum.csv");

    model.result().numerical().create("avgField", "AvVolume");
    model.result().numerical("avgField").selection().named("geom1_waterFluid_dom");
    model.result().numerical("avgField").set("expr",
        new String[] {"V", "ec.normE", "ec.normJ"});
    model.result().numerical("avgField").set("descr",
        new String[] {"Average water potential", "Average water electric field",
            "Average water current density"});
    model.result().table().create("tblAvg", "Table");
    model.result().table("tblAvg").label("Average water-domain values");
    model.result().numerical("avgField").set("table", "tblAvg");
    model.result().numerical("avgField").setResult();
    model.result().table("tblAvg").save(OUTPUT_DIR + "\\water_field_average.csv");

    model.result().create("pgPotential", "PlotGroup3D");
    model.result("pgPotential").label("Water electric potential on electrode-center plane");
    model.result("pgPotential").set("showlegendsmaxmin", true);
    model.result("pgPotential").feature().create("slice1", "Slice");
    model.result("pgPotential").feature("slice1").set("expr", "V");
    model.result("pgPotential").feature("slice1").set("unit", "V");
    model.result("pgPotential").feature("slice1").set("quickplane", "zx");
    model.result("pgPotential").feature("slice1").set("quickynumber", 1);
    model.result("pgPotential").feature("slice1").set("colortable", "Dipole");

    model.result().create("pgCurrent", "PlotGroup3D");
    model.result("pgCurrent").label("Water current-density magnitude on electrode-center plane");
    model.result("pgCurrent").set("showlegendsmaxmin", true);
    model.result("pgCurrent").feature().create("slice1", "Slice");
    model.result("pgCurrent").feature("slice1").set("expr", "max(ec.normJ,1e-9[A/m^2])");
    model.result("pgCurrent").feature("slice1").set("unit", "A/m^2");
    model.result("pgCurrent").feature("slice1").set("quickplane", "zx");
    model.result("pgCurrent").feature("slice1").set("quickynumber", 1);
    model.result("pgCurrent").feature("slice1").set("colorscalemode", "logarithmic");
    model.result("pgCurrent").feature("slice1").set("colortable", "ThermalLight");

    model.component("comp1").view("view1").camera().set("projection", "orthographic");
    model.component("comp1").view("view1").camera()
        .set("position", new double[] {1.25, -1.45, 0.15});
    model.component("comp1").view("view1").camera()
        .set("target", new double[] {0, 0, -0.42});
    model.component("comp1").view("view1").camera().set("up", new double[] {0, 0, 1});
    model.component("comp1").view("view1").camera().set("orthoscale", 0.88);

    model.result().export().create("imgPotential", "Image3D");
    model.result().export("imgPotential").set("plotgroup", "pgPotential");
    model.result().export("imgPotential").set("pngfilename",
        OUTPUT_DIR + "\\water_potential_center_plane.png");
    model.result().export("imgPotential").set("width", 1600);
    model.result().export("imgPotential").set("height", 1200);
    model.result().export("imgPotential").run();

    model.result().export().create("imgCurrent", "Image3D");
    model.result().export("imgCurrent").set("plotgroup", "pgCurrent");
    model.result().export("imgCurrent").set("pngfilename",
        OUTPUT_DIR + "\\water_current_density_center_plane.png");
    model.result().export("imgCurrent").set("width", 1600);
    model.result().export("imgCurrent").set("height", 1200);
    model.result().export("imgCurrent").run();

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
    image.set("widthpx", "1600");
    image.set("heightpx", "1400");
    image.set("pngfilename", OUTPUT_DIR + "\\tank_electrode_geometry.png");
    image.export();

    model.save(MODEL_FILE);
    System.out.println("MODEL_FILE=" + MODEL_FILE);
    System.out.println("OUTPUT_DIR=" + OUTPUT_DIR);
    ModelUtil.remove("Model");
    return null;
  }

  public static void main(String[] args) throws Exception {
    run();
  }
}
