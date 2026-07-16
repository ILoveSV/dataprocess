import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class WaterSystem3DPumpSource {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\comsol";
  private static final String INPUT_FILE = ROOT + "\\models\\water_system_3d_electric_field_v3.mph";
  private static final String MODEL_FILE = ROOT + "\\models\\water_system_3d_pump_source_v6.mph";

  public static Model run() throws Exception {
    Model model = ModelUtil.load("Model", INPUT_FILE);
    model.modelPath(ROOT + "\\models");
    model.label("water_system_3d_pump_source_v6.mph");
    model.title("3D Water Circulation System - Pump Chassis Source V6");
    model.description(
        "Independent pump-chassis, motor-cable, and wall-supply source cases. The pump source is "
            + "represented by a parameterized chassis-to-PE common-mode voltage because winding geometry, "
            + "protective-earth impedance, and measured chassis voltage are not yet available.");

    model.param().set("source_case", "1",
        "1=pump30, 2=pump50, 3=motor30, 4=motor50, 5=wall50, 6=combined50");
    model.param().set("V_pump_cm", "1[V]", "Pump chassis-to-PE RMS reference voltage");
    model.param().set("drive_freq",
        "if(source_case==1||source_case==3,30[Hz],50[Hz])", "Frequency for the active source case");
    model.param().set("pump_scale",
        "if(source_case==1||source_case==2||source_case==6,1,0)", "Pump chassis source scale");
    model.param().set("motor_scale",
        "if(source_case==3,0.6,if(source_case==4||source_case==6,1,0))",
        "Motor-cable voltage scale; 30 Hz follows constant V/f");
    model.param().set("wall_scale", "if(source_case==5||source_case==6,1,0)",
        "Wall-supply voltage scale");

    model.component("comp2").physics("ec").feature().remove("gndPump");
    model.component("comp2").physics("ec").create("potPump", "ElectricPotential", 2);
    model.component("comp2").physics("ec").feature("potPump")
        .label("Parameterized pump chassis common-mode source");
    model.component("comp2").physics("ec").feature("potPump").selection()
        .named("geom2_pumpEq_bnd");
    model.component("comp2").physics("ec").feature("potPump")
        .set("V0", "pump_scale*V_pump_cm");

    String[] phaseFactor = new String[] {"1", "exp(-i*2*pi/3)", "exp(i*2*pi/3)"};
    for (int phase = 1; phase <= 3; phase++) {
      model.component("comp2").physics("ec").feature("potMotor" + phase)
          .set("V0", "motor_scale*V_phase*" + phaseFactor[phase - 1]);
      model.component("comp2").physics("ec").feature("potWall" + phase)
          .set("V0", "wall_scale*V_phase*" + phaseFactor[phase - 1]);
    }

    model.study("stdField").label("Independent pump, motor-cable, and wall-supply cases");
    model.study("stdField").feature("freq").set("plist", "drive_freq");

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
