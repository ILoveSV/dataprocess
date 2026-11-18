import com.comsol.model.Model;
import com.comsol.model.ModelEntityImage;
import com.comsol.model.ModelNode;
import com.comsol.model.util.ModelUtil;
import java.util.Arrays;

public class RectangularTankExternalV2 {
  private static final String OUT = "C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/research/simulation/projects/lab_cathodic/rectangular_tank_v2";

  private static void selectGeometry(ModelNode c, String tag) {
    c.geom("g").feature(tag).set("selresult", true);
    c.geom("g").feature(tag).set("selresultshow", "all");
  }

  private static void block(ModelNode c, String tag, String label, String[] size, String[] pos) {
    c.geom("g").create(tag, "Block");
    c.geom("g").feature(tag).label(label);
    c.geom("g").feature(tag).set("size", size);
    c.geom("g").feature(tag).set("pos", pos);
    selectGeometry(c, tag);
  }

  private static void cylinder(ModelNode c, String tag, String label, String r, String h, String... pos) {
    c.geom("g").create(tag, "Cylinder");
    c.geom("g").feature(tag).label(label);
    c.geom("g").feature(tag).set("r", r);
    c.geom("g").feature(tag).set("h", h);
    c.geom("g").feature(tag).set("pos", pos);
    c.geom("g").feature(tag).set("axis", new double[]{0, 1, 0});
    selectGeometry(c, tag);
  }

  private static void difference(ModelNode c, String tag, String label, String in, String... tools) {
    c.geom("g").create(tag, "Difference");
    c.geom("g").feature(tag).label(label);
    c.geom("g").feature(tag).selection("input").set(in);
    c.geom("g").feature(tag).selection("input2").set(tools);
    c.geom("g").feature(tag).set("keepsubtract", true);
    selectGeometry(c, tag);
  }

  private static void wetSurface(ModelNode c, String tag, String body) {
    c.selection().create(tag, "Intersection");
    c.selection(tag).set("entitydim", 2);
    c.selection(tag).set("input", new String[]{"waterBoundaries", "g_" + body + "_bnd"});
    c.cpl().create(tag + "Int", "Integration");
    c.cpl(tag + "Int").selection().named(tag);
    c.cpl(tag + "Int").set("intorder", 6);
  }

  private static void color(ModelNode c, String tag, double... rgb) {
    c.geom("g").feature(tag).set("color","custom");
    c.geom("g").feature(tag).set("customcolor",rgb);
  }

  private static void material(ModelNode c, String tag, String selection, String sigma, String eps) {
    c.material().create(tag,"Common");
    c.material(tag).selection().named(selection);
    c.material(tag).propertyGroup("def").set("electricconductivity",sigma);
    c.material(tag).propertyGroup("def").set("relpermittivity",eps);
  }

  private static void potential(ModelNode c, String tag, String selection, String value) {
    c.physics("ec").create(tag,"ElectricPotential",2);
    c.physics("ec").feature(tag).selection().named(selection);
    c.physics("ec").feature(tag).set("V0",value);
  }

  public static void summary(Model m, String name) throws Exception {
    String[] expr = {"V_diff","waterInt(sigma_water*(abs(ec.Ex)^2+abs(ec.Ey)^2+abs(ec.Ez)^2))/V_diff",
      "waterInt(sigma_water*(abs(ec.Ex)^2+abs(ec.Ey)^2+abs(ec.Ez)^2))",
      "waterInt(1)","water_h","wetSteelInt(1)","wetGraphiteInt(1)","gap_horizontal"};
    if (!Arrays.asList(m.result().numerical().tags()).contains("audit")) {
      m.result().numerical().create("audit","EvalGlobal");
      m.result().table().create("auditTable","Table");
      m.result().numerical("audit").set("table","auditTable");
    }
    m.result().numerical("audit").set("expr",expr);
    m.result().numerical("audit").set("unit",new String[]{"V","A","W","L","mm","cm^2","cm^2","mm"});
    m.result().numerical("audit").set("descr",new String[]{"Differential voltage","Ohmic current from dissipation",
      "DC-equivalent water power (not phasor cycle average)","Water volume","Water depth","Steel window area","Graphite wetted area","Clear gap"});
    m.result().numerical("audit").setResult();
    m.result().table("auditTable").save(OUT+"/"+name+"_water.csv");
    double[][] a=m.result().numerical("audit").getReal();
    System.out.println(name+"_WATER="+Arrays.deepToString(a));
    if (!Double.isFinite(a[1][0]) || a[1][0]<=0 || Math.abs(a[5][0]-240)>0.1)
      throw new IllegalStateException("Water-domain audit failed");
    for (String suffix : new String[]{"05","2","3","4"}) {
      m.result().dataset("cp"+suffix).set("data","dset1");
      m.result().numerical("eval"+suffix).setResult();
      m.result().table("tbl"+suffix).save(OUT+"/"+name+"_point_"+suffix+"m.csv");
      double[][] values=m.result().numerical("eval"+suffix).getReal();
      System.out.println(name+"_POINT_"+suffix+"="+Arrays.deepToString(values));
      if(values.length!=5) throw new IllegalStateException("Empty observation dataset");
      for(double[] row:values) if(row.length==0 || !Double.isFinite(row[0])) throw new IllegalStateException("Invalid point field");
    }
  }

  private static void plots(Model m) throws Exception {
    ModelNode c = m.component("c");
    c.view().create("fields",3);
    c.view("fields").camera().set("projection", "orthographic");
    c.view("fields").camera().set("position", new double[]{0.08, -0.25, 1.25});
    c.view("fields").camera().set("target", new double[]{0, 0, 0.05});
    c.view("fields").camera().set("up", new double[]{0, 1, 0});
    c.view("fields").camera().set("orthoscale", 0.95);
    m.result().dataset().create("electrodePlane","CutPlane");
    m.result().dataset("electrodePlane").set("quickplane","xy");
    m.result().dataset("electrodePlane").set("quickz","z_graphite");
    for (String[] spec : new String[][]{{"pgV","V","V","water_potential.png","Water potential at graphite axis height (V)"},
        {"pgJ","ec.normJ","A/m^2","water_current_density.png","Water current density at graphite axis height (A/m^2)"}}) {
      m.result().create(spec[0], "PlotGroup3D");
      m.result(spec[0]).set("data", "electrodePlane");
      m.result(spec[0]).set("view", "fields");
      m.result(spec[0]).set("titletype", "manual");
      m.result(spec[0]).set("title", spec[4]);
      m.result(spec[0]).create("slice", "Surface");
      int waterDomain=c.selection("g_water_dom").entities(3)[0];
      m.result(spec[0]).feature("slice").set("expr", "if(dom=="+waterDomain+","+spec[1]+",NaN)");
      m.result(spec[0]).feature("slice").set("unit", spec[2]);
      m.result(spec[0]).feature("slice").set("colortable", "ThermalLight");
      m.result().export().create("img" + spec[0], "Image3D");
      m.result().export("img" + spec[0]).set("plotgroup", spec[0]);
      m.result().export("img" + spec[0]).set("pngfilename", OUT + "/" + spec[3]);
      m.result().export("img" + spec[0]).set("width", 1600);
      m.result().export("img" + spec[0]).set("height", 1100);
      m.result().export("img" + spec[0]).set("zoomextents", false);
      m.result().export("img" + spec[0]).set("options3d", true);
      m.result().export("img" + spec[0]).set("legend3d", "on");
      m.result().export("img" + spec[0]).set("title3d", "on");
      m.result().export("img" + spec[0]).run();
    }

    Model dryModel = ModelUtil.create("DryTank");
    for (String param : m.param().varnames()) dryModel.param().set(param,m.param().get(param));
    dryModel.component().create("layout", true);
    ModelNode dry = dryModel.component("layout");
    solids(dry);
    dry.geom("g").run();
    String view = dry.view().tags()[0];
    dry.view(view).camera().set("projection","orthographic");
    dry.view(view).camera().set("position",new double[]{0,-0.09,1.30});
    dry.view(view).camera().set("target",new double[]{0,0,0.12});
    dry.view(view).camera().set("up",new double[]{0,1,0});
    dry.view(view).camera().set("orthoscale",0.98);
    ModelEntityImage image = dry.geom("g").image();
    image.set("view",view); image.set("zoomextents",false);
    image.set("showgrid",false); image.set("grid",false);
    image.set("showselection",true); image.set("showmaterial",false);
    image.set("drawmode","on"); image.set("background","color");
    image.set("customcolor",new double[]{1,1,1}); image.set("size","manualweb");
    image.set("widthpx","1500"); image.set("heightpx","1100");
    image.set("pngfilename",OUT+"/tank_electrode_layout.png"); image.export();
    dryModel.label("rectangular_tank_layout_v2.mph");
    dryModel.save(OUT+"/rectangular_tank_layout_v2.mph");
    ModelUtil.remove("DryTank");
  }

  private static void solids(ModelNode c) {
    c.geom().create("g", 3);
    c.geom("g").lengthUnit("m");
    block(c,"tankOuter","Plastic container outside",new String[]{"tank_width+2*wall","tank_length+2*wall","tank_height+wall"},new String[]{"-tank_width/2-wall","-tank_length/2-wall","-wall"});
    block(c,"tankCavity","Open container cavity tool",new String[]{"tank_width","tank_length","tank_height+wall"},new String[]{"-tank_width/2","-tank_length/2","0"});
    difference(c,"tank","Open rectangular plastic tank","tankOuter","tankCavity");
    c.geom("g").feature("tank").set("keepsubtract",false);
    cylinder(c,"steel","Sealed stainless steel pipe envelope","r_steel","steel_length","x_steel","-steel_length/2","z_steel");
    cylinder(c,"tapeOuter","Sealing-layer envelope","r_steel+tape","steel_length+2*tape","x_steel","-steel_length/2-tape","z_steel");
    block(c,"windowTool","Tool for exposed curved window",new String[]{"r_steel+2*tape","window_length","2*window_half_height"},new String[]{"x_steel","-window_length/2","z_steel-window_half_height"});
    difference(c,"tapeSolid","Insulation with open window and sealed ends","tapeOuter","steel","windowTool");
    c.geom("g").create("removeTool", "Delete");
    c.geom("g").feature("removeTool").selection("input").init();
    c.geom("g").feature("removeTool").selection("input").set("windowTool");
    cylinder(c,"graphite","Horizontal graphite anode","r_graphite","graphite_length","x_graphite","graphite_y-graphite_length/2","z_graphite");
    color(c,"tank",0.95,0.66,0.73);
    color(c,"steel",0.65,0.69,0.73);
    color(c,"tapeSolid",0.08,0.57,0.41);
    color(c,"graphite",0.19,0.20,0.23);
  }

  public static void main(String[] args) throws Exception {
    Model m = ModelUtil.create("Tank");
    m.modelPath(OUT);
    m.label("rectangular_tank_20V_external_v2.mph");
    m.title("20 V rectangular tank and isolated-source external field");
    m.description("20 V ideal electrode differential voltage. Low-frequency EQS DC proxy; balanced common-mode reference is an assumption, not a floating-source solution. Ideal grounded floor, no leads or building walls. Graphite is present but hidden by air/water surfaces; open the separate layout model for solids.");
    String[][] params = {
        {"tank_width","0.20[m]","Confirmed inner width"},
        {"tank_length","0.48[m]","Assumed inner length fitting the 40 cm pipe"},
        {"tank_height","0.30[m]","Assumed inner height"}, {"wall","4[mm]","Assumed plastic wall"},
        {"steel_length","0.40[m]","Sealed pipe length"}, {"r_steel","50[mm]","Pipe outside radius"},
        {"tape","1.5[mm]","Assumed sealing layer thickness"}, {"bottom_gap","3[mm]","Small water clearance below specimens"},
        {"r_graphite","12.5[mm]","Graphite radius"}, {"graphite_length","0.20[m]","Graphite length"},
        {"graphite_y","0[m]","Graphite centered on exposed window"},
        {"gap_horizontal","0.05[m]","Provisional 5 cm gap fitting the 20 cm box"},
        {"window_length","0.20[m]","Axial exposed window length"}, {"window_arc","0.12[m]","Developed width along steel circumference"},
        {"window_half_height","r_steel*sin(window_arc/(2*r_steel))","Window vertical half span"},
        {"x_steel","-(gap_horizontal+r_steel+r_graphite)/2+(r_steel-r_graphite)/2","Steel axis x"},
        {"x_graphite","x_steel+gap_horizontal+r_steel+r_graphite","Graphite axis x"},
        {"z_steel","bottom_gap+tape+r_steel","Steel axis height"},
        {"z_graphite","z_steel","Graphite axis aligned with window center; insulating support assumed"},
        {"window_top","z_steel+window_half_height","Highest exposed steel point"},
        {"submergence","3[mm]","Water surface above the window top"},
        {"water_h","window_top+submergence","Water height above inner bottom"},
        {"sigma_water","0.05[S/m]","Inherited 500 uS/cm assumption, not measured for this box"},
        {"V_diff","20[V]","Ideal electrode-to-electrode DC voltage"},
        {"V_cm","0[V]","Electrode average potential relative to earth; assumed"},
        {"f_proxy","1e-3[Hz]","DC proxy, not an experimental spectral line"},
        {"air_r","10[m]","Air box half width"}, {"air_h","10[m]","Air top elevation"},
        {"obs_x","tank_width/2+wall+0.5[m]","0.5 m to right of outer wall"},
        {"obs_z","0.5[m]-wall","0.5 m above floor; inner bottom is z=0"},
        {"h_air","0.8[m]","Maximum far air mesh size"},
        {"h_near","0.06[m]","Air mesh near the requested observation point"},
        {"h_mid","0.25[m]","Air mesh around 2 to 4 m observations"},
        {"h_water","9[mm]","Water mesh maximum size"}};
    for (String[] p : params) m.param().set(p[0], p[1], p[2]);

    m.component().create("c", true);
    ModelNode c=m.component("c");
    solids(c);
    block(c,"waterBlock","Shallow water before solid cutouts",new String[]{"tank_width","tank_length","water_h"},new String[]{"-tank_width/2","-tank_length/2","0"});
    difference(c,"water","Conductive water","waterBlock","steel","tapeSolid","graphite");
    block(c,"airBlock","Outer air box",new String[]{"2*air_r","2*air_r","air_h+wall"},new String[]{"-air_r","-air_r","-wall"});
    block(c,"nearBlock","Near air precursor",new String[]{"2[m]","2[m]","1.2[m]+wall"},new String[]{"-1[m]","-1[m]","-wall"});
    difference(c,"nearAir","Refined air around tank and P","nearBlock","tank","water","steel","tapeSolid","graphite");
    block(c,"midBlock","Middle air precursor",new String[]{"10[m]","10[m]","3[m]+wall"},new String[]{"-5[m]","-5[m]","-wall"});
    difference(c,"midAir","Refined air around comparison points","midBlock","tank","water","steel","tapeSolid","graphite","nearAir");
    difference(c,"air","Far air","airBlock","tank","water","steel","tapeSolid","graphite","nearAir","midAir");
    c.geom("g").create("obs","Point");
    c.geom("g").feature("obs").set("p",new String[]{"obs_x","0","obs_z"});
    c.geom("g").feature("obs").label("P: wall +0.5 m, floor +0.5 m");
    c.geom("g").run();

    c.selection().create("waterBoundaries","Adjacent");
    c.selection("waterBoundaries").set("entitydim",3);
    c.selection("waterBoundaries").set("outputdim",2);
    c.selection("waterBoundaries").set("input",new String[]{"g_water_dom"});
    wetSurface(c,"wetSteel","steel"); wetSurface(c,"wetGraphite","graphite");
    c.cpl().create("waterInt","Integration");
    c.cpl("waterInt").selection().named("g_water_dom");
    material(c,"waterMat","g_water_dom","sigma_water","80");
    material(c,"airMat","g_air_dom","0[S/m]","1.0006");
    material(c,"nearAirMat","g_nearAir_dom","0[S/m]","1.0006");
    material(c,"midAirMat","g_midAir_dom","0[S/m]","1.0006");
    material(c,"tankMat","g_tank_dom","0[S/m]","2.3");
    material(c,"tapeMat","g_tapeSolid_dom","0[S/m]","3.2");
    c.selection().create("active","Union");
    c.selection("active").set("entitydim",3);
    c.selection("active").set("input",new String[]{"g_water_dom","g_air_dom","g_nearAir_dom","g_midAir_dom","g_tank_dom","g_tapeSolid_dom"});
    c.selection().create("local","Union");
    c.selection("local").set("entitydim",3);
    c.selection("local").set("input",new String[]{"g_water_dom","g_tank_dom","g_tapeSolid_dom"});
    c.physics().create("ec","ConductiveMedia","g");
    c.physics("ec").selection().named("active");
    c.physics("ec").prop("ShapeProperty").set("order_electricpotential",2);
    potential(c,"positive","g_graphite_bnd","V_cm+V_diff/2");
    potential(c,"negative","g_steel_bnd","V_cm-V_diff/2");
    String[][] planes={{"floor","z","-wall"},{"ceiling","z","air_h"},
      {"left","x","-air_r"},{"right","x","air_r"},{"front","y","-air_r"},{"back","y","air_r"}};
    for(String[] plane:planes) {
      c.selection().create(plane[0],"Box");
      c.selection(plane[0]).set("entitydim",2);
      c.selection(plane[0]).set("condition","inside");
      c.selection(plane[0]).set(plane[1]+"min",plane[2]+"-1e-6[m]");
      c.selection(plane[0]).set(plane[1]+"max",plane[2]+"+1e-6[m]");
      c.physics("ec").create("gnd"+plane[0],"Ground",2);
      c.physics("ec").feature("gnd"+plane[0]).selection().named(plane[0]);
    }
    System.out.println("GRAPHITE_DOMAINS="+Arrays.toString(c.selection("g_graphite_dom").entities(3)));
    System.out.println("STEEL_WINDOW="+Arrays.toString(c.selection("wetSteel").entities(2)));
    System.out.println("GRAPHITE_WET="+Arrays.toString(c.selection("wetGraphite").entities(2)));
    if(c.selection("g_graphite_dom").entities(3).length==0) throw new IllegalStateException("Missing graphite");
    c.mesh().create("mesh","g");
    c.mesh("mesh").feature("size").set("custom",true);
    c.mesh("mesh").feature("size").set("hmax","h_air");
    c.mesh("mesh").feature("size").set("hmin","0.5[mm]");
    c.mesh("mesh").feature("size").set("hgrad",1.4);
    c.mesh("mesh").create("localSize","Size");
    c.mesh("mesh").feature("localSize").selection().geom("g",3);
    c.mesh("mesh").feature("localSize").selection().named("local");
    c.mesh("mesh").feature("localSize").set("custom",true);
    c.mesh("mesh").feature("localSize").set("hmax","h_water");
    c.mesh("mesh").feature("localSize").set("hmaxactive",true);
    for(String[] size:new String[][]{{"nearSize","g_nearAir_dom","h_near"},{"midSize","g_midAir_dom","h_mid"}}) {
      c.mesh("mesh").create(size[0],"Size");
      c.mesh("mesh").feature(size[0]).selection().geom("g",3);
      c.mesh("mesh").feature(size[0]).selection().named(size[1]);
      c.mesh("mesh").feature(size[0]).set("custom",true);
      c.mesh("mesh").feature(size[0]).set("hmax",size[2]);
      c.mesh("mesh").feature(size[0]).set("hmaxactive",true);
    }
    c.mesh("mesh").create("tet","FreeTet");
    c.mesh("mesh").feature("tet").selection().named("active");
    c.mesh("mesh").run();
    m.study().create("std");
    m.study("std").create("freq","Frequency");
    m.study("std").feature("freq").set("plist","f_proxy");
    for(String suffix:new String[]{"05","2","3","4"}) {
      double d=suffix.equals("05")?0.5:Double.parseDouble(suffix);
      String ds="cp"+suffix, ev="eval"+suffix, tb="tbl"+suffix;
      m.result().dataset().create(ds,"CutPoint3D");
      m.result().dataset(ds).set("pointx",new double[]{m.param().evaluate("tank_width")/2+m.param().evaluate("wall")+d});
      m.result().dataset(ds).set("pointy",new double[]{0});
      m.result().dataset(ds).set("pointz",new double[]{m.param().evaluate("obs_z")});
      m.result().dataset(ds).label("Right of outer wall "+d+" m; 0.5 m above floor");
      m.result().numerical().create(ev,"EvalPoint");
      m.result().numerical(ev).set("data",ds);
      m.result().numerical(ev).set("expr",new String[]{"real(ec.Ex)","real(ec.Ey)","real(ec.Ez)","ec.normE","real(V)"});
      m.result().numerical(ev).set("unit",new String[]{"V/m","V/m","V/m","V/m","V"});
      m.result().table().create(tb,"Table");
      m.result().numerical(ev).set("table",tb);
    }
    m.study("std").createAutoSequences("all");
    m.sol("sol1").feature("s1").set("stol",1e-9);
    m.sol("sol1").runAll();
    summary(m,"baseline");
    m.save(OUT+"/rectangular_tank_20V_external_v2.mph");
    plots(m);
    m.save(OUT+"/rectangular_tank_20V_external_v2.mph");
    System.out.println("SAVED baseline and layout");
    for(String[] test:new String[][]{{"negative_earth","V_cm","10[V]"},{"positive_earth","V_cm","-10[V]"},
       {"proxy_0001","f_proxy","1e-4[Hz]"},{"proxy_001","f_proxy","1e-2[Hz]"}}) {
      m.param().set("V_cm","0[V]");m.param().set("f_proxy","1e-3[Hz]");
      m.param().set(test[1],test[2]);m.sol("sol1").runAll();summary(m,test[0]);
    }
    ModelUtil.remove("Tank");
    System.out.println("COMPLETED V2");
  }
}

