import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class WaterSystem3DSourceDecomposition {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\comsol";
  private static final String INPUT_FILE = ROOT + "\\models\\water_system_3d_electric_field_v3.mph";
  private static final String MODEL_FILE = ROOT + "\\models\\water_system_3d_source_decomposition_v4.mph";

  public static Model run() throws Exception {
    Model model = ModelUtil.load("Model", INPUT_FILE);
    model.modelPath(ROOT + "\\models");
    model.label("water_system_3d_source_decomposition_v4.mph");
    model.title("3D Water Circulation System - Source Decomposition V4");
    model.description(
        "Independent linear source cases using the V3 geometry, materials, grounding, mesh, and probes. "
            + "Case 1: motor cable 30 Hz; case 2: motor cable 50 Hz; case 3: wall supply 50 Hz; "
            + "case 4: motor cable plus wall supply at 50 Hz.");

    model.param().set("source_case", "1", "1=motor30, 2=motor50, 3=wall50, 4=combined50");
    model.param().set("drive_freq", "if(source_case==1,30[Hz],50[Hz])", "Frequency for each source case");
    model.param().set("motor_scale",
        "if(source_case==1,0.6,if(source_case==2,1,if(source_case==3,0,1)))",
        "Motor-cable voltage scale for each source case");
    model.param().set("wall_scale", "if(source_case>=3,1,0)",
        "Wall-supply voltage scale for each source case");
    model.param().set("V_motor_case", "V_phase*motor_scale", "Active motor-cable phase voltage");
    model.param().set("V_wall_case", "V_phase*wall_scale", "Active wall-supply phase voltage");

    String[] phaseFactor = new String[] {"1", "exp(-i*2*pi/3)", "exp(i*2*pi/3)"};
    for (int phase = 1; phase <= 3; phase++) {
      model.component("comp2").physics("ec").feature("potMotor" + phase)
          .set("V0", "V_motor_case*" + phaseFactor[phase - 1]);
      model.component("comp2").physics("ec").feature("potWall" + phase)
          .set("V0", "V_wall_case*" + phaseFactor[phase - 1]);
    }

    model.study().remove("stdField");
    model.study().create("stdField");
    model.study("stdField").label("Independent source contribution cases");
    model.study("stdField").create("param", "Parametric");
    model.study("stdField").feature("param").setIndex("pname", "source_case", 0);
    model.study("stdField").feature("param").setIndex("plistarr", "1 2 3 4", 0);
    model.study("stdField").feature("param").setIndex("punit", "", 0);
    model.study("stdField").create("freq", "Frequency");
    model.study("stdField").feature("freq").set("plist", "drive_freq");
    model.study("stdField").feature("freq").set("activate", new String[] {"ec", "on"});

    for (int distance = 2; distance <= 4; distance++) {
      model.result().numerical("eval" + distance).set("expr",
          new String[] {"V", "ec.Ex", "ec.Ey", "ec.Ez", "ec.normE", "E_sensor", "V_MEMS"});
    }

    model.save(MODEL_FILE);
    return model;
  }

  public static void main(String[] args) throws Exception {
    run();
  }
}
