package lanminecraft.qa;

import java.lang.reflect.Method;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/** Read-only checks of the actual Patchouli books loaded by a Forge 1.19.2 client. */
public final class UniversioPatchouliLocaleProbe {
    private static final String BOOK_REGISTRY = "vazkii.patchouli.common.book.BookRegistry";
    private static final String CLIENT_REGISTRY = "vazkii.patchouli.client.book.ClientBookRegistry";
    private static final String BOOK_ITEM = "vazkii.patchouli.common.item.ItemModBook";
    private static final Set<String> STARTER_IDS = Set.of(
            "advancedperipherals:manual", "hexcasting:thehexbook", "squirtgun:gun_manual");
    private static final Class<?>[] NO_ARGS = {};

    private UniversioPatchouliLocaleProbe() {
    }

    /** Run on the game client thread after world join and resource loading. */
    public static Map<String, Object> check(ClassLoader gameLoader, String locale)
            throws ReflectiveOperationException {
        if (!locale.equals("en_us") && !locale.equals("ru_ru")) {
            throw new IllegalArgumentException("Unsupported UniversIO test language: " + locale);
        }
        boolean russian = locale.equals("ru_ru");
        Class<?> clientRegistry = type(gameLoader, CLIENT_REGISTRY);
        Object clientBooks = clientRegistry.getField("INSTANCE").get(null);
        expect("Patchouli language", locale, clientRegistry.getField("currentLang").get(clientBooks));
        Class<?> bookRegistry = type(gameLoader, BOOK_REGISTRY);
        Object registry = bookRegistry.getField("INSTANCE").get(null);
        Map<?, ?> books = (Map<?, ?>) bookRegistry.getField("books").get(registry);
        Class<?> component = type(gameLoader, "net.minecraft.network.chat.Component");
        Method getString = component.getMethod("getString");
        Method translate = component.getMethod("m_237115_", String.class);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("locale", locale);
        result.put("universio", checkBook(books, getString, translate, "patchouli:universutil",
                "patchouli:asgd", russian ? "Мультиблоки" : "Multiblocks",
                russian ? "Справочник по предметам мода Universutil" : "Help Regarding Items From The Universutil Mod"));
        result.put("universioAsgdText", checkTextPage(gameLoader,
                checkEntry(books, getString, "patchouli:universutil", "patchouli:asgd/asgd",
                        russian ? "Установка ASGD" : "ASGD"),
                russian ? "Установка генерации искусственной сверхновой (ASGD)"
                        : "Artificial Supernova Generation Device or the ASGD"));
        result.put("advancedPeripherals", checkBook(books, getString, translate, "advancedperipherals:manual",
                "advancedperipherals:peripherals", russian ? "Периферийные устройства" : "Peripherals",
                russian ? "В справочнике собраны основные сведения" : "This manual provides basic information"));
        result.put("squirtgun", checkBook(books, getString, translate, "squirtgun:gun_manual",
                "squirtgun:phials", russian ? "Флаконы" : "Phials",
                russian ? "Здесь начинается руководство." : "You are here"));
        result.put("hexNotebook", checkBook(books, getString, translate, "hexcasting:thehexbook",
                "hexcasting:basics", russian ? "Вводный урок" : "Getting Started",
                russian ? "Кажется" : "I seem to have discovered"));
        String staffTitle = russian ? "Посох" : "Staff";
        checkEntry(books, getString, "hexcasting:thehexbook", "hexcasting:items/staff", staffTitle);
        result.put("hexStaffEntry", staffTitle);
        result.put("botania", checkBook(books, getString, translate, "botania:lexicon",
                "botania:alfhomancy", russian ? "Эльфомания" : "Alfhomancy",
                russian ? "Магия, Технологии. Естество." : "Magic, Tech. Naturally."));
        String bloodPendantTitle = russian ? "Кровавый кулон" : "Tainted Blood Pendant";
        checkEntry(books, getString, "botania:lexicon", "botania:baubles/blood_pendant", bloodPendantTitle);
        result.put("botaniaBloodPendant", bloodPendantTitle);
        result.put("starterBooks", checkStarterBooks(gameLoader, getString, russian));
        return result;
    }

    private static Map<String, Object> checkBook(Map<?, ?> books, Method getString, Method translate,
            String bookId, String categoryId, String categoryName, String landingPrefix)
            throws ReflectiveOperationException {
        Object book = atId(books, bookId);
        Object contents = invoke(book, "getContents");
        if (Boolean.TRUE.equals(invoke(contents, "isErrored"))) {
            throw new IllegalStateException("Patchouli could not load " + bookId,
                    (Exception) invoke(contents, "getException"));
        }
        Map<?, ?> categories = (Map<?, ?>) contents.getClass().getField("categories").get(contents);
        Map<?, ?> entries = (Map<?, ?>) contents.getClass().getField("entries").get(contents);
        if (entries.isEmpty()) {
            throw new IllegalStateException("No Patchouli entries loaded for " + bookId);
        }
        Object category = atId(categories, categoryId);
        String activeName = expect(bookId + " category title", categoryName,
                getString.invoke(invoke(category, "getName")));
        String landingKey = (String) book.getClass().getField("landingText").get(book);
        String activeLanding = (String) getString.invoke(translate.invoke(null, landingKey));
        if (!activeLanding.startsWith(landingPrefix)) {
            throw new IllegalStateException(bookId + " landing text expected prefix ["
                    + landingPrefix + "] but got [" + activeLanding + "]");
        }
        return Map.of("id", bookId, "category", activeName, "entries", entries.size(), "landing", activeLanding);
    }

    private static Object checkEntry(Map<?, ?> books, Method getString, String bookId, String entryId,
            String title) throws ReflectiveOperationException {
        Object contents = invoke(atId(books, bookId), "getContents");
        Map<?, ?> entries = (Map<?, ?>) contents.getClass().getField("entries").get(contents);
        Object entry = atId(entries, entryId);
        expect(entryId + " title", title, getString.invoke(invoke(entry, "getName")));
        return entry;
    }

    private static String checkTextPage(ClassLoader gameLoader, Object entry, String prefix)
            throws ReflectiveOperationException {
        Object firstPage = ((List<?>) invoke(entry, "getPages")).get(0);
        Class<?> textPage = type(gameLoader, "vazkii.patchouli.client.book.page.abstr.PageWithText");
        var textField = textPage.getDeclaredField("text");
        textField.setAccessible(true);
        Object text = textField.get(firstPage);
        String renderedInput = (String) type(gameLoader, "vazkii.patchouli.api.IVariable")
                .getMethod("asString").invoke(text);
        if (!renderedInput.startsWith(prefix)) {
            throw new IllegalStateException("UniversIO ASGD first page expected prefix ["
                    + prefix + "] but got [" + renderedInput + "]");
        }
        return renderedInput;
    }

    private static Map<String, String> checkStarterBooks(ClassLoader gameLoader, Method getString, boolean russian)
            throws ReflectiveOperationException {
        Object client = type(gameLoader, "net.minecraft.client.Minecraft").getMethod("m_91087_").invoke(null);
        Object player = client.getClass().getField("f_91074_").get(client);
        Object inventory = invoke(player, "m_150109_");
        Class<?> bookItem = type(gameLoader, BOOK_ITEM);
        Method getBook = bookItem.getMethod("getBook", type(gameLoader, "net.minecraft.world.item.ItemStack"));
        int slots = (int) invoke(inventory, "m_6643_");
        Map<String, String> granted = new TreeMap<>();
        for (int slot = 0; slot < slots; slot++) {
            Object stack = invoke(inventory, "m_8020_", new Class<?>[]{int.class}, slot);
            if (!bookItem.isInstance(invoke(stack, "m_41720_"))) {
                continue;
            }
            Object book = getBook.invoke(null, stack);
            if (book != null) {
                String id = book.getClass().getField("id").get(book).toString();
                if (STARTER_IDS.contains(id)) {
                    granted.put(id, (String) getString.invoke(invoke(stack, "m_41786_")));
                }
            }
        }
        if (!granted.keySet().equals(STARTER_IDS)) {
            throw new IllegalStateException("Expected starter Patchouli books " + STARTER_IDS
                    + " but found " + granted.keySet());
        }
        expect("granted Advanced Peripherals book", "Advanced Peripherals", granted.get("advancedperipherals:manual"));
        expect("granted Hex Notebook", russian ? "Рунный блокнот" : "Hex Notebook", granted.get("hexcasting:thehexbook"));
        expect("granted Squirtgun manual",
                russian ? "Руководство по водяному пистолету" : "Squirtgun Manual", granted.get("squirtgun:gun_manual"));
        return granted;
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

    private static Object atId(Map<?, ?> registry, String id) {
        for (var entry : registry.entrySet()) {
            if (entry.getKey().toString().equals(id)) {
                return entry.getValue();
            }
        }
        throw new IllegalStateException("Missing Patchouli ID " + id);
    }

    private static String expect(String label, String expected, Object actual) {
        if (!expected.equals(actual)) {
            throw new IllegalStateException(label + " expected [" + expected + "] but got [" + actual + "]");
        }
        return expected;
    }
}
