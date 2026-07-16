import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public class WaterLoopStreamingPotentialV7 {
  private static final String ROOT =
      "C:\\Users\\17584\\Documents\\ALearning\\Project\\tools\\DataProcess\\comsol";
  private static final String MODEL_FILE =
      ROOT + "\\models\\water_loop_streaming_potential_v7.mph";

  public static Model run() throws Exception {
    Model model = ModelUtil.create("Model");
    model.modelPath(ROOT + "\\models");
    model.label("water_loop_streaming_potential_v7.mph");
    model.title("Water Loop Turbulent Flow and Streaming Potential V7");
    model.description(
        "Reduced DN40 equivalent loop using SST turbulent flow and thin-double-layer "
            + "electrokinetic coupling. Default water and zeta-potential values are engineering "
            + "assumptions pending measurement.");

    model.param().set("pipe_length", "2.8[m]", "Equivalent wetted loop length");
    model.param().set("pipe_diam", "40[mm]", "Assumed DN40 hydraulic diameter");
    model.param().set("flow_rate", "6.3[m^3/h]", "Rated volume flow");
    model.param().set("u_mean", "flow_rate/(pi*(pipe_diam/2)^2)", "Mean pipe velocity");
    model.param().set("rho_water", "998.2[kg/m^3]", "Water density at 20 degC");
    model.param().set("mu_water", "1.002e-3[Pa*s]", "Water dynamic viscosity at 20 degC");
    model.param().set("sigma_water", "0.05[S/m]", "Measured 500 uS/cm conductivity");
    model.param().set("epsr_water", "80.2", "Relative permittivity near 20 degC");
    model.param().set("zeta_wall", "-30[mV]", "Baseline PE/rubber-water zeta potential");
    model.param().set("eps_water", "epsilon0_const*epsr_water", "Water permittivity");
    model.param().set("L_stream", "-eps_water*zeta_wall/mu_water",
        "Thin-double-layer streaming-current coefficient");
    model.param().set("C_stream", "eps_water*zeta_wall/(mu_water*sigma_water)",
        "Helmholtz-Smoluchowski voltage-pressure coefficient");
    model.param().set("pump_head", "32[m]", "Nameplate head used only as an upper-bound reference");
    model.param().set("V_stream_head", "C_stream*rho_water*g_const*pump_head",
        "Nameplate-head streaming-potential reference");
    model.param().set("Re_pipe", "rho_water*u_mean*pipe_diam/mu_water", "Pipe Reynolds number");

    model.component().create("comp1", true);
    model.component("comp1").geom().create("geom1", 3);
    model.component("comp1").geom("geom1").lengthUnit("m");
    model.component("comp1").geom("geom1").create("waterPipe", "Cylinder");
    model.component("comp1").geom("geom1").feature("waterPipe").label("Equivalent DN40 water loop");
    model.component("comp1").geom("geom1").feature("waterPipe").set("r", "pipe_diam/2");
    model.component("comp1").geom("geom1").feature("waterPipe").set("h", "pipe_length");
    model.component("comp1").geom("geom1").feature("waterPipe").set("axis", new double[] {1, 0, 0});
    model.component("comp1").geom("geom1").feature("waterPipe").set("selresult", true);
    model.component("comp1").geom("geom1").run();
    System.out.println("V7_STEP=geometry_complete");

    model.component("comp1").material().create("matWater", "Common");
    model.component("comp1").material("matWater").label("Ordinary conductive water at 20 degC");
    model.component("comp1").material("matWater").selection().set(1);
    model.component("comp1").material("matWater").propertyGroup("def")
        .set("density", new String[] {"rho_water"});
    model.component("comp1").material("matWater").propertyGroup("def")
        .set("dynamicviscosity", new String[] {"mu_water"});
    model.component("comp1").material("matWater").propertyGroup("def")
        .set("electricconductivity", new String[] {"sigma_water"});
    model.component("comp1").material("matWater").propertyGroup("def")
        .set("relpermittivity", new String[] {"epsr_water"});
    System.out.println("V7_STEP=material_complete");

    model.component("comp1").physics().create("spf", "TurbulentFlowSST", "geom1");
    model.component("comp1").physics("spf").selection().set(1);
    model.component("comp1").physics("spf").create("inlet", "InletBoundary", 2);
    model.component("comp1").physics("spf").feature("inlet").label("Rated-flow inlet");
    model.component("comp1").physics("spf").feature("inlet").selection().set(1);
    model.component("comp1").physics("spf").feature("inlet").set("BoundaryCondition", "Velocity");
    model.component("comp1").physics("spf").feature("inlet").set("U0in", "u_mean");
    model.component("comp1").physics("spf").create("outlet", "OutletBoundary", 2);
    model.component("comp1").physics("spf").feature("outlet").label("Zero-gauge-pressure outlet");
    model.component("comp1").physics("spf").feature("outlet").selection().set(6);
    model.component("comp1").physics("spf").feature("outlet").set("p0", "0[Pa]");
    System.out.println("V7_STEP=flow_physics_complete");

    model.component("comp1").physics().create("ec", "ConductiveMedia", "geom1");
    model.component("comp1").physics("ec").selection().set(1);
    model.component("comp1").physics("ec").create("streamCurrent", "ExternalCurrentDensity", 3);
    model.component("comp1").physics("ec").feature("streamCurrent")
        .label("Pressure-gradient streaming current");
    model.component("comp1").physics("ec").feature("streamCurrent").selection().set(1);
    model.component("comp1").physics("ec").feature("streamCurrent").set("Je",
        new String[] {"L_stream*d(p,x)", "L_stream*d(p,y)", "L_stream*d(p,z)"});
    model.component("comp1").physics("ec").create("gnd", "Ground", 2);
    model.component("comp1").physics("ec").feature("gnd").label("Potential reference at outlet");
    model.component("comp1").physics("ec").feature("gnd").selection().set(6);
    System.out.println("V7_STEP=electric_physics_complete");

    model.component("comp1").mesh().create("mesh1");
    model.component("comp1").mesh("mesh1").create("ftet1", "FreeTet");
    model.component("comp1").mesh("mesh1").feature("size").set("hauto", 3);
    model.component("comp1").mesh("mesh1").feature("size").set("hmax", "20[mm]");
    model.component("comp1").mesh("mesh1").feature("size").set("hmin", "1.5[mm]");
    System.out.println("V7_STEP=mesh_complete");

    model.study().create("std1");
    model.study("std1").label("Stationary turbulent flow and streaming potential");
    model.study("std1").create("wdi", "WallDistanceInitialization");
    model.study("std1").create("stat", "Stationary");
    model.study("std1").feature("stat").set("activate", new String[] {"spf", "on", "ec", "on"});
    System.out.println("V7_STEP=study_complete");

    model.save(MODEL_FILE);
    return model;
  }

  public static void main(String[] args) throws Exception {
    run();
  }
}
