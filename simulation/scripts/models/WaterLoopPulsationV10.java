import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class WaterLoopPulsationV10 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\simulation";
  private static final String INPUT_FILE =
      ROOT + "\\models\\water_loop_streaming_potential_v7.mph";
  private static final String MODEL_FILE =
      ROOT + "\\models\\water_loop_pulsation_v10.mph";
  private static final String RAW_DIR = ROOT + "\\results\\pulsation_v10\\raw";
  private static final double[] AMPLITUDES = {0.02, 0.05, 0.10, 0.20, 0.30, 0.50};

  private static String amplitudeCode(double amplitude) {
    return String.format(java.util.Locale.US, "%03d", Math.round(amplitude * 100));
  }

  private static void createEvaluation(Model model, String filename) {
    model.result().table().create("tblPulse", "Table");
    model.result().table("tblPulse").label("Inlet pulse time series");
    model.result().numerical().create("avgPulseIn", "AvSurface");
    model.result().numerical("avgPulseIn").selection().set(1);
    model.result().numerical("avgPulseIn").set("expr", new String[] {"spf.U", "p"});
    model.result().numerical("avgPulseIn").set("unit", new String[] {"m/s", "Pa"});
    model.result().numerical("avgPulseIn").set("table", "tblPulse");
    model.result().numerical("avgPulseIn").setResult();
    model.result().table("tblPulse").save(filename);
    model.result().numerical().remove("avgPulseIn");
    model.result().table().remove("tblPulse");
  }

  public static void main(String[] args) throws Exception {
    Model model = ModelUtil.load("Model", INPUT_FILE);
    model.modelPath(ROOT + "\\models");
    model.label("water_loop_pulsation_v10.mph");
    model.title("Water-loop 3.1 s hydraulic pulsation parameter scan V10");
    model.description(
        "Transient SST hydraulic model driven by the measured 3.1 s period. The inlet velocity is "
            + "vbar*(1+A*sin(2*pi*t/T)); A is scanned rather than fixed at 5 percent. Electric "
            + "currents are converted from the exported pressure harmonics in postprocessing so "
            + "the one-way coupling does not destabilize the transient flow solve. The 50 Hz "
            + "operating case uses the same period provisionally.");

    model.param().set("T_pulse", "3.1[s]", "Measured hydraulic period in the 30 Hz VFD condition");
    model.param().set("f_pulse", "1/T_pulse", "Hydraulic pulse repetition frequency");
    model.param().set("operating_hz", "30", "VFD operating condition label, 30 or 50 Hz");
    model.param().set("speed_scale", "operating_hz/50", "Pump-affinity mean-flow scale");
    model.param().set("flow_rate_mode", "flow_rate*speed_scale", "Mean flow for operating condition");
    model.param().set("u_mean_mode", "flow_rate_mode/(pi*(pipe_diam/2)^2)",
        "Mean inlet speed for operating condition");
    model.param().set("A_pulse", "0.05", "Unknown fractional velocity-modulation amplitude");
    model.param().set("t_pulse_eval", "if(isdefined(t),t,0[s])",
        "Use t=0 during stationary initialization and physical time in transient solve");
    model.param().set("u_inlet", "u_mean_mode*(1+A_pulse*sin(2*pi*t_pulse_eval/T_pulse))",
        "Measured-period sinusoidal inlet velocity model");

    model.component("comp1").physics("spf").feature("inlet").set("U0in", "u_inlet");
    if (model.study("std1").feature().hasTag("time")) {
      model.study("std1").feature().remove("time");
    }
    if (model.study("std1").feature().hasTag("stat")) {
      model.study("std1").feature().remove("stat");
    }
    model.study("std1").create("stat", "Stationary");
    model.study("std1").feature("stat").set("activate", new String[] {"spf", "on", "ec", "off"});
    model.study("std1").create("time", "Transient");
    model.study("std1").label("Transient SST hydraulic pulse scan");
    model.study("std1").feature("time").set("tlist", "range(0,T_pulse/100,5*T_pulse)");
    model.study("std1").feature("time").set("activate", new String[] {"spf", "on", "ec", "off"});

    model.save(MODEL_FILE);
    System.out.println("V10_MODEL_SAVED=" + MODEL_FILE);

    int[] operatingModes = {30, 50};
    for (int operatingMode : operatingModes) {
      model.param().set("operating_hz", Integer.toString(operatingMode));
      for (double amplitude : AMPLITUDES) {
        if (operatingMode == 30 && Math.abs(amplitude - 0.02) < 1e-12) {
          System.out.println("V10_CASE_REUSE=op30,A=0.02");
          continue;
        }
        model.param().set("A_pulse", Double.toString(amplitude));
        if (model.sol().tags().length > 0) {
          model.sol(model.sol().tags()[0]).clearSolution();
        }
        System.out.println("V10_CASE_START=op" + operatingMode + ",A=" + amplitude);
        try {
          model.study("std1").run();
          String output = RAW_DIR + "\\op" + operatingMode + "_A"
              + amplitudeCode(amplitude) + ".csv";
          createEvaluation(model, output);
          System.out.println("V10_CASE_DONE=op" + operatingMode + ",A=" + amplitude
              + ",file=" + output);
        } catch (Exception exception) {
          System.out.println("V10_CASE_FAILED=op" + operatingMode + ",A=" + amplitude
              + ",message=" + exception.getMessage());
        }
      }
    }

    model.label("water_loop_pulsation_v10_last_solution.mph");
    model.save(ROOT + "\\models\\water_loop_pulsation_v10_last_solution.mph");
    ModelUtil.remove("Model");
  }
}
