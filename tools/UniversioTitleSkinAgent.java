import java.lang.instrument.Instrumentation;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;

/** Reads the native title model and texture on the game thread without input or transformers. */
public final class UniversioTitleSkinAgent {
    private static final String PREFIX = "lanminecraft.steamqa.";
    private static final String MC = "net.minecraft.client.Minecraft";
    private static final String TITLE = "net.minecraft.client.gui.screens.TitleScreen";
    private static final String FANCY = "de.keksuccino.fancymenu.menu.fancy.item.items.playerentity.";
    private static final String PLAYER_ITEM = "a378933c-23ad-4424-a48d-e77735ad8a0a1671843070430";
    private static final String RESOURCE = "net.minecraft.resources.ResourceLocation";
    private static final int TEXTURE_2D = 0x0de1;
    private static final int TEXTURE_BINDING_2D = 0x8069;
    private static final int TEXTURE_WIDTH = 0x1000;
    private static final int TEXTURE_HEIGHT = 0x1001;
    private static final int RGBA = 0x1908;
    private static final int UNSIGNED_BYTE = 0x1401;
    private static final int[] PIXELS = {0x3dc991ff, 0xb340e8ff, 0xff9e42ff};
    private static final int[] X = {9, 11, 14};

    private final Path game, evidence;
    private final String expectedLocation;
    private final boolean expectedSlim, negative;
    private volatile String lastObservation = "no-native-title";
    private Object client;

    public static void premain(String ignored, Instrumentation instrumentation) {
        Thread observer = new Thread(() -> {
            try {
                new UniversioTitleSkinAgent().observe(instrumentation);
            } catch (Exception error) {
                error.printStackTrace(System.err);
            }
        }, "UniversIO native skin QA");
        observer.setDaemon(true);
        observer.start();
    }

    private UniversioTitleSkinAgent() throws Exception {
        Path run = Path.of(System.getProperty(PREFIX + "run")).toRealPath();
        game = Path.of(System.getProperty(PREFIX + "game")).toRealPath();
        evidence = Path.of(System.getProperty(PREFIX + "evidence")).toRealPath();
        if (!run.getParent().getFileName().toString().equals("agent-runs") ||
                !run.getParent().getParent().getFileName().toString().equals("artifacts") ||
                !Files.isRegularFile(run.resolve("RUN.json"), LinkOption.NOFOLLOW_LINKS) ||
                !game.startsWith(run.resolve("game")) || !evidence.startsWith(run.resolve("evidence")) ||
                !System.getProperty(PREFIX + "minecraftVersion").equals("1.19.2")) {
            throw new SecurityException("Use a marked, isolated Forge 1.19.2 instance");
        }
        expectedLocation = System.getProperty(PREFIX + "fixtureSkinLocation", "");
        if (!expectedLocation.matches("minecraft:skins/[0-9a-f]{40}")) {
            throw new IllegalArgumentException("Expected a pinned synthetic skin texture location");
        }
        expectedSlim = Boolean.getBoolean(PREFIX + "fixtureSkinSlim");
        negative = Boolean.getBoolean(PREFIX + "fixtureSkinNegative");
    }

    private void observe(Instrumentation instrumentation) throws Exception {
        Path result = evidence.resolve("native-menu-skin.properties");
        try {
            long startup = System.nanoTime() + Duration.ofMinutes(7).toNanos();
            while (System.nanoTime() < startup && client == null) {
                boolean running = Thread.getAllStackTraces().values().stream().flatMap(java.util.Arrays::stream)
                        .anyMatch(frame -> frame.getClassName().equals(MC) && frame.getMethodName().equals("m_91374_"));
                if (running) {
                    for (Class<?> loaded : instrumentation.getAllLoadedClasses()) {
                        if (loaded.getName().equals(MC)) client = loaded.getMethod("m_91087_").invoke(null);
                    }
                }
                if (client == null) Thread.sleep(250);
            }
            if (client == null) throw new IllegalStateException("Minecraft client was never initialized");
            long deadline = System.nanoTime() + Duration.ofSeconds(35).toNanos();
            int consecutive = 0;
            while (System.nanoTime() < deadline) {
                CompletableFuture<Boolean> frame = new CompletableFuture<>();
                ((Executor) client).execute(() -> {
                    try {
                        frame.complete(readFrame());
                    } catch (Throwable error) {
                        frame.completeExceptionally(error);
                    }
                });
                if (frame.get(12, TimeUnit.SECONDS)) {
                    if (++consecutive >= (negative ? 14 : 4)) {
                        Files.writeString(result, "status=PASS\nmode=" + (negative ? "control" : "candidate") +
                                "\n" + lastObservation + "\n");
                        return;
                    }
                } else {
                    consecutive = 0;
                }
                Thread.sleep(250);
            }
            throw new IllegalStateException("Native title observation did not reach its expected state");
        } catch (Exception failure) {
            Files.writeString(result, "status=FAIL\nlast=" + lastObservation.replace('\n', ' ') +
                    "\nerror=" + failure.toString().replace('\n', ' ') + "\n");
            throw failure;
        } finally {
            if (client != null) {
                ((Executor) client).execute(() -> {
                    try {
                        call(client, "m_91395_");
                    } catch (ReflectiveOperationException error) {
                        error.printStackTrace(System.err);
                    }
                });
            }
        }
    }

    private boolean readFrame() throws Exception {
        Object screen = client.getClass().getField("f_91080_").get(client);
        if (screen == null || !type(TITLE).isInstance(screen) || call(client, "m_91265_") != null) return false;

        Object model = ((Map<?, ?>) type(FANCY + "PlayerEntityCustomizationItemContainer")
                .getField("ELEMENT_CACHE").get(null)).get(PLAYER_ITEM);
        if (model == null || !model.getClass().getField("copyClientPlayer").getBoolean(model) ||
                !Boolean.TRUE.equals(call(model, "shouldRender"))) {
            lastObservation = "title=ready\nplayerElement=not-visible";
            return false;
        }
        Object properties = call(model, "getActiveEntityProperties");
        boolean actualSlim = Boolean.TRUE.equals(call(properties, "isSlim"));
        Object location = call(properties, "getSkinTextureLocation");
        String locationName = location.toString();
        lastObservation = "title=ready\nplayerElement=" + PLAYER_ITEM + "\ntexture=" + locationName +
                "\nmodel=" + (actualSlim ? "slim" : "classic");
        if (negative) return !expectedLocation.equals(locationName);
        if (!expectedLocation.equals(locationName) || expectedSlim != actualSlim) return false;

        Object manager = call(client, "m_91097_");
        Object texture = manager.getClass().getMethod("m_118506_", type(RESOURCE)).invoke(manager, location);
        if (!type("net.minecraft.client.renderer.texture.HttpTexture").isInstance(texture)) return false;
        int textureId = ((Number) call(texture, "m_117963_")).intValue();
        Class<?> gl = type("org.lwjgl.opengl.GL11");
        int previous = (int) gl.getMethod("glGetInteger", int.class).invoke(null, TEXTURE_BINDING_2D);
        Method bind = gl.getMethod("glBindTexture", int.class, int.class);
        bind.invoke(null, TEXTURE_2D, textureId);
        try {
            Method size = gl.getMethod("glGetTexLevelParameteri", int.class, int.class, int.class);
            int width = (int) size.invoke(null, TEXTURE_2D, 0, TEXTURE_WIDTH);
            int height = (int) size.invoke(null, TEXTURE_2D, 0, TEXTURE_HEIGHT);
            if (width != 64 || height != 64) return false;
            ByteBuffer rgba = ByteBuffer.allocateDirect(width * height * 4);
            gl.getMethod("glGetTexImage", int.class, int.class, int.class, int.class, ByteBuffer.class)
                    .invoke(null, TEXTURE_2D, 0, RGBA, UNSIGNED_BYTE, rgba);
            String actual = "";
            for (int index = 0; index < X.length; index++) {
                int pixel = rgba.getInt((9 * width + X[index]) * 4);
                actual += String.format(Locale.ROOT, "%08x", pixel);
                if (pixel != PIXELS[index]) {
                    lastObservation += "\nmatchingPixels=" + index;
                    return false;
                }
            }
            lastObservation += "\npixels=" + actual;
            return true;
        } finally {
            bind.invoke(null, TEXTURE_2D, previous);
        }
    }

    private Class<?> type(String name) throws ClassNotFoundException {
        return Class.forName(name, false, client.getClass().getClassLoader());
    }

    private static Object call(Object target, String method) throws ReflectiveOperationException {
        return target.getClass().getMethod(method).invoke(target);
    }
}
