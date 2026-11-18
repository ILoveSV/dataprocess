import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;
import java.util.Arrays;
public class RefreshICCPPlots {
  public static void main(String[] args) throws Exception {
    Model m=ModelUtil.load("SubICCP",SubmarineICCP.ROOT+"/models/submarine_iccp_base_10A.mph");
    for(String t:new String[]{"hullpotential","externalfield"}) {
      if(Arrays.asList(m.result().tags()).contains(t))m.result().remove(t);
      if(Arrays.asList(m.result().export().tags()).contains("img"+t))m.result().export().remove("img"+t);
    }
    if(Arrays.asList(m.result().dataset().tags()).contains("fieldplane"))m.result().dataset().remove("fieldplane");
    m.param().set("I_nominal","10[A]");
    SubmarineICCP.plots(m);
    m.save(SubmarineICCP.ROOT+"/models/submarine_iccp_base_10A.mph");
    ModelUtil.remove("SubICCP");
  }
}
