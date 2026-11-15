"""Stage a controls-only update from the fresh, published UniversIO manifest."""

import hashlib
import io
import json
from pathlib import Path
import re
import sys
import urllib.request
import zipfile

from check_preset import build

URL = "https://github.com/MarkZamore/UniversIO/releases/download/pack-latest/"
PRESET = "launcher/controls-preset.txt"
BASE = "a4ecd8ce9f7013d2bda77b1fd869f846411af8b2"
BASE_SHA256 = "2eefe2544b9852abdf39322ef129f23b87b9e5572bf5394591bce1607a090108"


def pin(data):
    return {"sizeBytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def get(name, limit):
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", name):
        raise ValueError(f"Invalid release asset name: {name}")
    with urllib.request.urlopen(URL + name, timeout=90) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"Release asset exceeds limit: {name}")
    return data


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def archive(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as output:
        for name, data in sorted(files.items()):
            output.writestr(zipfile.ZipInfo(name), data, compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


def main(out, revision, timestamp):
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Expected full source revision")
    preset = build()
    raw = get("pack-manifest.json", 8 * 1024 * 1024)
    old = json.loads(raw)
    old_assets = [row for row in old["assets"] if PRESET in row["covers"]]
    old_files = [row for row in old["files"] if row["path"] == PRESET]
    if old["packId"] != "minecraft-18" or old["minecraftVersion"] != "1.19.2" or old["loader"] != {"type": "forge", "version": "43.2.10"}:
        raise ValueError("Unexpected public pack identity or runtime")
    if not old_files:
        if old["revision"] != BASE or pin(raw)["sha256"] != BASE_SHA256:
            raise ValueError("Review the controls capture against the replacement base")
    else:
        if len(old_assets) != 1 or len(old_files) != 1 or old_assets[0]["covers"] != [PRESET]:
            raise ValueError("Unexpected existing controls asset")
        original_jars = json.loads((Path(__file__).with_name("source-jars.json")).read_text(encoding="utf-8"))
        actual_jars = {row["path"]: row["sha256"] for row in old["files"] if row["path"].startswith("mods/")}
        if actual_jars != original_jars:
            raise ValueError("Mod JARs changed. Review the registered controls again.")
    library_pin = old["library"]
    library = get(library_pin["name"], 4 * 1024 * 1024)
    if pin(library) != {key: library_pin[key] for key in pin(library)}:
        raise ValueError("Public library content differs from the manifest")
    with zipfile.ZipFile(io.BytesIO(library)) as source:
        if sorted(source.namelist()) != ["library.json", "preview.jpg"]:
            raise ValueError("Unexpected library members")
        card = json.loads(source.read("library.json"))
        image = source.read("preview.jpg")
    if card["id"] != old["packId"] or card["revision"] != old["revision"]:
        raise ValueError("Public library identity differs from the manifest")
    card["revision"] = revision
    library = archive({"library.json": encode(card), "preview.jpg": image})
    archive_pin = pin(library)
    library_name = f"library-{archive_pin['sha256']}.zip"
    controls = archive({PRESET: preset})
    controls_pin = pin(controls)
    controls_name = f"r-{controls_pin['sha256'][:12]}-controls-preset.zip"
    old["assets"] = [row for row in old["assets"] if row not in old_assets]
    old["assets"].append({"name": controls_name, "kind": "zipRoot", **controls_pin, "covers": [PRESET]})
    old["files"] = [row for row in old["files"] if row not in old_files]
    old["files"].append({"path": PRESET, **pin(preset)})
    old.update(revision=revision, generatedAtUtc=timestamp, library={"revision": revision, "name": library_name, **archive_pin})
    out.mkdir(parents=True)
    for name, data in ((library_name, library), (controls_name, controls), ("pack-manifest.json", encode(old))):
        (out / name).write_bytes(data)
    (out / "previous.sha256").write_text(pin(raw)["sha256"] + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
