import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;
import java.util.Arrays;

public class InspectPhysics {
  public static void main(String[] args) throws Exception {
    Model model = ModelUtil.load("Model", args[0]);
    String physicsTag = args.length > 1 ? args[1] : "ec";
    for (String tag : model.component("comp1").physics(physicsTag).feature().tags()) {
      System.out.println(tag + " | " + model.component("comp1").physics(physicsTag).feature(tag).getType());
      System.out.println("  properties=" + Arrays.toString(
          model.component("comp1").physics(physicsTag).feature(tag).properties()));
    }
  }
}
