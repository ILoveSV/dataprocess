import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;
import java.util.*;

/** Generic three-dimensional ICCP circuit with nonlinear metal-water interfaces. */
public class SubmarineICCP {
  static final String ROOT = "C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/research/01_vessel_background/iccp_v1";
  static String configured(String name) {
    for(String[] p:ICCPInputs.PARAMETERS)if(p[0].equals(name))return p[1];
    throw new IllegalArgumentException("Missing parameter: "+name);
  }
  static String currentTag(double value) {
    return java.math.BigDecimal.valueOf(value).stripTrailingZeros().toPlainString();
  }

  static void selected(Model m, String t) {
    m.component("c").geom("g").feature(t).set("selresult", true);
    m.component("c").geom("g").feature(t).set("selresultshow", "all");
  }
  static void block(Model m, String t, String[] size, String[] pos) {
    m.component("c").geom("g").create(t, "Block");
    m.component("c").geom("g").feature(t).set("size", size);
    m.component("c").geom("g").feature(t).set("pos", pos);
    selected(m,t);
  }
  static void cylinder(Model m, String t, String r, String h, String[] pos, double[] axis) {
    m.component("c").geom("g").create(t, "Cylinder");
    m.component("c").geom("g").feature(t).set("r",r);
    m.component("c").geom("g").feature(t).set("h",h);
    m.component("c").geom("g").feature(t).set("pos",pos);
    m.component("c").geom("g").feature(t).set("axis",axis);
    selected(m,t);
  }
  static void selection(Model m, String tag, String type, String[] add, String[] subtract) {
    m.component("c").selection().create(tag,type);
    m.component("c").selection(tag).set("entitydim",2);
    if(type.equals("Difference")) {
      m.component("c").selection(tag).set("add",add);
      m.component("c").selection(tag).set("subtract",subtract);
    } else m.component("c").selection(tag).set("input",add);
  }
  static void integral(Model m, String tag, String sel) {
    m.component("c").cpl().create(tag,"Integration");
    m.component("c").cpl(tag).selection().named(sel);
    m.component("c").cpl(tag).set("intorder",6);
  }
  static void interpolation(Model m, String name, String[][] rows) throws Exception {
    m.func().create(name,"Interpolation");
    m.func(name).set("funcname",name);
    m.func(name).set("source","table");
    m.func(name).set("table",rows);
    m.func(name).set("argunit","V");
    m.func(name).set("fununit","A/m^2");
    m.func(name).set("interp","linear");
    m.func(name).set("extrap","linear");
  }
  static void inward(Model m, String tag, String sel, String expr) {
    m.component("c").physics("ec").create(tag,"NormalCurrentDensity",2);
    m.component("c").physics("ec").feature(tag).selection().named(sel);
    m.component("c").physics("ec").feature(tag).set("nJ",expr);
  }
  static void csv(Model m, String tag, String kind, String ds, String[] expr, String[] headers, String path) throws Exception {
    m.result().numerical().create(tag,kind);
    if(ds!=null)m.result().numerical(tag).set("data",ds);
    m.result().numerical(tag).set("expr",expr);
    m.result().numerical(tag).set("descr",headers);
    m.result().table().create(tag+"table","Table");
    m.result().numerical(tag).set("table",tag+"table");
    m.result().numerical(tag).setResult();
    m.result().table(tag+"table").save(path);
    m.result().numerical().remove(tag);
    m.result().table().remove(tag+"table");
  }
  static void evaluate(Model m, String name) throws Exception {
    String dir=ROOT+"/results/"+name;
    csv(m,"audit","EvalGlobal",null,
      new String[]{"Vm","I_total","iwetSteel(jsteel)","iwetProp(jprop)",
        "iwetSteel(jsteel)+iwetProp(jprop)+I_total",
        "ifar(ec.Jx*nx+ec.Jy*ny+ec.Jz*nz)",
        "iwetSteel(ec.Jx*nx+ec.Jy*ny+ec.Jz*nz+jsteel)",
        "iwetProp(ec.Jx*nx+ec.Jy*ny+ec.Jz*nz+jprop)",
        "iwetSteel(1)","iwetProp(1)","a1(1)","a2(1)","a3(1)","a4(1)",
        "minSteel(eta)","maxSteel(eta)",
        "iwetSteel(if(eta<=-0.8[V],1,0))/iwetSteel(1)",
        "minProp(eta)","maxProp(eta)",
        "iwetSteel(if(eta < -0.96382958[V] || eta > -0.35571579[V],1,0))/iwetSteel(1)",
        "iwetProp(if(eta < -0.91985107[V] || eta > -0.02695065[V],1,0))/iwetProp(1)"},
      new String[]{"Vm_V_AgAgCl","I_ICCP_A","steel_net_anodic_A","prop_net_anodic_A","circuit_residual_A",
        "far_gradient_flux_A","steel_gradient_residual_A","prop_gradient_residual_A","steel_wet_area_m2",
        "prop_wet_area_m2","anode1_area_m2","anode2_area_m2","anode3_area_m2","anode4_area_m2",
        "steel_eta_min_V","steel_eta_max_V","steel_fraction_below_minus_0_8V","prop_eta_min_V","prop_eta_max_V",
        "steel_extrapolated_area_fraction","prop_extrapolated_area_fraction"},dir+"_audit.csv");
    for(String mode:new String[]{"axial","side","plane"}) {
      List<double[]> pts=new ArrayList<>();
      double depth=m.param().evaluate("depth_sub"), beam=m.param().evaluate("B");
      double z=-depth-beam/2-m.param().evaluate("obs_below_keel");
      if(mode.equals("axial"))for(int k=0;k<=240;k++)pts.add(new double[]{-150+1.25*k,0,z});
      if(mode.equals("side"))for(double d:new double[]{10,20,30,50,75,100})pts.add(new double[]{0,d,-depth});
      if(mode.equals("plane"))for(int j=0;j<=40;j++)for(int i=0;i<=80;i++)pts.add(new double[]{-80+2*i,-40+2*j,z});
      double[] xs=new double[pts.size()],ys=xs.clone(),zs=xs.clone();
      for(int i=0;i<pts.size();i++){xs[i]=pts.get(i)[0];ys[i]=pts.get(i)[1];zs[i]=pts.get(i)[2];}
      String ds="sample"+mode;
      if(Arrays.asList(m.result().dataset().tags()).contains(ds))m.result().dataset().remove(ds);
      m.result().dataset().create(ds,"CutPoint3D");
      m.result().dataset(ds).set("pointx",xs);m.result().dataset(ds).set("pointy",ys);m.result().dataset(ds).set("pointz",zs);
      csv(m,"ev"+mode,"EvalPoint",ds,new String[]{"x","y","z","V","ec.Ex","ec.Ey","ec.Ez","ec.normE"},
        new String[]{"x_m","y_m","z_m","water_potential_V","Ex_V_m","Ey_V_m","Ez_V_m","normE_V_m"},dir+"_"+mode+".csv");
    }
  }
  static void image(Model m, String plot, String path, double[] pos, double[] target, double scale) throws Exception {
    String view="view_"+plot;
    if(!Arrays.asList(m.component("c").view().tags()).contains(view))m.component("c").view().create(view,3);
    m.component("c").view(view).camera().set("projection","orthographic");
    m.component("c").view(view).camera().set("position",pos);
    m.component("c").view(view).camera().set("target",target);
    m.component("c").view(view).camera().set("up",new double[]{0,0,1});
    m.component("c").view(view).camera().set("orthoscale",scale);
    m.component("c").view(view).set("showgrid",false);
    m.result(plot).set("view",view);
    m.result(plot).run();
    String itag="img"+plot;
    m.result().export().create(itag,"Image3D");
    m.result().export(itag).set("plotgroup",plot);
    m.result().export(itag).set("pngfilename",path);
    m.result().export(itag).set("size","manualweb");
    m.result().export(itag).set("width",1800);
    m.result().export(itag).set("height",1100);
    m.result().export(itag).set("zoomextents",false);
    m.result().export(itag).set("options3d",true);
    m.result().export(itag).set("legend3d","on");
    m.result().export(itag).set("title3d","on");
    m.result().export(itag).run();
  }
  static void plots(Model m) throws Exception {
    m.result().create("hullpotential","PlotGroup3D");
    m.result("hullpotential").set("data","dset1");
    m.result("hullpotential").label("Metal-to-local-water polarization potential vs Ag/AgCl");
    m.result("hullpotential").set("titletype","manual");
    m.result("hullpotential").set("title","ICCP "+currentTag(m.param().evaluate("I_total"))+" A: metal-to-water potential (V vs Ag/AgCl)");
    m.result("hullpotential").create("surf","Surface");
    m.result("hullpotential").feature("surf").create("sel","Selection");
    m.result("hullpotential").feature("surf").feature("sel").selection().set(m.component("c").selection("metals").entities(2));
    m.result("hullpotential").feature("surf").set("expr","eta");
    m.result("hullpotential").feature("surf").set("unit","V");
    m.result("hullpotential").feature("surf").set("colortable","RainbowLight");
    m.result("hullpotential").create("anodes","Surface");
    m.result("hullpotential").feature("anodes").create("sel","Selection");
    m.result("hullpotential").feature("anodes").feature("sel").selection().set(m.component("c").selection("anodes").entities(2));
    m.result("hullpotential").feature("anodes").set("expr","1");
    m.result("hullpotential").feature("anodes").set("coloring","uniform");
    m.result("hullpotential").feature("anodes").set("color","red");
    image(m,"hullpotential",ROOT+"/results/submarine_iccp_3d.png",new double[]{85,-100,42},new double[]{0,0,-20},55);
    m.result().create("externalfield","PlotGroup3D");
    m.result("externalfield").set("data","dset1");
    m.result("externalfield").label("Electric field 20 m below the keel");
    m.result("externalfield").set("titletype","manual");
    m.result("externalfield").set("title","ICCP "+currentTag(m.param().evaluate("I_total"))+" A: electric field below keel (uV/m)");
    m.result().dataset().create("fieldplane","CutPlane");
    m.result().dataset("fieldplane").set("quickplane","xy");
    m.result().dataset("fieldplane").set("quickz","-depth_sub-B/2-obs_below_keel");
    m.result("externalfield").create("plane","Surface");
    m.result("externalfield").feature("plane").set("data","fieldplane");
    m.result("externalfield").feature("plane").set("expr","ec.normE");
    m.result("externalfield").feature("plane").set("unit","uV/m");
    m.result("externalfield").feature("plane").set("colortable","ThermalLight");
    m.result("externalfield").feature("plane").create("crop","Filter");
    m.result("externalfield").feature("plane").feature("crop").set("expr","abs(x)<=80[m] && abs(y)<=40[m]");
    m.result("externalfield").create("body","Surface");
    m.result("externalfield").feature("body").create("sel","Selection");
    m.result("externalfield").feature("body").feature("sel").selection().set(m.component("c").selection("metals").entities(2));
    m.result("externalfield").feature("body").set("expr","1");
    m.result("externalfield").feature("body").set("coloring","uniform");
    m.result("externalfield").feature("body").set("color","gray");
    image(m,"externalfield",ROOT+"/results/submarine_external_field_3d.png",new double[]{110,-140,105},new double[]{0,0,-30},150);
  }
  static Model build(String name, String radius, String meshScale) throws Exception {
    Model m=ModelUtil.create("SubICCP");
    m.modelPath(ROOT+"/models");m.label(name+".mph");
    m.title("3D generic submarine ICCP with nonlinear HY80 and NAB polarization");
    m.description("Literature-informed scenario: Schaefer et al. COMSOL 2011 methodology; Thiel et al. 2020 Fig.3 digitized polarization curves; generic assumed geometry and anode placement. Floating common metal potential solved from integral current balance. No SACP, no forced hull grounding, no propeller rotation, no real-vessel calibration.");
    for(String[] p:ICCPInputs.PARAMETERS)m.param().set(p[0],p[1]);
    m.param().set("domain_radius",radius);m.param().set("mesh_scale",meshScale);
    m.param().set("I_nominal",m.param().get("I_total"),"Reference total ICCP current for the scenario sweep");
    m.param().set("I_total","0[A]");
    m.param().set("I_bow","I_total*bow_share/2");
    m.param().set("I_stern","I_total*(1-bow_share)/2");
    interpolation(m,"hy80",ICCPInputs.HY80);
    interpolation(m,"nab",ICCPInputs.NAB);
    m.component().create("c",true);m.component("c").geom().create("g",3);
    m.component("c").geom("g").lengthUnit("m");
    block(m,"water",new String[]{"2*domain_radius","2*domain_radius","domain_radius"},new String[]{"-domain_radius","-domain_radius","-domain_radius"});
    m.component("c").geom("g").create("hull","Ellipsoid");
    m.component("c").geom("g").feature("hull").set("semiaxes",new String[]{"L/2","B/2","B/2"});
    m.component("c").geom("g").feature("hull").set("pos",new String[]{"0","0","-depth_sub"});selected(m,"hull");
    block(m,"sail",new String[]{"6[m]","1.2[m]","4[m]"},new String[]{"-3[m]","-0.6[m]","-depth_sub+B/2-0.8[m]"});
    block(m,"rudderV",new String[]{"4[m]","0.25[m]","6[m]"},new String[]{"-L/2+1[m]","-0.125[m]","-depth_sub-3[m]"});
    block(m,"rudderH",new String[]{"4[m]","6[m]","0.25[m]"},new String[]{"-L/2+1[m]","-3[m]","-depth_sub-0.125[m]"});
    cylinder(m,"shaft","0.20[m]","2[m]",new String[]{"-L/2-1[m]","0","-depth_sub"},new double[]{1,0,0});
    m.component("c").geom("g").create("steel","Union");
    m.component("c").geom("g").feature("steel").selection("input").set(new String[]{"hull","sail","rudderV","rudderH","shaft"});
    m.component("c").geom("g").feature("steel").set("intbnd",false);selected(m,"steel");
    cylinder(m,"prop","prop_radius","prop_thickness",new String[]{"-L/2-1[m]","0","-depth_sub"},new double[]{-1,0,0});
    for(int k=1;k<=4;k++) {
      boolean bow=k<=2; int s=(k%2==1)?1:-1;
      String x=bow?"anode_x":"-anode_x";
      cylinder(m,"shield"+k,"shield_radius","anode_y-B/3",new String[]{x,s+"*B/3","-depth_sub"},new double[]{0,s,0});
      cylinder(m,"anode"+k,"anode_radius","anode_thickness",new String[]{x,s+"*anode_y","-depth_sub"},new double[]{0,s,0});
    }
    List<String> solids=new ArrayList<>(Arrays.asList("steel","prop"));
    for(int k=1;k<=4;k++){solids.add("shield"+k);solids.add("anode"+k);}
    m.component("c").geom("g").create("sea","Difference");
    m.component("c").geom("g").feature("sea").selection("input").set("water");
    m.component("c").geom("g").feature("sea").selection("input2").set(solids.toArray(new String[0]));
    m.component("c").geom("g").feature("sea").set("keepsubtract",true);selected(m,"sea");
    m.component("c").geom("g").run();
    m.component("c").selection().create("waterb","Adjacent");
    m.component("c").selection("waterb").set("entitydim",3);
    m.component("c").selection("waterb").set("outputdim",2);
    m.component("c").selection("waterb").set("input",new String[]{"g_sea_dom"});
    for(String solid:solids)selection(m,"wet"+solid,"Intersection",new String[]{"waterb","g_"+solid+"_bnd"},null);
    List<String> wet=new ArrayList<>();for(String solid:solids)wet.add("wet"+solid);
    selection(m,"obstacles","Union",wet.toArray(new String[0]),null);
    selection(m,"metals","Union",new String[]{"wetsteel","wetprop"},null);
    selection(m,"anodes","Union",new String[]{"wetanode1","wetanode2","wetanode3","wetanode4"},null);
    m.component("c").selection().create("top","Box");
    m.component("c").selection("top").set("entitydim",2);m.component("c").selection("top").set("condition","inside");
    for(String axis:new String[]{"x","y"}){m.component("c").selection("top").set(axis+"min","-domain_radius-1[m]");m.component("c").selection("top").set(axis+"max","domain_radius+1[m]");}
    m.component("c").selection("top").set("zmin","-0.001[m]");m.component("c").selection("top").set("zmax","0.001[m]");
    selection(m,"far","Difference",new String[]{"waterb"},new String[]{"obstacles","top"});
    integral(m,"iwetSteel","wetsteel");integral(m,"iwetProp","wetprop");integral(m,"ifar","far");
    for(int k=1;k<=4;k++)integral(m,"a"+k,"wetanode"+k);
    for(String op:new String[]{"minSteel","maxSteel","minProp","maxProp"}) {
      m.component("c").cpl().create(op,op.startsWith("min")?"Minimum":"Maximum");
      m.component("c").cpl(op).selection().named(op.endsWith("Steel")?"wetsteel":"wetprop");
    }
    m.component("c").variable().create("v");
    m.component("c").variable("v").set("eta","Vm-V","Metal minus local electrolyte potential vs Ag/AgCl");
    m.component("c").variable("v").set("jsteel","hull_damage*hy80(eta)");
    m.component("c").variable("v").set("jprop","prop_damage*nab(eta)");
    m.component("c").material().create("watermat","Common");
    m.component("c").material("watermat").selection().named("g_sea_dom");
    m.component("c").material("watermat").propertyGroup("def").set("electricconductivity","sigma_w");
    m.component("c").material("watermat").propertyGroup("def").set("relpermittivity","80");
    m.component("c").physics().create("ec","ConductiveMedia","g");
    m.component("c").physics("ec").selection().named("g_sea_dom");
    m.component("c").physics("ec").prop("ShapeProperty").set("order_electricpotential",2);
    inward(m,"steelpol","wetsteel","jsteel");inward(m,"proppol","wetprop","jprop");
    for(int k=1;k<=4;k++)inward(m,"src"+k,"wetanode"+k,(k<=2?"I_bow":"I_stern")+"/a"+k+"(1)");
    m.component("c").physics("ec").create("farzero","Ground",2);m.component("c").physics("ec").feature("farzero").selection().named("far");
    m.component("c").physics().create("ge","GlobalEquations");
    m.component("c").physics("ge").feature("ge1").set("name",new String[]{"Vm"});
    m.component("c").physics("ge").feature("ge1").set("equation",new String[]{"iwetSteel(jsteel)+iwetProp(jprop)+I_total"});
    m.component("c").physics("ge").feature("ge1").set("initialValueU",new String[]{"-0.52"});
    m.component("c").physics("ge").feature("ge1").set("DependentVariableQuantity","none");
    m.component("c").physics("ge").feature("ge1").set("CustomDependentVariableUnit","V");
    m.component("c").physics("ge").feature("ge1").set("SourceTermQuantity","none");
    m.component("c").physics("ge").feature("ge1").set("CustomSourceTermUnit","A");
    m.component("c").mesh().create("mesh","g");
    m.component("c").mesh("mesh").feature("size").set("custom",true);
    m.component("c").mesh("mesh").feature("size").set("hmax","domain_radius/5");
    m.component("c").mesh("mesh").feature("size").set("hmin","0.06[m]*mesh_scale");
    m.component("c").mesh("mesh").feature("size").set("hgrad",1.4);
    m.component("c").mesh("mesh").create("hullsize","Size");
    m.component("c").mesh("mesh").feature("hullsize").selection().named("obstacles");
    m.component("c").mesh("mesh").feature("hullsize").set("custom",true);
    m.component("c").mesh("mesh").feature("hullsize").set("hmax","hull_mesh*mesh_scale");
    m.component("c").mesh("mesh").feature("hullsize").set("hmaxactive",true);
    m.component("c").mesh("mesh").create("asize","Size");
    m.component("c").mesh("mesh").feature("asize").selection().named("anodes");
    m.component("c").mesh("mesh").feature("asize").set("custom",true);
    m.component("c").mesh("mesh").feature("asize").set("hmax","anode_mesh*mesh_scale");
    m.component("c").mesh("mesh").feature("asize").set("hmaxactive",true);
    m.component("c").mesh("mesh").create("propsize","Size");
    m.component("c").mesh("mesh").feature("propsize").selection().named("wetprop");
    m.component("c").mesh("mesh").feature("propsize").set("custom",true);
    m.component("c").mesh("mesh").feature("propsize").set("hmax","0.30[m]*mesh_scale");
    m.component("c").mesh("mesh").feature("propsize").set("hmaxactive",true);
    m.component("c").mesh("mesh").create("radial","SizeExpression");
    m.component("c").mesh("mesh").feature("radial").set("sizeexpr","mesh_scale*(mesh_near+mesh_growth*sqrt(x^2+y^2+(z+depth_sub)^2))");
    m.component("c").mesh("mesh").feature("radial").set("gridtype","cellsize");
    m.component("c").mesh("mesh").feature("radial").set("cellsize","8[m]");
    m.component("c").mesh("mesh").create("tet","FreeTet");
    m.component("c").mesh("mesh").feature("tet").selection().named("g_sea_dom");
    m.component("c").mesh("mesh").run();
    m.study().create("std");m.study("std").create("stat","Stationary");m.study("std").createAutoSequences("all");
    m.sol("sol1").feature("s1").set("stol",1e-7);
    m.sol("sol1").feature("s1").create("fc","FullyCoupled");
    m.sol("sol1").feature("s1").feature("fc").set("maxiter",80);
    m.sol("sol1").feature("s1").create("direct","Direct");
    m.sol("sol1").feature("s1").feature("direct").set("linsolver","pardiso");
    m.sol("sol1").feature("s1").feature("fc").set("linsolver","direct");
    for(String t:m.sol("sol1").feature("s1").feature().tags())if(m.sol("sol1").feature("s1").feature(t).getType().equals("Segregated"))m.sol("sol1").feature("s1").feature().remove(t);
    return m;
  }
  public static void main(String[] args) throws Exception {
    String variant=args!=null&&args.length>0?args[0]:"base";
    String radius=variant.equals("wide")?"1.5*("+configured("domain_radius")+")":configured("domain_radius");
    String mesh=variant.equals("base")?configured("mesh_scale"):"0.75*("+configured("mesh_scale")+")";
    Model m=build(variant,radius,mesh);
    double nominal=m.param().evaluate("I_nominal");
    double[] currents=variant.equals("base")?new double[]{0,0.5*nominal,nominal,2*nominal}:new double[]{nominal};
    for(double current:currents) {
      String tag=variant+"_"+currentTag(current)+"A";
      m.param().set("I_total",current+"[A]");
      System.out.println("SOLVING "+tag);m.sol("sol1").runAll();
      evaluate(m,tag);
      m.label("submarine_iccp_"+tag+".mph");m.save(ROOT+"/models/submarine_iccp_"+tag+".mph");
      if(variant.equals("base")&&current==nominal){plots(m);m.save(ROOT+"/models/submarine_iccp_"+tag+".mph");}
      System.out.println("SAVED "+tag);
    }
    ModelUtil.remove("SubICCP");
  }
}
