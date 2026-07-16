import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class SolvePumpSourceV6 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\comsol";
  private static final String MODEL_FILE = ROOT + "\\models\\water_system_3d_pump_source_v6.mph";
  private static final String SOLVED_FILE =
      ROOT + "\\models\\water_system_3d_pump_source_v6_solved.mph";
  private static final String[] CASES = {
      "pump_chassis_30hz", "pump_chassis_50hz", "motor_cable_30hz",
      "motor_cable_50hz", "wall_supply_50hz", "combined_50hz"
  };
  private static final int[] FREQUENCIES = {30, 50, 30, 50, 50, 50};
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

    for (int caseIndex = 0; caseIndex < CASES.length; caseIndex++) {
      model.param().set("source_case", Integer.toString(caseIndex + 1));
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
              + FREQUENCIES[caseIndex] + "," + distance + "," + NAMES[row] + ","
              + re + "," + im + "," + complexMagnitude(re, im));
        }
      }
    }

    for (int distanceIndex = 0; distanceIndex < 3; distanceIndex++) {
      double[] norm = new double[CASES.length];
      double[] sensor = new double[CASES.length];
      for (int caseIndex = 0; caseIndex < CASES.length; caseIndex++) {
        norm[caseIndex] = vectorMagnitude(real[caseIndex][distanceIndex], imag[caseIndex][distanceIndex]);
        sensor[caseIndex] = complexMagnitude(real[caseIndex][distanceIndex][5][0], imag[caseIndex][distanceIndex][5][0]);
      }

      double residualSquared = 0;
      double combinedSquared = 0;
      for (int component = 1; component <= 3; component++) {
        double sumRe = real[1][distanceIndex][component][0]
            + real[3][distanceIndex][component][0] + real[4][distanceIndex][component][0];
        double sumIm = imag[1][distanceIndex][component][0]
            + imag[3][distanceIndex][component][0] + imag[4][distanceIndex][component][0];
        double diffRe = real[5][distanceIndex][component][0] - sumRe;
        double diffIm = imag[5][distanceIndex][component][0] - sumIm;
        residualSquared += diffRe * diffRe + diffIm * diffIm;
        combinedSquared += real[5][distanceIndex][component][0] * real[5][distanceIndex][component][0]
            + imag[5][distanceIndex][component][0] * imag[5][distanceIndex][component][0];
      }
      double residual = Math.sqrt(residualSquared / combinedSquared);
      System.out.println("SUMMARY," + (distanceIndex + 2) + "," + norm[0] + "," + norm[1]
          + "," + norm[2] + "," + norm[3] + "," + norm[4] + "," + norm[5] + ","
          + (100 * norm[1] / norm[5]) + "," + (100 * norm[3] / norm[5]) + ","
          + (100 * norm[4] / norm[5]) + "," + sensor[1] + "," + sensor[5] + "," + residual);
    }

    model.label("water_system_3d_pump_source_v6_solved.mph");
    model.save(SOLVED_FILE);
    ModelUtil.remove("Model");
  }
}
