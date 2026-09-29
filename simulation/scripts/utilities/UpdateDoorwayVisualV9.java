import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class UpdateDoorwayVisualV9 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\simulation";
  private static final String[] INPUT_FILES = {
      ROOT + "\\models\\water_system_3d_doorway_environment_v9.mph",
      ROOT + "\\models\\water_system_3d_doorway_environment_v9_solved.mph"
  };
  private static final String[] OUTPUT_FILES = {
      ROOT + "\\models\\water_system_3d_doorway_environment_v9.mph",
      ROOT + "\\models\\water_system_3d_doorway_environment_v9_solved_floor_fixed.mph"
  };

  public static void main(String[] args) throws Exception {
    for (int index = 0; index < INPUT_FILES.length; index++) {
      String tag = "Model" + index;
      Model model = ModelUtil.load(tag, INPUT_FILES[index]);
      model.component("comp1").geom("geom1").feature("floor")
          .label("Symmetric floor spanning full glass partition");
      model.component("comp1").geom("geom1").feature("floor")
          .set("size", new String[] {"partition_width", "5.2[m]", "0.05[m]"});
      model.component("comp1").geom("geom1").feature("floor")
          .set("pos", new String[] {"-partition_width/2", "-4.35[m]", "-0.05[m]"});
      model.component("comp1").geom("geom1").run();
      if (index == 1) model.label("water_system_3d_doorway_environment_v9_solved_floor_fixed.mph");
      model.save(OUTPUT_FILES[index]);
      ModelUtil.remove(tag);
    }
  }
}
