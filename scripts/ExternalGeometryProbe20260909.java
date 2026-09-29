import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;
public class ExternalGeometryProbe20260909 {
 static final String ROOT="C:/Users/17584/Documents/ALearning/Project/tools/DataProcess";
 static final String OUT=ROOT+"/results/thesis_followup_20260909/external";
 public static void main(String[] args) throws Exception {
  String[] names={"original","headspace_fixed","headspace_tape_fixed"};
  for(String id:names){
   Model m=ModelUtil.load("Probe",id.equals("original")?ROOT+"/comsol/models/cathodic_protection_external_field_v4.mph":OUT+"/"+id+".mph");
   String[] labels={"headspace","tape_gap","water"};
   double z=m.param().evaluate("steel_center_z");
   double[][] xyz={{0,.15,.8},{-.04125-.05005,0,z},{0,.15,.3}};
   for(int k=0;k<3;k++){
    String ds="probe"+k;m.result().dataset().create(ds,"CutPoint3D");m.result().dataset(ds).set("pointx",new double[]{xyz[k][0]});m.result().dataset(ds).set("pointy",new double[]{xyz[k][1]});m.result().dataset(ds).set("pointz",new double[]{xyz[k][2]});
    String ev="probeEval"+k;m.result().numerical().create(ev,"EvalPoint");m.result().numerical(ev).set("data",ds);m.result().numerical(ev).set("expr",new String[]{"real(V)","ec.normE"});
    String tbl="probeTbl"+k;m.result().table().create(tbl,"Table");m.result().numerical(ev).set("table",tbl);m.result().numerical(ev).setResult();m.result().table(tbl).save(OUT+"/probe_"+id+"_"+labels[k]+".csv");
   }
   ModelUtil.remove("Probe");System.out.println("PROBE_DONE "+id);
  }
 }
}
