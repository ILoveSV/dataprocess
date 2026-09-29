from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/'scripts/ExternalFieldFollowup20260909.java').read_text(encoding='utf8').replace('public class ExternalFieldFollowup20260909','public class ExternalFieldConvergence20260909')
a=s.index('  public static void main(String[] args)')
s=s[:a]+'''  public static void main(String[] args) throws Exception {
    String[] names={"mesh_coarse","mesh_fine","domain_medium","domain_large"};
    double[][] jobs={{10,3,1.3},{10,3,.75},{15,6,1},{20,9,1}};
    FIX_HEAD=true;FIX_TAPE=true;
    for(int k=0;k<jobs.length;k++){
      CASE=names[k];RADIUS=jobs[k][0];HEIGHT=jobs[k][1];MESH_SCALE=jobs[k][2];
      try{run();}catch(Exception e){e.printStackTrace();System.out.println("FAILED "+CASE);try{ModelUtil.remove("Model");}catch(Exception ignored){}}
    }
  }
}
'''
(ROOT/'scripts/ExternalFieldConvergence20260909.java').write_text(s,encoding='utf8')
