import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;
public class FinishICCPBase {
  public static void main(String[] args) throws Exception {
    Model m=ModelUtil.load("SubICCP",SubmarineICCP.ROOT+"/models/submarine_iccp_base_10A.mph");
    SubmarineICCP.plots(m);
    m.save(SubmarineICCP.ROOT+"/models/submarine_iccp_base_10A.mph");
    m.param().set("I_total","20[A]");
    m.sol("sol1").runAll();SubmarineICCP.evaluate(m,"base_20A");
    m.label("submarine_iccp_base_20A.mph");m.save(SubmarineICCP.ROOT+"/models/submarine_iccp_base_20A.mph");
    System.out.println("SAVED base_20A");ModelUtil.remove("SubICCP");
  }
}
