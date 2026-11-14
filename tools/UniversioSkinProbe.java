import com.mojang.authlib.GameProfile;
import com.mojang.authlib.minecraft.MinecraftProfileTexture;
import com.mojang.authlib.minecraft.MinecraftProfileTexture.Type;
import dev.latvian.mods.rhino.Context;
import dev.latvian.mods.rhino.Function;
import dev.latvian.mods.rhino.NativeJavaClass;
import dev.latvian.mods.rhino.Scriptable;
import dev.latvian.mods.rhino.ScriptableObject;
import dev.latvian.mods.rhino.mod.util.MinecraftRemapper;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.zip.GZIPInputStream;

public class UniversioSkinProbe {
    private static final String ITEM = "a378933c-23ad-4424-a48d-e77735ad8a0a1671843070430";
    private static final String PLAYER_CACHE = "de.keksuccino.fancymenu.menu.fancy.item.items.playerentity.PlayerEntityCustomizationItemContainer";

    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("Pass the path to lanmc_menu_player_skin.js");
        }
        String script = Files.readString(Path.of(args[0]));
        Context context = Context.enter();
        try (var mapping = new GZIPInputStream(Context.class.getResourceAsStream("/mm.jsmappings"))) {
            var remapper = MinecraftRemapper.load(mapping, false);
            context.setRemapper(remapper);
            Scriptable scope = context.initStandardObjects();
            var events = new Events();
            bind(context, scope, "Java", new Classes(context, scope));
            bind(context, scope, "ClientEvents", events);
            context.evaluateString(scope, script, args[0], 1, null);
            check(events.paintScreen != null, "paintScreen is registered");
            var mc = new Minecraft();
            var main = new TitleScreen();
            var model = new Model();
            Players.ELEMENT_CACHE.put(ITEM, model);
            var other = new Model();
            Players.ELEMENT_CACHE.put("other-player", other);
            fire(context, scope, events, new Object(), mc);
            check(mc.session.reads == 0, "other menu is ignored");
            model.copyClientPlayer = false;
            fire(context, scope, events, main, mc);
            check(mc.session.reads == 0, "author copy-player setting is respected");
            model.copyClientPlayer = true;
            fire(context, scope, events, main, mc);
            check(mc.session.reads == 1 && mc.skins.registrations == 0, "missing profile texture keeps defaults");
            fire(context, scope, events, main, mc);
            check(mc.session.reads == 1, "missing textures throttle repeated lookups");
            mc.session.skin = new MinecraftProfileTexture("https://localhost/skin.png", Map.of("model", "slim"));
            Thread.sleep(1050);
            fire(context, scope, events, main, mc);
            check(model.slim && mc.skins.registrations == 1, "slim launcher skin is registered once");
            check(model.slimRenderer.properties.texture.equals(mc.skins.location) &&
                  model.normalRenderer.properties.replacements == 0, "only the active FancyMenu renderer picks up the native texture");
            check(other.normalRenderer.properties.replacements == 0, "different FancyMenu player element remains at default");
            int replacements = model.slimRenderer.properties.replacements;
            fire(context, scope, events, main, mc);
            check(mc.session.reads == 2 && mc.skins.registrations == 1 &&
                    model.slimRenderer.properties.replacements == replacements, "unchanged resolved texture avoids further lookup, registration, and writes");
            model.slimRenderer.properties.texture = new Location("old");
            model.slim = false;
            fire(context, scope, events, main, mc);
            check(model.slim && model.slimRenderer.properties.texture.equals(mc.skins.location), "late FancyMenu update is corrected");
            Model recreated = new Model();
            Players.ELEMENT_CACHE.put(ITEM, recreated);
            fire(context, scope, events, main, mc);
            check(recreated.slim && recreated.slimRenderer.properties.texture.equals(mc.skins.location) &&
                    mc.skins.registrations == 1, "new FancyMenu cache element uses the cached native texture");
            context.evaluateString(scope, script, args[0], 1, null);
            var classicClient = new Minecraft();
            classicClient.session.skin = new MinecraftProfileTexture("https://localhost/skin.png", Map.of());
            var classic = new Model();
            classic.slim = true;
            Players.ELEMENT_CACHE.put(ITEM, classic);
            fire(context, scope, events, main, classicClient);
            check(!classic.slim && classic.normalRenderer.properties.texture.equals(classicClient.skins.location), "classic launcher skin uses the classic renderer");
            mapped(remapper, "net.minecraft.client.Minecraft", "m_91094_", "getUser");
            mapped(remapper, "net.minecraft.client.User", "m_92548_", "getGameProfile");
            mapped(remapper, "net.minecraft.client.Minecraft", "m_91108_", "getMinecraftSessionService");
            mapped(remapper, "net.minecraft.client.Minecraft", "m_91109_", "getSkinManager");
            mapped(remapper, "net.minecraft.client.resources.SkinManager", "m_118825_", "registerTexture", MinecraftProfileTexture.class, Type.class);
        }
    }

    private static void mapped(MinecraftRemapper mapper, String type, String srg, String expected, Class<?>... parameters) throws Exception {
        Class<?> target = Class.forName(type, false, Thread.currentThread().getContextClassLoader());
        String actual = mapper.getMappedMethod(target, target.getMethod(srg, parameters));
        check(expected.equals(actual), type + " " + srg + " maps to " + expected + " (actual " + actual + ")");
    }

    private static void bind(Context context, Scriptable scope, String name, Object value) {
        ScriptableObject.putProperty(scope, name, Context.javaToJS(context, value, scope), context);
    }

    private static void fire(Context context, Scriptable scope, Events events, Object screen, Minecraft client) {
        events.paintScreen.call(context, scope, scope, new Object[]{Context.javaToJS(context, new Paint(screen, client), scope)});
    }

    private static void check(boolean ok, String label) {
        if (!ok) throw new AssertionError(label);
        System.out.println("PASS " + label);
    }

    public static class Classes {
        private final Context context;
        private final Scriptable scope;
        Classes(Context context, Scriptable scope) { this.context = context; this.scope = scope; }
        public NativeJavaClass loadClass(String name) {
            Class<?> result = switch (name) {
                case "net.minecraft.client.gui.screens.TitleScreen" -> TitleScreen.class;
                case "com.mojang.authlib.minecraft.MinecraftProfileTexture$Type" -> Type.class;
                case PLAYER_CACHE -> Players.class;
                default -> throw new AssertionError("Unknown class " + name);
            };
            return new NativeJavaClass(context, scope, result);
        }
    }

    public static class Events {
        Function paintScreen;
        public void paintScreen(Function listener) { paintScreen = listener; }
    }

    public static class TitleScreen {}

    public static class Players {
        public static final Map<String, Model> ELEMENT_CACHE = new HashMap<>();
    }

    public static class Model {
        public boolean copyClientPlayer = true;
        public boolean slim;
        public final Renderer slimRenderer = new Renderer();
        public final Renderer normalRenderer = new Renderer();
        public Properties getActiveEntityProperties() { return (slim ? slimRenderer : normalRenderer).properties; }
    }

    public static class Renderer {
        public final Properties properties = new Properties();
    }

    public static class Properties {
        private Location texture = new Location("default");
        private int replacements;
        public Location getSkinTextureLocation() { return texture; }
        public void setSkinTextureLocation(Location newTexture) {
            this.texture = newTexture;
            ++replacements;
        }
    }

    public record Location(String texture) {}

    public static class Paint {
        public final Object screen;
        public final Minecraft mc;
        Paint(Object screen, Minecraft mc) { this.screen = screen; this.mc = mc; }
    }

    public static class Minecraft {
        private final User user = new User();
        private final Session session = new Session(user.profile);
        private final SkinManager skins = new SkinManager();
        public User getUser() { return user; }
        public Session getMinecraftSessionService() { return session; }
        public SkinManager getSkinManager() { return skins; }
    }

    public static class User {
        private final GameProfile profile = new GameProfile(UUID.fromString("b78c6471-26b9-43a2-b2a9-40dca9b53de7"), "TestPlayer");
        public GameProfile getGameProfile() { return profile; }
    }

    public static class Session {
        private final GameProfile expected;
        private MinecraftProfileTexture skin;
        private int reads;
        Session(GameProfile expected) { this.expected = expected; }
        public Map<Type, MinecraftProfileTexture> getTextures(GameProfile profile, boolean signedOnly) {
            if (profile != expected || signedOnly) throw new AssertionError("Expected own unsigned launcher profile");
            ++reads;
            return skin == null ? new HashMap<>() : new HashMap<>(Map.of(Type.SKIN, skin));
        }
    }

    public static class SkinManager {
        private final Location location = new Location("skin");
        private int registrations;
        public Location registerTexture(MinecraftProfileTexture texture, Type type) {
            if (texture == null || type != Type.SKIN) throw new AssertionError("Expected local launcher skin");
            ++registrations;
            return location;
        }
    }
}
