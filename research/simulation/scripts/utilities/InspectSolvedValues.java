import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class InspectSolvedValues {
  public static void main(String[] args) throws Exception {
    Model model = ModelUtil.load("Model", args[0]);
    double[][] values = model.result().numerical("gev1").getReal();
    for (int row = 0; row < values.length; row++) {
      for (int col = 0; col < values[row].length; col++) {
        System.out.println("value[" + row + "][" + col + "]=" + values[row][col]);
      }
    }
  }
}
