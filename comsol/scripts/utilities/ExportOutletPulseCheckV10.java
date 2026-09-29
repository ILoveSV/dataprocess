import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class ExportOutletPulseCheckV10 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\comsol";
  private static final String MODEL_FILE =
      ROOT + "\\models\\water_loop_pulsation_v10_last_solution.mph";
  private static final String OUTPUT_FILE =
      ROOT + "\\results\\pulsation_v10\\outlet_pressure_check_op50_A050.csv";

  public static void main(String[] args) throws Exception {
    Model model = ModelUtil.load("Model", MODEL_FILE);
    model.result().table().create("tblOutCheck", "Table");
    model.result().numerical().create("avgOutCheck", "AvSurface");
    model.result().numerical("avgOutCheck").selection().set(6);
    model.result().numerical("avgOutCheck").set("expr", new String[] {"p"});
    model.result().numerical("avgOutCheck").set("unit", new String[] {"Pa"});
    model.result().numerical("avgOutCheck").set("table", "tblOutCheck");
    model.result().numerical("avgOutCheck").setResult();
    model.result().table("tblOutCheck").save(OUTPUT_FILE);
    System.out.println("OUTLET_CHECK=" + OUTPUT_FILE);
    ModelUtil.remove("Model");
  }
}
