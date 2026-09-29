import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;
public class PostprocessLocal20260915 {
 static final String ROOT="C:/Users/17584/Documents/ALearning/Project/tools/DataProcess";
 static final String SOURCE=ROOT+"/results/thesis_followup_20260909/external";
 static final String OUT=ROOT+"/results/thesis_followup_20260915/external";
 public static void main(String[] args) throws Exception {
  String[] ids={"local_h100","local_h075","local_h050"};
  for(String id:ids){
   try{
    Model m=ModelUtil.load("Recover",id.equals("original_saved")?ROOT+"/comsol/models/cathodic_protection_external_field_v4.mph":SOURCE+"/"+id+".mph");
    boolean sphere=id.startsWith("sphere");
    for(int d=2;d<=(sphere?2:4);d++){
     String tag="recovered"+d;m.result().numerical().create(tag,"EvalPoint");m.result().numerical(tag).set("data",sphere?"points":"cp"+d);
     String magnitude="sqrt(abs(pprint(ec.Ex))^2+abs(pprint(ec.Ey))^2+abs(pprint(ec.Ez))^2)";
     m.result().numerical(tag).set("expr",sphere?new String[]{"x","real(V)","real(pprint(ec.Ex))",magnitude}:new String[]{"real(V)","imag(V)","real(pprint(ec.Ex))","imag(pprint(ec.Ex))","real(pprint(ec.Ey))","imag(pprint(ec.Ey))","real(pprint(ec.Ez))","imag(pprint(ec.Ez))",magnitude});
     String t="recTbl"+d;m.result().table().create(t,"Table");m.result().numerical(tag).set("table",t);m.result().numerical(tag).setResult();m.result().table(t).save(OUT+"/"+id+"_ppr"+(sphere?"":"_"+d+"m")+".csv");
    }
    ModelUtil.remove("Recover");System.out.println("RECOVER_DONE "+id);
   }catch(Exception e){e.printStackTrace();try{ModelUtil.remove("Recover");}catch(Exception ignored){}}
  }
 }
}
