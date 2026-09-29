import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;
import java.nio.file.*;
import java.io.*;
import java.util.*;

/** Isolated water-domain gap audit. All source MPH files remain read-only. */
public class CathodicGapAudit20260908 {
 static final String ROOT="C:/Users/17584/Documents/ALearning/Project/tools/DataProcess";
 static final String OUT=ROOT+"/results/thesis_completion_20260908/gap";
 static double eval(Model m,String tag,String type,String selection,String expr){
  m.result().numerical().create(tag,type);
  if(selection!=null)m.result().numerical(tag).selection().named(selection);
  m.result().numerical(tag).set("expr",expr);
  double v=m.result().numerical(tag).getReal()[0][0];
  m.result().numerical().remove(tag);return v;
 }
 static void one(double gap,double offset,int size) throws Exception {
  String id=String.format(Locale.ROOT,"g%03d_x%03d_m%d",(int)gap,(int)offset,size);
  Model m=ModelUtil.load("GapModel",ROOT+"/comsol/models/cathodic_protection_tank_3d_current_sweep_v3.mph");
  m.label("Conditional water-domain gap audit "+id);
  m.param().set("electrode_gap",gap+"[mm]");
  m.param().set("pair_x",offset+"[mm]","Scenario shift of electrode-pair center, not measured placement");
  m.param().set("I_total","0.01[A]");
  for(String tag:m.component("comp1").geom("geom1").feature().tags()){
   try{
    String[] p=m.component("comp1").geom("geom1").feature(tag).getStringArray("pos");
    if(p!=null&&p.length==3&&p[0].contains("electrode_spacing")){
     p[0]="("+p[0]+")+pair_x";
     m.component("comp1").geom("geom1").feature(tag).set("pos",p);
    }
   }catch(Exception ignored){}
  }
  for(String tag:m.sol().tags())m.sol().remove(tag);
  for(String tag:m.study().tags())m.study().remove(tag);
  m.component("comp1").geom("geom1").run();
  m.component("comp1").mesh("mesh1").autoMeshSize(size);
  m.component("comp1").mesh("mesh1").run();
  m.study().create("gapstudy");m.study("gapstudy").create("stat","Stationary");
  m.study("gapstudy").run();
  double voltage=eval(m,"gapvoltage","EvalGlobal",null,"ec.term1.V0_ode");
  double power=eval(m,"gappower","IntVolume","geom1_waterFluid_dom","ec.Jx*ec.Ex+ec.Jy*ec.Ey+ec.Jz*ec.Ez");
  double volume=eval(m,"gapvolume","IntVolume","geom1_waterFluid_dom","1");
  double field=eval(m,"gapfield","AvVolume","geom1_waterFluid_dom","ec.normE");
  double residual=Math.abs(power-0.01*voltage)/Math.abs(0.01*voltage);
  String line=String.format(Locale.ROOT,"%s,%.1f,%.1f,%d,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g%n",id,gap,offset,size,voltage,voltage/.01,power,residual,volume,field);
  m.result().numerical().create("gapSummary","EvalGlobal");
  m.result().numerical("gapSummary").set("expr",new String[]{"electrode_gap/1[mm]","pair_x/1[mm]",Integer.toString(size),"ec.term1.V0_ode","ec.term1.V0_ode/I_total",Double.toString(power),Double.toString(residual),Double.toString(volume),Double.toString(field)});
  m.result().numerical("gapSummary").set("descr",new String[]{"gap_mm","pair_center_x_mm","mesh_auto_size","terminal_v_at_10ma","resistance_ohm","power_w","power_balance_relative_error","water_volume_m3","mean_water_field_v_m"});
  m.result().table().create("gapTable","Table");m.result().numerical("gapSummary").set("table","gapTable");m.result().numerical("gapSummary").setResult();
  m.result().table("gapTable").save(OUT+"/"+id+".csv");
  m.save(OUT+"/"+id+".mph");
  System.out.println("DONE "+line.trim());
  ModelUtil.remove("GapModel");
 }
 public static void main(String[] args) throws Exception {
  // 55 mm offset keeps the full 400 mm pipe inside the circular tank at 300 mm gap.
  double[][] jobs={{20,0,5},{10,55,5},{20,55,5},{50,55,5},{100,55,5},{200,55,5},{300,55,5},{10,55,6},{10,55,4},{300,55,6},{300,55,4}};
  for(double[] j:jobs){
   try{one(j[0],j[1],(int)j[2]);}
   catch(Exception e){e.printStackTrace();try{ModelUtil.remove("GapModel");}catch(Exception x){}
    System.out.println("FAILED "+Arrays.toString(j)+" "+e.toString());
   }
  }
 }
}
