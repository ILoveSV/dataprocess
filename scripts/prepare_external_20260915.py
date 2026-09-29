"""Isolated continuation of the September 9 COMSOL verification branch."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT / 'analysis/thesis_followup_20260915/external';OUT.mkdir(parents=True,exist_ok=True)
s=(ROOT/'scripts/ExternalRecoveredField20260909.java').read_text(encoding='utf8')
s=s.replace('public class ExternalRecoveredField20260909','public class PostprocessLocal20260915')
s=s.replace('static final String OUT=ROOT+"/results/thesis_followup_20260909/external";', 'static final String SOURCE=ROOT+"/results/thesis_followup_20260909/external";\n static final String OUT=ROOT+"/results/thesis_followup_20260915/external";')
a=s.index('  String[] ids=');b=s.index('\n',a);s=s[:a]+'  String[] ids={"local_h100","local_h075","local_h050"};'+s[b:]
s=s.replace(':OUT+"/"+id+".mph"',':SOURCE+"/"+id+".mph"')
(ROOT/'scripts/PostprocessLocal20260915.java').write_text(s,encoding='utf8')
s=(ROOT/'scripts/ExternalLocalMesh20260909.java').read_text(encoding='utf8').replace('public class ExternalLocalMesh20260909','public class ExternalDomain20260915')
s=s.replace('/results/thesis_followup_20260909/external','/results/thesis_followup_20260915/external')
a=s.index('  public static void main(String[] args)')
s=s[:a]+'''  public static void main(String[] args) throws Exception {
    String[] names={"local_r15_h6","local_r20_h9","local_r30_h15"};
    double[][] jobs={{15,6},{20,9},{30,15}};
    FIX_HEAD=true;FIX_TAPE=true;OBS_H=.05;
    for(int k=0;k<jobs.length;k++){
      CASE=names[k];RADIUS=jobs[k][0];HEIGHT=jobs[k][1];
      try{run();}catch(Exception e){e.printStackTrace();System.out.println("FAILED "+CASE);try{ModelUtil.remove("Model");}catch(Exception ignored){}}
    }
  }
}
'''
# Export both raw and recovered derivatives without selecting a preferred result.
needle='      model.result().table(table).save(OUTPUT_DIR + "/"+CASE+"_" + distance + "m.csv");'
assert needle in s
s=s.replace(needle,needle+'''
      model.result().numerical(eval).set("expr",new String[]{"real(V)","imag(V)","real(pprint(ec.Ex))","imag(pprint(ec.Ex))","real(pprint(ec.Ey))","imag(pprint(ec.Ey))","real(pprint(ec.Ez))","imag(pprint(ec.Ez))","sqrt(abs(pprint(ec.Ex))^2+abs(pprint(ec.Ey))^2+abs(pprint(ec.Ez))^2)"});
      model.result().numerical(eval).setResult();model.result().table(table).save(OUTPUT_DIR+"/"+CASE+"_ppr_"+distance+"m.csv");
''')
(ROOT/'scripts/ExternalDomain20260915.java').write_text(s,encoding='utf8')
print('Prepared local recovery and three domain cases')
