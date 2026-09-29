"""Generate isolated final convergence and prespecified gap/boundary cases."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
base=(ROOT/'scripts/ExternalDomain20260915.java').read_text(encoding='utf8')
# Explicit in the new source; saved historical MPH files also have custom=on.
base=base.replace('model.component("comp1").mesh("mesh1").feature("size").set("hauto", 3);','model.component("comp1").mesh("mesh1").feature("size").set("hauto", 3);\n    model.component("comp1").mesh("mesh1").feature("size").set("custom", "on");')
base=base.replace('Unit floating cathodic-protection differential transfer','Specified ground-referenced differential transfer')
def write(name,main):
 s=base[:base.index('  public static void main(String[] args)')]+main+'\n}\n'
 s=s.replace('public class ExternalDomain20260915','public class '+name)
 (ROOT/'scripts'/f'{name}.java').write_text(s,encoding='utf8')
write('ExternalFinalChecks20260916','''
 public static void main(String[] args) throws Exception {
  FIX_HEAD=true;FIX_TAPE=true;GAP=20;SHIFT=0;
  String[] names={"local_r30_h15_h025","local_r40_h21"};
  double[][] jobs={{30,15,.025},{40,21,.05}};
  for(int k=0;k<jobs.length;k++){
   CASE=names[k];RADIUS=jobs[k][0];HEIGHT=jobs[k][1];OBS_H=jobs[k][2];
   try{run();}catch(Exception e){e.printStackTrace();System.out.println("FAILED "+CASE);try{ModelUtil.remove("Model");}catch(Exception ignored){}}
  }
 }
''')
# A fixed, declared two-height routing scenario avoids opposite-polarity wire
# intersections when the electrode-pair center is shifted by 55 mm.
base=base.replace('double[] posEnd = {0.0, -0.027, 0.90};','double[] posEnd = {0.0, -0.027, 0.92};')
base=base.replace('new double[] {xPos, 0.0, 0.90}', 'new double[] {xPos, 0.0, 0.92}')
base=base.replace('"posStub", "Positive feedthrough conductor", "wire_radius", "48[mm]"','"posStub", "Positive feedthrough conductor", "wire_radius", "68[mm]"')
base=base.replace('"airPosStubCut", "Air cutout: positive feedthrough", "wire_radius", "48[mm]"','"airPosStubCut", "Air cutout: positive feedthrough", "wire_radius", "68[mm]"')
write('ExternalGapCases20260916','''
 public static void main(String[] args) throws Exception {
  FIX_HEAD=true;FIX_TAPE=true;RADIUS=30;HEIGHT=15;OBS_H=.05;SHIFT=55;
  String[] names={"gap_g010","gap_g020","gap_g050","gap_g100","gap_g200","gap_g300","single_g010","single_g300"};
  double[] gaps={10,20,50,100,200,300,10,300};
  for(int k=0;k<gaps.length;k++){
   CASE=names[k];GAP=gaps[k];EXCITATION=k<6?"balanced":"single";
   try{run();}catch(Exception e){e.printStackTrace();System.out.println("FAILED "+CASE);try{ModelUtil.remove("Model");}catch(Exception ignored){}}
  }
 }
''')
write('ExternalGapChecks20260916','''
 public static void main(String[] args) throws Exception {
  FIX_HEAD=true;FIX_TAPE=true;RADIUS=30;HEIGHT=15;OBS_H=.025;SHIFT=55;MESH_SCALE=.75;
  for(int gap:new int[]{10,300}){
   GAP=gap;CASE=gap==10?"gap_g010_fine":"gap_g300_fine";
   try{run();}catch(Exception e){e.printStackTrace();System.out.println("FAILED "+CASE);try{ModelUtil.remove("Model");}catch(Exception ignored){}}
  }
 }
''')
print('Created final checks and pending gap/boundary batch sources')
