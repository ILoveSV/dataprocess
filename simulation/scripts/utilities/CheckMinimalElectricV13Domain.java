import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class CheckMinimalElectricV13Domain {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\simulation";
  private static final String MODEL_FILE =
      ROOT + "\\models\\water_system_3d_minimal_electric_v13.mph";

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
    model.param().set("air_radius", "10[m]", "Reproducible final-domain check");
    model.component("comp2").geom("geom2").run();
    String[] phase = {"1", "exp(-i*2*pi/3)", "exp(i*2*pi/3)"};
    int[] frequencies = {50, 100000};
    String[] cases = {"motor_differential_50hz", "cable_common_mode_100khz"};

    for (int caseIndex = 0; caseIndex < cases.length; caseIndex++) {
      for (int phaseIndex = 1; phaseIndex <= 3; phaseIndex++) {
        String voltage = caseIndex == 0
            ? "V_phase*" + phase[phaseIndex - 1]
            : "V_cm_unit";
        model.component("comp2").physics("ec").feature("potMotor" + phaseIndex)
            .set("V0", voltage);
        model.component("comp2").physics("ec").feature("potWall" + phaseIndex)
            .set("V0", "0[V]");
      }
      model.component("comp2").physics("ec").feature("potPump").set("V0", "0[V]");
      if (model.sol().tags().length > 0) {
        model.sol(model.sol().tags()[0]).clearSolution();
      }
      model.study("stdField").feature("freq")
          .set("plist", Integer.toString(frequencies[caseIndex]));
      model.study("stdField").run();

      for (int distance = 2; distance <= 4; distance++) {
        model.result().dataset("cp" + distance).set("data", "dset1");
        model.result().numerical("eval" + distance).set("looplevelinput", "first");
        double[][] real = model.result().numerical("eval" + distance).getReal();
        double[][] imag = model.result().numerical("eval" + distance).getImag();
        System.out.println("V13_DOMAIN10," + cases[caseIndex] + ","
            + frequencies[caseIndex] + "," + distance + ","
            + vectorMagnitude(real, imag));
      }
      System.out.println("V13_DOMAIN10_COMPLETE," + cases[caseIndex]);
    }
    ModelUtil.remove("Model");
  }
}
