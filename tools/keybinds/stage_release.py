"""Stage controls and client script updates from the published UniversIO manifest."""

import hashlib
import io
import json
from pathlib import Path
import re
import sys
import urllib.request
import zipfile

from check_preset import build

PACK = Path(__file__).resolve().parents[2]
PAUSE_SCRIPT = "kubejs/client_scripts/lanmc_pause_reports_layout.js"
PROJECTE_SCRIPT = "kubejs/client_scripts/lanmc_projecte_update_notice.js"
SCRIPT_ASSETS = {PAUSE_SCRIPT: "pause-reports", PROJECTE_SCRIPT: "projecte-notice"}
PAUSE_LAYOUT = "config/fancymenu/customization/pause_screen.txt"
OWNERSHIP = "launcher/pack-owned.txt"

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


def stage_client_scripts(manifest):
    files = {row["path"]: row for row in manifest["files"]}
    author = json.loads((PACK / "tools/upstream-client-lock.json").read_bytes())
    layout, = [row for row in author["overrides"] if row["path"] == PAUSE_LAYOUT]
    if any(files[PAUSE_LAYOUT][key] != layout[key] for key in ("sizeBytes", "sha256")):
        raise ValueError("Review the new FancyMenu pause layout")
    recipe = json.loads((PACK / "tools/overlay.json").read_bytes())
    script_pins = {row["path"]: row for row in recipe["clientScripts"]["files"]}
    owners = (PACK / OWNERSHIP).read_bytes()
    outputs = {}

    def add_asset(label, members):
        data = archive(members)
        asset_pin = pin(data)
        name = f"r-{asset_pin['sha256'][:12]}-{label}.zip"
        manifest["assets"].append({"name": name, "kind": "zipRoot", **asset_pin, "covers": sorted(members)})
        outputs[name] = data

    for path, label in SCRIPT_ASSETS.items():
        script = (PACK / path).read_bytes()
        if {"path": path, **pin(script)} != script_pins[path]:
            raise ValueError(f"Script differs from its recipe: {path}")
        if owners.splitlines().count(path.encode()) != 1:
            raise ValueError(f"Expected one ownership entry: {path}")
        if files.get(path) == script_pins[path]:
            continue
        for previous in [row for row in manifest["assets"] if path in row["covers"]]:
            if previous["covers"] != [path]:
                raise ValueError(f"Expected an independent script archive: {path}")
            manifest["assets"].remove(previous)
        files[path] = script_pins[path]
        add_asset(label, {path: script})

    ownership_pin = {"path": OWNERSHIP, **pin(owners)}
    if files[OWNERSHIP] != ownership_pin:
        owner_asset, = [row for row in manifest["assets"] if OWNERSHIP in row["covers"]]
        data = get(owner_asset["name"], 4 * 1024 * 1024)
        if any(pin(data)[key] != owner_asset[key] for key in ("sizeBytes", "sha256")):
            raise ValueError("Unexpected published ownership archive")
        with zipfile.ZipFile(io.BytesIO(data)) as source:
            if sorted(source.namelist()) != sorted(owner_asset["covers"]):
                raise ValueError("Unexpected ownership archive members")
            owner_files = {name: source.read(name) for name in source.namelist()}
        for name, data in owner_files.items():
            if files[name] != {"path": name, **pin(data)}:
                raise ValueError(f"Published archive member differs: {name}")
        scripts = {path.encode() for path in SCRIPT_ASSETS}
        if [line for line in owners.splitlines() if line not in scripts] != [
            line for line in owner_files[OWNERSHIP].splitlines() if line not in scripts
        ]:
            raise ValueError("Ownership must retain all unrelated paths")
        files[OWNERSHIP] = ownership_pin
        owner_files[OWNERSHIP] = owners
        manifest["assets"].remove(owner_asset)
        add_asset("launcher", owner_files)
    manifest["files"] = list(files.values())
    return outputs


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
    extra_assets = stage_client_scripts(old)
    out.mkdir(parents=True)
    for name, data in ((library_name, library), (controls_name, controls), ("pack-manifest.json", encode(old))):
        (out / name).write_bytes(data)
    for name, data in extra_assets.items():
        (out / name).write_bytes(data)
    (out / "previous.sha256").write_text(pin(raw)["sha256"] + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
