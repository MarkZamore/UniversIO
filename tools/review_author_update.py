"""Check UniversIO's author menu layouts before invoking shared archive review."""

import argparse
import json
from pathlib import Path
import sys

from multiplayer_warning import load_option


PACK = Path(__file__).resolve().parents[1]
MENU_PATH = "config/fancymenu/customization/main_menu.txt"
MENU_SIZE = 4965
MENU_SHA256 = "47d46f7befbad3abf5ea07123feb507d06e896fec1dcc91072fe8f500387770a"


def verify_title_menu(author_lock):
    menus = [row for row in author_lock["overrides"] if row["path"].casefold() == MENU_PATH]
    if len(menus) != 1 or (menus[0]["path"], menus[0]["sizeBytes"], menus[0]["sha256"]) != (
        MENU_PATH, MENU_SIZE, MENU_SHA256,
    ):
        raise ValueError(f"Review required for changed, missing or duplicate author title layout: {MENU_PATH}")


PAUSE_LAYOUT = "config/fancymenu/customization/pause_screen.txt"
PAUSE_SIZE = 1776
PAUSE_SHA256 = "baebb05cc5b6f0e5b747cc47854725270512ab3a9b450a0d4d60274b090a84bc"


def verify_pause_menu(author_lock):
    menus = [row for row in author_lock["overrides"] if row["path"].casefold() == PAUSE_LAYOUT]
    if len(menus) != 1 or (menus[0]["path"], menus[0]["sizeBytes"], menus[0]["sha256"]) != (
        PAUSE_LAYOUT, PAUSE_SIZE, PAUSE_SHA256,
    ):
        raise ValueError(f"Review required for changed, missing or duplicate author pause layout: {PAUSE_LAYOUT}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher-source", type=Path, required=True)
    parser.add_argument("--candidate-lock", type=Path, required=True)
    args = parser.parse_args()
    tools = args.launcher_source.resolve() / "tools/PackData/CurseForge"
    if not (tools / "release_overlay.py").is_file():
        parser.error("Expected the shared CurseForge tools from a LANMinecraft checkout")
    sys.path.insert(0, str(tools))
    import release_overlay

    try:
        client = release_overlay.read_lock(PACK / release_overlay.CLIENT_LOCK, "client-only")
        current = release_overlay.read_lock(PACK / release_overlay.COMPLETE_LOCK, "complete")
        candidate = release_overlay.read_lock(args.candidate_lock, "client-only")
        release_overlay.same_author(client, current)
        verify_title_menu(current)
        verify_title_menu(candidate)
        verify_pause_menu(current)
        verify_pause_menu(candidate)
        load_option(current)
        load_option(candidate)
        recipe = release_overlay.review_update(PACK, current, candidate)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    print(json.dumps(recipe, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
