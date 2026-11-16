"""Carry the UniversIO multiplayer warning option through full pack builds."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


PACK = Path(__file__).resolve().parents[1]
OPTION_PATH = "launcher/options-default.txt"
OPTION_BYTES = b"!skipMultiplayerWarning:true\n"


def load_option(author):
    source = (PACK / OPTION_PATH).read_bytes()
    pin = {"path": OPTION_PATH, "sizeBytes": len(source),
           "sha256": hashlib.sha256(source).hexdigest()}
    if source != OPTION_BYTES or pin != json.loads((PACK / "tools/launcher-options-pin.json").read_bytes()):
        raise ValueError("UniversIO must ship exactly the pinned multiplayer warning option")
    if any(row["path"].casefold() == OPTION_PATH for key in ("overrides", "files")
           for row in author.get(key, [])):
        raise ValueError("Review the author's new launcher options file")
    return pin, source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher-source", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--verify-manifest", type=Path)
    args = parser.parse_args()
    shared = args.launcher_source.resolve() / "tools/PackData/CurseForge"
    sys.path.insert(0, str(shared))
    import prepare
    import release_overlay

    try:
        stage = Path(os.path.abspath(args.stage))
        prepare.no_links(stage)
        runs = PACK.parents[1] / "artifacts/agent-runs"
        parts = stage.relative_to(runs).parts
        if len(parts) < 2 or not prepare.read_local_json(runs / parts[0] / "RUN.json").get("owner"):
            raise ValueError("Expected an existing stage inside an owned agent run")
        author = release_overlay.read_lock(PACK / release_overlay.COMPLETE_LOCK, "complete")
        client = release_overlay.read_lock(PACK / release_overlay.CLIENT_LOCK, "client-only")
        release_overlay.same_author(client, author)
        policy, excluded = release_overlay.verify_stage(stage, PACK, author)
        pin, source = load_option(author)
        target = prepare.native_path(stage / "game" / OPTION_PATH)
        prepare.no_links(target)
        if args.verify_manifest:
            manifest = prepare.read_local_json(args.verify_manifest)
            files = manifest["files"]
            if target.read_bytes() != source or [row for row in files if row["path"] == OPTION_PATH] != [pin]:
                raise ValueError("The staged launcher option and its release pin must match")
            manifest["files"] = [row for row in files if row["path"] != OPTION_PATH]
            recipe, _, _, _ = release_overlay.source_policy(PACK, author)
            jar_patches = prepare.jar_metadata_patches(recipe, author, PACK)
            book_jars = prepare.book_jar_localizations(recipe, author, PACK, jar_patches)
            release_overlay.verify_manifest(manifest, policy, author, excluded, [*jar_patches, *book_jars])
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(source)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
