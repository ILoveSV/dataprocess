/*
 * water_tank_model.java
 */

import com.comsol.model.*;
import com.comsol.model.util.*;

/** Model exported on Jul 15 2026, 18:50 by COMSOL 6.4.0.293. */
public class water_tank_model {

  public static Model run() {
    Model model = ModelUtil.create("Model");

    model.modelPath("D:\\COMSOL64\\Multiphysics\\data");

    model.component().create("comp1", true);

    model.component("comp1").geom().create("geom1", 2);

    model.component("comp1").mesh().create("mesh1");

    model.component("comp1").geom("geom1").lengthUnit("mm");
    model.component("comp1").geom("geom1").create("r1", "Rectangle");
    model.component("comp1").geom("geom1").feature("r1").set("size", new double[]{1, 0.65});
    model.component("comp1").geom("geom1").feature("r1").set("pos", new double[]{0, 0});
    model.component("comp1").geom("geom1").run("r1");
    model.component("comp1").geom("geom1").feature("r1").set("size", new String[]{"560/2", "0.65"});
    model.component("comp1").geom("geom1").run("r1");
    model.component("comp1").geom("geom1").feature("r1").set("size", new String[]{"560/2", "870"});
    model.component("comp1").geom("geom1").run("r1");
    model.component("comp1").geom("geom1").create("r2", "Rectangle");
    model.component("comp1").geom("geom1").feature("r2").set("size", new double[]{100, 70});
    model.component("comp1").geom("geom1").feature("r2").set("pos", new double[]{0, 870});
    model.component("comp1").geom("geom1").run("r2");
    model.component("comp1").geom("geom1").create("pol1", "Polygon");
    model.component("comp1").geom("geom1").feature("pol1").set("source", "table");
    model.component("comp1").geom("geom1").feature("pol1")
         .set("table", new double[][]{{100, 940}, {100, 870}, {280, 870}, {100, 940}});
    model.component("comp1").geom("geom1").run("pol1");
    model.component("comp1").geom("geom1").create("uni1", "Union");
    model.component("comp1").geom("geom1").feature("uni1").selection("input").set("pol1", "r1", "r2");
    model.component("comp1").geom("geom1").feature("uni1").set("intbnd", false);
    model.component("comp1").geom("geom1").run("uni1");
    model.component("comp1").geom("geom1").run("pol1");
    model.component("comp1").geom("geom1").feature("pol1")
         .set("table", new double[][]{{100, 921.0994296603725}, {100, 870}, {231.39853341240337, 870}, {100, 921.0994296603725}});
    model.component("comp1").geom("geom1").run("pol1");
    model.component("comp1").geom("geom1").feature("pol1")
         .set("table", new double[][]{{100, 921.0994296603725}, {100, 870}, {280, 870}, {100, 921.0994296603725}});
    model.component("comp1").geom("geom1").run("pol1");
    model.component("comp1").geom("geom1").feature("pol1")
         .set("table", new double[][]{{100, 910}, {100, 870}, {280, 870}, {100, 910}});
    model.component("comp1").geom("geom1").run("pol1");
    model.component("comp1").geom("geom1").run("uni1");
    model.component("comp1").geom("geom1").runPre("uni1");
    model.component("comp1").geom("geom1").run("uni1");
    model.component("comp1").geom("geom1").run();
    model.component("comp1").geom("geom1").feature("r1").set("size", new String[]{"560/2", "870"});
    model.component("comp1").geom("geom1").run("r1");
    model.component("comp1").geom("geom1").runPre("fin");
    model.component("comp1").geom("geom1").create("mir1", "Mirror");
    model.component("comp1").geom("geom1").feature("mir1").selection("input").set("uni1");
    model.component("comp1").geom("geom1").run("mir1");
    model.component("comp1").geom("geom1").feature("mir1").set("keep", true);
    model.component("comp1").geom("geom1").run("mir1");
    model.component("comp1").geom("geom1").create("uni2", "Union");
    model.component("comp1").geom("geom1").feature("uni2").selection("input").set("mir1", "uni1");
    model.component("comp1").geom("geom1").feature("uni2").set("intbnd", false);
    model.component("comp1").geom("geom1").run("uni2");

    model.component("comp1").view("view1").set("showgrid", true);

    model.component("comp1").geom("geom1").runPre("uni2");
    model.component("comp1").geom("geom1").run("uni2");
    model.component("comp1").geom("geom1").create("r3", "Rectangle");
    model.component("comp1").geom("geom1").feature("r3").set("size", new double[]{800, 80});
    model.component("comp1").geom("geom1").feature("r3").set("pos", new double[]{280, 40});
    model.component("comp1").geom("geom1").run("r3");
    model.component("comp1").geom("geom1").feature("r3").set("size", new double[]{800, 50});
    model.component("comp1").geom("geom1").run("r3");
    model.component("comp1").geom("geom1").feature("r3").set("size", new double[]{540, 50});
    model.component("comp1").geom("geom1").run("r3");
    model.component("comp1").geom("geom1").run();
    model.component("comp1").geom("geom1").create("r4", "Rectangle");
    model.component("comp1").geom("geom1").feature("r4").set("size", new double[]{560, 660});
    model.component("comp1").geom("geom1").feature("r4").set("pos", new double[]{-280, 0});
    model.component("comp1").geom("geom1").run("r4");
    model.component("comp1").geom("geom1").run();

    model.component("comp1").physics().create("spf", "LaminarFlow", "geom1");
    model.component("comp1").physics().remove("spf");
    model.component("comp1").physics().create("temw", "TransientElectromagneticWaves", "geom1");
    model.component("comp1").physics("temw").create("epd1", "ElectricPointDipole", 0);
    model.component("comp1").physics("temw").feature("epd1").set("DipoleSpecification", "DipoleMoment");
    model.component("comp1").physics("temw").feature("epd1")
         .set("pI", new String[]{"p0_src*src_dir_x*exp(-((t-t0_src)/tau_src)^2)", "p0_src*src_dir_y*exp(-((t-t0_src)/tau_src)^2)", "0"});

    model.param().set("src_dir_x", "0");
    model.param().descr("src_dir_x", "\u6e90\u65b9\u5411 x \u5206\u91cf");
    model.param().set("src_dir_y", "1");
    model.param().descr("src_dir_y", "\u6e90\u65b9\u5411 y \u5206\u91cf\uff0c\u5f84\u5411\u6fc0\u52b1");
    model.param().set("src_dir_z", "0");
    model.param().descr("src_dir_z", "\u6e90\u65b9\u5411 z \u5206\u91cf");
    model.param().set("t0_src", "1[ns]");
    model.param().descr("t0_src", "PD \u9ad8\u65af\u8109\u51b2\u4e2d\u5fc3\u65f6\u95f4");
    model.param().set("tau_src", "0.3[ns]");
    model.param().descr("tau_src", "PD \u9ad8\u65af\u8109\u51b2\u5bbd\u5ea6");
    model.param().set("p0_src", "1e-3[A*m]");
    model.param()
         .descr("p0_src", "PD \u70b9\u6e90\u7535\u6d41\u5076\u6781\u77e9\u5e45\u503c\uff0c\u5f52\u4e00\u5316\u6e90\u5f3a");
    model.param().remove("src_dir_z");

    model.component("comp1").geom("geom1").create("pt1", "Point");
    model.component("comp1").geom("geom1").feature("pt1").set("p", new double[]{550, 65});
    model.component("comp1").geom("geom1").run("pt1");
    model.component("comp1").geom("geom1").run();

    model.component("comp1").physics("temw").feature("epd1").selection().set(15);

    model.component("comp1").material().create("mat1", "Common");
    model.component("comp1").material("mat1").label("mat_transformer_oil");
    model.component("comp1").material("mat1").propertyGroup("def")
         .set("relpermittivity", new String[]{"epsr_oil", "0", "0", "0", "epsr_oil", "0", "0", "0", "epsr_oil"});
    model.component("comp1").material("mat1").propertyGroup("def")
         .set("relpermeability", new String[]{"1", "0", "0", "0", "1", "0", "0", "0", "1"});
    model.component("comp1").material("mat1").propertyGroup("def")
         .set("electricconductivity", new String[]{"sigma_oil", "0", "0", "0", "sigma_oil", "0", "0", "0", "sigma_oil"});
    model.component("comp1").material("mat1").propertyGroup("def").featureInfo().create("info");
    model.component("comp1").material("mat1").propertyGroup("def").set("relpermittivity", new String[]{"80"});
    model.component("comp1").material("mat1").propertyGroup("def")
         .set("electricconductivity", new String[]{"500[uS/cm]"});
    model.component("comp1").material("mat1").label("\u6c34");

    model.component("comp1").physics("temw").prop("MeshControl").set("SizeControlParameter", "Frequency");
    model.component("comp1").physics("temw").prop("MeshControl").set("PhysicsControlledMeshMaximumFrequency", 50);

    model.component("comp1").mesh("mesh1").run();
    model.component("comp1").mesh("mesh1").automatic(false);
    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 1);
    model.component("comp1").mesh("mesh1").run("size");
    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 10);
    model.component("comp1").mesh("mesh1").run();
    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 100);
    model.component("comp1").mesh("mesh1").run();
    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 20);
    model.component("comp1").mesh("mesh1").run();
    model.component("comp1").mesh("mesh1").feature("size").set("hmin", 0.5);
    model.component("comp1").mesh("mesh1").run("size");
    model.component("comp1").mesh("mesh1").run();

    model.study().create("std1");
    model.study("std1").create("time", "Transient");
    model.study("std1").feature("time").set("tlist", "range(0,0.1[ns],5[ns])");
    model.study("std1").createAutoSequences("sol");
    model.study("std1").createAutoSequences("jobs");

    model.sol("sol1").runFromTo("st1", "v1");

    model.result().create("pg1", "PlotGroup2D");
    model.result("pg1").set("smooth", "internal");
    model.result("pg1").feature().create("surf1", "Surface");
    model.result("pg1").feature("surf1").set("smooth", "internal");
    model.result("pg1").feature("surf1").set("data", "parent");
    model.result("pg1").run();
    model.result("pg1").run();
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("expr", "log10(temw.normE/(1[V/m])+1)");
    model.result("pg1").run();

    model.study("std1").feature("time").set("plot", true);
    model.study("std1").feature("time").set("plotfreq", "tsteps");
    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();

    model.study("std1").feature("time").set("tlist", "range(0,0.1[ns],50[ns])");
    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result("pg1").run();
    model.result("pg1").run();

    model.component("comp1").physics("temw").create("lport1", "LumpedPort", 1);
    model.component("comp1").physics("temw").feature("lport1").selection().set(18);
    model.component("comp1").physics("temw").feature("lport1").set("PortType", "Uniform");

    model.component("comp1").view("view1").set("showDirections", false);

    model.component("comp1").physics("temw").feature("lport1")
         .set("TransientVoltagePulseType", "ModulatedGaussianPulse");
    model.component("comp1").physics("temw").feature("epd1").active(false);
    model.component("comp1").physics("temw").feature("lport1").set("f0", "50[Hz]");

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();

    model.component("comp1").physics("temw").feature("lport1").set("f0", "50[GHz]");

    model.study("std1").createAutoSequences("all");

    model.component("comp1").physics("temw").feature("lport1").set("f0", "50[Hz]");

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();

    model.study("std1").feature("time").set("tlist", "range(0,1[ns],500[ns])");
    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();

    model.component("comp1").physics("temw").feature("lport1").set("fmodShiftRatio", "30[%]");

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("expr", "temw.normE");
    model.result("pg1").run();

    model.component("comp1").physics("temw").feature("lport1").set("TerminalType", "Current");
    model.component("comp1").physics("temw").feature("lport1").set("CurrentPulseType", "ElectrostaticDischarge");
    model.component("comp1").physics("temw").feature("lport1")
         .set("ElectrostaticDischargePulseModel", "ChargedDeviceModel");
    model.component("comp1").physics("temw").feature("lport1").set("CurrentPulseType", "UserDefined");
    model.component("comp1").physics("temw").feature("lport1").set("TerminalType", "Cable");
    model.component("comp1").physics("temw").feature("lport1").set("f0", "500[Hz]");

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();

    model.component("comp1").physics("temw").feature("lport1").set("f0", "5000[Hz]");

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("expr", "log10(temw.normE/(1[V/m])+1)");
    model.result("pg1").run();

    model.component("comp1").physics("temw").feature("lport1").set("TransientVoltagePulseType", "UserDefined");
    model.component("comp1").physics("temw").feature("lport1").set("PortType", "UserDefined");

    model.component("comp1").view("view1").set("showDirections", false);

    model.component("comp1").physics("temw").feature().remove("lport1");
    model.component("comp1").physics("temw").feature("epd1").active(true);

    model.component("comp1").geom("geom1").feature("r3").set("size", new double[]{270, 50});
    model.component("comp1").geom("geom1").run("pt1");
    model.component("comp1").geom("geom1").run();

    model.component("comp1").mesh("mesh1").run();
    model.component("comp1").mesh("mesh1").run();

    model.study("std1").feature("time").set("tlist", "range(0,0.1[ns],500[ns])");
    model.study("std1").createAutoSequences("all");

    model.component("comp1").geom("geom1").feature("r3").set("size", new double[]{320, 50});
    model.component("comp1").geom("geom1").run("pt1");

    model.study("std1").createAutoSequences("all");
    model.study("std1").feature("time").set("tlist", "range(0,0.1[ns],50[ns])");
    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();

    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 10);
    model.component("comp1").mesh("mesh1").run("size");
    model.component("comp1").mesh("mesh1").run();

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("colortabletrans", "nonlinear");
    model.result("pg1").feature("surf1").set("colorcalibration", -1.5);
    model.result("pg1").feature("surf1").set("expr", "log10(temw.normE/(1[V/m]))");
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepFirst(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("colorcalibration", 0);
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepLast(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("expr", "log10(temw.normE/(1[V/m])+1)");
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("expr", "log10(temw.normE/(1[V/m])+0.8)");
    model.result("pg1").run();
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("expr", "log10(temw.normE/(1[V/m])+1)");
    model.result("pg1").run();
    model.result("pg1").run();

    model.component("comp1").geom("geom1").create("c1", "Circle");
    model.component("comp1").geom("geom1").feature("c1").set("r", 6000);
    model.component("comp1").geom("geom1").feature("c1").set("pos", new double[]{0, 0});
    model.component("comp1").geom("geom1").run("c1");
    model.component("comp1").geom("geom1").feature("c1").set("angle", 180);
    model.component("comp1").geom("geom1").run("c1");
    model.component("comp1").geom("geom1").run("c1");
    model.component("comp1").geom("geom1").run();

    model.component("comp1").material().create("mat2", "Common");
    model.component("comp1").material("mat2").propertyGroup("def").func().create("eta", "Piecewise");
    model.component("comp1").material("mat2").propertyGroup("def").func().create("Cp", "Piecewise");
    model.component("comp1").material("mat2").propertyGroup("def").func().create("rho", "Analytic");
    model.component("comp1").material("mat2").propertyGroup("def").func().create("k", "Piecewise");
    model.component("comp1").material("mat2").propertyGroup("def").func().create("cs", "Analytic");
    model.component("comp1").material("mat2").propertyGroup("def").func().create("an1", "Analytic");
    model.component("comp1").material("mat2").propertyGroup("def").func().create("an2", "Analytic");
    model.component("comp1").material("mat2").propertyGroup()
         .create("RefractiveIndex", "RefractiveIndex", "Refractive index");
    model.component("comp1").material("mat2").propertyGroup()
         .create("NonlinearModel", "NonlinearModel", "Nonlinear model");
    model.component("comp1").material("mat2").propertyGroup().create("idealGas", "idealGas", "Ideal gas");
    model.component("comp1").material("mat2").propertyGroup("idealGas").func().create("Cp", "Piecewise");
    model.component("comp1").material("mat2").label("Air");
    model.component("comp1").material("mat2").set("family", "air");
    model.component("comp1").material("mat2").propertyGroup("def").label("Basic");
    model.component("comp1").material("mat2").propertyGroup("def").func("eta").label("Piecewise");
    model.component("comp1").material("mat2").propertyGroup("def").func("eta").set("arg", "T");
    model.component("comp1").material("mat2").propertyGroup("def").func("eta")
         .set("pieces", new String[][]{{"200.0", "1600.0", "-8.38278E-7+8.35717342E-8*T^1-7.69429583E-11*T^2+4.6437266E-14*T^3-1.06585607E-17*T^4"}});
    model.component("comp1").material("mat2").propertyGroup("def").func("eta").set("argunit", "K");
    model.component("comp1").material("mat2").propertyGroup("def").func("eta").set("fununit", "Pa*s");
    model.component("comp1").material("mat2").propertyGroup("def").func("Cp").label("Piecewise 2");
    model.component("comp1").material("mat2").propertyGroup("def").func("Cp").set("arg", "T");
    model.component("comp1").material("mat2").propertyGroup("def").func("Cp")
         .set("pieces", new String[][]{{"200.0", "1600.0", "1047.63657-0.372589265*T^1+9.45304214E-4*T^2-6.02409443E-7*T^3+1.2858961E-10*T^4"}});
    model.component("comp1").material("mat2").propertyGroup("def").func("Cp").set("argunit", "K");
    model.component("comp1").material("mat2").propertyGroup("def").func("Cp").set("fununit", "J/(kg*K)");
    model.component("comp1").material("mat2").propertyGroup("def").func("rho").label("Analytic");
    model.component("comp1").material("mat2").propertyGroup("def").func("rho")
         .set("expr", "pA*0.02897/R_const[K*mol/J]/T");
    model.component("comp1").material("mat2").propertyGroup("def").func("rho").set("args", new String[]{"pA", "T"});
    model.component("comp1").material("mat2").propertyGroup("def").func("rho").set("fununit", "kg/m^3");
    model.component("comp1").material("mat2").propertyGroup("def").func("rho")
         .set("argunit", new String[]{"Pa", "K"});
    model.component("comp1").material("mat2").propertyGroup("def").func("rho")
         .set("plotaxis", new String[]{"off", "on"});
    model.component("comp1").material("mat2").propertyGroup("def").func("rho")
         .set("plotfixedvalue", new String[]{"101325", "273.15"});
    model.component("comp1").material("mat2").propertyGroup("def").func("rho")
         .set("plotargs", new String[][]{{"pA", "101325", "101325"}, {"T", "273.15", "293.15"}});
    model.component("comp1").material("mat2").propertyGroup("def").func("k").label("Piecewise 3");
    model.component("comp1").material("mat2").propertyGroup("def").func("k").set("arg", "T");
    model.component("comp1").material("mat2").propertyGroup("def").func("k")
         .set("pieces", new String[][]{{"200.0", "1600.0", "-0.00227583562+1.15480022E-4*T^1-7.90252856E-8*T^2+4.11702505E-11*T^3-7.43864331E-15*T^4"}});
    model.component("comp1").material("mat2").propertyGroup("def").func("k").set("argunit", "K");
    model.component("comp1").material("mat2").propertyGroup("def").func("k").set("fununit", "W/(m*K)");
    model.component("comp1").material("mat2").propertyGroup("def").func("cs").label("Analytic 2");
    model.component("comp1").material("mat2").propertyGroup("def").func("cs")
         .set("expr", "sqrt(1.4*R_const[K*mol/J]/0.02897*T)");
    model.component("comp1").material("mat2").propertyGroup("def").func("cs").set("args", new String[]{"T"});
    model.component("comp1").material("mat2").propertyGroup("def").func("cs").set("fununit", "m/s");
    model.component("comp1").material("mat2").propertyGroup("def").func("cs").set("argunit", new String[]{"K"});
    model.component("comp1").material("mat2").propertyGroup("def").func("cs")
         .set("plotfixedvalue", new String[]{"273.15"});
    model.component("comp1").material("mat2").propertyGroup("def").func("cs")
         .set("plotargs", new String[][]{{"T", "273.15", "373.15"}});
    model.component("comp1").material("mat2").propertyGroup("def").func("an1").label("Analytic 1");
    model.component("comp1").material("mat2").propertyGroup("def").func("an1").set("funcname", "alpha_p");
    model.component("comp1").material("mat2").propertyGroup("def").func("an1")
         .set("expr", "-1/rho(pA,T)*d(rho(pA,T),T)");
    model.component("comp1").material("mat2").propertyGroup("def").func("an1").set("args", new String[]{"pA", "T"});
    model.component("comp1").material("mat2").propertyGroup("def").func("an1").set("fununit", "1/K");
    model.component("comp1").material("mat2").propertyGroup("def").func("an1")
         .set("argunit", new String[]{"Pa", "K"});
    model.component("comp1").material("mat2").propertyGroup("def").func("an1")
         .set("plotaxis", new String[]{"off", "on"});
    model.component("comp1").material("mat2").propertyGroup("def").func("an1")
         .set("plotfixedvalue", new String[]{"101325", "273.15"});
    model.component("comp1").material("mat2").propertyGroup("def").func("an1")
         .set("plotargs", new String[][]{{"pA", "101325", "101325"}, {"T", "273.15", "373.15"}});
    model.component("comp1").material("mat2").propertyGroup("def").func("an2").label("Analytic 2a");
    model.component("comp1").material("mat2").propertyGroup("def").func("an2").set("funcname", "muB");
    model.component("comp1").material("mat2").propertyGroup("def").func("an2").set("expr", "0.6*eta(T)");
    model.component("comp1").material("mat2").propertyGroup("def").func("an2").set("args", new String[]{"T"});
    model.component("comp1").material("mat2").propertyGroup("def").func("an2").set("fununit", "Pa*s");
    model.component("comp1").material("mat2").propertyGroup("def").func("an2").set("argunit", new String[]{"K"});
    model.component("comp1").material("mat2").propertyGroup("def").func("an2")
         .set("plotfixedvalue", new String[]{"200"});
    model.component("comp1").material("mat2").propertyGroup("def").func("an2")
         .set("plotargs", new String[][]{{"T", "200", "1600"}});
    model.component("comp1").material("mat2").propertyGroup("def").set("thermalexpansioncoefficient", "");
    model.component("comp1").material("mat2").propertyGroup("def").set("molarmass", "");
    model.component("comp1").material("mat2").propertyGroup("def").set("bulkviscosity", "");
    model.component("comp1").material("mat2").propertyGroup("def")
         .set("thermalexpansioncoefficient", new String[]{"alpha_p(pA,T)", "0", "0", "0", "alpha_p(pA,T)", "0", "0", "0", "alpha_p(pA,T)"});
    model.component("comp1").material("mat2").propertyGroup("def").set("molarmass", "0.02897[kg/mol]");
    model.component("comp1").material("mat2").propertyGroup("def").set("bulkviscosity", "muB(T)");
    model.component("comp1").material("mat2").propertyGroup("def")
         .set("relpermeability", new String[]{"1", "0", "0", "0", "1", "0", "0", "0", "1"});
    model.component("comp1").material("mat2").propertyGroup("def")
         .set("relpermittivity", new String[]{"1", "0", "0", "0", "1", "0", "0", "0", "1"});
    model.component("comp1").material("mat2").propertyGroup("def").set("dynamicviscosity", "eta(T)");
    model.component("comp1").material("mat2").propertyGroup("def").set("ratioofspecificheat", "1.4");
    model.component("comp1").material("mat2").propertyGroup("def")
         .set("electricconductivity", new String[]{"0[S/m]", "0", "0", "0", "0[S/m]", "0", "0", "0", "0[S/m]"});
    model.component("comp1").material("mat2").propertyGroup("def").set("heatcapacity", "Cp(T)");
    model.component("comp1").material("mat2").propertyGroup("def").set("density", "rho(pA,T)");
    model.component("comp1").material("mat2").propertyGroup("def")
         .set("thermalconductivity", new String[]{"k(T)", "0", "0", "0", "k(T)", "0", "0", "0", "k(T)"});
    model.component("comp1").material("mat2").propertyGroup("def").set("soundspeed", "cs(T)");
    model.component("comp1").material("mat2").propertyGroup("def").addInput("temperature");
    model.component("comp1").material("mat2").propertyGroup("def").addInput("pressure");
    model.component("comp1").material("mat2").propertyGroup("RefractiveIndex").label("Refractive index");
    model.component("comp1").material("mat2").propertyGroup("RefractiveIndex")
         .set("n", new String[]{"1", "0", "0", "0", "1", "0", "0", "0", "1"});
    model.component("comp1").material("mat2").propertyGroup("NonlinearModel").label("Nonlinear model");
    model.component("comp1").material("mat2").propertyGroup("NonlinearModel").set("BA", "def.gamma-1");
    model.component("comp1").material("mat2").propertyGroup("idealGas").label("Ideal gas");
    model.component("comp1").material("mat2").propertyGroup("idealGas").func("Cp").label("Piecewise 2");
    model.component("comp1").material("mat2").propertyGroup("idealGas").func("Cp").set("arg", "T");
    model.component("comp1").material("mat2").propertyGroup("idealGas").func("Cp")
         .set("pieces", new String[][]{{"200.0", "1600.0", "1047.63657-0.372589265*T^1+9.45304214E-4*T^2-6.02409443E-7*T^3+1.2858961E-10*T^4"}});
    model.component("comp1").material("mat2").propertyGroup("idealGas").func("Cp").set("argunit", "K");
    model.component("comp1").material("mat2").propertyGroup("idealGas").func("Cp").set("fununit", "J/(kg*K)");
    model.component("comp1").material("mat2").propertyGroup("idealGas").set("Rs", "R_const/Mn");
    model.component("comp1").material("mat2").propertyGroup("idealGas").set("heatcapacity", "Cp(T)");
    model.component("comp1").material("mat2").propertyGroup("idealGas").set("ratioofspecificheat", "1.4");
    model.component("comp1").material("mat2").propertyGroup("idealGas").set("molarmass", "0.02897[kg/mol]");
    model.component("comp1").material("mat2").propertyGroup("idealGas").addInput("temperature");
    model.component("comp1").material("mat2").propertyGroup("idealGas").addInput("pressure");
    model.component("comp1").material("mat2").materialType("nonSolid");
    model.component("comp1").material("mat2").selection().set(1);

    model.component("comp1").mesh("mesh1").run("size");
    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 100);
    model.component("comp1").mesh("mesh1").run("size");
    model.component("comp1").mesh("mesh1").run();

    model.component("comp1").material("mat2").selection().set(1, 3);
    model.component("comp1").material("mat1").selection().set(2, 4);

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result("pg1").run();

    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 50);

    return model;
  }

  public static Model run2(Model model) {
    model.component("comp1").mesh("mesh1").run();

    model.component("comp1").physics("temw").create("pec2", "PerfectElectricConductor", 1);
    model.component("comp1").physics("temw").feature("pec2").selection()
         .set(2, 4, 6, 7, 8, 10, 12, 13, 16, 17, 18, 19, 20);

    model.component("comp1").geom("geom1").create("uni3", "Union");
    model.component("comp1").geom("geom1").feature("uni3").selection("input").set("r3", "r4");
    model.component("comp1").geom("geom1").feature("uni3").set("intbnd", false);
    model.component("comp1").geom("geom1").run("uni3");
    model.component("comp1").geom("geom1").feature().move("uni3", 9);
    model.component("comp1").geom("geom1").run("uni3");
    model.component("comp1").geom("geom1").runPre("uni3");
    model.component("comp1").geom("geom1").run("uni3");
    model.component("comp1").geom("geom1").run("uni3");
    model.component("comp1").geom("geom1").feature().remove("uni3");
    model.component("comp1").geom("geom1").runPre("fin");
    model.component("comp1").geom("geom1").run();

    model.component("comp1").physics("temw").feature("pec2").selection()
         .set(2, 4, 6, 7, 8, 10, 11, 12, 13, 16, 17, 18, 19, 20);

    model.component("comp1").mesh("mesh1").run();
    model.component("comp1").mesh("mesh1").run();

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("colorcalibration", -1.5);
    model.result().table().create("evl2", "Table");
    model.result().table("evl2").comments("\u4ea4\u4e92\u7684\u4e8c\u7ef4\u503c");
    model.result().table("evl2").label("Evaluation 2D");
    model.result().table("evl2").setColumnHeaders(new String[]{"x", "y", "Value"});
    model.result().table("evl2")
         .addRow(new double[]{429.60974121093756, 912.383056640625, 0}, new double[]{0, 0, 0});
    model.result().table("evl2").setColumnHeaders(new String[]{"x", "y", "Value"});
    model.result().table("evl2")
         .addRow(new double[]{632.1447143554688, 793.5037231445312, 0}, new double[]{0, 0, 0});

    model.component("comp1").physics("temw").feature("pec2").selection()
         .set(2, 4, 6, 7, 11, 12, 13, 16, 17, 18, 19, 20);

    model.result("pg1").run();
    model.result("pg1").run();

    model.study("std1").feature("time").set("tlist", "range(0,1[ns],500[ns])");
    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result().table("evl2").setColumnHeaders(new String[]{"x", "y", "Value"});
    model.result().table("evl2")
         .addRow(new double[]{2697.5458984375, 1322.2017822265625, 6.9762627604729426E-6}, new double[]{0, 0, 0});
    model.result().dataset().create("cpt1", "CutPoint2D");
    model.result().dataset("cpt1").set("pointx", 1000);
    model.result().dataset("cpt1").set("pointy", 2000);
    model.result().create("pg2", "PlotGroup1D");
    model.result("pg2").run();
    model.result("pg2").create("ptgr1", "PointGraph");
    model.result("pg2").feature("ptgr1").set("markerpos", "datapoints");
    model.result("pg2").feature("ptgr1").set("linewidth", "preference");
    model.result("pg2").set("data", "cpt1");
    model.result("pg2").run();
    model.result("pg2").run();
    model.result("pg2").feature("ptgr1").set("expr", "log10(temw.normE/(1[V/m])+1)");
    model.result("pg2").run();
    model.result("pg2").feature("ptgr1").set("expr", "log10(temw.Ex/(1[V/m])+1)");
    model.result("pg2").run();
    model.result("pg2").run();

    model.component("comp1").physics("temw").feature().remove("pec2");

    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 100);
    model.component("comp1").mesh("mesh1").run();

    model.sol("sol1").clearSolutionData();

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result("pg2").run();

    model.study("std1").feature("time").set("tlist", "range(0,0.1[ns],50[ns])");
    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result("pg2").run();

    model.study("std1").feature("time").set("tlist", "range(0,0.01[ns],100[ns])");
    model.study("std1").createAutoSequences("all");

    model.result("pg2").run();

    model.study("std1").feature("time").set("tlist", "range(0,0.1[ns],100[ns])");

    model.param().set("p0_src", "1e2[A*m]");

    model.sol("sol1").clearSolutionData();

    model.param().set("src_dir_y", "0");
    model.param().set("src_dir_x", "-1");

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result("pg2").run();
    model.result("pg1").run();
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("expr", "log10(temw.normE/(1[V/m]))");
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepFirst(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("expr", "log10(temw.normE/(1[V/m])+10)");
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg2").run();
    model.result("pg2").feature("ptgr1").set("expr", "log10(temw.Ex/(1[V/m])+10)");
    model.result("pg2").run();
    model.result("pg2").set("ylog", false);
    model.result("pg2").set("xlog", false);
    model.result("pg2").run();
    model.result("pg1").run();
    model.result().dataset("cpt1").set("pointy", "2000 3000 5000");
    model.result("pg2").run();

    model.component("comp1").physics("temw").create("pec2", "PerfectElectricConductor", 1);
    model.component("comp1").physics("temw").feature("pec2").selection().set(16, 18, 20);

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result("pg2").run();

    model.component("comp1").physics("temw").feature("pec2").selection().set(1, 3, 9, 14);

    model.component("comp1").mesh("mesh1").run();
    model.component("comp1").mesh("mesh1").run();

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result("pg2").run();

    model.param().set("f0", "50[Hz]");
    model.param().set("T0", "1/f0");
    model.param().set("tau_src", "T0");
    model.param().set("t0_src", "T0*3");

    model.study("std1").feature("time").set("tlist", "range(0,T0/50,10*T0)");
    model.study("std1").createAutoSequences("all");
    model.study("std1").feature("time").set("tlist", "range(0,T0/2,10*T0)");
    model.study("std1").createAutoSequences("all");

    model.result("pg1").run();

    model.component("comp1").physics("temw").feature("epd1")
         .set("pI", new String[]{"p0_src*src_dir_x*sin(2*pi*f0*t)", "0", "0"});

    model.study("std1").createAutoSequences("all");

    model.result("pg2").run();
    model.result("pg1").run();
    model.result("pg2").run();

    model.sol("sol1").clearSolutionData();

    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 200);
    model.component("comp1").mesh("mesh1").run();

    model.study("std1").createAutoSequences("all");

    model.result("pg1").run();

    model.param().remove("f0");
    model.param().remove("T0");
    model.param().set("t0_src", "1[ns]");
    model.param().set("tau_src", "0.3[ns]");

    model.component("comp1").physics("temw").feature("epd1")
         .set("pI", new String[]{"p0_src*src_dir_x*exp(-((t-t0_src)/tau_src)^2)", "p0_src*src_dir_y*exp(-((t-t0_src)/tau_src)^2)", "0"});

    model.study("std1").feature("time").set("tlist", "range(0,0.1[ns],100[ns])");
    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();

    model.component("comp1").physics("temw").feature("pec2").selection().set(1, 3, 9, 14, 16);

    model.component("comp1").geom("geom1").create("r5", "Rectangle");
    model.component("comp1").geom("geom1").feature("r5").set("size", new double[]{70, 70});
    model.component("comp1").geom("geom1").feature("r5").set("pos", new double[]{600, 20});
    model.component("comp1").geom("geom1").run("r5");
    model.component("comp1").geom("geom1").feature("r5").set("size", new double[]{70, 110});
    model.component("comp1").geom("geom1").run("r5");
    model.component("comp1").geom("geom1").feature("r5").set("size", new double[]{120, 110});
    model.component("comp1").geom("geom1").run("r5");
    model.component("comp1").geom("geom1").feature("pt1").set("p", new double[][]{{660}, {75}});
    model.component("comp1").geom("geom1").run("r5");
    model.component("comp1").geom("geom1").feature("r5").set("size", new double[]{120, 120});
    model.component("comp1").geom("geom1").feature("r5").set("pos", new double[]{600, 10});
    model.component("comp1").geom("geom1").run("r5");
    model.component("comp1").geom("geom1").feature("r5").set("size", new double[]{120, 100});
    model.component("comp1").geom("geom1").run("r5");
    model.component("comp1").geom("geom1").feature("r5").set("size", new double[]{120, 90});
    model.component("comp1").geom("geom1").feature("r5").set("pos", new double[]{600, 20});
    model.component("comp1").geom("geom1").run("r5");
    model.component("comp1").geom("geom1").run();

    model.component("comp1").material("mat2").selection().set(1, 3);

    model.component("comp1").geom("geom1").feature("pt1").set("p", new double[][]{{660}, {65}});
    model.component("comp1").geom("geom1").run("r5");
    model.component("comp1").geom("geom1").run();

    model.component("comp1").physics("temw").feature("pec2").selection()
         .set(1, 2, 3, 4, 6, 7, 9, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21);

    model.study("std1").createAutoSequences("all");

    model.component("comp1").material("mat1").selection().set(2, 4);
    model.component("comp1").material("mat2").selection().set(1, 3, 5);

    model.component("comp1").mesh("mesh1").run();

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result("pg2").run();
    model.result("pg1").run();

    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 150);
    model.component("comp1").mesh("mesh1").run();

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();

    model.param().descr("tau_src", "");
    model.param().descr("t0_src", "");

    model.result("pg2").run();
    model.result("pg1").run();
    model.result("pg2").run();
    model.result("pg2").run();
    model.result("pg1").run();
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("expr", "log10(temw.Ex/(1[V/m])+10)");
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepFirst(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepLast(0);
    model.result("pg1").run();
    model.result().export().create("anim1", "Animation");
    model.result().export("anim1").set("target", "player");
    model.result().export("anim1").set("fontsize", "9");
    model.result().export("anim1").set("colortheme", "globaltheme");
    model.result().export("anim1").set("customcolor", new double[]{1, 1, 1});
    model.result().export("anim1").set("background", "color");
    model.result().export("anim1").set("gltfincludelines", "on");
    model.result().export("anim1").set("title1d", "on");
    model.result().export("anim1").set("legend1d", "on");
    model.result().export("anim1").set("logo1d", "on");

    return model;
  }

  public static Model run3(Model model) {
    model.result().export("anim1").set("options1d", "on");
    model.result().export("anim1").set("title2d", "on");
    model.result().export("anim1").set("legend2d", "on");
    model.result().export("anim1").set("logo2d", "on");
    model.result().export("anim1").set("options2d", "on");
    model.result().export("anim1").set("title3d", "on");
    model.result().export("anim1").set("legend3d", "on");
    model.result().export("anim1").set("logo3d", "on");
    model.result().export("anim1").set("options3d", "on");
    model.result().export("anim1").set("axisorientation", "on");
    model.result().export("anim1").set("grid", "off");
    model.result().export("anim1").set("axes1d", "on");
    model.result().export("anim1").set("axes2d", "on");
    model.result().export("anim1").set("showgrid", "on");
    model.result().export("anim1").showFrame();
    model.result().export("anim1").showFrame();
    model.result().create("pg3", "PlotGroup2D");
    model.result("pg3").set("smooth", "internal");
    model.result("pg3").feature().create("surf1", "Surface");
    model.result("pg3").feature("surf1").set("smooth", "internal");
    model.result("pg3").feature("surf1").set("data", "parent");
    model.result("pg3").run();
    model.result("pg3").run();
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("expr", "log10(temw.normE/(1[V/m])+10)");
    model.result("pg1").run();
    model.result("pg2").run();
    model.result("pg2").feature("ptgr1").set("expr", "log10(temw.normE/(1[V/m])+10)");
    model.result("pg2").run();
    model.result("pg2").run();
    model.result("pg1").run();
    model.result("pg3").run();
    model.result().move("pg3", 1);
    model.result("pg2").run();
    model.result("pg2").run();
    model.result("pg2").feature("ptgr1").set("expr", "temw.normE");
    model.result("pg2").run();
    model.result("pg2").feature("ptgr1").set("expr", "log10(temw.normE/(1[V/m])+10)");
    model.result("pg2").run();
    model.result("pg2").feature("ptgr1").set("legend", true);
    model.result("pg2").feature("ptgr1").set("legendmethod", "manual");
    model.result("pg2").feature("ptgr1").setIndex("legends", "2m", 0);
    model.result("pg2").feature("ptgr1").setIndex("legends", "3m", 1);
    model.result("pg2").feature("ptgr1").setIndex("legends", "5m", 2);
    model.result("pg2").run();
    model.result("pg2").feature("ptgr1").set("descractive", true);
    model.result("pg2").feature("ptgr1").set("descr", "\u7535\u573a\u5f52\u4e00\u5316");
    model.result("pg2").feature("ptgr1").set("expr", "log10(temw.normE/(1[V/m])+1)");
    model.result("pg2").run();
    model.result("pg2").feature("ptgr1").set("descr", "\u5f52\u4e00\u5316\u7535\u573a");
    model.result("pg2").run();
    model.result("pg3").run();
    model.result().export("anim1").showFrame();
    model.result().export("anim1").run();
    model.result("pg1").run();
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("descractive", true);
    model.result("pg1").feature("surf1").set("descr", "\u5f52\u4e00\u5316\u7535\u573a");
    model.result("pg1").run();
    model.result().export("anim1").showFrame();
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("expr", "log10(temw.normE/(1[V/m])+1)");
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("colorcalibration", -0.5);
    model.result("pg1").feature("surf1").stepFirst(0);
    model.result("pg1").run();
    model.result().export("anim1").showFrame();
    model.result().export("anim1").run();
    model.result().export("anim1").run();
    model.result().export("anim1").run();
    model.result("pg2").run();
    model.result("pg1").run();
    model.result("pg1").run();
    model.result("pg3").run();
    model.result("pg1").run();

    model.label("700.mph");

    model.component("comp1").physics("temw").selection().set(2, 3, 4, 5);

    model.component("comp1").mesh("mesh1").run();
    model.component("comp1").mesh("mesh1").run();

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result().export("anim1").showFrame();
    model.result().export("anim1").showFrame();
    model.result("pg1").run();

    model.component("comp1").geom("geom1").feature().remove("c1");
    model.component("comp1").geom("geom1").runPre("fin");
    model.component("comp1").geom("geom1").run();

    model.component("comp1").mesh("mesh1").run();
    model.component("comp1").mesh("mesh1").run();
    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 100);
    model.component("comp1").mesh("mesh1").run();
    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 50);
    model.component("comp1").mesh("mesh1").run();
    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 20);
    model.component("comp1").mesh("mesh1").run();

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();

    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 100);
    model.component("comp1").mesh("mesh1").run();

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result("pg2").run();
    model.result("pg3").run();
    model.result("pg3").stepFirst(0);
    model.result("pg3").run();
    model.result("pg3").stepLast(0);
    model.result("pg3").run();
    model.result("pg1").run();
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("colorcalibration", -0.5);
    model.result("pg1").run();
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepFirst(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepNext(0);
    model.result("pg1").run();
    model.result("pg1").feature("surf1").stepLast(0);
    model.result("pg1").run();

    model.component("comp1").mesh("mesh1").feature("size").set("hmax", 50);
    model.component("comp1").mesh("mesh1").run();

    model.study("std1").createAutoSequences("all");

    model.sol("sol1").runAll();

    model.result("pg1").run();
    model.result().export("anim1").showFrame();
    model.result().export("anim1").run();
    model.result().export("anim1").run();
    model.result().export("anim1").run();
    model.result("pg1").run();
    model.result("pg1").feature("surf1").set("colorcalibration", -1.4);
    model.result().export("anim1").showFrame();
    model.result().export("anim1").run();
    model.result().export("anim1").run();

    model.label("\u6c34\u7bb1.mph");

    return model;
  }

  public static void main(String[] args) {
    Model model = run();
    model = run2(model);
    run3(model);
  }

}
