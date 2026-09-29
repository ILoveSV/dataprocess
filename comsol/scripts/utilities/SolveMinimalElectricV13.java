import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class SolveMinimalElectricV13 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\comsol";
  private static final String MODEL_FILE =
      ROOT + "\\models\\water_system_3d_minimal_electric_v13.mph";
  private static final String SOLVED_FILE =
      ROOT + "\\models\\water_system_3d_minimal_electric_v13_solved.mph";

  private static final String[] CASES = {
      "motor_differential_30hz", "motor_differential_50hz",
      "cable_common_mode_4khz", "cable_common_mode_8khz",
      "cable_common_mode_12khz", "cable_common_mode_20khz",
      "cable_common_mode_50khz", "cable_common_mode_80khz",
      "cable_common_mode_100khz", "cable_common_mode_120khz",
      "cable_common_mode_150khz", "cable_common_mode_200khz"
  };
  private static final String[] MODES = {
      "balanced_differential", "balanced_differential",
      "normalized_common_mode", "normalized_common_mode", "normalized_common_mode",
      "normalized_common_mode", "normalized_common_mode", "normalized_common_mode",
      "normalized_common_mode", "normalized_common_mode", "normalized_common_mode",
      "normalized_common_mode"
  };
  private static final int[] FREQUENCIES = {
      30, 50, 4000, 8000, 12000, 20000, 50000, 80000, 100000, 120000, 150000, 200000
  };
  private static final double[] SOURCE_RMS_V = {
      131.63586137523467, 219.3931022920578,
      1, 1, 1, 1, 1, 1, 1, 1, 1, 1
  };
  private static final String[] NAMES = {"V", "Ex", "Ey", "Ez", "normE", "E_sensor"};

  private static double vectorMagnitude(double[][] re, double[][] im) {
    double sum = 0;
    for (int component = 1; component <= 3; component++) {
      sum += re[component][0] * re[component][0]
          + im[component][0] * im[component][0];
    }
    return Math.sqrt(sum);
  }

  public static void main(String[] args) throws Exception {
    Model model = ModelUtil.load("Model", MODEL_FILE);
    String[] phase = {"1", "exp(-i*2*pi/3)", "exp(i*2*pi/3)"};

    for (int caseIndex = 0; caseIndex < CASES.length; caseIndex++) {
      boolean differential30 = caseIndex == 0;
      boolean differential50 = caseIndex == 1;
      boolean commonMode = caseIndex >= 2;

      model.component("comp2").physics("ec").feature("pcsStreamLow").set("Qjp", "0[A]");
      model.component("comp2").physics("ec").feature("pcsStreamHigh").set("Qjp", "0[A]");
      model.component("comp2").physics("ec").feature("potPump").set("V0", "0[V]");
      for (int phaseIndex = 1; phaseIndex <= 3; phaseIndex++) {
        String motorVoltage = "0[V]";
        if (differential30) {
          motorVoltage = "0.6*V_phase*" + phase[phaseIndex - 1];
        } else if (differential50) {
          motorVoltage = "V_phase*" + phase[phaseIndex - 1];
        } else if (commonMode) {
          motorVoltage = "V_cm_unit";
        }
        model.component("comp2").physics("ec").feature("potMotor" + phaseIndex)
            .set("V0", motorVoltage);
        model.component("comp2").physics("ec").feature("potWall" + phaseIndex)
            .set("V0", "0[V]");
      }

      if (model.sol().tags().length > 0) {
        model.sol(model.sol().tags()[0]).clearSolution();
      }
      model.study("stdField").feature("freq")
          .set("plist", Integer.toString(FREQUENCIES[caseIndex]));
      model.study("stdField").run();

        for (int distanceIndex = 0; distanceIndex < 3; distanceIndex++) {
          int distance = distanceIndex + 2;
          String tag = "eval" + distance;
          model.result().dataset("cp" + distance).set("data", "dset1");
          model.result().numerical(tag).set("looplevelinput", "first");
          double[][] real = model.result().numerical(tag).getReal();
          double[][] imag = model.result().numerical(tag).getImag();
          for (int row = 0; row < NAMES.length; row++) {
            double re = real[row][0];
            double im = imag[row][0];
            System.out.println("V13_PHASOR," + (caseIndex + 1) + "," + CASES[caseIndex] + ","
                + MODES[caseIndex] + "," + FREQUENCIES[caseIndex] + ","
                + SOURCE_RMS_V[caseIndex] + "," + distance + "," + NAMES[row] + ","
                + re + "," + im + "," + Math.hypot(re, im));
          }
          System.out.println("V13_SUMMARY," + CASES[caseIndex] + "," + MODES[caseIndex] + ","
              + FREQUENCIES[caseIndex] + "," + SOURCE_RMS_V[caseIndex] + "," + distance + ","
              + vectorMagnitude(real, imag) + ","
              + Math.hypot(real[5][0], imag[5][0]));
        }
        System.out.println("V13_CASE_COMPLETE," + (caseIndex + 1) + "," + CASES[caseIndex]);
    }

    model.label("water_system_3d_minimal_electric_v13_solved.mph");
    model.save(SOLVED_FILE);
    ModelUtil.remove("Model");
  }
}
