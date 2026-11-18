"""Generate isolated COMSOL builder from retained V4 source; never edit historical model."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=(ROOT / 'research/simulation/scripts/models/CathodicProtectionExternalFieldV4.java').read_text(encoding='utf8')
s=s.replace('public class CathodicProtectionExternalFieldV4','public class ExternalFieldFollowup20260909')
a=s.index('  private static final String ROOT =');b=s.index('  private static void color',a)
s=s[:a]+'''  private static final String ROOT="C:/Users/17584/Documents/ALearning/Project/tools/DataProcess";
  private static final String OUTPUT_DIR=ROOT+"/results/thesis_followup_20260909/external";
  private static String CASE="";
  private static double GAP=20,SHIFT=0,RADIUS=10,HEIGHT=3,MESH_SCALE=1;
  private static boolean FIX_HEAD=true,FIX_TAPE=false;
  private static String EXCITATION="balanced";
'''+s[b:]
s=s.replace('model.modelPath(ROOT + "\\\\models");','model.modelPath(OUTPUT_DIR);')
s=s.replace('model.param().set("air_radius", "10[m]",','model.param().set("air_radius", RADIUS+"[m]",')
s=s.replace('model.param().set("air_height", "3[m]",','model.param().set("air_height", HEIGHT+"[m]",')
s=s.replace('model.param().set("electrode_gap", "20[mm]",','model.param().set("electrode_gap", GAP+"[mm]",')
s=s.replace('    model.component().create("comp1", true);','    model.param().set("pair_x", SHIFT+"[mm]");\n    model.component().create("comp1", true);')
s=s.replace('"-electrode_spacing/2"','"-electrode_spacing/2+pair_x"').replace('"electrode_spacing/2"','"electrode_spacing/2+pair_x"')
s=s.replace('double xNeg = -0.04125;','double xNeg = SHIFT/1000-(GAP/1000+.0625)/2;')
s=s.replace('double xPos = 0.04125;','double xPos = SHIFT/1000+(GAP/1000+.0625)/2;')
s=s.replace('"steel_pipe_r+0.1[mm]", "steel_pipe_length+0.4[mm]",','FIX_TAPE ? "steel_pipe_r" : "steel_pipe_r+0.1[mm]", "steel_pipe_length+0.4[mm]",')
at='    model.component("comp1").geom("geom1").feature("fin").set("action", "union");'
s=s.replace(at,'''    if(FIX_HEAD) {
      cylinder(model,"headBase","Explicit enclosed tank headspace","tank_inner_r","lid_under_z-tank_wall-water_h",new String[]{"0","0","tank_wall+water_h"},.72,.86,.95);
      cylinder(model,"headNegCut","Headspace negative holder cut","16[mm]","suspension_length",new String[]{"-electrode_spacing/2+pair_x","0","support_bottom_z"},.72,.86,.95);
      cylinder(model,"headPosCut","Headspace positive holder cut","16[mm]","suspension_length",new String[]{"electrode_spacing/2+pair_x","0","support_bottom_z"},.72,.86,.95);
      model.component("comp1").geom("geom1").create("headAir","Difference");
      model.component("comp1").geom("geom1").feature("headAir").selection("input").set("headBase");
      model.component("comp1").geom("geom1").feature("headAir").selection("input2").set(new String[]{"headNegCut","headPosCut"});
      color(model,"headAir",.72,.86,.95);
    }
'''+at)
at='    model.component("comp1").physics().create("ec", "ConductiveMedia", "geom1");'
s=s.replace(at,'    if(FIX_HEAD) material(model,"matHeadAir","Enclosed air above water","geom1_headAir_dom","1e-14[S/m]","1.0006");\n'+at)
s=s.replace('"-V_diff_unit/2");','EXCITATION.equals("single") ? "0[V]" : "-V_diff_unit/2");')
s=s.replace('"V_diff_unit/2");','EXCITATION.equals("single") ? "V_diff_unit" : "V_diff_unit/2");')
s=s.replace('.set("hmax", "0.8[m]");','.set("hmax",(0.8*MESH_SCALE)+"[m]");')
s=s.replace('.set("hmin", "2[mm]");','.set("hmin",(2*MESH_SCALE)+"[mm]");')
s=s.replace('new String[] {"V", "ec.Ex", "ec.Ey", "ec.Ez", "ec.normE"}', 'new String[] {"real(V)","imag(V)","real(ec.Ex)","imag(ec.Ex)","real(ec.Ey)","imag(ec.Ey)","real(ec.Ez)","imag(ec.Ez)","ec.normE"}')
a=s.index('      model.result().numerical(eval).set("descr",');b=s.index('      String table',a);s=s[:a]+s[b:]
s=s.replace('OUTPUT_DIR + "\\\\unit_transfer_" + distance + "m.csv"','OUTPUT_DIR + "/"+CASE+"_" + distance + "m.csv"')
a=s.index('    model.save(MODEL_FILE);');b=s.index('    ModelUtil.remove("Model");',a)
s=s[:a]+'''    model.label(CASE+".mph");
    model.title("Conditional balanced/single-ended external-field geometry audit");
    model.description("Historical V4 derivative. Explicit headspace and optional closed tape gap. Specified ground-referenced drive, not a validated floating circuit.");
    model.save(OUTPUT_DIR+"/"+CASE+".mph");
    System.out.println("DONE "+CASE);
'''+s[b:]
a=s.index('  public static void main(String[] args)');s=s[:a]+'''  public static void main(String[] args) throws Exception {
    // First isolate the missing headspace; then audit the artificial 0.1 mm tape gap.
    for(int k=0;k<2;k++){
      CASE=k==0?"headspace_fixed":"headspace_tape_fixed";FIX_TAPE=k==1;
      try{run();}catch(Exception e){e.printStackTrace();System.out.println("FAILED "+CASE);try{ModelUtil.remove("Model");}catch(Exception ignored){}}
    }
  }
}
'''
(ROOT/'scripts/ExternalFieldFollowup20260909.java').write_text(s,encoding='utf8')
print('Generated isolated builder')
