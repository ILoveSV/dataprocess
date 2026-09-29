import com.comsol.model.*;
import com.comsol.model.util.*;
public class ExternalCurrentExports20260916 {
 static String OUT="C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/results/thesis_followup_20260915/external";
 public static void main(String[] args) throws Exception {
  for(String id:new String[]{"gap_g010_fine","gap_g300_fine"}){
   Model m=ModelUtil.load("Model",OUT+"/"+id+".mph");
   for(String key:new String[]{"custom","hauto","hmax","hmin","hgrad"})System.out.println("SETTING "+id+" "+key+" "+m.component("comp1").mesh("mesh1").feature("size").getString(key));
   for(String group:new String[]{"pos","neg","ground"}) {
    String[] sels=group.equals("pos")?new String[]{"geom1_graphite_bnd","geom1_posTrunk_bnd","geom1_posBranch_bnd","geom1_posStub_bnd"}:group.equals("neg")?new String[]{"geom1_steel_bnd","geom1_negTrunk_bnd","geom1_negBranch_bnd","geom1_negStub_bnd"}:new String[]{"geom1_floor_bnd","geom1_sourceBox_bnd"};
    m.component("comp1").selection().create("u"+group,"Union");
    m.component("comp1").selection("u"+group).set("entitydim",2);
    m.component("comp1").selection("u"+group).set("input",sels);
    m.result().numerical().create("i"+group,"IntSurface");
    m.result().numerical("i"+group).selection().named("u"+group);
    m.result().numerical("i"+group).set("expr",new String[]{"reacf(V)"});
    m.result().table().create("t"+group,"Table");
    m.result().numerical("i"+group).set("table","t"+group);
    m.result().numerical("i"+group).setResult();
    m.result().table("t"+group).save(OUT+"/"+id+"_current_"+group+".csv");
   }
   ModelUtil.remove("Model");
  }
 }
}
