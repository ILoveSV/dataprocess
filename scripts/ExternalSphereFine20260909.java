import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;
/** Radial finite-shell benchmark for the same electroquasistatic interface. */
public class ExternalSphereFine20260909 {
 static final String OUT="C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/results/thesis_followup_20260909/external";
 public static void main(String[] args) throws Exception {
  Model m=ModelUtil.create("Sphere");m.component().create("comp1",true);m.component("comp1").geom().create("geom1",3);
  for(String tag:new String[]{"outer","inner"}){m.component("comp1").geom("geom1").create(tag,"Sphere");m.component("comp1").geom("geom1").feature(tag).set("r",tag.equals("outer")?5:1);m.component("comp1").geom("geom1").feature(tag).set("selresult",true);}
  m.component("comp1").geom("geom1").create("shell","Difference");m.component("comp1").geom("geom1").feature("shell").selection("input").set("outer");m.component("comp1").geom("geom1").feature("shell").selection("input2").set("inner");m.component("comp1").geom("geom1").run();
  // Geometric box selections separate inner/outer boundaries without hard-coded entity numbers.
  m.component("comp1").selection().create("inside","Box");m.component("comp1").selection("inside").set("entitydim",2);
  m.component("comp1").selection("inside").set("condition","inside");
  for(String axis:new String[]{"x","y","z"}){m.component("comp1").selection("inside").set(axis+"min",-1.01);m.component("comp1").selection("inside").set(axis+"max",1.01);}
  m.component("comp1").selection().create("outside","Complement");m.component("comp1").selection("outside").set("entitydim",2);m.component("comp1").selection("outside").set("input",new String[]{"inside"});
  m.component("comp1").material().create("mat","Common");m.component("comp1").material("mat").propertyGroup("def").set("electricconductivity",new String[]{"1e-14[S/m]"});m.component("comp1").material("mat").propertyGroup("def").set("relpermittivity",new String[]{"1.0006"});
  m.component("comp1").physics().create("ec","ConductiveMedia","geom1");m.component("comp1").physics("ec").prop("ShapeProperty").set("order_electricpotential",1);
  m.component("comp1").physics("ec").create("potential","ElectricPotential",2);m.component("comp1").physics("ec").feature("potential").selection().named("inside");m.component("comp1").physics("ec").feature("potential").set("V0","1[V]");
  m.component("comp1").physics("ec").create("ground","Ground",2);m.component("comp1").physics("ec").feature("ground").selection().named("outside");
  m.component("comp1").mesh().create("mesh1");m.component("comp1").mesh("mesh1").autoMeshSize(1);m.component("comp1").mesh("mesh1").run();
  m.study().create("std");m.study("std").create("freq","Frequency");m.study("std").feature("freq").set("plist","0.001");m.study("std").run();
  m.result().dataset().create("points","CutPoint3D");m.result().dataset("points").set("pointx",new double[]{2,3,4});m.result().dataset("points").set("pointy",new double[]{0,0,0});m.result().dataset("points").set("pointz",new double[]{0,0,0});
  m.result().numerical().create("eval","EvalPoint");m.result().numerical("eval").set("data","points");m.result().numerical("eval").set("expr",new String[]{"x","real(V)","real(ec.Ex)","ec.normE"});
  m.result().table().create("tbl","Table");m.result().numerical("eval").set("table","tbl");m.result().numerical("eval").setResult();m.result().table("tbl").save(OUT+"/sphere_benchmark_fine.csv");m.save(OUT+"/sphere_benchmark_fine.mph");ModelUtil.remove("Sphere");System.out.println("SPHERE_DONE");
 }
}

