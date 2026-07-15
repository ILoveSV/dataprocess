import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;
import java.util.Arrays;

public class ExportSourceDecompositionV4 {
  public static void main(String[] args) throws Exception {
    if (args.length < 1) {
      System.err.println("Usage: ExportSourceDecompositionV4 <solved-model.mph>");
      System.exit(2);
    }
    Model model = ModelUtil.load("Model", args[0]);
    String[] names = {"source_case", "freq", "V", "Ex", "Ey", "Ez", "normE", "E_sensor", "V_MEMS"};
    String[] cases = {"motor_30hz", "motor_50hz", "wall_50hz", "combined_50hz"};
    for (int distance = 2; distance <= 4; distance++) {
      String tag = "eval" + distance;
      model.result().dataset("cp" + distance).set("data", "dset1");
      model.result().numerical(tag).set("expr",
          new String[] {"source_case", "freq", "V", "ec.Ex", "ec.Ey", "ec.Ez", "ec.normE", "E_sensor", "V_MEMS"});
      System.out.println("DISTANCE_M=" + distance);
      System.out.println("LOOPLEVEL_DEFAULT="
          + Arrays.deepToString(model.result().numerical(tag).getIntMatrix("looplevel")));
      for (int sourceCase = 1; sourceCase <= cases.length; sourceCase++) {
        model.result().dataset("dset1").set("outerinput", "manualindices");
        model.result().dataset("dset1").set("outersolnumindices", new int[] {sourceCase});
        double[][] real = model.result().numerical(tag).getReal();
        double[][] imag = model.result().numerical(tag).getImag();
        System.out.println("CASE_ID=" + sourceCase + ",CASE_NAME=" + cases[sourceCase - 1]);
        for (int row = 0; row < real.length; row++) {
          String name = row < names.length ? names[row] : "expr" + row;
          double re = real[row].length > 0 ? real[row][0] : Double.NaN;
          double im = row < imag.length && imag[row].length > 0 ? imag[row][0] : 0.0;
          System.out.println("name=" + name + ",real=" + re + ",imag=" + im);
        }
      }
    }
    ModelUtil.remove("Model");
  }
}
