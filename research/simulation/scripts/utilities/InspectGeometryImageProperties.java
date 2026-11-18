import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;
import java.util.Arrays;

public class InspectGeometryImageProperties {
  private static final String MODEL_FILE =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\research\\simulation"
          + "\\models\\cathodic_protection_electrode_assembly_3d_v1.mph";

  public static void main(String[] args) throws Exception {
    Model model = ModelUtil.load("Model", MODEL_FILE);
    System.out.println("GEOM_IMAGE_PROPERTIES=" + Arrays.toString(
        model.component("comp1").geom("geom1").image().properties()));
    System.out.println("VIEW_PROPERTIES=" + Arrays.toString(
        model.component("comp1").view("view1").properties()));
    System.out.println("CAMERA_PROPERTIES=" + Arrays.toString(
        model.component("comp1").view("view1").camera().properties()));
    System.out.println("AXIS_PROPERTIES=" + Arrays.toString(
        model.component("comp1").view("view1").axis().properties()));
    System.out.println("CAMERA_POSITION=" + Arrays.toString(
        model.component("comp1").view("view1").camera().getDoubleArray("position")));
    System.out.println("CAMERA_TARGET=" + Arrays.toString(
        model.component("comp1").view("view1").camera().getDoubleArray("target")));
    System.out.println("CAMERA_UP=" + Arrays.toString(
        model.component("comp1").view("view1").camera().getDoubleArray("up")));
    System.out.println("CAMERA_ORTHOSCALE="
        + model.component("comp1").view("view1").camera().getDouble("orthoscale"));
    System.out.println("IMAGE_DRAWMODE_ALLOWED=" + Arrays.toString(
        model.component("comp1").geom("geom1").image()
            .getAllowedPropertyValues("drawmode")));
    System.out.println("IMAGE_SHOWMATERIAL_ALLOWED=" + Arrays.toString(
        model.component("comp1").geom("geom1").image()
            .getAllowedPropertyValues("showmaterial")));
    System.out.println("IMAGE_ZOOMLEVEL="
        + model.component("comp1").geom("geom1").image().getDouble("zoomlevel"));
    ModelUtil.remove("Model");
  }
}
