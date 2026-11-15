"""Build or check the UniversIO controls preset against the captured Forge mappings."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PRESET = HERE.parent.parent / "launcher/controls-preset.txt"
UNBOUND = "key.keyboard.unknown"
LINE = re.compile(r"key_([^:\s]+):(key\.(?:keyboard|mouse)\.[a-z0-9.]+)(?::(SHIFT|CONTROL|ALT))?")
CRAFTING_CHORDS = {
    "key.keyboard.k": {
        "key.craftingtweaks.compressStack": None,
        "key.craftingtweaks.compressOne": "CONTROL",
        "key.craftingtweaks.compressAll": "SHIFT",
    },
    "key.keyboard.down": {
        "key.craftingtweaks.refill_last_stack": None,
        "key.craftingtweaks.refill_last": "CONTROL",
    },
}


def mappings(text):
    result = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        match = LINE.fullmatch(line)
        if not match or match[1] in result:
            raise ValueError(f"Invalid or duplicate assignment: {line}")
        result[match[1]] = line.split(":", 1)[1]
    return result


def build():
    stock = mappings((HERE / "stock.txt").read_text(encoding="utf-8"))
    edits = json.loads((HERE / "layout.json").read_text(encoding="utf-8"))
    if edits.keys() - stock.keys() or set(edits) & set(list(stock)[:34]):
        raise ValueError("An override is unknown or changes a base Minecraft control")
    expected = {**stock, **edits}
    rows = "# UniversIO 5.3 / Minecraft 1.19.2 Forge 43.2.10\n"
    rows += "".join(f"key_{name}:{value}\n" for name, value in expected.items())
    groups = defaultdict(dict)
    for name, value in mappings(rows).items():
        key, _, modifier = value.partition(":")
        if key != UNBOUND:
            groups[key][name] = modifier or None
    for key, group in groups.items():
        if len(group) > 1 and group != CRAFTING_CHORDS.get(key):
            raise ValueError(f"Shared input {key}: {', '.join(group)}")
    if any(groups[key] != expected for key, expected in CRAFTING_CHORDS.items()):
        raise ValueError("Crafting Tweaks chord family changed")
    active = sum(len(group) for group in groups.values())
    print(f"{len(stock)} controls, {active} bound, {len(edits)} overrides; two isolated GUI chord families")
    return rows.encode("utf-8")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--write", action="store_true")
    args = cli.parse_args()
    content = build()
    if args.write:
        PRESET.write_bytes(content)
    elif PRESET.read_bytes() != content:
        raise SystemExit("Preset differs from the reviewed layout")
