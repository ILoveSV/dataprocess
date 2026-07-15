import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class WaterSystem3DVfdSpectrum {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\comsol";
  private static final String INPUT_FILE = ROOT + "\\models\\water_system_3d_electric_field_v3.mph";
  private static final String MODEL_FILE = ROOT + "\\models\\water_system_3d_vfd_spectrum_v5.mph";

  public static Model run() throws Exception {
    Model model = ModelUtil.load("Model", INPUT_FILE);
    model.modelPath(ROOT + "\\models");
    model.label("water_system_3d_vfd_spectrum_v5.mph");
    model.title("3D Water Circulation System - VFD Spectrum V5");
    model.description(
        "V3 geometry and electric-current model with a parameterized VFD source: balanced 30/50 Hz "
            + "fundamental output plus common-mode PWM carrier components at 4, 8, and 12 kHz. "
            + "Carrier frequency and common-mode amplitudes are assumptions pending measurement.");

    model.param().set("f_sw", "4[kHz]", "Assumed VFD carrier frequency");
    model.param().set("V_dc", "1.35*V_ll", "Approximate rectified DC-link voltage");
    model.param().set("V_cm_pwm", "100[V]", "Assumed RMS common-mode carrier component");
    model.param().set("pwm_h2", "0.5", "Assumed second carrier-harmonic ratio");
    model.param().set("pwm_h3", "0.25", "Assumed third carrier-harmonic ratio");
    model.param().set("V_cm_spectrum",
        "if(abs(freq-f_sw)<1[Hz],V_cm_pwm,"
            + "if(abs(freq-2*f_sw)<1[Hz],pwm_h2*V_cm_pwm,"
            + "if(abs(freq-3*f_sw)<1[Hz],pwm_h3*V_cm_pwm,0[V])))",
        "Common-mode RMS voltage selected by frequency");

    String[] phaseFactor = new String[] {"1", "exp(-i*2*pi/3)", "exp(i*2*pi/3)"};
    for (int phase = 1; phase <= 3; phase++) {
      String motorPotential =
          "if(freq<100[Hz],V_phase*min(freq/f_base,1)*" + phaseFactor[phase - 1]
              + ",V_cm_spectrum)";
      String wallPotential =
          "if(abs(freq-50[Hz])<1[Hz],V_phase*" + phaseFactor[phase - 1] + ",0[V])";
      model.component("comp2").physics("ec").feature("potMotor" + phase)
          .set("V0", motorPotential);
      model.component("comp2").physics("ec").feature("potWall" + phase)
          .set("V0", wallPotential);
    }

    model.study("stdField").label("VFD fundamental and PWM common-mode spectrum");
    model.study("stdField").feature("freq").set("plist", "30 50 f_sw 2*f_sw 3*f_sw");

    for (int distance = 2; distance <= 4; distance++) {
      model.result().numerical("eval" + distance).set("expr",
          new String[] {"V", "ec.Ex", "ec.Ey", "ec.Ez", "ec.normE", "E_sensor", "V_MEMS"});
    }

    model.save(MODEL_FILE);
    return model;
  }

  public static void main(String[] args) throws Exception {
    run();
  }
}
