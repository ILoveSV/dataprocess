import com.comsol.model.Model;
import com.comsol.model.SolverFeature;
import com.comsol.model.util.ModelUtil;
import java.util.Arrays;

public class InspectSolverTree {
  private static void printFeature(SolverFeature feature, String path) {
    String type = feature.getType();
    if (type.equals("Time") || type.equals("Segregated") || type.equals("SegregatedStep")
        || type.equals("FullyCoupled") || type.equals("Variables") || type.equals("Stationary")) {
      System.out.println(path + "/" + feature.tag() + " | " + type + " | " + feature.label());
      if (type.equals("Time") || type.equals("Segregated") || type.equals("FullyCoupled")) {
        System.out.println("  properties=" + Arrays.toString(feature.properties()));
      }
    }
    for (String childTag : feature.feature().tags()) {
      printFeature(feature.feature(childTag), path + "/" + feature.tag());
    }
  }

  public static void main(String[] args) throws Exception {
    Model model = ModelUtil.load("Model", args[0]);
    for (String solTag : model.sol().tags()) {
      System.out.println("SOLUTION=" + solTag);
      for (String featureTag : model.sol(solTag).feature().tags()) {
        printFeature(model.sol(solTag).feature(featureTag), solTag);
      }
    }
    ModelUtil.remove("Model");
  }
}
