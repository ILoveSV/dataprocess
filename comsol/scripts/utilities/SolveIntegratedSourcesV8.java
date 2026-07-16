import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class SolveIntegratedSourcesV8 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\comsol";
  private static final String MODEL_FILE =
      ROOT + "\\models\\water_system_3d_integrated_sources_v8.mph";
  private static final String SOLVED_FILE =
      ROOT + "\\models\\water_system_3d_integrated_sources_v8_solved.mph";
  private static final String[] CASES = {
      "water_flow_30hz", "water_flow_50hz", "pump_chassis_30hz", "pump_chassis_50hz",
      "vfd_motor_cable_30hz", "vfd_motor_cable_50hz", "wall_supply_50hz",
      "combined_30hz", "combined_50hz", "vfd_pwm_4khz", "vfd_pwm_8khz", "vfd_pwm_12khz"
  };
  private static final String[] CATEGORIES = {
      "water_flow", "water_flow", "pump_body", "pump_body", "vfd_output", "vfd_output",
      "wall_power", "combined", "combined", "vfd_pwm", "vfd_pwm", "vfd_pwm"
  };
  private static final int[] FREQUENCIES = {30, 50, 30, 50, 30, 50, 50, 30, 50, 4000, 8000, 12000};
  private static final String[] NAMES = {"V", "Ex", "Ey", "Ez", "normE", "E_sensor", "V_MEMS"};

  private static boolean hasTag(String[] tags, String wanted) {
    for (String tag : tags) if (tag.equals(wanted)) return true;
    return false;
  }

  private static double vectorMagnitude(double[][] re, double[][] im) {
    double sum = 0;
    for (int component = 1; component <= 3; component++) {
      sum += re[component][0] * re[component][0] + im[component][0] * im[component][0];
    }
    return Math.sqrt(sum);
  }

  private static double complexMagnitude(double re, double im) {
    return Math.sqrt(re * re + im * im);
  }

  public static void main(String[] args) throws Exception {
    Model model = ModelUtil.load("Model", MODEL_FILE);
    double[][][][] real = new double[CASES.length][3][][];
    double[][][][] imag = new double[CASES.length][3][][];
    String[] phase = {"1", "exp(-i*2*pi/3)", "exp(i*2*pi/3)"};

    for (int caseIndex = 0; caseIndex < CASES.length; caseIndex++) {
      boolean flow = caseIndex == 0 || caseIndex == 1 || caseIndex == 7 || caseIndex == 8;
      boolean pump = caseIndex == 2 || caseIndex == 3 || caseIndex == 7 || caseIndex == 8;
      boolean motor30 = caseIndex == 4 || caseIndex == 7;
      boolean motor50 = caseIndex == 5 || caseIndex == 8;
      boolean wall = caseIndex == 6 || caseIndex == 8;
      boolean pwm = caseIndex >= 9;

      model.component("comp2").physics("ec").feature("pcsStreamLow")
          .set("Qjp", flow ? "I_stream_ac" : "0[A]");
      model.component("comp2").physics("ec").feature("pcsStreamHigh")
          .set("Qjp", flow ? "-I_stream_ac" : "0[A]");
      model.component("comp2").physics("ec").feature("potPump")
          .set("V0", pump ? "V_pump_cm" : "0[V]");

      for (int phaseIndex = 1; phaseIndex <= 3; phaseIndex++) {
        String motorVoltage = "0[V]";
        if (motor30) motorVoltage = "0.6*V_phase*" + phase[phaseIndex - 1];
        if (motor50) motorVoltage = "V_phase*" + phase[phaseIndex - 1];
        if (pwm) {
          String amplitude = caseIndex == 9 ? "V_cm_pwm" : caseIndex == 10 ? "0.5*V_cm_pwm" : "0.25*V_cm_pwm";
          motorVoltage = amplitude;
        }
        model.component("comp2").physics("ec").feature("potMotor" + phaseIndex)
            .set("V0", motorVoltage);
        model.component("comp2").physics("ec").feature("potWall" + phaseIndex)
            .set("V0", wall ? "V_phase*" + phase[phaseIndex - 1] : "0[V]");
      }

      if (hasTag(model.sol().tags(), "sol1")) model.sol("sol1").clearSolution();
      model.study("stdField").feature("freq").set("plist", Integer.toString(FREQUENCIES[caseIndex]));
      model.study("stdField").run();

      for (int distanceIndex = 0; distanceIndex < 3; distanceIndex++) {
        int distance = distanceIndex + 2;
        String tag = "eval" + distance;
        model.result().dataset("cp" + distance).set("data", "dset1");
        model.result().numerical(tag).set("looplevelinput", "first");
        real[caseIndex][distanceIndex] = model.result().numerical(tag).getReal();
        imag[caseIndex][distanceIndex] = model.result().numerical(tag).getImag();
        for (int row = 0; row < NAMES.length; row++) {
          double re = real[caseIndex][distanceIndex][row][0];
          double im = imag[caseIndex][distanceIndex][row][0];
          System.out.println("PHASOR," + (caseIndex + 1) + "," + CASES[caseIndex] + ","
              + CATEGORIES[caseIndex] + "," + FREQUENCIES[caseIndex] + "," + distance + ","
              + NAMES[row] + "," + re + "," + im + "," + complexMagnitude(re, im));
        }
        System.out.println("CASE_SUMMARY," + CASES[caseIndex] + "," + CATEGORIES[caseIndex] + ","
            + FREQUENCIES[caseIndex] + "," + distance + ","
            + vectorMagnitude(real[caseIndex][distanceIndex], imag[caseIndex][distanceIndex]) + ","
            + complexMagnitude(real[caseIndex][distanceIndex][5][0], imag[caseIndex][distanceIndex][5][0]));
      }
    }

    int[][] checks = {{0, 2, 4, 7}, {1, 3, 5, 6, 8}};
    for (int checkIndex = 0; checkIndex < checks.length; checkIndex++) {
      int combined = checks[checkIndex][checks[checkIndex].length - 1];
      for (int distanceIndex = 0; distanceIndex < 3; distanceIndex++) {
        double residualSquared = 0;
        double combinedSquared = 0;
        for (int component = 1; component <= 3; component++) {
          double sumRe = 0;
          double sumIm = 0;
          for (int source = 0; source < checks[checkIndex].length - 1; source++) {
            int caseIndex = checks[checkIndex][source];
            sumRe += real[caseIndex][distanceIndex][component][0];
            sumIm += imag[caseIndex][distanceIndex][component][0];
          }
          double diffRe = real[combined][distanceIndex][component][0] - sumRe;
          double diffIm = imag[combined][distanceIndex][component][0] - sumIm;
          residualSquared += diffRe * diffRe + diffIm * diffIm;
          combinedSquared += real[combined][distanceIndex][component][0] * real[combined][distanceIndex][component][0]
              + imag[combined][distanceIndex][component][0] * imag[combined][distanceIndex][component][0];
        }
        System.out.println("SUPERPOSITION," + FREQUENCIES[combined] + "," + (distanceIndex + 2) + ","
            + Math.sqrt(residualSquared / combinedSquared));
      }
    }

    model.label("water_system_3d_integrated_sources_v8_solved.mph");
    model.save(SOLVED_FILE);
    ModelUtil.remove("Model");
  }
}
