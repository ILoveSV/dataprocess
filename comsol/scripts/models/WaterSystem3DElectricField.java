import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class WaterSystem3DElectricField {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\comsol";
  private static final String INPUT_FILE = ROOT + "\\models\\water_system_3d_geometry_v2.mph";
  private static final String MODEL_FILE = ROOT + "\\models\\water_system_3d_electric_field_v3.mph";

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

  private static void cylinder(
      Model model, String tag, String label, String radius, double[] from, double[] to,
      double r, double g, double b) {
    double dx = to[0] - from[0];
    double dy = to[1] - from[1];
    double dz = to[2] - from[2];
    double length = Math.sqrt(dx * dx + dy * dy + dz * dz);
    model.component("comp2").geom("geom2").create(tag, "Cylinder");
    model.component("comp2").geom("geom2").feature(tag).label(label);
    model.component("comp2").geom("geom2").feature(tag).set("r", radius);
    model.component("comp2").geom("geom2").feature(tag).set("h", length);
    model.component("comp2").geom("geom2").feature(tag).set("pos", from);
    model.component("comp2").geom("geom2").feature(tag)
        .set("axis", new double[] {dx, dy, dz});
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

  private static void potential(Model model, String tag, String label, String selection, String value) {
    model.component("comp2").physics("ec").create(tag, "ElectricPotential", 2);
    model.component("comp2").physics("ec").feature(tag).label(label);
    model.component("comp2").physics("ec").feature(tag).selection().named(selection);
    model.component("comp2").physics("ec").feature(tag).set("V0", value);
  }

  public static Model run() throws Exception {
    Model model = ModelUtil.load("Model", INPUT_FILE);
    model.modelPath(ROOT + "\\models");
    model.label("water_system_3d_electric_field_v3.mph");
    model.title("3D Water Circulation System - Electric Field V3");
    model.description(
        "V2 visual geometry plus a reduced electroquasistatic component for the 5 m air field, "
            + "reinforced-concrete floor, conventional PE grounding, 30/50 Hz VFD output, and "
            + "electric-field observations at 2 m, 3 m, and 4 m. MEMS voltage remains parameterized "
            + "because the transfer coefficient and noise floor have not been calibrated.");

    model.param().set("air_radius", "5[m]", "Requested radial observation domain");
    model.param().set("air_height", "3[m]", "Assumed air height above the floor");
    model.param().set("floor_thickness", "0.5[m]", "Equivalent thick laboratory floor");
    model.param().set("epsr_concrete", "5", "Dry reinforced-concrete effective permittivity");
    model.param().set("sigma_concrete", "1e-5[S/m]", "Dry concrete effective conductivity");
    model.param().set("V_ll", "380[V]", "Three-phase line-to-line RMS voltage");
    model.param().set("V_phase", "V_ll/sqrt(3)", "Phase-to-neutral RMS voltage");
    model.param().set("f_base", "50[Hz]", "Rated VFD base frequency");
    model.param().set("V_motor", "V_phase*min(freq/f_base,1)", "Assumed constant V/f motor voltage");
    model.param().set("wall_active", "if(freq>40[Hz],1,0)", "Wall supply exists only in 50 Hz solution");
    model.param().set("K_MEMS", "1[V/(V/m)]", "Placeholder MEMS field-to-voltage coefficient");
    model.param().set("V_MEMS_bias", "0[V]", "Placeholder MEMS channel bias");
    model.param().set("sensor_nx", "0", "MEMS sensitive-axis x component");
    model.param().set("sensor_ny", "1", "MEMS sensitive-axis y component");
    model.param().set("sensor_nz", "0", "MEMS sensitive-axis z component");

    model.component().create("comp2", true);
    model.component("comp2").label("Reduced electric-field model");
    model.component("comp2").geom().create("geom2", 3);
    model.component("comp2").geom("geom2").lengthUnit("m");

    model.component("comp2").geom("geom2").create("air", "Cylinder");
    model.component("comp2").geom("geom2").feature("air").label("5 m radius air domain");
    model.component("comp2").geom("geom2").feature("air").set("r", "air_radius");
    model.component("comp2").geom("geom2").feature("air").set("h", "air_height");
    model.component("comp2").geom("geom2").feature("air").set("pos", new String[] {"0", "0", "0"});
    color(model, "air", 0.72, 0.86, 0.95);

    block(model, "slab", "Thick reinforced-concrete laboratory floor",
        new String[] {"2*air_radius", "2*air_radius", "floor_thickness"},
        new String[] {"-air_radius", "-air_radius", "-floor_thickness"}, 0.46, 0.47, 0.48);

    model.component("comp2").geom("geom2").create("tankOuterEq", "Cylinder");
    model.component("comp2").geom("geom2").feature("tankOuterEq").label("Equivalent PE tank");
    model.component("comp2").geom("geom2").feature("tankOuterEq").set("r", "tank_diam/2");
    model.component("comp2").geom("geom2").feature("tankOuterEq").set("h", "tank_total_h");
    color(model, "tankOuterEq", 0.92, 0.94, 0.89);

    model.component("comp2").geom("geom2").create("tankCavityEq", "Cylinder");
    model.component("comp2").geom("geom2").feature("tankCavityEq").set("r", "tank_diam/2-tank_wall");
    model.component("comp2").geom("geom2").feature("tankCavityEq").set("h", "tank_total_h-tank_wall");
    model.component("comp2").geom("geom2").feature("tankCavityEq")
        .set("pos", new String[] {"0", "0", "tank_wall"});
    model.component("comp2").geom("geom2").create("tankShellEq", "Difference");
    model.component("comp2").geom("geom2").feature("tankShellEq").label("Equivalent PE tank shell");
    model.component("comp2").geom("geom2").feature("tankShellEq").selection("input").set("tankOuterEq");
    model.component("comp2").geom("geom2").feature("tankShellEq").selection("input2").set("tankCavityEq");
    color(model, "tankShellEq", 0.92, 0.94, 0.89);

    model.component("comp2").geom("geom2").create("waterEq", "Cylinder");
    model.component("comp2").geom("geom2").feature("waterEq").label("170 L conductive water");
    model.component("comp2").geom("geom2").feature("waterEq").set("r", "tank_diam/2-tank_wall");
    model.component("comp2").geom("geom2").feature("waterEq")
        .set("h", "water_volume/(pi*(tank_diam/2-tank_wall)^2)");
    model.component("comp2").geom("geom2").feature("waterEq")
        .set("pos", new String[] {"0", "0", "tank_wall"});
    color(model, "waterEq", 0.18, 0.55, 0.88);

    cylinder(model, "pumpEq", "Grounded pump and motor chassis", "0.13[m]",
        new double[] {0.84, 0, 0.18}, new double[] {1.20, 0, 0.18}, 0.08, 0.30, 0.58);
    block(model, "vfdEq", "Grounded 3.7 kW VFD chassis",
        new String[] {"0.34", "0.20", "0.55"}, new String[] {"2.34", "-0.10", "0.52"},
        0.18, 0.18, 0.20);
    block(model, "supplyEq", "Grounded wall 380 V supply box",
        new String[] {"0.22", "0.16", "0.30"}, new String[] {"2.72", "-0.08", "0.72"},
        0.80, 0.80, 0.76);

    for (int phase = 0; phase < 3; phase++) {
      double y = (phase - 1) * 0.024;
      cylinder(model, "motorCore" + (phase + 1), "VFD motor cable phase " + (phase + 1), "8[mm]",
          new double[] {2.30, y, 0.40}, new double[] {1.18, y, 0.40}, 0.72, 0.18, 0.12);
      cylinder(model, "wallCore" + (phase + 1), "Wall supply phase " + (phase + 1), "8[mm]",
          new double[] {2.69, y, 0.86}, new double[] {2.72, y, 0.86}, 0.72, 0.18, 0.12);
    }

    for (int i = 2; i <= 4; i++) {
      model.component("comp2").geom("geom2").create("obs" + i, "Point");
      model.component("comp2").geom("geom2").feature("obs" + i).label("Observation point " + i + " m");
      model.component("comp2").geom("geom2").feature("obs" + i)
          .set("p", new double[] {0, -i, 1});
      model.component("comp2").geom("geom2").feature("obs" + i).set("selresult", true);
    }

    model.component("comp2").geom("geom2").feature("fin").set("action", "union");
    model.component("comp2").geom("geom2").run();

    material(model, "matAir", "Air", "geom2_air_dom", "1e-14[S/m]", "1.0006");
    material(model, "matConcrete", "Equivalent reinforced concrete", "geom2_slab_dom",
        "sigma_concrete", "epsr_concrete");
    material(model, "matPE", "PE tank", "geom2_tankShellEq_dom", "1e-15[S/m]", "2.3");
    material(model, "matWater", "Water at 500 uS/cm", "geom2_waterEq_dom", "sigma_water", "80");
    material(model, "matPump", "Grounded pump metal", "geom2_pumpEq_dom", "5.8e7[S/m]", "1");
    material(model, "matVfd", "Grounded VFD metal", "geom2_vfdEq_dom", "5.8e7[S/m]", "1");
    material(model, "matSupply", "Grounded supply-box metal", "geom2_supplyEq_dom", "5.8e7[S/m]", "1");
    for (int phase = 1; phase <= 3; phase++) {
      material(model, "matMotor" + phase, "Motor cable copper phase " + phase,
          "geom2_motorCore" + phase + "_dom", "5.8e7[S/m]", "1");
      material(model, "matWall" + phase, "Wall supply copper phase " + phase,
          "geom2_wallCore" + phase + "_dom", "5.8e7[S/m]", "1");
    }

    model.component("comp2").physics().create("ec", "ConductiveMedia", "geom2");
    model.component("comp2").physics("ec").label("Electric currents - 30/50 Hz background");

    model.component("comp2").physics("ec").create("gndPump", "Ground", 2);
    model.component("comp2").physics("ec").feature("gndPump").label("Pump protective earth");
    model.component("comp2").physics("ec").feature("gndPump").selection().named("geom2_pumpEq_bnd");
    model.component("comp2").physics("ec").create("gndVfd", "Ground", 2);
    model.component("comp2").physics("ec").feature("gndVfd").label("VFD protective earth");
    model.component("comp2").physics("ec").feature("gndVfd").selection().named("geom2_vfdEq_bnd");
    model.component("comp2").physics("ec").create("gndSupply", "Ground", 2);
    model.component("comp2").physics("ec").feature("gndSupply").label("Supply-box protective earth");
    model.component("comp2").physics("ec").feature("gndSupply").selection().named("geom2_supplyEq_bnd");

    String[] phaseFactor = new String[] {"1", "exp(-i*2*pi/3)", "exp(i*2*pi/3)"};
    for (int phase = 1; phase <= 3; phase++) {
      potential(model, "potMotor" + phase, "VFD output phase " + phase,
          "geom2_motorCore" + phase + "_bnd", "V_motor*" + phaseFactor[phase - 1]);
      potential(model, "potWall" + phase, "Wall 50 Hz phase " + phase,
          "geom2_wallCore" + phase + "_bnd", "wall_active*V_phase*" + phaseFactor[phase - 1]);
    }

    model.component("comp2").variable().create("varMems");
    model.component("comp2").variable("varMems").label("Parameterized MEMS response");
    model.component("comp2").variable("varMems")
        .set("E_sensor", "ec.Ex*sensor_nx+ec.Ey*sensor_ny+ec.Ez*sensor_nz");
    model.component("comp2").variable("varMems")
        .set("V_MEMS", "K_MEMS*E_sensor+V_MEMS_bias");

    model.component("comp2").mesh().create("mesh2");
    model.component("comp2").mesh("mesh2").create("ftet1", "FreeTet");
    model.component("comp2").mesh("mesh2").feature("size").set("hauto", 4);
    model.component("comp2").mesh("mesh2").feature("size").set("hmax", "0.65[m]");
    model.component("comp2").mesh("mesh2").feature("size").set("hmin", "6[mm]");

    model.study().create("stdField");
    model.study("stdField").label("30 Hz and 50 Hz electric-field background");
    model.study("stdField").create("freq", "Frequency");
    model.study("stdField").feature("freq").set("plist", "30 50");
    model.study("stdField").feature("freq").set("activate", new String[] {"ec", "on"});

    for (int i = 2; i <= 4; i++) {
      String ds = "cp" + i;
      model.result().dataset().create(ds, "CutPoint3D");
      model.result().dataset(ds).label("Observation point " + i + " m");
      model.result().dataset(ds).set("pointx", new double[] {0});
      model.result().dataset(ds).set("pointy", new double[] {-i});
      model.result().dataset(ds).set("pointz", new double[] {1});

      String eval = "eval" + i;
      model.result().numerical().create(eval, "EvalPoint");
      model.result().numerical(eval).label("Electric field at " + i + " m");
      model.result().numerical(eval).set("data", ds);
      model.result().numerical(eval).set("expr",
          new String[] {"V", "ec.Ex", "ec.Ey", "ec.Ez", "ec.normE", "E_sensor", "V_MEMS"});
      model.result().numerical(eval).set("unit",
          new String[] {"V", "V/m", "V/m", "V/m", "V/m", "V/m", "V"});
    }

    model.save(MODEL_FILE);
    return model;
  }

  public static void main(String[] args) throws Exception {
    run();
  }
}
