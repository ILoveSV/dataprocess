import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class ExportHydraulicPulseTransferV10 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\comsol";
  private static final String MODEL_FILE =
      ROOT + "\\models\\water_system_3d_doorway_environment_v9.mph";
  private static final double PULSE_PERIOD = 3.1;
  private static final int HARMONIC_COUNT = 10;
  private static final String[] NAMES =
      {"V", "Ex", "Ey", "Ez", "normE", "E_sensor", "V_MEMS"};

  private static String frequencyList() {
    StringBuilder values = new StringBuilder();
    for (int harmonic = 1; harmonic <= HARMONIC_COUNT; harmonic++) {
      if (harmonic > 1) values.append(' ');
      values.append(Double.toString(harmonic / PULSE_PERIOD));
    }
    return values.toString();
  }

  public static void main(String[] args) throws Exception {
    Model model = ModelUtil.load("Model", MODEL_FILE);

    model.component("comp2").physics("ec").feature("pcsStreamLow").set("Qjp", "1[A]");
    model.component("comp2").physics("ec").feature("pcsStreamHigh").set("Qjp", "-1[A]");
    model.component("comp2").physics("ec").feature("potPump").set("V0", "0[V]");
    for (int phase = 1; phase <= 3; phase++) {
      model.component("comp2").physics("ec").feature("potMotor" + phase).set("V0", "0[V]");
      model.component("comp2").physics("ec").feature("potWall" + phase).set("V0", "0[V]");
    }

    if (model.sol().tags().length > 0) model.sol(model.sol().tags()[0]).clearSolution();
    model.study("stdField").feature("freq").set("plist", frequencyList());
    model.study("stdField").run();

    for (int distance = 2; distance <= 4; distance++) {
      String tag = "eval" + distance;
      model.result().dataset("cp" + distance).set("data", "dset1");
      model.result().numerical(tag).set("looplevelinput", "all");
      double[][] real = model.result().numerical(tag).getReal();
      double[][] imag = model.result().numerical(tag).getImag();
      System.out.println("TRANSFER_SHAPE,distance=" + distance + ",rows=" + real.length
          + ",columns=" + real[0].length);
      for (int harmonic = 1; harmonic <= HARMONIC_COUNT; harmonic++) {
        int column = harmonic - 1;
        for (int row = 0; row < NAMES.length; row++) {
          double realValue = real[row][column];
          double imagValue = imag[row][column];
          System.out.println("PULSE_TRANSFER," + harmonic + ","
              + (harmonic / PULSE_PERIOD) + "," + distance + "," + NAMES[row] + ","
              + realValue + "," + imagValue + "," + Math.hypot(realValue, imagValue));
        }
      }
    }

    ModelUtil.remove("Model");
  }
}
