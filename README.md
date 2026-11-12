# UniversIO

Подготовка сборки 5.3 для LANMinecraft. [Авторский клиентский выпуск](https://www.curseforge.com/minecraft/modpacks/universio/files/5035806)

`tools/upstream-client-lock.json` фиксирует SHA256 и размер оригинального ZIP, ссылки на официальный источник, записи зависимостей и SHA256 файлов внутри авторских overrides. Minecraft и загрузчик взяты из оригинального манифеста. Java в `portable-pack.json` соответствует выбору текущего лаунчера для этой версии Minecraft и проверяется при запуске.

## Восстановление авторского клиента

Закреплённый авторский клиент CurseForge использует project ID 735681 и file ID 5035806.
Для подготовки текущего кандидата из корня LANMinecraft запустите:

```powershell
python -B tools/PackData/CurseForge/release_overlay.py stage --pack-source LocalSources/UniversIO --output $stage
```

`tools/overlay.json` сохраняет политику открытия мира через Steam. Для нового авторского выпуска снимите отдельную квитанцию через `prepare.py --client-only` и проверьте её командой `release_overlay.py review-update`. При изменении защищённого входа пересмотрите рецепт и закрепите новые точные байты. После нативной проверки сохраните полный `tools/upstream-lock.json` и выполните `release_overlay.py verify` по готовому манифесту.

`tools/curseforge-fallbacks.json` закрепляет три обязательные зависимости с пустыми метаданными CurseForge. Project ID и file ID взяты из авторского `manifest.json`, имена проектов сверены по `modlist.html` того же экспорта. Полные файлы получены с официального CDN по точным file ID.

- Almost Unified `633823/4886620` совпал по SHA256 и CRC32 `d44e19d1` с `mods/almostunified-forge-1.19.2-0.7.2.jar` из авторского серверного архива 5.3. [Серверный архив UniversIO 5.3](https://www.curseforge.com/minecraft/modpacks/universio/files/5035809)
- Tiny Item Animations `808006/4331279` совпал побайтно с авторским выпуском Forge `C5JsLyaK` на Modrinth. Авторские заметки объясняют его отсутствие в серверном архиве. [Авторский выпуск Tiny Item Animations](https://modrinth.com/mod/tiny-item-animations/version/C5JsLyaK)
- Durability101 `325020/3829751` получен с официального CDN по ID и имени закреплённого файла. Размер 4 112 байт, SHA1 `4545850709df2cccc96d9c8540a8563f1d1c08b1`. Файл отсутствует в серверном архиве. [Официальный проект Durability101](https://www.curseforge.com/minecraft/mc-mods/durability101)

## Публикация

Условия авторского источника — All Rights Reserved.

Пользователь подтвердил наличие разрешения на перезалив. Публикация следует после проверки полного состава и нативной приёмки.
