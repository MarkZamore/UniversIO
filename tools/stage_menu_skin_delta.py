"""Stage only the UniversIO client script, ownership update, and library revision."""

import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile


SOURCE = Path(__file__).resolve().parents[1]
PREVIOUS = "38bc16b005fe4805c4d863f975686992089786ce"
PREVIOUS_SHA = "5230624acca074821b9e5f410063eabe245516cda799946b50048b3b66e15960"
SCRIPT = "kubejs/client_scripts/lanmc_menu_player_skin.js"
OWNERSHIP = "launcher/pack-owned.txt"


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def stage(launcher, workspace, previous, output, revision):
    sys.path.insert(0, str(launcher / "tools/PackData/CurseForge"))
    import prepare
    import release_overlay
    import stage_release

    def pinned_bytes(path, pin):
        data = path.read_bytes()
        prepare.require(prepare.fingerprint(data) == {k: pin[k] for k in ("sizeBytes", "sha256")}, f"Unexpected bytes: {path.name}")
        return data

    def built_zip(rows):
        result = io.BytesIO()
        with zipfile.ZipFile(result, "w") as archive:
            for name, data in sorted(rows.items()):
                item = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                archive.writestr(item, data, compress_type=zipfile.ZIP_DEFLATED)
        return result.getvalue()

    source_manifest = (previous / "pack-manifest.json").read_bytes()
    prepare.require(hashlib.sha256(source_manifest).hexdigest() == PREVIOUS_SHA, "Unexpected published manifest")
    old = prepare.decode_json(source_manifest)
    prepare.require(old["revision"] == PREVIOUS and old["packId"] == "minecraft-18", "Expected the current UniversIO release")
    author = release_overlay.read_lock(SOURCE / release_overlay.COMPLETE_LOCK, "complete")
    client = release_overlay.read_lock(SOURCE / release_overlay.CLIENT_LOCK, "client-only")
    release_overlay.same_author(client, author)
    recipe, _, _, descriptor = release_overlay.source_policy(SOURCE, author)
    scripts = prepare.client_scripts(recipe, SOURCE, author)
    prepare.require(list(scripts) == [SCRIPT], "Expected one menu client script")
    ownership = prepare.overlay_bytes(SOURCE / OWNERSHIP)
    policy = {
        release_overlay.DESCRIPTOR: descriptor,
        OWNERSHIP: prepare.fingerprint(ownership),
        **{row["path"]: {key: row[key] for key in ("sizeBytes", "sha256")} for row in recipe["additions"]},
        **{row["path"]: row["after"] for row in recipe["patches"]},
        **{name: prepare.fingerprint(data) for name, data in prepare.book_localizations(recipe, SOURCE, author).items()},
        **{name: prepare.fingerprint(data) for name, data in prepare.quest_translation(recipe, SOURCE, author).items()},
        SCRIPT: prepare.fingerprint(scripts[SCRIPT]),
    }
    jac = prepare.jar_metadata_patches(recipe, author, SOURCE)
    book_jars = prepare.book_jar_localizations(recipe, author, SOURCE, jac)
    jar_patches = [*jac, *book_jars]
    stamp = stage_release.check_source(SOURCE, revision, old["packId"], policy, jac, recipe, book_jars)
    files = {row["path"]: row for row in old["files"]}
    prepare.require(SCRIPT not in files and len(files) == len(old["files"]), "Existing script or duplicate public row")
    previous_ownership = files[OWNERSHIP]
    files[OWNERSHIP] = {"path": OWNERSHIP, **policy[OWNERSHIP]}
    files[SCRIPT] = {"path": SCRIPT, **policy[SCRIPT]}

    owner_assets = [row for row in old["assets"] if OWNERSHIP in row["covers"]]
    prepare.require(len(owner_assets) == 1 and owner_assets[0]["kind"] == "zipRoot", "Expected one ownership archive")
    owner_asset = owner_assets[0]
    old_dir = previous / "assets"
    with zipfile.ZipFile(io.BytesIO(pinned_bytes(old_dir / owner_asset["name"], owner_asset))) as archive:
        prepare.require(Counter(archive.namelist()) == Counter(owner_asset["covers"]), "Unexpected previous ownership archive files")
        owner_files = {name: archive.read(name) for name in archive.namelist()}
    prepare.require(prepare.fingerprint(owner_files[OWNERSHIP]) == {k: previous_ownership[k] for k in ("sha256", "sizeBytes")} and
                    owner_files[OWNERSHIP].splitlines() + [SCRIPT.encode()] == ownership.splitlines(),
                    "Ownership changes must append only the menu script")
    owner_files[OWNERSHIP] = ownership
    for name, data in owner_files.items():
        prepare.require(prepare.fingerprint(data) == {k: files[name][k] for k in ("sha256", "sizeBytes")}, f"Changed ownership archive member: {name}")

    with zipfile.ZipFile(io.BytesIO(pinned_bytes(old_dir / old["library"]["name"], old["library"]))) as archive:
        library = {name: archive.read(name) for name in archive.namelist()}
    metadata = prepare.decode_json(library["library.json"])
    prepare.require(metadata["revision"] == PREVIOUS, "Unexpected old library revision")
    metadata["revision"] = revision
    library["library.json"] = json_bytes(metadata)
    library_bytes = built_zip(library)
    library_pin = prepare.fingerprint(library_bytes)
    library_descriptor = {"revision": revision, "name": f"library-{library_pin['sha256']}.zip", **library_pin}

    def asset(rows, label):
        data = built_zip(rows)
        pin = prepare.fingerprint(data)
        return {"name": f"r-{pin['sha256'][:12]}-{label}.zip", "kind": "zipRoot", "covers": sorted(rows), **pin}, data

    launcher_asset, launcher_bytes = asset(owner_files, "launcher")
    script_asset, script_bytes = asset({SCRIPT: scripts[SCRIPT]}, "universio-menu-skin")
    assets = [row for row in old["assets"] if row is not owner_asset] + [launcher_asset, script_asset]
    prepare.require(Counter(name for row in assets for name in row["covers"]) == Counter(files.keys()), "Candidate coverage differs")
    manifest = {**old, "revision": revision, "generatedAtUtc": stamp, "files": list(files.values()),
                "assets": sorted(assets, key=lambda row: row["name"]), "library": library_descriptor}
    release_overlay.verify_manifest(manifest, policy, author, jar_patches=jar_patches)
    output = prepare.check_output(output, workspace=workspace)
    assets_dir = output / "assets"
    assets_dir.mkdir(parents=True)
    for entry, data in ((launcher_asset, launcher_bytes), (script_asset, script_bytes), (library_descriptor, library_bytes)):
        (assets_dir / entry["name"]).write_bytes(data)
    stage_release.verify_library(output, library_descriptor)
    prepare.write_json(output / "pack-manifest.json", manifest)
    print(f"Staged {len(manifest['files'])} exact files with {len(assets) - 2} unchanged payload assets")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    stage(args.launcher.resolve(), args.workspace.resolve(), args.previous.resolve(), args.output, args.revision)
