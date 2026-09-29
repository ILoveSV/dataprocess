import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class BuildCathodicProtectionCurrentSweepV3 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\simulation";
  private static final String INPUT_FILE =
      ROOT + "\\models\\cathodic_protection_tank_3d_preliminary_v2.mph";
  private static final String MODEL_FILE =
      ROOT + "\\models\\cathodic_protection_tank_3d_current_sweep_v3.mph";
  private static final String OUTPUT_DIR =
      ROOT + "\\results\\cathodic_protection_tank_3d_current_sweep_v3";

  public static Model run() throws Exception {
    Model model = ModelUtil.load("Model", INPUT_FILE);
    model.modelPath(ROOT + "\\models");
    model.label("cathodic_protection_tank_3d_current_sweep_v3.mph");
    model.title("3D Cathodic-Protection Current Sweep with Measured Terminal Voltages V3");
    model.description(
        "Updated four-current cathodic-protection model. The confirmed tap-water conductivity "
            + "is 500 uS/cm, the electrodes have a 20 mm minimum surface gap, both suspension "
            + "rods are 350 mm, and both active electrodes are fully submerged. The graphite "
            + "positive electrode is driven at 0.01, 0.05, 0.10, and 0.20 A while the steel "
            + "negative electrode is the cathodic reference. Measured stable supply voltages "
            + "are retained for comparison and are not imposed simultaneously on the current model.");

    model.param().set("sigma_water", "0.05[S/m]", "Confirmed 500 uS/cm tap-water conductivity");
    model.param().set("electrode_gap", "20[mm]", "Confirmed minimum electrode surface gap");
    model.param().set("electrode_spacing",
        "steel_pipe_r+graphite_diam/2+electrode_gap",
        "Axis spacing corresponding to the 20 mm minimum surface gap");
    model.param().set("suspension_length", "0.35[m]",
        "Provisional lid-underside to electrode-top suspension length");
    model.param().set("support_bottom_z", "-lid_thickness-suspension_length",
        "Bottom of the 350 mm steel suspension rod");
    model.param().set("steel_pipe_center_z",
        "support_bottom_z+support_embed-(steel_pipe_r+tape_thickness)",
        "Steel-pipe center after lowering the specimen");
    model.param().set("graphite_top_z", "-lid_thickness-suspension_length",
        "Graphite active-section top after lowering the electrode");
    model.param().set("V_measured",
        "if(I_total<0.03[A],0.20[V],if(I_total<0.075[A],0.50[V],"
            + "if(I_total<0.15[A],0.70[V],1.20[V])))",
        "Stable power-supply voltage measured at each current setting");

    model.component("comp1").geom("geom1").feature("graphiteHolder")
        .set("h", "suspension_length");
    model.component("comp1").geom("geom1").feature("wetGraphiteHolder")
        .set("h", "suspension_length");
    model.component("comp1").geom("geom1").feature("steelSupport")
        .label("350 mm steel-electrode suspension rod");
    model.component("comp1").geom("geom1").feature("graphiteHolder")
        .label("350 mm insulated graphite suspension rod");
    model.component("comp1").geom("geom1").run();

    model.component("comp1").material("matWater")
        .label("Confirmed tap water at 500 uS/cm");
    model.component("comp1").physics("ec").feature("term1")
        .label("Four-level graphite constant-current terminal");
    model.component("comp1").physics("ec").feature("gnd1")
        .label("Negative steel cathode exposed window");

    model.component("comp1").mesh("mesh1").run();

    model.study().remove("std1");
    model.sol().remove("sol1");
    model.study().create("std1");
    model.study("std1").label("Four-level stationary cathodic-discharge current sweep");
    model.study("std1").create("param", "Parametric");
    model.study("std1").feature("param").setIndex("pname", "I_total", 0);
    model.study("std1").feature("param")
        .setIndex("plistarr", "0.01 0.05 0.10 0.20", 0);
    model.study("std1").feature("param").setIndex("punit", "A", 0);
    model.study("std1").create("stat", "Stationary");
    model.study("std1").createAutoSequences("all");
    model.sol("sol1").runAll();

    model.save(MODEL_FILE);

    model.result().numerical().remove("terminalSummary");
    model.result().numerical().remove("maxField");
    model.result().numerical().remove("avgField");
    model.result().table().remove("tblTerminal");
    model.result().table().remove("tblMax");
    model.result().table().remove("tblAvg");

    model.result().numerical().create("sweepSummary", "EvalGlobal");
    model.result().numerical("sweepSummary").set("expr", new String[] {
        "I_total", "V_measured", "ec.term1.V0_ode",
        "V_measured-ec.term1.V0_ode", "abs(ec.term1.V0_ode/I_total)",
        "abs(V_measured/I_total)"});
    model.result().numerical("sweepSummary").set("descr", new String[] {
        "Applied constant current", "Measured stable supply voltage",
        "COMSOL water-domain terminal voltage", "Measured minus COMSOL voltage",
        "COMSOL ohmic resistance", "Measured apparent resistance"});
    model.result().table().create("tblSweep", "Table");
    model.result().table("tblSweep").label("Four-current measured and modeled comparison");
    model.result().numerical("sweepSummary").set("table", "tblSweep");
    model.result().numerical("sweepSummary").setResult();
    model.result().table("tblSweep").save(OUTPUT_DIR + "\\current_voltage_comparison.csv");

    model.result().numerical().create("fieldSummary", "AvVolume");
    model.result().numerical("fieldSummary").selection().named("geom1_waterFluid_dom");
    model.result().numerical("fieldSummary").set("expr",
        new String[] {"ec.normE", "ec.normJ"});
    model.result().numerical("fieldSummary").set("descr",
        new String[] {"Average water electric field", "Average water current density"});
    model.result().table().create("tblField", "Table");
    model.result().table("tblField").label("Four-current average water-field values");
    model.result().numerical("fieldSummary").set("table", "tblField");
    model.result().numerical("fieldSummary").setResult();
    model.result().table("tblField").save(OUTPUT_DIR + "\\water_field_average_by_current.csv");

    model.save(MODEL_FILE);
    System.out.println("MODEL_FILE=" + MODEL_FILE);
    System.out.println("OUTPUT_DIR=" + OUTPUT_DIR);
    ModelUtil.remove("Model");
    return null;
  }

  public static void main(String[] args) throws Exception {
    run();
  }
}
