import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class ExportModelJava {
  public static void main(String[] args) throws Exception {
    if (args.length != 2) {
      throw new IllegalArgumentException("Usage: ExportModelJava input.mph output.java");
    }
    Model model = ModelUtil.load("Model", args[0]);
    model.save(args[1], "java");
  }
}
