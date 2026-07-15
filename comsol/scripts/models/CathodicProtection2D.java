import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class CathodicProtection2D {
  private static final String OUTPUT_DIR =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\comsol\\results\\cathodic_protection_2d";

  public static Model run() throws Exception {
    Model model = ModelUtil.create("Model");
    model.modelPath(OUTPUT_DIR);
    model.label("cathodic_protection_2d.mph");
    model.title("2D Cathodic Protection: Graphite and Aluminum in Water");
    model.description(
        "Top-view engineering approximation. A 10 mA graphite terminal and grounded "
            + "100 mm square aluminum plate are separated by 300 mm in a 560 mm diameter "
            + "water region. The surrounding air uses a tiny artificial conductivity only "
            + "to visualize a continuous potential extension; it is not interpreted as DC leakage.");

    model.param().set("water_diam", "0.56[m]", "Water region diameter");
    model.param().set("water_rad", "water_diam/2", "Water region radius");
    model.param().set("air_rad", "5.0[m]", "Outer radius of plotted air region");
    model.param().set("spacing", "0.30[m]", "Electrode center spacing");
    model.param().set("graphite_diam", "0.010[m]", "Assumed graphite rod diameter");
    model.param().set("al_size", "0.10[m]", "Aluminum plate width in top view");
    model.param().set("depth", "0.10[m]", "Equivalent out-of-plane immersed depth");
    model.param().set("I_total", "10[mA]", "Applied graphite terminal current");
    model.param().set("I_2d", "I_total/depth*1[m]", "2D terminal current scaled to unit thickness");
    model.param().set("sigma_water", "0.005[S/m]", "50 uS/cm water conductivity");
    model.param().set("sigma_air", "1e-12[S/m]", "Artificial air conductivity for potential extension");
    model.param().set("x_g", "-spacing/2", "Graphite center x coordinate");
    model.param().set("x_al", "spacing/2", "Aluminum center x coordinate");

    model.component().create("comp1", true);
    model.component("comp1").geom().create("geom1", 2);
    model.component("comp1").geom("geom1").lengthUnit("m");
    model.component("comp1").mesh().create("mesh1");

    model.component("comp1").geom("geom1").create("outer", "Circle");
    model.component("comp1").geom("geom1").feature("outer").set("r", "air_rad");
    model.component("comp1").geom("geom1").feature("outer").set("selresult", true);

    model.component("comp1").geom("geom1").create("water", "Circle");
    model.component("comp1").geom("geom1").feature("water").set("r", "water_rad");
    model.component("comp1").geom("geom1").feature("water").set("selresult", true);

    model.component("comp1").geom("geom1").create("graphite", "Circle");
    model.component("comp1").geom("geom1").feature("graphite").set("r", "graphite_diam/2");
    model.component("comp1").geom("geom1").feature("graphite")
        .set("pos", new String[] {"x_g", "0"});
    model.component("comp1").geom("geom1").feature("graphite").set("selresult", true);

    model.component("comp1").geom("geom1").create("aluminum", "Rectangle");
    model.component("comp1").geom("geom1").feature("aluminum")
        .set("size", new String[] {"al_size", "al_size"});
    model.component("comp1").geom("geom1").feature("aluminum").set("base", "center");
    model.component("comp1").geom("geom1").feature("aluminum")
        .set("pos", new String[] {"x_al", "0"});
    model.component("comp1").geom("geom1").feature("aluminum").set("selresult", true);

    model.component("comp1").geom("geom1").create("uni1", "Union");
    model.component("comp1").geom("geom1").feature("uni1").selection("input")
        .set(new String[] {"outer", "water", "graphite", "aluminum"});
    model.component("comp1").geom("geom1").feature("uni1").set("intbnd", true);
    model.component("comp1").geom("geom1").run();

    model.component("comp1").selection().create("selGraphite", "Box");
    model.component("comp1").selection("selGraphite").set("entitydim", 1);
    model.component("comp1").selection("selGraphite").set("xmin", "x_g-0.006[m]");
    model.component("comp1").selection("selGraphite").set("xmax", "x_g+0.006[m]");
    model.component("comp1").selection("selGraphite").set("ymin", "-0.006[m]");
    model.component("comp1").selection("selGraphite").set("ymax", "0.006[m]");
    model.component("comp1").selection("selGraphite").set("condition", "inside");
    model.component("comp1").selection("selGraphite").label("Graphite electrode boundary");

    model.component("comp1").selection().create("selAluminum", "Box");
    model.component("comp1").selection("selAluminum").set("entitydim", 1);
    model.component("comp1").selection("selAluminum").set("xmin", "x_al-al_size/2-0.001[m]");
    model.component("comp1").selection("selAluminum").set("xmax", "x_al+al_size/2+0.001[m]");
    model.component("comp1").selection("selAluminum").set("ymin", "-al_size/2-0.001[m]");
    model.component("comp1").selection("selAluminum").set("ymax", "al_size/2+0.001[m]");
    model.component("comp1").selection("selAluminum").set("condition", "inside");
    model.component("comp1").selection("selAluminum").label("Aluminum electrode boundary");

    model.component("comp1").selection().create("selWaterDomain", "Disk");
    model.component("comp1").selection("selWaterDomain").set("entitydim", 2);
    model.component("comp1").selection("selWaterDomain").set("posx", "0");
    model.component("comp1").selection("selWaterDomain").set("posy", "0");
    model.component("comp1").selection("selWaterDomain").set("r", "water_rad-1e-4[m]");
    model.component("comp1").selection("selWaterDomain").set("condition", "somevertex");
    model.component("comp1").selection("selWaterDomain").label("Water domains for current plot");

    model.component("comp1").physics().create("ec", "ConductiveMedia", "geom1");

    model.component("comp1").material().create("mat1", "Common");
    model.component("comp1").material("mat1").label("Water and air effective conductivity");
    model.component("comp1").material("mat1").propertyGroup("def").set(
        "electricconductivity",
        new String[] {"if(x^2+y^2<water_rad^2,sigma_water,sigma_air)"});
    model.component("comp1").material("mat1").propertyGroup("def").set(
        "relpermittivity", new String[] {"if(x^2+y^2<water_rad^2,80,1)"});

    model.component("comp1").physics("ec").create("term1", "Terminal", 1);
    model.component("comp1").physics("ec").feature("term1").selection().named("selGraphite");
    model.component("comp1").physics("ec").feature("term1").set("I0", "I_2d");
    model.component("comp1").physics("ec").feature("term1").label("10 mA graphite terminal");

    model.component("comp1").physics("ec").create("gnd1", "Ground", 1);
    model.component("comp1").physics("ec").feature("gnd1").selection().named("selAluminum");
    model.component("comp1").physics("ec").feature("gnd1").label("Aluminum reference electrode");

    model.component("comp1").mesh("mesh1").autoMeshSize(3);
    model.component("comp1").mesh("mesh1").run();

    model.study().create("std1");
    model.study("std1").label("Stationary 10 mA discharge");
    model.study("std1").create("stat", "Stationary");
    model.study("std1").createAutoSequences("all");
    model.sol("sol1").runAll();

    model.result().create("pg1", "PlotGroup2D");
    model.result("pg1").label("Electric potential: water and air extension");
    model.result("pg1").set("showlegendsmaxmin", true);
    model.result("pg1").feature().create("surf1", "Surface");
    model.result("pg1").feature("surf1").set("expr", "V");
    model.result("pg1").feature("surf1").set("unit", "V");
    model.result("pg1").feature("surf1").set("colortable", "Dipole");

    model.result().create("pg2", "PlotGroup2D");
    model.result("pg2").label("Current density magnitude");
    model.result("pg2").set("showlegendsmaxmin", true);
    model.result("pg2").feature().create("surf1", "Surface");
    model.result("pg2").feature("surf1").set("expr", "max(ec.normJ,1e-12[A/m^2])");
    model.result("pg2").feature("surf1").set("unit", "A/m^2");
    model.result("pg2").feature("surf1").set("colorscalemode", "logarithmic");
    model.result("pg2").feature("surf1").set("colortable", "ThermalLight");

    model.result().dataset().create("cln1", "CutLine2D");
    model.result().dataset("cln1").label("Electrode centerline");
    model.result().dataset("cln1").set(
        "genpoints", new double[][] {{-5.0, 0.0}, {5.0, 0.0}});

    model.result().create("pg3", "PlotGroup1D");
    model.result("pg3").label("Centerline electric potential");
    model.result("pg3").set("data", "cln1");
    model.result("pg3").feature().create("lngr1", "LineGraph");
    model.result("pg3").feature("lngr1").set("expr", "V");
    model.result("pg3").feature("lngr1").set("unit", "V");

    model.result().create("pg4", "PlotGroup2D");
    model.result("pg4").label("Electric field magnitude in 5 m radius region");
    model.result("pg4").set("showlegendsmaxmin", true);
    model.result("pg4").feature().create("surf1", "Surface");
    model.result("pg4").feature("surf1").set("expr", "max(ec.normE,1e-12[V/m])");
    model.result("pg4").feature("surf1").set("unit", "V/m");
    model.result("pg4").feature("surf1").set("colorscalemode", "logarithmic");
    model.result("pg4").feature("surf1").set("colortable", "SpectrumLight");

    model.result().numerical().create("gev1", "EvalGlobal");
    model.result().numerical("gev1").set(
        "expr", new String[] {"ec.term1.V0_ode", "ec.R11*1[m]/depth"});
    model.result().numerical("gev1").set(
        "descr", new String[] {"Graphite terminal voltage", "Equivalent resistance at total current"});
    model.result().table().create("tbl1", "Table");
    model.result().table("tbl1").label("Terminal voltage and resistance");
    model.result().numerical("gev1").set("table", "tbl1");
    model.result().numerical("gev1").setResult();
    model.result().table("tbl1").save(OUTPUT_DIR + "\\terminal_summary.csv");

    model.result().export().create("data1", "Data");
    model.result().export("data1").set("data", "cln1");
    model.result().export("data1").set("expr", new String[] {"V", "ec.normE", "ec.normJ"});
    model.result().export("data1").set("filename", OUTPUT_DIR + "\\centerline_potential.csv");
    model.result().export("data1").run();

    model.result().export().create("img1", "Image2D");
    model.result().export("img1").set("plotgroup", "pg1");
    model.result().export("img1").set("pngfilename", OUTPUT_DIR + "\\potential_water_air.png");
    model.result().export("img1").set("width", 1200);
    model.result().export("img1").set("height", 900);
    model.result().export("img1").run();

    model.result().export().create("img2", "Image2D");
    model.result().export("img2").set("plotgroup", "pg2");
    model.result().export("img2").set("pngfilename", OUTPUT_DIR + "\\current_density.png");
    model.result().export("img2").set("width", 1200);
    model.result().export("img2").set("height", 900);
    model.result().export("img2").run();

    model.result().export().create("img3", "Image2D");
    model.result().export("img3").set("plotgroup", "pg4");
    model.result().export("img3").set("pngfilename", OUTPUT_DIR + "\\electric_field_air_radius_5m.png");
    model.result().export("img3").set("width", 1200);
    model.result().export("img3").set("height", 900);
    model.result().export("img3").run();

    model.save(OUTPUT_DIR + "\\cathodic_protection_2d.mph");
    return model;
  }

  public static void main(String[] args) throws Exception {
    run();
  }
}
