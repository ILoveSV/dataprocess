from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/'scripts/ExternalSettingsProbe20260916.java').read_text(encoding='utf8')
s=s.replace('public class ExternalSettingsProbe20260916','public class ExternalCurrentExports20260916')
s=s.replace('new String[]{"local_r20_h9","local_r30_h15"}', 'new String[]{"gap_g010","gap_g020","gap_g050","gap_g100","gap_g200","gap_g300","single_g010","single_g300","gap_g010_fine","gap_g300_fine"}')
s=s.replace('   Model m=ModelUtil.load(', '   if(!new java.io.File(OUT+"/"+id+".mph").exists()){System.out.println("SKIP "+id);continue;}\n   Model m=ModelUtil.load(')
(ROOT/'scripts/ExternalCurrentExports20260916.java').write_text(s,encoding='utf8')
print('Created read-only current export postprocessor')
