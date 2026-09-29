import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;
import java.util.*;
/** Read-only source model. Export old solution, then bounded frequency audit on its mesh. */
public class ExternalFieldAudit20260909 {
 static final String ROOT="C:/Users/17584/Documents/ALearning/Project/tools/DataProcess";
 static final String OUT=ROOT+"/results/thesis_followup_20260909/external";
 static void export(Model m,String id) throws Exception {
  for(int d=2;d<=4;d++) {
   String tag="audit"+d;
   try{m.result().numerical().remove(tag);}catch(Exception ignored){}
   m.result().numerical().create(tag,"EvalPoint");
   m.result().numerical(tag).set("data","cp"+d);
   m.result().numerical(tag).set("expr",new String[]{"freq","real(V)","imag(V)","real(ec.Ex)","imag(ec.Ex)","real(ec.Ey)","imag(ec.Ey)","real(ec.Ez)","imag(ec.Ez)","ec.normE"});
   String table="auditTable"+d;
   try{m.result().table().remove(table);}catch(Exception ignored){}
   m.result().table().create(table,"Table");m.result().numerical(tag).set("table",table);m.result().numerical(tag).setResult();m.result().table(table).save(OUT+"/"+id+"_"+d+"m.csv");
  }
 }
 public static void main(String[] args) throws Exception {
  Model m=ModelUtil.load("Audit",ROOT+"/comsol/models/cathodic_protection_external_field_v4.mph");
  export(m,"original_saved");
  System.out.println("GEOMETRY_TAGS="+Arrays.toString(m.component("comp1").geom("geom1").feature().tags()));
  for(String p:new String[]{"hauto","custom","hmax","hmin"})try{System.out.println("MESH "+p+"="+m.component("comp1").mesh("mesh1").feature("size").getString(p));}catch(Exception e){System.out.println(e);}
  for(String tag:m.component("comp1").physics("ec").feature().tags()){
   System.out.println("BC "+tag+" "+m.component("comp1").physics("ec").feature(tag).getType());
  }
  m.result().dataset().create("headProbe","CutPoint3D");
  m.result().dataset("headProbe").set("pointx",new double[]{0});m.result().dataset("headProbe").set("pointy",new double[]{.15});m.result().dataset("headProbe").set("pointz",new double[]{.8});
  try{
   m.result().numerical().create("headEval","EvalPoint");m.result().numerical("headEval").set("data","headProbe");m.result().numerical("headEval").set("expr",new String[]{"V","ec.normE"});
   System.out.println("HEADSPACE_POINT="+Arrays.deepToString(m.result().numerical("headEval").getReal()));
  }catch(Exception e){System.out.println("HEADSPACE_PROBE_FAILED="+e.getMessage());}
  m.study("std1").feature("freq").set("plist","0.001 0.05 0.1 0.32258064516129");
  m.study("std1").run();export(m,"frequency_audit");
  m.save(OUT+"/original_geometry_frequency_audit.mph");
  System.out.println("AUDIT_DONE");ModelUtil.remove("Audit");
 }
}
