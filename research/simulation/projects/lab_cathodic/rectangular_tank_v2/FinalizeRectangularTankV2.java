import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class FinalizeRectangularTankV2 {
  public static void main(String[] args) throws Exception {
    String path="C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/research/simulation/projects/lab_cathodic/rectangular_tank_v2/rectangular_tank_20V_external_v2.mph";
    Model m=ModelUtil.load("Final",path);
    int water=m.component("c").selection("g_water_dom").entities(3)[0];
    for(String[] plot:new String[][]{{"pgV","real(V)"},{"pgJ","ec.normJ"}}) {
      m.result(plot[0]).feature("slice").set("expr","if(dom=="+water+","+plot[1]+",NaN)");
      m.result().export("img"+plot[0]).run();
    }
    m.save(path);
    ModelUtil.remove("Final");
    System.out.println("FINALIZED");
  }
}
