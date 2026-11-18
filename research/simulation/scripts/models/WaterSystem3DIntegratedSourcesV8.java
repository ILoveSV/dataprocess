import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class WaterSystem3DIntegratedSourcesV8 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\research\\simulation";
  private static final String INPUT_FILE =
      ROOT + "\\models\\water_system_3d_electric_field_v3.mph";
  private static final String MODEL_FILE =
      ROOT + "\\models\\water_system_3d_integrated_sources_v8.mph";

  public static Model run() throws Exception {
    Model model = ModelUtil.load("Model", INPUT_FILE);
    model.modelPath(ROOT + "\\models");
    model.label("water_system_3d_integrated_sources_v8.mph");
    model.title("3D Water Circulation System - Integrated Sources V8");
    model.description(
        "Integrated frequency-domain transfer model for water-flow streaming current, pump-chassis "
            + "common mode, VFD-to-motor cable, wall supply, and VFD PWM carrier components. "
            + "Unmeasured source amplitudes and phases remain explicit scaling assumptions.");

    model.param().set("pipe_length", "2.8[m]", "Equivalent wetted-loop length from V7");
    model.param().set("pipe_diam", "40[mm]", "Assumed DN40 hydraulic diameter");
    model.param().set("V_stream_base", "0.281218[mV]", "V7 baseline streaming potential");
    model.param().set("flow_ripple", "0.05", "Assumed pressure/streaming-current ripple ratio");
    model.param().set("I_stream_dc",
        "sigma_water*pi*(pipe_diam/2)^2*V_stream_base/pipe_length",
        "Equivalent open-circuit streaming-current source");
    model.param().set("I_stream_ac", "flow_ripple*I_stream_dc",
        "Assumed AC streaming-current component");
    model.param().set("V_pump_cm", "1[V]", "Pump chassis-to-PE RMS reference voltage");
    model.param().set("V_cm_pwm", "100[V]", "Assumed 4 kHz VFD common-mode RMS voltage");

    model.component("comp2").geom("geom2").create("streamLow", "Point");
    model.component("comp2").geom("geom2").feature("streamLow")
        .label("Equivalent streaming-current suction point");
    model.component("comp2").geom("geom2").feature("streamLow")
        .set("p", new double[] {0.24, 0, 0.10});
    model.component("comp2").geom("geom2").feature("streamLow").set("selresult", true);
    model.component("comp2").geom("geom2").create("streamHigh", "Point");
    model.component("comp2").geom("geom2").feature("streamHigh")
        .label("Equivalent streaming-current return point");
    model.component("comp2").geom("geom2").feature("streamHigh")
        .set("p", new double[] {0.18, 0, 0.68});
    model.component("comp2").geom("geom2").feature("streamHigh").set("selresult", true);
    model.component("comp2").geom("geom2").run();

    model.component("comp2").physics("ec").create("pcsStreamLow", "PointCurrentSource", 0);
    model.component("comp2").physics("ec").feature("pcsStreamLow")
        .label("Streaming-current source");
    model.component("comp2").physics("ec").feature("pcsStreamLow").selection()
        .named("geom2_streamLow_pnt");
    model.component("comp2").physics("ec").feature("pcsStreamLow").set("Qjp", "I_stream_ac");
    model.component("comp2").physics("ec").create("pcsStreamHigh", "PointCurrentSource", 0);
    model.component("comp2").physics("ec").feature("pcsStreamHigh")
        .label("Streaming-current sink");
    model.component("comp2").physics("ec").feature("pcsStreamHigh").selection()
        .named("geom2_streamHigh_pnt");
    model.component("comp2").physics("ec").feature("pcsStreamHigh").set("Qjp", "-I_stream_ac");

    model.component("comp2").physics("ec").feature().remove("gndPump");
    model.component("comp2").physics("ec").create("potPump", "ElectricPotential", 2);
    model.component("comp2").physics("ec").feature("potPump")
        .label("Parameterized pump chassis common mode");
    model.component("comp2").physics("ec").feature("potPump").selection()
        .named("geom2_pumpEq_bnd");
    model.component("comp2").physics("ec").feature("potPump").set("V0", "0[V]");

    for (int phase = 1; phase <= 3; phase++) {
      model.component("comp2").physics("ec").feature("potMotor" + phase).set("V0", "0[V]");
      model.component("comp2").physics("ec").feature("potWall" + phase).set("V0", "0[V]");
    }

    model.study("stdField").label("Integrated independent and combined source cases");
    model.study("stdField").feature("freq").set("plist", "30");
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
