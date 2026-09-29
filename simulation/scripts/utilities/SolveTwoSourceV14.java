import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class SolveTwoSourceV14 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\simulation";
  private static final String MODEL_FILE =
      ROOT + "\\models\\water_system_3d_two_source_v14.mph";
  private static final String SOLVED_FILE =
      ROOT + "\\models\\water_system_3d_two_source_v14_solved.mph";

  private static final int[] FREQUENCIES = {
      30, 50, 4000, 8000, 12000, 20000, 50000, 80000,
      100000, 120000, 150000, 200000
  };

  private static final String[] FREQUENCY_LABELS = {
      "30hz", "50hz", "4khz", "8khz", "12khz", "20khz", "50khz", "80khz",
      "100khz", "120khz", "150khz", "200khz"
  };

  private static final String[] E_NAMES = {"V", "Ex", "Ey", "Ez", "normE", "E_sensor"};
  private static final String[] M_NAMES = {"Bx", "By", "Bz", "Ax", "Ay", "Az"};

  private static double vectorMagnitude(double[][] re, double[][] im, int first) {
    double sum = 0;
    for (int component = first; component < first + 3; component++) {
      sum += re[component][0] * re[component][0]
          + im[component][0] * im[component][0];
    }
    return Math.sqrt(sum);
  }

  private static boolean hasTag(String[] tags, String expected) {
    for (String tag : tags) {
      if (tag.equals(expected)) {
        return true;
      }
    }
    return false;
  }

  private static void zeroElectricSources(Model model) {
    model.component("comp2").physics("ec").feature("pcsStreamLow").set("Qjp", "0[A]");
    model.component("comp2").physics("ec").feature("pcsStreamHigh").set("Qjp", "0[A]");
    model.component("comp2").physics("ec").feature("potPump").set("V0", "0[V]");
    for (int phase = 1; phase <= 3; phase++) {
      model.component("comp2").physics("ec").feature("potMotor" + phase)
          .set("V0", "0[V]");
      model.component("comp2").physics("ec").feature("potWall" + phase)
          .set("V0", "0[V]");
    }
  }

  private static void solveElectricCase(
      Model model, int caseIndex, String caseName, String mode, int frequency,
      double sourceRms, String[] motorVoltages, String pumpVoltage) throws Exception {
    zeroElectricSources(model);
    model.component("comp2").physics("ec").feature("potPump").set("V0", pumpVoltage);
    for (int phase = 1; phase <= 3; phase++) {
      model.component("comp2").physics("ec").feature("potMotor" + phase)
          .set("V0", motorVoltages[phase - 1]);
    }

    if (hasTag(model.sol().tags(), "sol1")) {
      model.sol("sol1").clearSolution();
    }
    model.study("stdField").feature("freq").set("plist", Integer.toString(frequency));
    model.study("stdField").run();

    for (int distance = 2; distance <= 4; distance++) {
      String tag = "eval" + distance;
      model.result().dataset("cp" + distance).set("data", "dset1");
      model.result().numerical(tag).set("looplevelinput", "first");
      double[][] real = model.result().numerical(tag).getReal();
      double[][] imag = model.result().numerical(tag).getImag();
      for (int row = 0; row < E_NAMES.length; row++) {
        double re = real[row][0];
        double im = imag[row][0];
        System.out.println("V14_E_PHASOR," + caseIndex + "," + caseName + "," + mode + ","
            + frequency + "," + sourceRms + "," + distance + "," + E_NAMES[row] + ","
            + re + "," + im + "," + Math.hypot(re, im));
      }
      System.out.println("V14_E_SUMMARY," + caseName + "," + mode + "," + frequency + ","
          + sourceRms + "," + distance + "," + vectorMagnitude(real, imag, 1) + ","
          + Math.hypot(real[5][0], imag[5][0]));
    }
    System.out.println("V14_E_CASE_COMPLETE," + caseIndex + "," + caseName);
  }

  private static String findLatestSolutionDataset(Model model) {
    String latest = null;
    for (String tag : model.result().dataset().tags()) {
      if (tag.startsWith("dset")) {
        latest = tag;
      }
    }
    if (latest == null) {
      throw new IllegalStateException("No solution dataset found for magnetic study");
    }
    return latest;
  }

  private static void createMagneticEvaluations(Model model, String dataTag) {
    for (int distance = 2; distance <= 4; distance++) {
      String datasetTag = "mcp" + distance;
      String evalTag = "meval" + distance;
      if (!hasTag(model.result().dataset().tags(), datasetTag)) {
        model.result().dataset().create(datasetTag, "CutPoint3D");
      }
      model.result().dataset(datasetTag).set("data", dataTag);
      model.result().dataset(datasetTag).set("pointx", new double[] {0});
      model.result().dataset(datasetTag).set("pointy", new double[] {-(0.28 + distance)});
      model.result().dataset(datasetTag).set("pointz", new double[] {0.5});
      if (!hasTag(model.result().numerical().tags(), evalTag)) {
        model.result().numerical().create(evalTag, "EvalPoint");
      }
      model.result().numerical(evalTag).set("data", datasetTag);
      model.result().numerical(evalTag).set("expr",
          new String[] {"mf.Bx", "mf.By", "mf.Bz", "mf.Ax", "mf.Ay", "mf.Az"});
      model.result().numerical(evalTag).set("unit",
          new String[] {"T", "T", "T", "Wb/m", "Wb/m", "Wb/m"});
    }
  }

  private static void solveMagneticCases(Model model) throws Exception {
    String dataTag = null;
    for (int index = 0; index < FREQUENCIES.length; index++) {
      int frequency = FREQUENCIES[index];
      model.study("stdMag").feature("freq").set("plist", Integer.toString(frequency));
      model.study("stdMag").run();
      if (dataTag == null) {
        dataTag = findLatestSolutionDataset(model);
        createMagneticEvaluations(model, dataTag);
      }

      for (int distance = 2; distance <= 4; distance++) {
        String evalTag = "meval" + distance;
        model.result().numerical(evalTag).set("looplevelinput", "first");
        double[][] real = model.result().numerical(evalTag).getReal();
        double[][] imag = model.result().numerical(evalTag).getImag();
        for (int row = 0; row < M_NAMES.length; row++) {
          double re = real[row][0];
          double im = imag[row][0];
          System.out.println("V14_M_PHASOR," + (index + 1) + ",return_loop_"
              + FREQUENCY_LABELS[index] + ",normalized_return_current," + frequency
              + ",1.0," + distance + "," + M_NAMES[row] + "," + re + "," + im + ","
              + Math.hypot(re, im));
        }

        double bMagnitude = vectorMagnitude(real, imag, 0);
        double omega = 2 * Math.PI * frequency;
        double eSquared = 0;
        for (int component = 3; component <= 5; component++) {
          double eReal = omega * imag[component][0];
          double eImag = -omega * real[component][0];
          eSquared += eReal * eReal + eImag * eImag;
        }
        double inducedEMagnitude = Math.sqrt(eSquared);
        System.out.println("V14_M_SUMMARY,return_loop_" + FREQUENCY_LABELS[index]
            + ",normalized_return_current," + frequency + ",1.0," + distance + ","
            + bMagnitude + "," + inducedEMagnitude);
      }
      System.out.println("V14_M_CASE_COMPLETE," + (index + 1) + ",return_loop_"
          + FREQUENCY_LABELS[index]);
    }
  }

  public static void main(String[] args) throws Exception {
    Model model = ModelUtil.load("Model", MODEL_FILE);
    String[] phase = {"1", "exp(-i*2*pi/3)", "exp(i*2*pi/3)"};
    String[] zero = {"0[V]", "0[V]", "0[V]"};
    int caseIndex = 0;
    boolean newSourcesOnly = args.length > 0 && args[0].equalsIgnoreCase("new_only");

    if (!newSourcesOnly) {
      solveElectricCase(model, ++caseIndex, "cable_differential_30hz", "balanced_differential",
          30, 131.63586137523467,
          new String[] {"0.6*V_phase*" + phase[0], "0.6*V_phase*" + phase[1],
              "0.6*V_phase*" + phase[2]}, "0[V]");
      solveElectricCase(model, ++caseIndex, "cable_differential_50hz", "balanced_differential",
          50, 219.3931022920578,
          new String[] {"V_phase*" + phase[0], "V_phase*" + phase[1],
              "V_phase*" + phase[2]}, "0[V]");

      for (int index = 2; index < FREQUENCIES.length; index++) {
        String[] common = {"V_cm_unit", "V_cm_unit", "V_cm_unit"};
        solveElectricCase(model, ++caseIndex, "cable_common_mode_" + FREQUENCY_LABELS[index],
            "normalized_cable_common_mode", FREQUENCIES[index], 1.0, common, "0[V]");
      }
    }

    for (int index = 0; index < FREQUENCIES.length; index++) {
      solveElectricCase(model, ++caseIndex, "motor_pump_chassis_" + FREQUENCY_LABELS[index],
          "normalized_chassis_common_mode", FREQUENCIES[index], 1.0, zero,
          "V_chassis_unit");
    }

    solveMagneticCases(model);

    model.label("water_system_3d_two_source_v14_solved.mph");
    model.save(SOLVED_FILE);
    ModelUtil.remove("Model");
  }
}
