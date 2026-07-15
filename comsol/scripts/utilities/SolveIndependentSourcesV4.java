import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class SolveIndependentSourcesV4 {
  private static boolean hasTag(String[] tags, String wanted) {
    for (String tag : tags) {
      if (tag.equals(wanted)) return true;
    }
    return false;
  }

  public static void main(String[] args) throws Exception {
    if (args.length < 1) {
      System.err.println("Usage: SolveIndependentSourcesV4 <v3-solved-model.mph>");
      System.exit(2);
    }
    Model model = ModelUtil.load("Model", args[0]);
    String[] names = {"V", "Ex", "Ey", "Ez", "normE", "E_sensor"};
    String[] cases = {"motor_30hz", "motor_50hz", "wall_50hz", "combined_50hz"};
    int[] frequencies = {30, 50, 50, 50};
    double[] motorScale = {0.6, 1.0, 0.0, 1.0};
    double[] wallScale = {0.0, 0.0, 1.0, 1.0};
    String[] phaseFactor = {"1", "exp(-i*2*pi/3)", "exp(i*2*pi/3)"};

    if (hasTag(model.sol().tags(), "sol1")) model.sol("sol1").clearSolution();
    model.study("stdField").feature("freq").set("plist", "30");

    for (int sourceCase = 0; sourceCase < cases.length; sourceCase++) {
      for (int phase = 1; phase <= 3; phase++) {
        model.component("comp2").physics("ec").feature("potMotor" + phase).set("V0",
            motorScale[sourceCase] + "*V_phase*" + phaseFactor[phase - 1]);
        model.component("comp2").physics("ec").feature("potWall" + phase).set("V0",
            wallScale[sourceCase] + "*V_phase*" + phaseFactor[phase - 1]);
      }
      model.study("stdField").feature("freq").set("plist", Integer.toString(frequencies[sourceCase]));
      model.study("stdField").run();

      System.out.println("CASE_ID=" + (sourceCase + 1) + ",CASE_NAME=" + cases[sourceCase]
          + ",FREQUENCY_HZ=" + frequencies[sourceCase]);
      for (int distance = 2; distance <= 4; distance++) {
        String tag = "eval" + distance;
        model.result().dataset("cp" + distance).set("data", "dset1");
        model.result().numerical(tag).set("expr",
            new String[] {"V", "ec.Ex", "ec.Ey", "ec.Ez", "ec.normE", "E_sensor"});
        model.result().numerical(tag).set("looplevelinput", "first");
        double[][] real = model.result().numerical(tag).getReal();
        double[][] imag = model.result().numerical(tag).getImag();
        System.out.println("DISTANCE_M=" + distance);
        for (int row = 0; row < real.length; row++) {
          String name = row < names.length ? names[row] : "expr" + row;
          double re = real[row].length > 0 ? real[row][0] : Double.NaN;
          double im = row < imag.length && imag[row].length > 0 ? imag[row][0] : 0.0;
          System.out.println("name=" + name + ",real=" + re + ",imag=" + im);
        }
      }

      if (sourceCase < cases.length - 1 && hasTag(model.sol().tags(), "sol1")) {
        model.sol("sol1").clearSolution();
      }
    }
    ModelUtil.remove("Model");
  }
}
