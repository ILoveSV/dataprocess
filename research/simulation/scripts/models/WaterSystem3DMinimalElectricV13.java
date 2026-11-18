import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class WaterSystem3DMinimalElectricV13 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\research\\simulation";
  private static final String INPUT_FILE =
      ROOT + "\\models\\water_system_3d_doorway_environment_v9.mph";
  private static final String MODEL_FILE =
      ROOT + "\\models\\water_system_3d_minimal_electric_v13.mph";

  private static void color(Model model, String tag, double r, double g, double b) {
    model.component("comp2").geom("geom2").feature(tag).set("selresult", true);
    model.component("comp2").geom("geom2").feature(tag).set("selresultshow", "all");
    model.component("comp2").geom("geom2").feature(tag).set("color", "custom");
    model.component("comp2").geom("geom2").feature(tag)
        .set("customcolor", new double[] {r, g, b});
  }

  public static Model run() throws Exception {
    Model model = ModelUtil.load("Model", INPUT_FILE);
    model.modelPath(ROOT + "\\models");
    model.label("water_system_3d_minimal_electric_v13.mph");
    model.title("3D Minimal-Credible External Electric Field Model V13");
    model.description(
        "Minimal non-water electrical model. It retains only the tightly bundled VFD-to-motor "
            + "cable differential fundamental and a normalized common-mode cable excitation. "
            + "The pump-chassis source, wall-supply source, water source, guessed PWM amplitudes, "
            + "and direct MEMS-voltage conversion are excluded from nominal predictions.");

    model.param().set("air_radius", "10[m]",
        "Final conservative air domain after the 7.5 m to 10 m boundary-sensitivity check");
    model.param().set("cable_core_radius", "3[mm]",
        "Equivalent insulated-core radius for the compact motor cable bundle");
    model.param().set("cable_core_offset", "4[mm]",
        "Compact phase-core offset from the bundle center");
    model.param().set("cable_center_z", "0.40[m]", "Motor-cable center height");
    model.param().set("V_cm_unit", "1[V]",
        "Normalized common-mode RMS source used for transfer coefficients");

    String[][] phasePositions = {
        {"2.30[m]", "-cable_core_offset", "cable_center_z-2[mm]"},
        {"2.30[m]", "cable_core_offset", "cable_center_z-2[mm]"},
        {"2.30[m]", "0", "cable_center_z+5[mm]"}
    };
    for (int phase = 1; phase <= 3; phase++) {
      String tag = "motorCore" + phase;
      model.component("comp2").geom("geom2").feature(tag)
          .label("Compact motor cable phase " + phase);
      model.component("comp2").geom("geom2").feature(tag).set("r", "cable_core_radius");
      model.component("comp2").geom("geom2").feature(tag).set("pos", phasePositions[phase - 1]);
      model.component("comp2").geom("geom2").feature(tag)
          .set("axis", new double[] {-1.12, 0, 0});
      model.component("comp2").geom("geom2").feature(tag).set("h", "1.12[m]");
    }

    model.component("comp2").geom("geom2").create("motorPE", "Cylinder");
    model.component("comp2").geom("geom2").feature("motorPE")
        .label("Motor-cable protective-earth core");
    model.component("comp2").geom("geom2").feature("motorPE").set("r", "cable_core_radius");
    model.component("comp2").geom("geom2").feature("motorPE").set("h", "1.12[m]");
    model.component("comp2").geom("geom2").feature("motorPE")
        .set("pos", new String[] {"2.30[m]", "0", "cable_center_z-9[mm]"});
    model.component("comp2").geom("geom2").feature("motorPE")
        .set("axis", new double[] {-1.12, 0, 0});
    color(model, "motorPE", 0.30, 0.72, 0.28);

    model.component("comp2").geom("geom2").run();

    model.component("comp2").material().create("matMotorPE", "Common");
    model.component("comp2").material("matMotorPE").label("Motor-cable PE copper");
    model.component("comp2").material("matMotorPE").selection()
        .named("geom2_motorPE_dom");
    model.component("comp2").material("matMotorPE").propertyGroup("def")
        .set("electricconductivity", new String[] {"5.8e7[S/m]"});
    model.component("comp2").material("matMotorPE").propertyGroup("def")
        .set("relpermittivity", new String[] {"1"});

    model.component("comp2").physics("ec").create("gndMotorPE", "Ground", 2);
    model.component("comp2").physics("ec").feature("gndMotorPE")
        .label("Motor-cable protective-earth reference");
    model.component("comp2").physics("ec").feature("gndMotorPE").selection()
        .named("geom2_motorPE_bnd");

    model.component("comp2").physics("ec").feature("pcsStreamLow").set("Qjp", "0[A]");
    model.component("comp2").physics("ec").feature("pcsStreamHigh").set("Qjp", "0[A]");
    model.component("comp2").physics("ec").feature("potPump").set("V0", "0[V]");
    for (int phase = 1; phase <= 3; phase++) {
      model.component("comp2").physics("ec").feature("potMotor" + phase)
          .set("V0", "0[V]");
      model.component("comp2").physics("ec").feature("potWall" + phase)
          .set("V0", "0[V]");
    }

    model.component("comp2").physics("ec")
        .label("Electric currents - minimal cable differential/common-mode transfer");
    model.component("comp2").mesh("mesh2").feature("size").set("hauto", 3);
    model.component("comp2").mesh("mesh2").feature("size").set("hmax", "0.8[m]");
    model.component("comp2").mesh("mesh2").feature("size").set("hmin", "2[mm]");
    model.study("stdField").label("Minimal cable source frequency-domain study");
    model.study("stdField").feature("freq").set("plist", "30[Hz]");

    model.save(MODEL_FILE);
    return model;
  }

  public static void main(String[] args) throws Exception {
    run();
  }
}
