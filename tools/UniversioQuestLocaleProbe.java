package lanminecraft.qa;

import java.lang.reflect.Array;
import java.lang.reflect.Method;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Read-only check of the synchronized FTB Quests data in a disposable Forge 1.19.2 client. */
public final class UniversioQuestLocaleProbe {
    private static final String QUEST_FILE = "dev.ftb.mods.ftbquests.client.ClientQuestFile";
    private static final String BOOK_ITEM = "dev.ftb.mods.ftbquests.item.QuestBookItem";
    private static final long INTRO_CHAPTER = Long.parseUnsignedLong("21BCD11F7C78692E", 16);
    private static final long UNIVERSE_CHAPTER = Long.parseUnsignedLong("4DE949A43712640D", 16);
    private static final long TIPS_QUEST = Long.parseUnsignedLong("0325F0340C37E5AE", 16);
    private static final Class<?>[] QUEST_ID = {long.class};
    private static final Class<?>[] NO_ARGS = {};

    private UniversioQuestLocaleProbe() {
    }

    /** Run on the game client thread after login and quest data synchronization. */
    public static Map<String, Object> check(ClassLoader gameLoader, String locale)
            throws ReflectiveOperationException {
        if (!locale.equals("en_us") && !locale.equals("ru_ru")) {
            throw new IllegalArgumentException("Unsupported UniversIO test language: " + locale);
        }
        boolean russian = locale.equals("ru_ru");
        Object client = type(gameLoader, "net.minecraft.client.Minecraft")
                .getMethod("m_91087_").invoke(null);
        Object languageManager = invoke(client, "m_91102_");
        Object language = invoke(languageManager, "m_118983_");
        String activeLocale = (String) invoke(language, "getCode");
        expect("game language", locale, activeLocale);

        Class<?> clientQuestFile = type(gameLoader, QUEST_FILE);
        if (!Boolean.TRUE.equals(clientQuestFile.getMethod("exists").invoke(null))) {
            throw new IllegalStateException("FTB Quests has not finished syncing to this client");
        }
        Object quests = clientQuestFile.getField("INSTANCE").get(null);
        Object intro = invoke(quests, "getChapter", QUEST_ID, INTRO_CHAPTER);
        Object universe = invoke(quests, "getChapter", QUEST_ID, UNIVERSE_CHAPTER);
        Object tips = invoke(quests, "getQuest", QUEST_ID, TIPS_QUEST);
        Class<?> component = type(gameLoader, "net.minecraft.network.chat.Component");
        Method getString = component.getMethod("getString");
        Method parseRawText = type(gameLoader, "dev.ftb.mods.ftbquests.util.TextUtils")
                .getMethod("parseRawText", String.class);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("locale", activeLocale);
        result.put("introChapter", expect("introduction chapter",
                russian ? "Справка" : "Informatica",
                getString.invoke(invoke(intro, "getTitle"))));
        List<?> universeSubtitles = (List<?>) universe.getClass().getField("subtitle").get(universe);
        Object universeSubtitle = parseRawText.invoke(null, universeSubtitles.get(0));
        result.put("universeSubtitle", expect("universe chapter subtitle",
                russian ? "CC: Новая вселенная" : "CC: A New Universe",
                getString.invoke(universeSubtitle)));
        result.put("tipsTitle", expect("tips quest title",
                russian ? "Важная информация" : "Important Information",
                getString.invoke(invoke(tips, "getTitle"))));
        result.put("tipsSubtitle", expect("tips quest subtitle",
                russian ? "Прочтите!" : "Read Me !",
                getString.invoke(invoke(tips, "getSubtitle"))));
        Object description = invoke(tips, "getDescription");
        result.put("tipsFirstLine", expect("tips quest first line",
                russian ? "+ Ultimine работает, только если вы держите инструмент."
                        : "+ You Can Only Use Ultimine While Holding A Tool",
                getString.invoke(Array.get(description, 0))));

        Object player = client.getClass().getField("f_91074_").get(client);
        Object inventory = invoke(player, "m_150109_");
        Class<?> bookItem = type(gameLoader, BOOK_ITEM);
        int slots = (int) invoke(inventory, "m_6643_");
        for (int slot = 0; slot < slots; slot++) {
            Object stack = invoke(inventory, "m_8020_", new Class<?>[]{int.class}, slot);
            if (bookItem.isInstance(invoke(stack, "m_41720_"))) {
                result.put("questBookName", expect("granted book name",
                        russian ? "Книга квестов" : "Quest Book",
                        getString.invoke(invoke(stack, "m_41786_"))));
                return result;
            }
        }
        throw new IllegalStateException("First-join quest book absent from the test player's inventory");
    }

    private static Class<?> type(ClassLoader loader, String name) throws ClassNotFoundException {
        return Class.forName(name, false, loader);
    }

    private static Object invoke(Object target, String name) throws ReflectiveOperationException {
        return invoke(target, name, NO_ARGS);
    }

    private static Object invoke(Object target, String name, Class<?>[] parameters, Object... arguments)
            throws ReflectiveOperationException {
        return target.getClass().getMethod(name, parameters).invoke(target, arguments);
    }

    private static String expect(String label, String expected, Object actual) {
        if (!expected.equals(actual)) {
            throw new IllegalStateException(label + " expected [" + expected + "] but got [" + actual + "]");
        }
        return expected;
    }
}
