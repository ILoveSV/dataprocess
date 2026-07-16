import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class ExportStreamingPotentialV7 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\comsol";
  private static final String MODEL_FILE =
      ROOT + "\\models\\water_loop_streaming_potential_v7_solved.mph";

  private static double value(Model model, String tag, int row) {
    double[][] values = model.result().numerical(tag).getReal();
    return values[row][0];
  }

  public static void main(String[] args) throws Exception {
    Model model = ModelUtil.load("Model", MODEL_FILE);
    model.result().numerical().create("avgIn", "AvSurface");
    model.result().numerical("avgIn").set("data", "dset1");
    model.result().numerical("avgIn").selection().set(1);
    model.result().numerical("avgIn").set("expr", new String[] {"p", "V"});
    model.result().numerical().create("avgOut", "AvSurface");
    model.result().numerical("avgOut").set("data", "dset1");
    model.result().numerical("avgOut").selection().set(6);
    model.result().numerical("avgOut").set("expr", new String[] {"p", "V"});
    model.result().numerical().create("maxFlow", "MaxVolume");
    model.result().numerical("maxFlow").set("data", "dset1");
    model.result().numerical("maxFlow").selection().set(1);
    model.result().numerical("maxFlow").set("expr", new String[] {"spf.U", "ec.normE"});
    for (int boundary = 1; boundary <= 6; boundary++) {
      String tag = "area" + boundary;
      model.result().numerical().create(tag, "IntSurface");
      model.result().numerical(tag).set("data", "dset1");
      model.result().numerical(tag).selection().set(boundary);
      model.result().numerical(tag).set("expr", new String[] {"1"});
      System.out.println("BOUNDARY_AREA," + boundary + "," + value(model, tag, 0));
      String avgTag = "center" + boundary;
      model.result().numerical().create(avgTag, "AvSurface");
      model.result().numerical(avgTag).set("data", "dset1");
      model.result().numerical(avgTag).selection().set(boundary);
      model.result().numerical(avgTag).set("expr", new String[] {"x", "y", "z"});
      System.out.println("BOUNDARY_CENTER," + boundary + "," + value(model, avgTag, 0)
          + "," + value(model, avgTag, 1) + "," + value(model, avgTag, 2));
    }

    double pIn = value(model, "avgIn", 0);
    double vIn = value(model, "avgIn", 1);
    double pOut = value(model, "avgOut", 0);
    double vOut = value(model, "avgOut", 1);
    double uMax = value(model, "maxFlow", 0);
    double eMax = value(model, "maxFlow", 1);
    double reynolds = model.param().evaluate("Re_pipe");
    double headReference = model.param().evaluate("V_stream_head");

    System.out.println("RESULT,pressure_in_Pa," + pIn);
    System.out.println("RESULT,pressure_out_Pa," + pOut);
    System.out.println("RESULT,pressure_drop_Pa," + (pIn - pOut));
    System.out.println("RESULT,potential_in_V," + vIn);
    System.out.println("RESULT,potential_out_V," + vOut);
    System.out.println("RESULT,streaming_potential_V," + (vIn - vOut));
    System.out.println("RESULT,max_velocity_m_per_s," + uMax);
    System.out.println("RESULT,max_electric_field_V_per_m," + eMax);
    System.out.println("RESULT,reynolds_number," + reynolds);
    System.out.println("RESULT,nameplate_head_reference_V," + headReference);
    ModelUtil.remove("Model");
  }
}
