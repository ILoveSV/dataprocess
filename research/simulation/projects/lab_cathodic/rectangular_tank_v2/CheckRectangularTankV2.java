import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class CheckRectangularTankV2 {
  public static void main(String[] args) throws Exception {
    String root="C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/research/simulation/projects/lab_cathodic/rectangular_tank_v2/";
    for(String test:new String[]{"coarse","wide"}) {
      Model m=ModelUtil.load("Check",root+"rectangular_tank_20V_external_v2.mph");
      if(test.equals("coarse")) {
        m.param().set("h_water","12[mm]");
        m.param().set("h_near","0.09[m]");
        m.param().set("h_mid","0.35[m]");
      } else {
        m.param().set("air_r","15[m]");m.param().set("air_h","15[m]");
        m.component("c").geom("g").run();
      }
      m.component("c").mesh("mesh").run();
      m.sol("sol1").runAll();
      RectangularTankExternalV2.summary(m,test);
      ModelUtil.remove("Check");
    }
    System.out.println("CHECKS_COMPLETED");
  }
}
