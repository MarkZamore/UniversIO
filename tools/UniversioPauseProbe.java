import dev.latvian.mods.rhino.Context;
import dev.latvian.mods.rhino.NativeJavaClass;
import dev.latvian.mods.rhino.Scriptable;
import dev.latvian.mods.rhino.ScriptableObject;
import dev.latvian.mods.rhino.mod.util.MinecraftRemapper;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.function.Consumer;
import java.util.zip.GZIPInputStream;

public final class UniversioPauseProbe {
    public static void main(String[] args) throws Exception {
        Context context = Context.enter();
        try (var stream = new GZIPInputStream(Context.class.getResourceAsStream("/mm.jsmappings"))) {
            var mapper = MinecraftRemapper.load(stream, false);
            context.setRemapper(mapper);
            Scriptable scope = context.initStandardObjects();
            ScriptableObject.putProperty(scope, "Java",
                    Context.javaToJS(context, new Classes(context, scope), scope), context);
            context.evaluateString(scope, Files.readString(Path.of(args[0])), args[0], 1, null);
            var stats = new Button("gui.stats", 104, 75);
            var options = new Button("menu.options", 0, 124);
            var reports = new Button("menu.playerReporting", 104, 85);
            fire(reports, stats, options);
            check(reports.x == 104 && reports.y == 124, "reports aligns with the free right slot");
            check(stats.y == 75 && options.y == 124, "other controls do not move");
            reports.y = 85;
            var lan = new Button("menu.shareToLan", 104, 124);
            fire(reports, stats, options, lan);
            check(reports.y == 85 && lan.y == 124, "occupied right slot is preserved");
            fire(stats, options, lan);
            check(lan.y == 124, "unpublished world keeps the LAN action");
            reports.y = 98;
            fire(reports, stats, options);
            check(reports.y == 98, "non-overlapping native layout stays put");
            reports.x = 144;
            reports.y = 105;
            stats.x = 144;
            stats.y = 95;
            options.y = 144;
            fire(reports, stats, options);
            check(reports.x == 144 && reports.y == 144, "coordinates follow the resized layout");
            Class<?> widget = Class.forName("net.minecraft.client.gui.components.AbstractWidget", false,
                    Thread.currentThread().getContextClassLoader());
            for (String[] field : List.of(
                    new String[]{"f_93620_", "x"}, new String[]{"f_93621_", "y"},
                    new String[]{"f_93624_", "visible"})) {
                check(field[1].equals(mapper.getMappedField(widget, widget.getField(field[0]))),
                        "Forge field mapping " + field[1]);
            }
            for (String[] method : List.of(
                    new String[]{"m_93694_", "getHeight"}, new String[]{"m_5711_", "getWidth"},
                    new String[]{"m_6035_", "getMessage"})) {
                String actual = mapper.getMappedMethod(widget, widget.getMethod(method[0]));
                check(method[1].equals(actual), "Forge method mapping " + method[1] + " = " + actual);
            }
        }
    }

    static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
        System.out.println("PASS " + message);
    }

    static void fire(Widget... widgets) {
        Forge.EVENT_BUS.listener.accept(new RenderPre(new PauseScreen(List.of(widgets))));
    }

    public record Classes(Context context, Scriptable scope) {
        public NativeJavaClass loadClass(String name) {
            Class<?> type = switch (name.substring(name.lastIndexOf('.') + 1)) {
                case "PauseScreen" -> PauseScreen.class;
                case "AbstractWidget" -> Widget.class;
                case "Button" -> Button.class;
                case "TranslatableContents" -> Translatable.class;
                case "MinecraftForge" -> Forge.class;
                case "EventPriority" -> Priority.class;
                case "ScreenEvent$Render$Pre" -> RenderPre.class;
                default -> throw new AssertionError(name);
            };
            return new NativeJavaClass(context, scope, type);
        }
    }

    public enum Priority { LOWEST }
    public static class Forge { public static final Bus EVENT_BUS = new Bus(); }
    public static class Bus {
        Consumer<RenderPre> listener;
        public void addListener(Priority priority, boolean cancelled, Class<RenderPre> event, Consumer<RenderPre> listener) {
            check(priority == Priority.LOWEST && !cancelled && event == RenderPre.class, "Forge pre-render registration");
            this.listener = listener;
        }
    }
    public record PauseScreen(List<Widget> children) {}
    public record RenderPre(PauseScreen screen) { public PauseScreen getScreen() { return screen; } }
    public record Translatable(String key) { public String getKey() { return key; } }
    public record Message(Translatable value) { public Translatable getContents() { return value; } }
    public static class Widget {
        public int x;
        public int y;
        public boolean visible = true;
        public int getWidth() { return 98; }
        public int getHeight() { return 20; }
    }
    public static class Button extends Widget {
        private final Message message;
        public Button(String key, int x, int y) {
            this.x = x;
            this.y = y;
            message = new Message(new Translatable(key));
        }
        public Message getMessage() { return message; }
    }
}
