import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;
import java.io.PrintWriter;

public class LegacyHalfMeter {
  private static final String SIM="C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/research/simulation/";
  private static final String OUT=SIM+"projects/lab_cathodic/rectangular_tank_v2/legacy_half_meter/";
  private static final String HF="4000 8000 12000 20000 50000 80000 100000 120000 150000 200000";
  private static final String ALL="30 50 "+HF;
  private static final double[] DIST={0.5,2,3,4};
  private static final String[] SUFFIX={"05","2","3","4"};
  private static final String[] PHASE={"1","exp(-i*2*pi/3)","exp(i*2*pi/3)"};

  private static void points(Model m, String prefix, String solution, boolean magnetic) {
    String[] expr=magnetic
        ? new String[]{"freq","mf.Bx","mf.By","mf.Bz","mf.Ax","mf.Ay","mf.Az","dom"}
        : new String[]{"freq","ec.Ex","ec.Ey","ec.Ez","ec.normE","dom"};
    for (int i=0;i<DIST.length;i++) {
      String cp=prefix+"cp"+SUFFIX[i], ev=prefix+"eval"+SUFFIX[i];
      m.result().dataset().create(cp,"CutPoint3D");
      m.result().dataset(cp).set("data",solution);
      m.result().dataset(cp).set("pointx",new double[]{0});
      m.result().dataset(cp).set("pointy",new double[]{-(0.28+DIST[i])});
      m.result().dataset(cp).set("pointz",new double[]{0.5});
      m.result().dataset(cp).label((magnetic?"PE loop: ":"Electric: ")+"tank wall "+DIST[i]+" m toward door; z = 0.5 m");
      m.result().numerical().create(ev,"EvalPoint");
      m.result().numerical(ev).set("data",cp);
      m.result().numerical(ev).set("expr",expr);
      m.result().numerical(ev).set("looplevelinput","all");
    }
  }

  private static double norm(double[][] re,double[][] im,int row,int j) {
    double sum=0;
    for(int i=row;i<row+3;i++) {
      double x=Math.hypot(re[i][j],im[i][j]);
      sum+=x*x;
    }
    return Math.sqrt(sum);
  }

  private static void export(Model m,String prefix,String source,double input,int expected,
      String airSelection,String component,PrintWriter out) {
    boolean magnetic=prefix.equals("hm");
    int[] air=m.component(component).selection(airSelection).entities(3);
    for (int i=0;i<DIST.length;i++) {
      String ev=prefix+"eval"+SUFFIX[i];
      double[][] re=m.result().numerical(ev).getReal(), im=m.result().numerical(ev).getImag();
      if(re.length!=(magnetic?8:6)||re[0].length!=expected)
        throw new IllegalStateException(source+" unexpected solution count at "+DIST[i]);
      for(int j=0;j<expected;j++) {
        double f=re[0][j];
        int dom=(int)Math.round(re[re.length-1][j]);
        boolean inAir=false;
        for(int d:air) if(d==dom) inAir=true;
        if(!inAir) throw new IllegalStateException(source+" observation not in air: "+dom);
        double e=magnetic?2*Math.PI*f*norm(re,im,4,j):norm(re,im,1,j);
        double b=magnetic?norm(re,im,1,j):0;
        if(!(e>0)||!Double.isFinite(e)) throw new IllegalStateException(source+" invalid field");
        out.println("HM_ROW,"+source+","+f+","+input+","+DIST[i]+","+e+","+b+","+dom);
      }
    }
    out.flush();
    System.out.println("EXPORTED "+source+" "+expected+" frequencies");
  }

  private static void electric(Model m,String frequencies,String scale,String pump) {
    for(int i=1;i<=3;i++) {
      String v=scale.equals("diff30")?"0.6*V_phase*"+PHASE[i-1]:
          scale.equals("diff50")?"V_phase*"+PHASE[i-1]:
          scale.equals("cable_cm")?"V_cm_unit":"0[V]";
      m.component("comp2").physics("ec").feature("potMotor"+i).set("V0",v);
      m.component("comp2").physics("ec").feature("potWall"+i).set("V0","0[V]");
    }
    m.component("comp2").physics("ec").feature("potPump").set("V0",pump);
    m.component("comp2").physics("ec").feature("pcsStreamLow").set("Qjp","0[A]");
    m.component("comp2").physics("ec").feature("pcsStreamHigh").set("Qjp","0[A]");
    m.sol("sol1").clearSolution();
    m.study("stdField").feature("freq").set("plist",frequencies);
    m.study("stdField").run();
  }

  private static void save(Model m,String file) throws Exception {
    m.label(file);
    m.save(OUT+file);
    ModelUtil.remove(m.tag());
  }

  public static void finishMagnetic(Model v14,PrintWriter out) throws Exception {
    String magneticData=v14.result().dataset("mcp2").getString("data");
    points(v14,"hm",magneticData,true);
    v14.sol("sol2").clearSolution();
    v14.study("stdMag").feature("freq").set("plist",ALL);
    v14.study("stdMag").run();
    export(v14,"hm","pe_loop",1,12,"geomMag_airMag_dom","compMag",out);
    save(v14,"chassis_pe_v14_with_0p5m.mph");
  }

  public static void main(String[] args) throws Exception {
    {
      PrintWriter out=new PrintWriter(System.out,true);
      Model round=ModelUtil.load("Round",SIM+"models/cathodic_protection_external_field_v4.mph");
      points(round,"he","dset1",false);
      export(round,"he","round_v4_unit",1,1,"geom1_airFluid_dom","comp1",out);
      save(round,"round_v4_with_0p5m.mph");

      Model cable=ModelUtil.load("Cable",SIM+"models/water_system_3d_minimal_electric_v13_solved.mph");
      points(cable,"he","dset1",false);
      for(String[] run:new String[][]{{"30","diff30","131.63586137523467"},
        {"50","diff50","219.3931022920578"},{HF,"cable_cm","1"}}) {
        electric(cable,run[0],run[1],"0[V]");
        export(cable,"he",run[1],Double.parseDouble(run[2]),run[0].split(" ").length,
            "geom2_air_dom","comp2",out);
      }
      save(cable,"cable_v13_with_0p5m.mph");

      Model v14=ModelUtil.load("Chassis",SIM+"models/water_system_3d_two_source_v14_solved.mph");
      points(v14,"he","dset1",false);
      electric(v14,ALL,"chassis_cm","V_chassis_unit");
      export(v14,"he","chassis_cm",1,12,"geom2_air_dom","comp2",out);
      finishMagnetic(v14,out);
    }
    System.out.println("HALF_METER_COMPLETED");
  }
}
