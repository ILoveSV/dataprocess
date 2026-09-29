import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

/** Public-scale generic hull; prescribed balanced currents, not an actual vessel signature. */
public class GenericSubmarineDC {
  static final String OUT = "C:/Users/17584/Documents/ALearning/Project/tools/DataProcess/research/01_vessel_background/comsol";

  static void boxSelection(Model m, String tag, int dim, double[] lo, double[] hi) {
    m.component("c").selection().create(tag, "Box");
    m.component("c").selection(tag).set("entitydim", dim);
    m.component("c").selection(tag).set("condition", "inside");
    String[] axes = {"x", "y", "z"};
    for (int k=0;k<3;k++) {
      m.component("c").selection(tag).set(axes[k]+"min", lo[k]);
      m.component("c").selection(tag).set(axes[k]+"max", hi[k]);
    }
  }

  static void table(Model m, String tag, String type, String dataset, String[] expr, String path) throws Exception {
    m.result().numerical().create(tag, type);
    if (dataset != null) m.result().numerical(tag).set("data", dataset);
    m.result().numerical(tag).set("expr", expr);
    m.result().table().create(tag+"t", "Table");
    m.result().numerical(tag).set("table", tag+"t");
    m.result().numerical(tag).setResult();
    m.result().table(tag+"t").save(path);
  }

  static void run(String name, double radius, double localSize) throws Exception {
    boolean benchmark=name.equals("benchmark");
    Model m = ModelUtil.create("Sub");
    m.label(name+".mph");
    m.title("Generic 50 m submerged hull: prescribed current DC transfer");
    m.description("Length and depth motivated by Schaefer et al. 2019. Beam and source distributions are explicit assumptions. No real-class calibration, no polarization solution, no sensor/detection model. Water EC and air ES are coupled one way at the flat water surface.");
    m.param().set("L", "50[m]");
    m.param().set("B", "6[m]");
    m.param().set("depth_sub", "20[m]");
    m.param().set("sigma_w", "4[S/m]");
    m.param().set("Iref", "1[A]", "Normalization only, not known vessel current");
    m.param().set("domain_radius",radius+"[m]");
    m.param().set("mesh_scale",Double.toString(localSize/1.2));
    m.component().create("c", true);
    m.component("c").geom().create("g", 3);
    m.component("c").geom("g").lengthUnit("m");
    for (String tag : new String[]{"water", "air"}) {
      m.component("c").geom("g").create(tag, "Block");
      m.component("c").geom("g").feature(tag).set("size", new double[]{2*radius,2*radius,radius});
      m.component("c").geom("g").feature(tag).set("pos", new double[]{-radius,-radius,tag.equals("water")?-radius:0});
      m.component("c").geom("g").feature(tag).set("selresult",true);
    }
    m.component("c").geom("g").create("hull", "Ellipsoid");
    m.component("c").geom("g").feature("hull").set("semiaxes", new String[]{"L/2","B/2","B/2"});
    m.component("c").geom("g").feature("hull").set("pos", new String[]{"0","0","-depth_sub"});
    m.component("c").geom("g").create("sea", "Difference");
    m.component("c").geom("g").feature("sea").selection("input").set("water");
    m.component("c").geom("g").feature("sea").selection("input2").set("hull");
    m.component("c").geom("g").feature("sea").set("selresult",true);
    m.component("c").geom("g").run();
    boxSelection(m,"hullb",2,new double[]{-25.1,-3.1,-23.1},new double[]{25.1,3.1,-16.9});
    boxSelection(m,"surface",2,new double[]{-radius-.1,-radius-.1,-.001},new double[]{radius+.1,radius+.1,.001});
    for (String tag : new String[]{"waterouter","airouter"}) {
      m.component("c").selection().create(tag,"Adjacent");
      m.component("c").selection(tag).set("entitydim",3);
      m.component("c").selection(tag).set("outputdim",2);
      m.component("c").selection(tag).set("input",new String[]{tag.equals("waterouter")?"g_sea_dom":"g_air_dom"});
    }
    for (String tag : new String[]{"waterfar","airfar"}) {
      m.component("c").selection().create(tag,"Difference");
      m.component("c").selection(tag).set("entitydim",2);
      m.component("c").selection(tag).set("add", new String[]{tag.equals("waterfar")?"waterouter":"airouter"});
      m.component("c").selection(tag).set("subtract",tag.equals("waterfar")?new String[]{"hullb","surface"}:new String[]{"surface"});
    }
    for (String tag : new String[]{"hullint","farint"}) {
      m.component("c").cpl().create(tag,"Integration");
      m.component("c").cpl(tag).selection().geom("g",2);
      m.component("c").cpl(tag).selection().named(tag.equals("hullint")?"hullb":"waterfar");
      m.component("c").cpl(tag).set("intorder",6);
    }
    m.component("c").variable().create("v");
    m.component("c").variable("v").set("wp", "exp(-((x-12[m])/4[m])^2)");
    m.component("c").variable("v").set("wm", "exp(-((x+20[m])/3[m])^2)");
    m.component("c").variable("v").set("jin", "Iref*(wp/hullint(wp)-wm/hullint(wm))");
    // Analytic point pair inside the excluded hull provides a manufactured BC check.
    for(String tag:new String[]{"rp","rm","ip","im"}) {
      String sx=(tag.equals("rp")||tag.equals("ip"))?"x-5[m]":"x+5[m]";
      String sz=tag.startsWith("r")?"z+depth_sub":"z-depth_sub";
      m.component("c").variable("v").set(tag,"sqrt(("+sx+")^2+y^2+("+sz+")^2)");
    }
    m.component("c").variable("v").set("phiw_exact","Iref/(4*pi*sigma_w)*(1/rp-1/rm+1/ip-1/im)");
    m.component("c").variable("v").set("phia_exact","Iref/(2*pi*sigma_w)*(1/rp-1/rm)");
    if(benchmark) m.component("c").variable("v").set("jin","sigma_w*(d(phiw_exact,x)*nx+d(phiw_exact,y)*ny+d(phiw_exact,z)*nz)");
    for (String tag : new String[]{"matw","mata"}) {
      m.component("c").material().create(tag,"Common");
      m.component("c").material(tag).selection().named(tag.equals("matw")?"g_sea_dom":"g_air_dom");
      m.component("c").material(tag).propertyGroup("def").set("electricconductivity",tag.equals("matw")?"sigma_w":"0[S/m]");
      m.component("c").material(tag).propertyGroup("def").set("relpermittivity",tag.equals("matw")?"80":"1");
    }
    m.component("c").physics().create("ec","ConductiveMedia","g");
    m.component("c").physics("ec").prop("ShapeProperty").set("order_electricpotential",2);
    m.component("c").physics("ec").selection().named("g_sea_dom");
    m.component("c").physics("ec").create("src","NormalCurrentDensity",2);
    m.component("c").physics("ec").feature("src").selection().named("hullb");
    m.component("c").physics("ec").feature("src").set("nJ","jin");
    m.component("c").physics("ec").create("far",benchmark?"ElectricPotential":"Ground",2);
    m.component("c").physics("ec").feature("far").selection().named("waterfar");
    if(benchmark)m.component("c").physics("ec").feature("far").set("V0","phiw_exact");
    m.component("c").physics().create("es","Electrostatics","g");
    m.component("c").physics("es").prop("ShapeProperty").set("order_electricpotential",2);
    m.component("c").physics("es").selection().named("g_air_dom");
    m.component("c").physics("es").field("electricpotential").field("Va");
    m.component("c").physics("es").field("electricpotential").component(new String[]{"Va"});
    m.component("c").physics("es").create("wl","ElectricPotential",2);
    m.component("c").physics("es").feature("wl").selection().named("surface");
    m.component("c").physics("es").feature("wl").set("V0","V");
    m.component("c").physics("es").create("far",benchmark?"ElectricPotential":"Ground",2);
    m.component("c").physics("es").feature("far").selection().named("airfar");
    if(benchmark)m.component("c").physics("es").feature("far").set("V0","phia_exact");
    m.component("c").mesh().create("mesh","g");
    m.component("c").mesh("mesh").feature("size").set("custom",true);
    m.component("c").mesh("mesh").feature("size").set("hmax",radius/5);
    m.component("c").mesh("mesh").feature("size").set("hmin",localSize/3);
    m.component("c").mesh("mesh").feature("size").set("hgrad",1.35);
    m.component("c").mesh("mesh").create("hs","Size");
    m.component("c").mesh("mesh").feature("hs").selection().geom("g",2);
    m.component("c").mesh("mesh").feature("hs").selection().named("hullb");
    m.component("c").mesh("mesh").feature("hs").set("custom",true);
    m.component("c").mesh("mesh").feature("hs").set("hmax",localSize);
    m.component("c").mesh("mesh").feature("hs").set("hmaxactive",true);
    m.component("c").mesh("mesh").create("radial","SizeExpression");
    m.component("c").mesh("mesh").feature("radial").set("sizeexpr","mesh_scale*(2[m]+0.08*sqrt(x^2+y^2+(z+depth_sub)^2))");
    m.component("c").mesh("mesh").feature("radial").set("gridtype","cellsize");
    m.component("c").mesh("mesh").feature("radial").set("cellsize","8[m]");
    m.component("c").mesh("mesh").create("tet","FreeTet");
    m.component("c").mesh("mesh").run();
    m.study().create("std");
    m.study("std").create("stat","Stationary");
    m.study("std").createAutoSequences("all");
    m.sol("sol1").feature("s1").create("fc1","FullyCoupled");
    m.sol("sol1").feature("s1").set("stol",1e-8);
    for(String tag:m.sol("sol1").feature("s1").feature().tags()) {
      if(m.sol("sol1").feature("s1").feature(tag).getType().equals("Segregated"))
        m.sol("sol1").feature("s1").feature().remove(tag);
    }
    m.sol("sol1").runAll();
    table(m,"audit","EvalGlobal",null,new String[]{"hullint(jin)","hullint(Iref*wp/hullint(wp))","hullint(Iref*wm/hullint(wm))","hullint(x*jin)","hullint(y*jin)","hullint(z*jin)","farint(ec.Jx*nx+ec.Jy*ny+ec.Jz*nz)","hullint(ec.Jx*nx+ec.Jy*ny+ec.Jz*nz+jin)","hullint(x*jin-sigma_w*V*nx)","hullint(y*jin-sigma_w*V*ny)","hullint(z*jin-sigma_w*V*nz)"},OUT+"/"+name+"_audit.csv");
    for (String medium : new String[]{"water","air"}) {
      String ds=medium+"line";
      int n=61;
      double[] x=new double[n],y=new double[n],z=new double[n];
      for(int k=0;k<n;k++){x[k]=-150+5*k;z[k]=medium.equals("water")?-65:25;}
      m.result().dataset().create(ds,"CutPoint3D");
      m.result().dataset(ds).set("pointx",x);m.result().dataset(ds).set("pointy",y);m.result().dataset(ds).set("pointz",z);
      String phy=medium.equals("water")?"ec":"es";
      table(m,medium+"eval","EvalPoint",ds,new String[]{"x","y","z",medium.equals("water")?"V":"Va",phy+".Ex",phy+".Ey",phy+".Ez",phy+".normE"},OUT+"/"+name+"_"+medium+"_line.csv");
      ds=medium+"side";
      double[] offsets={10,20,30,50,75,100};x=new double[offsets.length];z=new double[offsets.length];
      for(int k=0;k<z.length;k++)z[k]=medium.equals("water")?-20:1;
      m.result().dataset().create(ds,"CutPoint3D");
      m.result().dataset(ds).set("pointx",x);m.result().dataset(ds).set("pointy",offsets);m.result().dataset(ds).set("pointz",z);
      table(m,medium+"sideeval","EvalPoint",ds,new String[]{"x","y","z",medium.equals("water")?"V":"Va",phy+".Ex",phy+".Ey",phy+".Ez",phy+".normE"},OUT+"/"+name+"_"+medium+"_side.csv");
    }
    m.save(OUT+"/"+name+".mph");
    System.out.println("DONE "+name);
    ModelUtil.remove("Sub");
  }

  public static void main(String[] args) throws Exception {
    run("base",500,1.8);
    run("fine",500,1.2);
    run("wide",750,1.2);
    run("benchmark",500,1.2);
  }
}
