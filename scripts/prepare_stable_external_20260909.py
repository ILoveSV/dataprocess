from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/'scripts/ExternalFieldFollowup20260909.java').read_text(encoding='utf8').replace('public class ExternalFieldFollowup20260909','public class ExternalFieldStableDomain20260909')
s=s.replace('new String[] {"2*air_radius", "2*air_radius", "floor_thickness"}', 'new String[] {"2*(air_radius+1[m])", "2*(air_radius+1[m])", "floor_thickness"}')
s=s.replace('new String[] {"-air_radius", "-air_radius", "-floor_thickness"}', 'new String[] {"-air_radius-1[m]", "-air_radius-1[m]", "-floor_thickness"}')
a=s.index('  public static void main(String[] args)')
s=s[:a]+'''  public static void main(String[] args) throws Exception {
    String[] names={"padded_base","padded_coarse","padded_fine","padded_medium","padded_large"};
    double[][] jobs={{10,3,1},{10,3,1.3},{10,3,.75},{15,6,1},{20,9,1}};
    FIX_HEAD=true;FIX_TAPE=true;
    for(int k=0;k<jobs.length;k++){
      CASE=names[k];RADIUS=jobs[k][0];HEIGHT=jobs[k][1];MESH_SCALE=jobs[k][2];
      try{run();}catch(Exception e){e.printStackTrace();System.out.println("FAILED "+CASE);try{ModelUtil.remove("Model");}catch(Exception ignored){}}
    }
  }
}
'''
(ROOT/'scripts/ExternalFieldStableDomain20260909.java').write_text(s,encoding='utf8')
