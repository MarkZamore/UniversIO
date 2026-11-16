import dev.latvian.mods.rhino.Context;
import dev.latvian.mods.rhino.NativeJavaClass;
import dev.latvian.mods.rhino.Scriptable;
import dev.latvian.mods.rhino.ScriptableObject;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import net.minecraftforge.eventbus.EventBus;
import net.minecraftforge.eventbus.api.BusBuilder;
import net.minecraftforge.eventbus.api.Event;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.eventbus.api.IEventListener;

public final class UniversioInventoryHudProbe {
    private static final String NOTICE_CLASS = "dlovin.inventoryhud.events.UpdateNotificationEvent";

    public static void main(String[] args) throws Exception {
        var notice = Class.forName(NOTICE_CLASS).getConstructor().newInstance();
        var other = new UnrelatedListener();
        var bus = Forge.EVENT_BUS;
        // ModLauncher injects the no-arg listener-list constructor into Forge
        // events. In a standalone JVM use a probe event with the actual HUD
        // listener as its registry key.
        var register = EventBus.class.getDeclaredMethod("addToListeners",
                Object.class, Class.class, IEventListener.class, EventPriority.class);
        register.setAccessible(true);
        register.invoke(bus, notice, ProbeJoin.class, (IEventListener) event -> ((ProbeJoin) event).called = true,
                EventPriority.NORMAL);
        register.invoke(bus, other, ScreenInitPost.class, (IEventListener) event -> other.calls++,
                EventPriority.NORMAL);
        var registry = EventBus.class.getDeclaredField("listeners");
        registry.setAccessible(true);
        var listeners = (Map<?, ?>) registry.get(bus);
        require(listeners.containsKey(notice), "Inventory HUD+ registers a notice instance");

        Context context = Context.enter();
        Scriptable scope = context.initStandardObjects();
        ScriptableObject.putProperty(scope, "Java",
                Context.javaToJS(context, new Classes(context, scope), scope), context);
        context.evaluateString(scope, "var console = {warn: (message) => { throw Error(message) }}",
                "probe console", 1, null);
        context.evaluateString(scope, Files.readString(Path.of(args[0])), args[0], 1, null);

        bus.post(new ScreenInitPost(new Object()));
        var before = new ProbeJoin();
        bus.post(before);
        require(listeners.containsKey(notice) && before.called, "unrelated screen keeps the pending notice");
        bus.post(new ScreenInitPost(new TitleScreen()));
        var after = new ProbeJoin();
        bus.post(after);
        require(!listeners.containsKey(notice) && !after.called, "first title screen removes the Inventory HUD+ notice");
        bus.post(new ScreenInitPost(new TitleScreen()));
        require(listeners.containsKey(other) && other.calls == 3, "unrelated listeners keep receiving events");
    }

    private static void require(boolean result, String label) {
        if (!result) throw new AssertionError(label);
        System.out.println("PASS " + label);
    }

    public record Classes(Context context, Scriptable scope) {
        public NativeJavaClass loadClass(String name) throws ClassNotFoundException {
            Class<?> type = switch (name) {
                case "net.minecraftforge.common.MinecraftForge" -> Forge.class;
                case "net.minecraftforge.eventbus.EventBus" -> EventBus.class;
                case "net.minecraftforge.eventbus.api.EventPriority" -> EventPriority.class;
                case "net.minecraftforge.client.event.ScreenEvent$Init$Post" -> ScreenInitPost.class;
                case "net.minecraft.client.gui.screens.TitleScreen" -> TitleScreen.class;
                case NOTICE_CLASS -> Class.forName(name);
                default -> throw new AssertionError(name);
            };
            return new NativeJavaClass(context, scope, type);
        }
    }

    public static final class Forge {
        public static final IEventBus EVENT_BUS = BusBuilder.builder().build();
    }

    public static final class TitleScreen {}

    public static final class ProbeJoin extends Event {
        boolean called;
    }

    public static final class ScreenInitPost extends Event {
        private final Object screen;
        public ScreenInitPost() { this(null); }
        ScreenInitPost(Object screen) { this.screen = screen; }
        public Object getScreen() { return screen; }
    }

    public static final class UnrelatedListener {
        int calls;
    }
}
