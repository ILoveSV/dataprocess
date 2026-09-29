from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/'scripts/ExternalFieldStableDomain20260909.java').read_text(encoding='utf8').replace('public class ExternalFieldStableDomain20260909','public class ExternalLocalMesh20260909')
s=s.replace('  private static boolean FIX_HEAD=true,FIX_TAPE=false;','  private static boolean FIX_HEAD=true,FIX_TAPE=false;\n  private static double OBS_H=.1;')
at='    model.component("comp1").geom("geom1").feature("fin").set("action", "union");'
s=s.replace(at,'''    for(int d=2;d<=4;d++){
      String tag="obsP"+d;model.component("comp1").geom("geom1").create(tag,"Point");
      model.component("comp1").geom("geom1").feature(tag).set("p",new String[]{"0","-(tank_diam/2+"+d+"[m])","0.5[m]"});
      model.component("comp1").geom("geom1").feature(tag).set("selresult",true);
    }
'''+at)
at='    model.component("comp1").mesh("mesh1").create("ftet1", "FreeTet");'
s=s.replace(at,'''    for(int d=2;d<=4;d++){
      String tag="obsSize"+d;model.component("comp1").mesh("mesh1").create(tag,"Size");
      model.component("comp1").mesh("mesh1").feature(tag).selection().geom("geom1",0);
      model.component("comp1").mesh("mesh1").feature(tag).selection().named("geom1_obsP"+d+"_pnt");
      model.component("comp1").mesh("mesh1").feature(tag).set("custom","on");
      model.component("comp1").mesh("mesh1").feature(tag).set("hmax",OBS_H+"[m]");
      model.component("comp1").mesh("mesh1").feature(tag).set("hmin",(OBS_H/4)+"[m]");
      model.component("comp1").mesh("mesh1").feature(tag).set("hgrad",1.2);
    }
'''+at)
a=s.index('  public static void main(String[] args)')
s=s[:a]+'''  public static void main(String[] args) throws Exception {
    String[] names={"local_h100","local_h075","local_h050"};double[] hs={.1,.075,.05};
    FIX_HEAD=true;FIX_TAPE=true;RADIUS=10;HEIGHT=3;
    for(int k=0;k<hs.length;k++){
      CASE=names[k];OBS_H=hs[k];
      try{run();}catch(Exception e){e.printStackTrace();System.out.println("FAILED "+CASE);try{ModelUtil.remove("Model");}catch(Exception ignored){}}
    }
  }
}
'''
(ROOT/'scripts/ExternalLocalMesh20260909.java').write_text(s,encoding='utf8')
