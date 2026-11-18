import com.comsol.model.Model;
import com.comsol.model.ModelEntityImage;
import com.comsol.model.ModelNode;
import com.comsol.model.util.ModelUtil;
import java.util.Arrays;

public class RectangularTankDischarge {
  private static final String OUT = "C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/research/simulation/projects/lab_cathodic/rectangular_tank_v1";

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

  private static void summary(Model m) throws Exception {
    m.result().numerical().create("audit", "EvalGlobal");
    m.result().numerical("audit").set("expr", new String[]{
        "I_total", "ec.term1.V0_ode", "ec.term1.V0_ode/I_total",
        "I_total*ec.term1.V0_ode", "waterInt(ec.Qh)", "waterInt(1)",
        "water_h", "water_h-window_top", "wetSteelInt(1)", "wetGraphiteInt(1)",
        "sqrt((x_graphite-x_steel)^2+(z_graphite-z_steel)^2)-r_steel-r_graphite"});
    m.result().numerical("audit").set("unit", new String[]{
        "A", "V", "ohm", "W", "W", "L", "mm", "mm", "cm^2", "cm^2", "mm"});
    m.result().numerical("audit").set("descr", new String[]{
        "Imposed current", "Graphite-to-steel ohmic voltage", "Water-path resistance",
        "Terminal power", "Integrated water Joule heating", "Water volume", "Water depth",
        "Water margin above window", "Wetted steel window", "Wetted graphite", "Electrode net gap"});
    m.result().table().create("auditTable", "Table");
    m.result().numerical("audit").set("table", "auditTable");
    m.result().numerical("audit").setResult();
    m.result().table("auditTable").save(OUT + "/terminal_summary.csv");
    double[][] result = m.result().numerical("audit").getReal();
    System.out.println("AUDIT=" + Arrays.deepToString(result));
    double[] a = new double[result.length];
    for (int i=0;i<result.length;i++) a[i]=result[i][0];
    double nominalWindow = 1e4*m.param().evaluate("window_length")*m.param().evaluate("window_arc");
    if (a.length!=11 || !Arrays.stream(a).allMatch(Double::isFinite)
        || a[1]<=0 || a[5]<=0 || Math.abs(a[3]-a[4])>1e-5*a[3]
        || Math.abs(a[8]-nominalWindow)>0.01*nominalWindow || a[7]<=0) {
      throw new IllegalStateException("Discharge audit failed");
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
      m.result(spec[0]).feature("slice").set("expr", spec[1]);
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
    m.label("rectangular_tank_discharge_v1.mph");
    m.title("Rectangular shallow tank - stationary cathodic discharge");
    m.description("Photo-informed geometry. The sealed steel cylinder represents occupied volume; only its wet exposed window conducts. No electrode kinetics, external air field or power-supply model.");
    String[][] params = {
        {"tank_width","0.30[m]","Assumed inner width, interpreting the given 30 cm"},
        {"tank_length","0.48[m]","Assumed inner length fitting the 40 cm pipe"},
        {"tank_height","0.30[m]","Assumed inner height"}, {"wall","4[mm]","Assumed plastic wall"},
        {"steel_length","0.40[m]","Sealed pipe length"}, {"r_steel","50[mm]","Pipe outside radius"},
        {"tape","1.5[mm]","Assumed sealing layer thickness"}, {"bottom_gap","3[mm]","Small water clearance below specimens"},
        {"r_graphite","12.5[mm]","Graphite radius"}, {"graphite_length","0.20[m]","Graphite length"},
        {"graphite_y","-0.07[m]","Photo-informed axial offset, not measured"},
        {"gap_horizontal","0.15[m]","Assumed transverse edge gap in plan view"},
        {"window_length","0.20[m]","Axial exposed window length"}, {"window_arc","0.12[m]","Developed width along steel circumference"},
        {"window_half_height","r_steel*sin(window_arc/(2*r_steel))","Window vertical half span"},
        {"x_steel","-(gap_horizontal+r_steel+r_graphite)/2+(r_steel-r_graphite)/2","Steel axis x"},
        {"x_graphite","x_steel+gap_horizontal+r_steel+r_graphite","Graphite axis x"},
        {"z_steel","bottom_gap+tape+r_steel","Steel axis height"},
        {"z_graphite","bottom_gap+r_graphite","Graphite axis height"},
        {"window_top","z_steel+window_half_height","Highest exposed steel point"},
        {"submergence","3[mm]","Water surface above the window top"},
        {"water_h","window_top+submergence","Water height above inner bottom"},
        {"sigma_water","0.05[S/m]","Inherited 500 uS/cm assumption, not measured for this box"},
        {"I_total","10[mA]","Reference graphite current"},
        {"h_water","9[mm]","Water mesh maximum size"}};
    for (String[] p : params) m.param().set(p[0], p[1], p[2]);

    m.component().create("c", true);
    ModelNode c=m.component("c");
    solids(c);
    block(c,"waterBlock","Shallow water before solid cutouts",new String[]{"tank_width","tank_length","water_h"},new String[]{"-tank_width/2","-tank_length/2","0"});
    difference(c,"water","Conductive water","waterBlock","steel","tapeSolid","graphite");
    c.geom("g").run();

    c.selection().create("waterBoundaries","Adjacent");
    c.selection("waterBoundaries").set("entitydim",3);
    c.selection("waterBoundaries").set("outputdim",2);
    c.selection("waterBoundaries").set("input",new String[]{"g_water_dom"});
    wetSurface(c,"wetSteel","steel"); wetSurface(c,"wetGraphite","graphite");
    c.cpl().create("waterInt","Integration");
    c.cpl("waterInt").selection().named("g_water_dom");
    c.material().create("waterMat","Common");
    c.material("waterMat").selection().named("g_water_dom");
    c.material("waterMat").propertyGroup("def").set("electricconductivity","sigma_water");
    c.material("waterMat").propertyGroup("def").set("relpermittivity","80");
    c.physics().create("ec","ConductiveMedia","g");
    c.physics("ec").selection().named("g_water_dom");
    c.physics("ec").prop("ShapeProperty").set("order_electricpotential",2);
    c.physics("ec").create("term1","Terminal",2);
    c.physics("ec").feature("term1").selection().named("wetGraphite");
    c.physics("ec").feature("term1").set("I0","I_total");
    c.physics("ec").feature("term1").label("Graphite current terminal");
    c.physics("ec").create("reference","Ground",2);
    c.physics("ec").feature("reference").selection().named("wetSteel");
    c.physics("ec").feature("reference").label("Steel window: potential reference, not protective earth");
    System.out.println("STEEL="+Arrays.toString(c.selection("wetSteel").entities(2)));
    System.out.println("GRAPHITE="+Arrays.toString(c.selection("wetGraphite").entities(2)));
    c.mesh().create("mesh","g");
    c.mesh("mesh").feature("size").set("custom",true);
    c.mesh("mesh").feature("size").set("hmax","h_water");
    c.mesh("mesh").feature("size").set("hmin","0.5[mm]");
    c.mesh("mesh").create("tet","FreeTet");
    c.mesh("mesh").feature("tet").selection().named("g_water_dom");
    c.mesh("mesh").run();
    m.study().create("std");
    m.study("std").create("stat","Stationary");
    m.study("std").run();
    summary(m);
    m.save(OUT + "/rectangular_tank_discharge_v1.mph");
    plots(m);
    m.save(OUT + "/rectangular_tank_discharge_v1.mph");
    System.out.println("SAVED rectangular_tank_discharge_v1");
    ModelUtil.remove("Tank");
  }
}
