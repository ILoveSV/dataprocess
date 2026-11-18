import com.comsol.model.Model;
import com.comsol.model.ModelEntityImage;
import com.comsol.model.util.ModelUtil;

public class ExportCathodicProtectionElectrodeAssemblyPreview {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\research\\simulation";
  private static final String MODEL_FILE =
      ROOT + "\\models\\cathodic_protection_electrode_assembly_3d_v1.mph";
  private static final String OUTPUT_FILE =
      ROOT + "\\results\\cathodic_protection_electrode_assembly_v1"
          + "\\cathodic_protection_electrode_assembly_v1.png";

  public static void main(String[] args) throws Exception {
    Model model = ModelUtil.load("Model", MODEL_FILE);
    ModelEntityImage image = model.component("comp1").geom("geom1").image();
    image.set("view", "view1");
    image.set("zoomextents", true);
    image.set("showselection", false);
    image.set("showmaterial", false);
    image.set("drawmode", "on");
    image.set("showgrid", false);
    image.set("grid", false);
    image.set("background", "color");
    image.set("customcolor", new double[] {1, 1, 1});
    image.set("size", "manualweb");
    image.set("widthpx", "1800");
    image.set("heightpx", "1400");
    image.set("pngfilename", OUTPUT_FILE);
    image.export();
    System.out.println("ELECTRODE_PREVIEW=" + OUTPUT_FILE);
    ModelUtil.remove("Model");
  }
}
