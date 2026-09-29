import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class WaterSystem3DTwoSourceV14 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\simulation";
  private static final String INPUT_FILE =
      ROOT + "\\models\\water_system_3d_minimal_electric_v13.mph";
  private static final String MODEL_FILE =
      ROOT + "\\models\\water_system_3d_two_source_v14.mph";

  public static Model run() throws Exception {
    Model model = ModelUtil.load("Model", INPUT_FILE);
    model.modelPath(ROOT + "\\models");
    model.label("water_system_3d_two_source_v14.mph");
    model.title("3D Representative Two-Source Electrical Model V14");
    model.description(
        "Representative relative-range model retaining only (1) the VFD-to-motor cable "
            + "differential/common-mode electric source and (3) the motor-pump chassis/PE "
            + "common-mode and return-current loop. Electric cases use voltage excitation; "
            + "the magnetic return-loop component uses a normalized 1 A closed edge current.");

    model.param().set("V_chassis_unit", "1[V]",
        "Normalized motor-pump chassis common-mode RMS voltage");
    model.param().set("I_return_unit", "1[A]",
        "Normalized motor-to-PE closed return-loop RMS current");
    model.param().set("return_loop_xc", "1.71[m]", "Return-loop center between VFD and motor");
    model.param().set("return_loop_a", "0.59[m]", "Return-loop half-length");
    model.param().set("return_loop_zc", "0.39[m]", "Return-loop center height");
    model.param().set("return_loop_b", "0.025[m]",
        "Equivalent forward-to-PE half-separation");

    model.component().create("compMag", true);
    model.component("compMag").label("Motor-pump chassis and PE return-current loop");
    model.component("compMag").geom().create("geomMag", 3);
    model.component("compMag").geom("geomMag").lengthUnit("m");

    model.component("compMag").geom("geomMag").create("airMag", "Cylinder");
    model.component("compMag").geom("geomMag").feature("airMag")
        .label("10 m magnetic-field air domain");
    model.component("compMag").geom("geomMag").feature("airMag").set("r", "air_radius");
    model.component("compMag").geom("geomMag").feature("airMag").set("h", "air_height");
    model.component("compMag").geom("geomMag").feature("airMag")
        .set("pos", new String[] {"0", "0", "0"});
    model.component("compMag").geom("geomMag").feature("airMag").set("selresult", true);
    model.component("compMag").geom("geomMag").feature("airMag")
        .set("selresultshow", "dom");

    model.component("compMag").geom("geomMag").create("returnLoop", "ParametricCurve");
    model.component("compMag").geom("geomMag").feature("returnLoop")
        .label("Equivalent motor winding and PE closed return loop");
    model.component("compMag").geom("geomMag").feature("returnLoop").set("parmin", "0");
    model.component("compMag").geom("geomMag").feature("returnLoop").set("parmax", "2*pi");
    model.component("compMag").geom("geomMag").feature("returnLoop").set("coord",
        new String[] {
            "return_loop_xc+return_loop_a*cos(s)",
            "0",
            "return_loop_zc+return_loop_b*sin(s)"
        });
    model.component("compMag").geom("geomMag").feature("returnLoop").set("selresult", true);
    model.component("compMag").geom("geomMag").feature("returnLoop")
        .set("selresultshow", "edg");
    model.component("compMag").geom("geomMag").run();

    model.component("compMag").material().create("matMagAir", "Common");
    model.component("compMag").material("matMagAir").label("Nonmagnetic laboratory air");
    model.component("compMag").material("matMagAir").selection()
        .named("geomMag_airMag_dom");
    model.component("compMag").material("matMagAir").propertyGroup("def")
        .set("relpermeability", new String[] {"1"});
    model.component("compMag").material("matMagAir").propertyGroup("def")
        .set("electricconductivity", new String[] {"1e-14[S/m]"});
    model.component("compMag").material("matMagAir").propertyGroup("def")
        .set("relpermittivity", new String[] {"1.0006"});

    model.component("compMag").physics().create("mf", "InductionCurrents", "geomMag");
    model.component("compMag").physics("mf")
        .label("Magnetic fields - normalized motor/PE return current");
    model.component("compMag").physics("mf").create("edgeReturn", "EdgeCurrent", 1);
    model.component("compMag").physics("mf").feature("edgeReturn")
        .label("1 A RMS closed common-mode return current");
    model.component("compMag").physics("mf").feature("edgeReturn").selection()
        .named("geomMag_returnLoop_edg");
    model.component("compMag").physics("mf").feature("edgeReturn")
        .set("Ie", "I_return_unit");

    model.component("compMag").mesh().create("meshMag");
    model.component("compMag").mesh("meshMag").feature("size").set("hauto", 3);
    model.component("compMag").mesh("meshMag").feature("size").set("hmax", "0.8[m]");
    model.component("compMag").mesh("meshMag").feature("size").set("hmin", "20[mm]");

    model.study("stdField").feature("freq")
        .set("activate", new String[] {"ec", "on", "mf", "off"});
    model.study().create("stdMag");
    model.study("stdMag").label("Normalized motor-pump and PE return-current study");
    model.study("stdMag").create("freq", "Frequency");
    model.study("stdMag").feature("freq").set("plist", "100[kHz]");
    model.study("stdMag").feature("freq")
        .set("activate", new String[] {"ec", "off", "mf", "on"});

    model.save(MODEL_FILE);
    return model;
  }

  public static void main(String[] args) throws Exception {
    run();
  }
}
