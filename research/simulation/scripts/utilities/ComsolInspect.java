import com.comsol.model.*;
import com.comsol.model.util.*;

public class ComsolInspect {
    private static String safeLabel(ModelEntity entity) {
        try {
            String label = entity.label();
            return label == null ? "" : label;
        } catch (Throwable t) {
            return "";
        }
    }

    private static void printTags(String title, Object list) {
        System.out.println("[" + title + "]");
        try {
            String[] tags = (String[]) list.getClass().getMethod("tags").invoke(list);
            if (tags.length == 0) {
                System.out.println("  (none)");
                return;
            }
            for (String tag : tags) {
                Object entityObject = list.getClass().getMethod("get", String.class).invoke(list, tag);
                ModelEntity entity = (ModelEntity) entityObject;
                System.out.println("  " + tag + " | " + safeLabel(entity));
            }
        } catch (Throwable t) {
            System.out.println("  ERROR: " + t.getMessage());
        }
    }

    private static void printParam(Model model) {
        System.out.println("[parameters]");
        try {
            String[] names = model.param().varnames();
            if (names.length == 0) {
                System.out.println("  (none)");
                return;
            }
            for (String name : names) {
                String value = "";
                String descr = "";
                try { value = model.param().get(name); } catch (Throwable ignored) {}
                try { descr = model.param().descr(name); } catch (Throwable ignored) {}
                System.out.println("  " + name + " = " + value + (descr.isEmpty() ? "" : " | " + descr));
            }
        } catch (Throwable t) {
            System.out.println("  ERROR: " + t.getMessage());
        }
    }

    private static void printComponentDetails(Model model) {
        try {
            for (String compTag : model.component().tags()) {
                ModelNode comp = model.component(compTag);
                System.out.println("[component " + compTag + " physics]");
                printTags("", comp.physics());
                System.out.println("[component " + compTag + " mesh]");
                printTags("", comp.mesh());
                System.out.println("[component " + compTag + " materials]");
                printTags("", comp.material());
                System.out.println("[component " + compTag + " selections]");
                printTags("", comp.selection());
                System.out.println("[component " + compTag + " geometry]");
                printTags("", comp.geom());
            }
        } catch (Throwable t) {
            System.out.println("[component details] ERROR: " + t.getMessage());
        }
    }

    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("Usage: ComsolInspect <model.mph>");
            System.exit(2);
        }
        try {
            ModelUtil.initStandalone(false);
            Model model = ModelUtil.load("inspect", args[0]);
            System.out.println("MODEL_FILE=" + args[0]);
            System.out.println("MODEL_LABEL=" + safeLabel(model));
            printParam(model);
            printTags("components", model.component());
            printComponentDetails(model);
            printTags("studies", model.study());
            printTags("solvers", model.sol());
            printTags("datasets", model.result().dataset());
            printTags("plots", model.result());
            printTags("exports", model.result().export());
            printTags("derived values", model.result().numerical());
            ModelUtil.remove("inspect");
        } catch (Throwable t) {
            t.printStackTrace();
            System.exit(1);
        }
    }
}
