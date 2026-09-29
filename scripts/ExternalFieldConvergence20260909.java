import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class ExternalFieldConvergence20260909 {
  private static final String ROOT="C:/Users/17584/Documents/ALearning/Project/tools/DataProcess";
  private static final String OUTPUT_DIR=ROOT+"/results/thesis_followup_20260909/external";
  private static String CASE="";
  private static double GAP=20,SHIFT=0,RADIUS=10,HEIGHT=3,MESH_SCALE=1;
  private static boolean FIX_HEAD=true,FIX_TAPE=false;
  private static String EXCITATION="balanced";
  private static void color(Model model, String tag, double r, double g, double b) {
    model.component("comp1").geom("geom1").feature(tag).set("selresult", true);
    model.component("comp1").geom("geom1").feature(tag).set("selresultshow", "all");
    model.component("comp1").geom("geom1").feature(tag).set("color", "custom");
    model.component("comp1").geom("geom1").feature(tag)
        .set("customcolor", new double[] {r, g, b});
  }

  private static void cylinder(
      Model model, String tag, String label, String radius, String height,
      String[] pos, double r, double g, double b) {
    model.component("comp1").geom("geom1").create(tag, "Cylinder");
    model.component("comp1").geom("geom1").feature(tag).label(label);
    model.component("comp1").geom("geom1").feature(tag).set("r", radius);
    model.component("comp1").geom("geom1").feature(tag).set("h", height);
    model.component("comp1").geom("geom1").feature(tag).set("pos", pos);
    color(model, tag, r, g, b);
  }

  private static void cylinderBetween(
      Model model, String tag, String label, String radius,
      double[] from, double[] to, double r, double g, double b) {
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

  private static void setAxisY(Model model, String tag) {
    model.component("comp1").geom("geom1").feature(tag)
        .set("axis", new double[] {0, 1, 0});
  }

  private static void block(
      Model model, String tag, String label, String[] size, String[] pos,
      double r, double g, double b) {
    model.component("comp1").geom("geom1").create(tag, "Block");
    model.component("comp1").geom("geom1").feature(tag).label(label);
    model.component("comp1").geom("geom1").feature(tag).set("size", size);
    model.component("comp1").geom("geom1").feature(tag).set("pos", pos);
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

  private static void potential(
      Model model, String tag, String label, String selection, String value) {
    model.component("comp1").physics("ec").create(tag, "ElectricPotential", 2);
    model.component("comp1").physics("ec").feature(tag).label(label);
    model.component("comp1").physics("ec").feature(tag).selection().named(selection);
    model.component("comp1").physics("ec").feature(tag).set("V0", value);
  }

  public static Model run() throws Exception {
    Model model = ModelUtil.create("Model");
    model.modelPath(OUTPUT_DIR);
    model.label("cathodic_protection_external_field_v4.mph");
    model.title("Floating Cathodic-Protection External Electric-Field Transfer V4");
    model.description(
        "A conservative standalone 10 m electroquasistatic model for the cathodic-protection "
            + "source. The isolated DC output is represented by a balanced plus/minus 0.5 V "
            + "differential excitation. The reported twisted pair is represented by a compact "
            + "6 mm center-spacing parallel-pair envelope, which omits additional cancellation "
            + "from the actual twists and therefore acts as a conservative transfer estimate. "
            + "The 1 mHz frequency is a numerical proxy for the static field; results are scaled "
            + "by the measured stable terminal voltages 0.2, 0.5, 0.7, and 1.2 V.");

    model.param().set("air_radius", RADIUS+"[m]", "Same conservative radius used by V13");
    model.param().set("air_height", HEIGHT+"[m]", "Laboratory air-domain height");
    model.param().set("floor_thickness", "0.5[m]", "Equivalent laboratory floor");
    model.param().set("tank_diam", "0.56[m]", "Tank outside diameter");
    model.param().set("tank_h", "0.87[m]", "Tank height");
    model.param().set("tank_wall", "5[mm]", "Assumed PE wall thickness");
    model.param().set("tank_inner_r", "tank_diam/2-tank_wall", "Tank inside radius");
    model.param().set("water_volume", "170[L]", "Baseline water volume");
    model.param().set("water_h", "water_volume/(pi*tank_inner_r^2)", "Water depth");
    model.param().set("sigma_water", "0.05[S/m]", "Confirmed 500 uS/cm");
    model.param().set("lid_thickness", "18[mm]", "Assumed lid thickness");
    model.param().set("back_plate_size", "0.62[m]", "Support-plate side length");
    model.param().set("back_plate_thickness", "12[mm]", "Support-plate thickness");
    model.param().set("steel_pipe_r", "50[mm]", "Steel-pipe outside radius");
    model.param().set("steel_pipe_length", "0.40[m]", "Steel-pipe length");
    model.param().set("graphite_r", "12.5[mm]", "Graphite radius");
    model.param().set("graphite_length", "0.20[m]", "Graphite active length");
    model.param().set("electrode_gap", GAP+"[mm]", "Confirmed minimum surface gap");
    model.param().set("electrode_spacing", "steel_pipe_r+graphite_r+electrode_gap",
        "Axis spacing corresponding to the surface gap");
    model.param().set("suspension_length", "0.35[m]", "Provisional suspension-rod length");
    model.param().set("support_embed", "5[mm]", "Small rod-to-pipe overlap");
    model.param().set("tape_thickness", "1.5[mm]", "Waterproof tape thickness");
    model.param().set("window_length", "0.20[m]", "Steel exposed-window axial length");
    model.param().set("window_arc_width", "0.12[m]", "Steel window developed width");
    model.param().set("window_chord", "2*steel_pipe_r*sin(window_arc_width/(2*steel_pipe_r))",
        "Window chord");
    model.param().set("lid_under_z", "tank_h-lid_thickness", "Lid underside elevation");
    model.param().set("support_bottom_z", "lid_under_z-suspension_length",
        "Bottom of both suspension holders");
    model.param().set("steel_center_z",
        "support_bottom_z+support_embed-(steel_pipe_r+tape_thickness)",
        "Horizontal steel-pipe center elevation");
    model.param().set("graphite_top_z", "support_bottom_z", "Graphite active-section top");
    model.param().set("wire_radius", "1.5[mm]", "Equivalent output-wire conductor radius");
    model.param().set("V_diff_unit", "1[V]", "Unit balanced differential excitation");
    model.param().set("f_dc_proxy", "1e-3[Hz]", "Low-frequency numerical proxy for DC");

    model.param().set("pair_x", SHIFT+"[mm]");
    model.component().create("comp1", true);
    model.component("comp1").label("Cathodic-protection source and 10 m environment");
    model.component("comp1").geom().create("geom1", 3);
    model.component("comp1").geom("geom1").lengthUnit("m");

    cylinder(model, "airBase", "10 m air-domain precursor", "air_radius", "air_height",
        new String[] {"0", "0", "0"}, 0.72, 0.86, 0.95);
    block(model, "floor", "Grounded reinforced-concrete floor",
        new String[] {"2*air_radius", "2*air_radius", "floor_thickness"},
        new String[] {"-air_radius", "-air_radius", "-floor_thickness"},
        0.46, 0.47, 0.48);

    cylinder(model, "tankOuter", "PE tank outer body", "tank_diam/2", "tank_h",
        new String[] {"0", "0", "0"}, 0.92, 0.94, 0.89);
    cylinder(model, "tankCavity", "Tank cavity tool", "tank_inner_r", "tank_h-tank_wall",
        new String[] {"0", "0", "tank_wall"}, 0.92, 0.94, 0.89);
    difference(model, "tankShell", "PE tank shell", "tankOuter", "tankCavity",
        0.92, 0.94, 0.89);
    cylinder(model, "roundLid", "PE circular tank lid", "tank_diam/2", "lid_thickness",
        new String[] {"0", "0", "lid_under_z"}, 0.84, 0.88, 0.80);
    block(model, "backPlate", "PE square support plate",
        new String[] {"back_plate_size", "back_plate_size", "back_plate_thickness"},
        new String[] {"-back_plate_size/2", "-back_plate_size/2", "tank_h"},
        0.92, 0.94, 0.90);

    cylinder(model, "waterBase", "170 L water before electrode cutouts",
        "tank_inner_r", "water_h", new String[] {"0", "0", "tank_wall"},
        0.20, 0.58, 0.90);

    cylinder(model, "steel", "Negative 20# steel-pipe conductor",
        "steel_pipe_r", "steel_pipe_length",
        new String[] {"-electrode_spacing/2+pair_x", "-steel_pipe_length/2", "steel_center_z"},
        0.48, 0.50, 0.52);
    setAxisY(model, "steel");
    cylinder(model, "tapeOuter", "Steel-pipe waterproof-tape outer surface",
        "steel_pipe_r+tape_thickness", "steel_pipe_length",
        new String[] {"-electrode_spacing/2+pair_x", "-steel_pipe_length/2", "steel_center_z"},
        0.05, 0.47, 0.34);
    setAxisY(model, "tapeOuter");
    cylinder(model, "tapeInner", "Steel-pipe waterproof-tape inner tool",
        FIX_TAPE ? "steel_pipe_r" : "steel_pipe_r+0.1[mm]", "steel_pipe_length+0.4[mm]",
        new String[] {"-electrode_spacing/2+pair_x", "-steel_pipe_length/2-0.2[mm]", "steel_center_z"},
        0.05, 0.47, 0.34);
    setAxisY(model, "tapeInner");
    difference(model, "tapeShell", "Steel-pipe tape shell", "tapeOuter", "tapeInner",
        0.05, 0.47, 0.34);
    block(model, "windowTool", "Steel exposed-window tool facing graphite",
        new String[] {"steel_pipe_r+2*tape_thickness", "window_length", "window_chord"},
        new String[] {"-electrode_spacing/2+pair_x", "-window_length/2",
            "steel_center_z-window_chord/2"},
        0.78, 0.30, 0.24);
    difference(model, "pipeTape", "Tape insulation with exposed steel window",
        "tapeShell", "windowTool", 0.05, 0.47, 0.34);
    cylinder(model, "tapeEnd1", "Negative-y tape end seal",
        "steel_pipe_r+tape_thickness", "tape_thickness",
        new String[] {"-electrode_spacing/2+pair_x", "-steel_pipe_length/2-tape_thickness",
            "steel_center_z"}, 0.05, 0.47, 0.34);
    setAxisY(model, "tapeEnd1");
    cylinder(model, "tapeEnd2", "Positive-y tape end seal",
        "steel_pipe_r+tape_thickness", "tape_thickness",
        new String[] {"-electrode_spacing/2+pair_x", "steel_pipe_length/2", "steel_center_z"},
        0.05, 0.47, 0.34);
    setAxisY(model, "tapeEnd2");
    cylinder(model, "steelHolder", "Insulated negative suspension holder",
        "16[mm]", "suspension_length",
        new String[] {"-electrode_spacing/2+pair_x", "0", "support_bottom_z"},
        0.12, 0.13, 0.14);
    cylinder(model, "graphiteHolder", "Insulated positive suspension holder",
        "16[mm]", "suspension_length",
        new String[] {"electrode_spacing/2+pair_x", "0", "support_bottom_z"},
        0.12, 0.13, 0.14);
    cylinder(model, "graphite", "Positive graphite electrode",
        "graphite_r", "graphite_length",
        new String[] {"electrode_spacing/2+pair_x", "0", "graphite_top_z-graphite_length"},
        0.10, 0.10, 0.11);

    // Compact differential-pair envelope from the isolated supply beside the pump to the lid.
    double[] negStart = {0.92, -0.303, 0.30};
    double[] posStart = {0.92, -0.297, 0.30};
    double[] negEnd = {0.0, -0.033, 0.90};
    double[] posEnd = {0.0, -0.027, 0.90};
    double xNeg = SHIFT/1000-(GAP/1000+.0625)/2;
    double xPos = SHIFT/1000+(GAP/1000+.0625)/2;
    cylinderBetween(model, "negTrunk", "Compact negative output core", "wire_radius",
        negStart, negEnd, 0.08, 0.18, 0.72);
    cylinderBetween(model, "posTrunk", "Compact positive output core", "wire_radius",
        posStart, posEnd, 0.82, 0.10, 0.08);
    cylinderBetween(model, "negBranch", "Negative branch to steel feedthrough", "wire_radius",
        negEnd, new double[] {xNeg, 0.0, 0.90}, 0.08, 0.18, 0.72);
    cylinderBetween(model, "posBranch", "Positive branch to graphite feedthrough", "wire_radius",
        posEnd, new double[] {xPos, 0.0, 0.90}, 0.82, 0.10, 0.08);
    cylinder(model, "negStub", "Negative feedthrough conductor", "wire_radius", "48[mm]",
        new String[] {"-electrode_spacing/2+pair_x", "0", "lid_under_z"}, 0.08, 0.18, 0.72);
    cylinder(model, "posStub", "Positive feedthrough conductor", "wire_radius", "48[mm]",
        new String[] {"electrode_spacing/2+pair_x", "0", "lid_under_z"}, 0.82, 0.10, 0.08);
    block(model, "sourceBox", "Passive grounded DC-supply chassis on wooden pump board",
        new String[] {"0.30[m]", "0.22[m]", "0.22[m]"},
        new String[] {"0.95[m]", "-0.41[m]", "0.08[m]"},
        0.22, 0.23, 0.25);

    // Duplicate immersed occupancy used to cut a nonoverlapping water domain.
    cylinder(model, "wetSteel", "Water cutout: steel-pipe volume",
        "steel_pipe_r", "steel_pipe_length",
        new String[] {"-electrode_spacing/2+pair_x", "-steel_pipe_length/2", "steel_center_z"},
        0.20, 0.58, 0.90);
    setAxisY(model, "wetSteel");
    cylinder(model, "wetTapeOuter", "Water cutout: tape outer volume",
        "steel_pipe_r+tape_thickness", "steel_pipe_length",
        new String[] {"-electrode_spacing/2+pair_x", "-steel_pipe_length/2", "steel_center_z"},
        0.20, 0.58, 0.90);
    setAxisY(model, "wetTapeOuter");
    block(model, "wetWindowTool", "Water cutout: steel window",
        new String[] {"steel_pipe_r+2*tape_thickness", "window_length", "window_chord"},
        new String[] {"-electrode_spacing/2+pair_x", "-window_length/2",
            "steel_center_z-window_chord/2"}, 0.20, 0.58, 0.90);
    difference(model, "wetTapeBody", "Water cutout: tape excluding window",
        "wetTapeOuter", "wetWindowTool", 0.20, 0.58, 0.90);
    cylinder(model, "wetTapeEnd1", "Water cutout: negative-y tape seal",
        "steel_pipe_r+tape_thickness", "tape_thickness",
        new String[] {"-electrode_spacing/2+pair_x", "-steel_pipe_length/2-tape_thickness",
            "steel_center_z"}, 0.20, 0.58, 0.90);
    setAxisY(model, "wetTapeEnd1");
    cylinder(model, "wetTapeEnd2", "Water cutout: positive-y tape seal",
        "steel_pipe_r+tape_thickness", "tape_thickness",
        new String[] {"-electrode_spacing/2+pair_x", "steel_pipe_length/2", "steel_center_z"},
        0.20, 0.58, 0.90);
    setAxisY(model, "wetTapeEnd2");
    cylinder(model, "wetSteelHolder", "Water cutout: negative holder", "16[mm]",
        "suspension_length", new String[] {"-electrode_spacing/2+pair_x", "0", "support_bottom_z"},
        0.20, 0.58, 0.90);
    cylinder(model, "wetGraphiteHolder", "Water cutout: positive holder", "16[mm]",
        "suspension_length", new String[] {"electrode_spacing/2+pair_x", "0", "support_bottom_z"},
        0.20, 0.58, 0.90);
    cylinder(model, "wetGraphite", "Water cutout: graphite volume", "graphite_r",
        "graphite_length", new String[] {"electrode_spacing/2+pair_x", "0",
            "graphite_top_z-graphite_length"}, 0.20, 0.58, 0.90);
    model.component("comp1").geom("geom1").create("waterTools", "Union");
    model.component("comp1").geom("geom1").feature("waterTools")
        .label("All immersed solid occupancy");
    model.component("comp1").geom("geom1").feature("waterTools").selection("input")
        .set(new String[] {"wetSteel", "wetTapeBody", "wetTapeEnd1", "wetTapeEnd2",
            "wetSteelHolder", "wetGraphiteHolder", "wetGraphite"});
    model.component("comp1").geom("geom1").feature("waterTools").set("intbnd", false);
    difference(model, "waterFluid", "Conductive water with immersed solids removed",
        "waterBase", "waterTools", 0.20, 0.58, 0.90);

    // Duplicate outside occupancy used to cut a nonoverlapping air domain.
    cylinder(model, "airTankCut", "Air cutout: complete tank envelope", "tank_diam/2", "tank_h",
        new String[] {"0", "0", "0"}, 0.72, 0.86, 0.95);
    block(model, "airPlateCut", "Air cutout: support plate",
        new String[] {"back_plate_size", "back_plate_size", "back_plate_thickness"},
        new String[] {"-back_plate_size/2", "-back_plate_size/2", "tank_h"},
        0.72, 0.86, 0.95);
    cylinderBetween(model, "airNegTrunkCut", "Air cutout: negative trunk", "wire_radius",
        negStart, negEnd, 0.72, 0.86, 0.95);
    cylinderBetween(model, "airPosTrunkCut", "Air cutout: positive trunk", "wire_radius",
        posStart, posEnd, 0.72, 0.86, 0.95);
    cylinderBetween(model, "airNegBranchCut", "Air cutout: negative branch", "wire_radius",
        negEnd, new double[] {xNeg, 0.0, 0.90}, 0.72, 0.86, 0.95);
    cylinderBetween(model, "airPosBranchCut", "Air cutout: positive branch", "wire_radius",
        posEnd, new double[] {xPos, 0.0, 0.90}, 0.72, 0.86, 0.95);
    cylinder(model, "airNegStubCut", "Air cutout: negative feedthrough", "wire_radius", "48[mm]",
        new String[] {"-electrode_spacing/2+pair_x", "0", "lid_under_z"}, 0.72, 0.86, 0.95);
    cylinder(model, "airPosStubCut", "Air cutout: positive feedthrough", "wire_radius", "48[mm]",
        new String[] {"electrode_spacing/2+pair_x", "0", "lid_under_z"}, 0.72, 0.86, 0.95);
    block(model, "airSourceCut", "Air cutout: DC-supply chassis",
        new String[] {"0.30[m]", "0.22[m]", "0.22[m]"},
        new String[] {"0.95[m]", "-0.41[m]", "0.08[m]"}, 0.72, 0.86, 0.95);
    model.component("comp1").geom("geom1").create("airTools", "Union");
    model.component("comp1").geom("geom1").feature("airTools")
        .label("All solid occupancy removed from outside air");
    model.component("comp1").geom("geom1").feature("airTools").selection("input")
        .set(new String[] {"airTankCut", "airPlateCut", "airNegTrunkCut", "airPosTrunkCut",
            "airNegBranchCut", "airPosBranchCut", "airNegStubCut", "airPosStubCut",
            "airSourceCut"});
    model.component("comp1").geom("geom1").feature("airTools").set("intbnd", false);
    difference(model, "airFluid", "Outside air with source solids removed",
        "airBase", "airTools", 0.72, 0.86, 0.95);

    if(FIX_HEAD) {
      cylinder(model,"headBase","Explicit enclosed tank headspace","tank_inner_r","lid_under_z-tank_wall-water_h",new String[]{"0","0","tank_wall+water_h"},.72,.86,.95);
      cylinder(model,"headNegCut","Headspace negative holder cut","16[mm]","suspension_length",new String[]{"-electrode_spacing/2+pair_x","0","support_bottom_z"},.72,.86,.95);
      cylinder(model,"headPosCut","Headspace positive holder cut","16[mm]","suspension_length",new String[]{"electrode_spacing/2+pair_x","0","support_bottom_z"},.72,.86,.95);
      model.component("comp1").geom("geom1").create("headAir","Difference");
      model.component("comp1").geom("geom1").feature("headAir").selection("input").set("headBase");
      model.component("comp1").geom("geom1").feature("headAir").selection("input2").set(new String[]{"headNegCut","headPosCut"});
      color(model,"headAir",.72,.86,.95);
    }
    model.component("comp1").geom("geom1").feature("fin").set("action", "union");
    model.component("comp1").geom("geom1").run();

    material(model, "matAir", "Air", "geom1_airFluid_dom", "1e-14[S/m]", "1.0006");
    material(model, "matFloor", "Equivalent reinforced concrete", "geom1_floor_dom",
        "1e-5[S/m]", "5");
    material(model, "matTank", "PE tank shell", "geom1_tankShell_dom", "1e-15[S/m]", "2.3");
    material(model, "matLid", "PE tank lid", "geom1_roundLid_dom", "1e-15[S/m]", "2.3");
    material(model, "matPlate", "PE support plate", "geom1_backPlate_dom", "1e-15[S/m]", "2.3");
    material(model, "matWater", "Tap water at 500 uS/cm", "geom1_waterFluid_dom",
        "sigma_water", "80");
    material(model, "matSteel", "20# steel negative electrode", "geom1_steel_dom",
        "6e6[S/m]", "1");
    material(model, "matGraphite", "Graphite positive electrode", "geom1_graphite_dom",
        "1e5[S/m]", "1");
    material(model, "matTape", "Waterproof tape", "geom1_pipeTape_dom", "1e-15[S/m]", "3.2");
    material(model, "matTapeEnd1", "Waterproof tape end 1", "geom1_tapeEnd1_dom", "1e-15[S/m]", "3.2");
    material(model, "matTapeEnd2", "Waterproof tape end 2", "geom1_tapeEnd2_dom", "1e-15[S/m]", "3.2");
    material(model, "matSteelHolder", "Negative insulated holder", "geom1_steelHolder_dom",
        "1e-15[S/m]", "3.2");
    material(model, "matGraphiteHolder", "Positive insulated holder", "geom1_graphiteHolder_dom",
        "1e-15[S/m]", "3.2");
    material(model, "matNegTrunk", "Negative output copper", "geom1_negTrunk_dom", "5.8e7[S/m]", "1");
    material(model, "matPosTrunk", "Positive output copper", "geom1_posTrunk_dom", "5.8e7[S/m]", "1");
    material(model, "matNegBranch", "Negative branch copper", "geom1_negBranch_dom", "5.8e7[S/m]", "1");
    material(model, "matPosBranch", "Positive branch copper", "geom1_posBranch_dom", "5.8e7[S/m]", "1");
    material(model, "matNegStub", "Negative feedthrough copper", "geom1_negStub_dom", "5.8e7[S/m]", "1");
    material(model, "matPosStub", "Positive feedthrough copper", "geom1_posStub_dom", "5.8e7[S/m]", "1");
    material(model, "matSource", "Passive grounded supply chassis", "geom1_sourceBox_dom",
        "3.5e7[S/m]", "1");

    if(FIX_HEAD) material(model,"matHeadAir","Enclosed air above water","geom1_headAir_dom","1e-14[S/m]","1.0006");
    model.component("comp1").physics().create("ec", "ConductiveMedia", "geom1");
    model.component("comp1").physics("ec")
        .label("Electroquasistatic balanced differential transfer at 1 mHz");
    model.component("comp1").physics("ec").prop("ShapeProperty")
        .set("order_electricpotential", 1);
    model.component("comp1").physics("ec").create("gndFloor", "Ground", 2);
    model.component("comp1").physics("ec").feature("gndFloor")
        .selection().named("geom1_floor_bnd");
    model.component("comp1").physics("ec").create("gndSource", "Ground", 2);
    model.component("comp1").physics("ec").feature("gndSource")
        .selection().named("geom1_sourceBox_bnd");

    potential(model, "potSteel", "Balanced negative steel potential", "geom1_steel_bnd",
        EXCITATION.equals("single") ? "0[V]" : "-V_diff_unit/2");
    potential(model, "potNegTrunk", "Balanced negative trunk potential", "geom1_negTrunk_bnd",
        EXCITATION.equals("single") ? "0[V]" : "-V_diff_unit/2");
    potential(model, "potNegBranch", "Balanced negative branch potential", "geom1_negBranch_bnd",
        EXCITATION.equals("single") ? "0[V]" : "-V_diff_unit/2");
    potential(model, "potNegStub", "Balanced negative feedthrough potential", "geom1_negStub_bnd",
        EXCITATION.equals("single") ? "0[V]" : "-V_diff_unit/2");
    potential(model, "potGraphite", "Balanced positive graphite potential", "geom1_graphite_bnd",
        EXCITATION.equals("single") ? "V_diff_unit" : "V_diff_unit/2");
    potential(model, "potPosTrunk", "Balanced positive trunk potential", "geom1_posTrunk_bnd",
        EXCITATION.equals("single") ? "V_diff_unit" : "V_diff_unit/2");
    potential(model, "potPosBranch", "Balanced positive branch potential", "geom1_posBranch_bnd",
        EXCITATION.equals("single") ? "V_diff_unit" : "V_diff_unit/2");
    potential(model, "potPosStub", "Balanced positive feedthrough potential", "geom1_posStub_bnd",
        EXCITATION.equals("single") ? "V_diff_unit" : "V_diff_unit/2");

    model.component("comp1").mesh().create("mesh1");
    model.component("comp1").mesh("mesh1").create("ftet1", "FreeTet");
    model.component("comp1").mesh("mesh1").feature("size").set("hauto", 3);
    model.component("comp1").mesh("mesh1").feature("size").set("hmax",(0.8*MESH_SCALE)+"[m]");
    model.component("comp1").mesh("mesh1").feature("size").set("hmin",(2*MESH_SCALE)+"[mm]");

    model.study().create("std1");
    model.study("std1").label("Unit floating cathodic-protection differential transfer");
    model.study("std1").create("freq", "Frequency");
    model.study("std1").feature("freq").set("plist", "f_dc_proxy");
    model.study("std1").feature("freq").set("activate", new String[] {"ec", "on"});
    model.study("std1").createAutoSequences("all");
    model.sol("sol1").runAll();

    for (int distance = 2; distance <= 4; distance++) {
      String ds = "cp" + distance;
      model.result().dataset().create(ds, "CutPoint3D");
      model.result().dataset(ds).label("Observation point " + distance + " m from tank wall");
      model.result().dataset(ds).set("pointx", new double[] {0});
      model.result().dataset(ds).set("pointy", new double[] {-(0.28 + distance)});
      model.result().dataset(ds).set("pointz", new double[] {0.5});
      String eval = "eval" + distance;
      model.result().numerical().create(eval, "EvalPoint");
      model.result().numerical(eval).set("data", ds);
      model.result().numerical(eval).set("expr",
          new String[] {"real(V)","imag(V)","real(ec.Ex)","imag(ec.Ex)","real(ec.Ey)","imag(ec.Ey)","real(ec.Ez)","imag(ec.Ez)","ec.normE"});
      String table = "tbl" + distance;
      model.result().table().create(table, "Table");
      model.result().table(table).label("Unit transfer at " + distance + " m from tank wall");
      model.result().numerical(eval).set("table", table);
      model.result().numerical(eval).setResult();
      model.result().table(table).save(OUTPUT_DIR + "/"+CASE+"_" + distance + "m.csv");
    }

    model.label(CASE+".mph");
    model.title("Conditional balanced/single-ended external-field geometry audit");
    model.description("Historical V4 derivative. Explicit headspace and optional closed tape gap. Specified ground-referenced drive, not a validated floating circuit.");
    model.save(OUTPUT_DIR+"/"+CASE+".mph");
    System.out.println("DONE "+CASE);
    ModelUtil.remove("Model");
    return null;
  }

  public static void main(String[] args) throws Exception {
    String[] names={"mesh_coarse","mesh_fine","domain_medium","domain_large"};
    double[][] jobs={{10,3,1.3},{10,3,.75},{15,6,1},{20,9,1}};
    FIX_HEAD=true;FIX_TAPE=true;
    for(int k=0;k<jobs.length;k++){
      CASE=names[k];RADIUS=jobs[k][0];HEIGHT=jobs[k][1];MESH_SCALE=jobs[k][2];
      try{run();}catch(Exception e){e.printStackTrace();System.out.println("FAILED "+CASE);try{ModelUtil.remove("Model");}catch(Exception ignored){}}
    }
  }
}
