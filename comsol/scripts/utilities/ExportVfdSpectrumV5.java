import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class ExportVfdSpectrumV5 {
  public static void main(String[] args) throws Exception {
    if (args.length < 1) {
      System.err.println("Usage: ExportVfdSpectrumV5 <solved-model.mph>");
      System.exit(2);
    }
    Model model = ModelUtil.load("Model", args[0]);
    String[] names = {"V", "Ex", "Ey", "Ez", "normE", "E_sensor", "V_MEMS"};
    int[] frequencies = {30, 50, 4000, 8000, 12000};
    for (int distance = 2; distance <= 4; distance++) {
      String tag = "eval" + distance;
      model.result().dataset("cp" + distance).set("data", "dset1");
      model.result().numerical(tag).set("expr",
          new String[] {"V", "ec.Ex", "ec.Ey", "ec.Ez", "ec.normE", "E_sensor", "V_MEMS"});
      System.out.println("DISTANCE_M=" + distance);
      for (int level = 1; level <= frequencies.length; level++) {
        model.result().numerical(tag).set("looplevelinput", "manual");
        model.result().numerical(tag).setIndex("looplevel", level, 0);
        double[][] real = model.result().numerical(tag).getReal();
        double[][] imag = model.result().numerical(tag).getImag();
        System.out.println("FREQUENCY_HZ=" + frequencies[level - 1]);
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
