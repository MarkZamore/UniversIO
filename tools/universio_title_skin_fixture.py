"""Serve an isolated synthetic skin while the existing Forge fixture inspects its native title."""
import argparse
import hashlib
import http.server
import io
import json
import os
import pathlib
import shutil
import stat
import struct
import subprocess
import threading
import time
import urllib.request
import uuid
import zipfile
import zlib

PROJECT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE = PROJECT / "artifacts/agent-runs/guest-peer-remaining-20261114"
LAUNCHER = PROJECT / "Minecraft/Launcher"
PACK = PROJECT / "Minecraft/Packs/UniversIO"
PROFILE = "1.19.2-forge-43.2.10"
REVISION = "38bc16b005fe4805c4d863f975686992089786ce"
MANIFEST = "5230624acca074821b9e5f410063eabe245516cda799946b50048b3b66e15960"
SCRIPT = "1e1b5b85a13ee4a6c667ec501613f378177ab098d0a9502d6b6e6afb9a520e50"
MENU = "47d46f7befbad3abf5ea07123feb507d06e896fec1dcc91072fe8f500387770a"
STEAM = "e4steam-forge-mc1.18.2-1.20.2-v0.3.4-lanmc-native-ui.2.jar"
STEAM_SHA = "3f397fc193f14d3c543b5ef9b4613bc149a21ca8e14bd93c39de3d1bc6f9553c"
JAVA = LAUNCHER / "JavaRuntimes/runtime/windows-x64/java-17/bin/java.exe"
STATE = LAUNCHER / "IdentityAdapters/b2a2b23bf6b56221b32613f5f6acc7b4fcec5e115e49d63be2b059d2c23674aa/adapter-state.json"
ASSEMBLY = LAUNCHER / "Runtime/e86ff2d180aeab13cf0d77bf6f0d1b1fceaae5ec8ae8d8969cb68bb9ecf49cab"
ADAPTER = PROJECT / "artifacts/agent-runs/guest-runtime-20261114/identity-500-release.jar"
ADAPTER_SHA = "864774e8355f65f63615bb3cfcac4c849a5454ba058adae9c2f393e1c1c29641"
PREVIOUS_ADAPTER_SHA = "f5274c077ea45aca68f609ba30c28e52acbf4caac82de74a717e2c24d5428945"
JDK = pathlib.Path("C:/Tools/jdk-25.0.2/bin")
HERE = pathlib.Path(__file__).resolve().parent
CLIENT_SCRIPT = HERE.parent / "kubejs/client_scripts/lanmc_menu_player_skin.js"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def adapter_skin_mapping():
    state = json.loads(STATE.read_text(encoding="utf-8-sig"))
    cached = STATE.parent / state["adapterSha256"] / "portable-identity-adapter.jar"
    if state["adapterSha256"] != PREVIOUS_ADAPTER_SHA or file_sha(cached) != PREVIOUS_ADAPTER_SHA:
        raise RuntimeError("The saved 1.19.2 skin mapping belongs to an unknown adapter")

    def contents(jar):
        with zipfile.ZipFile(jar) as archive:
            return {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}

    before, actual = map(contents, (cached, ADAPTER))
    changed = {key for key in before.keys() | actual.keys() if before.get(key) != actual.get(key)}
    if changed != {"portable-identity-hooks.jar",
                   "minecraft/portable/identity/PortableIdentityPreflight.class",
                   "minecraft/portable/identity/PortablePerPlayerChunksTransformer.class"}:
        raise RuntimeError("Reviewed unchanged UniversIO skin hooks must be re-verified")
    old_hooks, new_hooks = (contents(io.BytesIO(jar["portable-identity-hooks.jar"])) for jar in (before, actual))
    if {key for key in old_hooks.keys() | new_hooks.keys() if old_hooks.get(key) != new_hooks.get(key)} != {
            "minecraft/portable/identity/PortableLanAutoPublishHooks.class"}:
        raise RuntimeError("The embedded skin hooks changed between the reviewed agents")
    state["adapterSha256"] = ADAPTER_SHA
    return state


def checked_inputs():
    source = "https://github.com/MarkZamore/UniversIO/releases/download/pack-latest/pack-manifest.json"
    url = f"{source}?qa={time.time_ns()}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Cache-Control": "no-cache"}), timeout=30) as response:
        body = response.read()
    manifest = json.loads(body)
    if sha(body) != MANIFEST or manifest["revision"] != REVISION:
        raise RuntimeError("Review the newer public pack before running this native probe")
    pins = {
        PACK / "config/fancymenu/customization/main_menu.txt": MENU,
        CLIENT_SCRIPT: SCRIPT,
        JAVA: "1977f302375adbb920d41dac65c7e22eb9c2ed8e1e8d6258964154ff16f14406",
        STATE: "f9619cfa54195175eb73cdcc83554686af773379c3bd00ddddf321d36ca8b2dd",
        LAUNCHER / f"Shared/versions/{PROFILE}/{PROFILE}.json":
            "289a9c7c78b9e441261edadaf763e0354b1eeae7fbeb8cfe13f1a578e52a5258",
        ASSEMBLY / "LANMinecraft.dll": "86690aee6344917788ea4b733d7589fc14cf69226991b99b597c0afe23e6d593",
        ADAPTER: ADAPTER_SHA,
    }
    for path, expected in pins.items():
        if file_sha(path) != expected:
            raise RuntimeError(f"Unexpected bytes in {path}")
    candidates = [p for p in (LAUNCHER / "ManagedComponents").rglob(STEAM) if file_sha(p) == STEAM_SHA]
    if len(candidates) != 1:
        raise RuntimeError("Expected one managed e4steam JAR with the reviewed hash")
    if not (FIXTURE / "RUN.json").is_file():
        raise RuntimeError("The existing peer QA fixture is unavailable")
    state = adapter_skin_mapping()
    inputs = {
        "revision": REVISION, "manifestSha256": MANIFEST, "fileCount": len(manifest["files"]),
        "packBytes": sum(row["sizeBytes"] for row in manifest["files"]),
        "minecraft": "1.19.2", "forge": "43.2.10", "launcher": 500,
        "launcherAssemblySha256": pins[ASSEMBLY / "LANMinecraft.dll"], "identityAdapterSha256": ADAPTER_SHA,
        "adapterMappingSource": "Review-pinned 1.19.2 state from prior launcher; relevant hook bytecode identical",
        "fancyMenuSha256": next(x["sha256"] for x in manifest["files"] if x["path"] == "mods/fancymenu_forge_2.14.9_MC_1.19-1.19.2.jar"),
        "candidateScriptSha256": SCRIPT, "authorMenuSha256": MENU, "e4steamSha256": STEAM_SHA,
    }
    return inputs, candidates[0], state


def png_skin():
    def chunk(kind, contents):
        return struct.pack(">I", len(contents)) + kind + contents + struct.pack(">I", zlib.crc32(kind + contents))

    pixel_rows = bytearray()
    colors = (bytes.fromhex("3dc991ff"), bytes.fromhex("b340e8ff"), bytes.fromhex("ff9e42ff"))
    for y in range(64):
        pixel_rows.append(0)
        for x in range(64):
            # The face UV uses x=8..15 and y=8..15. Mark the native base texture at that location.
            pixel_rows.extend(colors[min(max((x - 8) // 2, 0), 2)] if 8 <= y <= 15 and 8 <= x <= 15
                              else bytes.fromhex("224577ff"))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 64, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixel_rows)) + chunk(b"IEND", b""))


def run_game(mode, inputs, steam, adapter_state):
    subprocess.run(["pwsh", "-NoProfile", "-Command",
                    "if (Get-Process java,javaw -ErrorAction SilentlyContinue) { throw 'A game is already running' };"
                    "$mem=(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory;"
                    "if ($mem -lt 9437184) { throw 'Fewer than 9 GiB are available' }"], check=True)
    storage = json.loads(subprocess.check_output(
        ["python", str(PROJECT / "tools/workspace_storage.py"), "--check"], text=True))
    if not storage["complete"] or storage["unique_bytes"] + inputs["packBytes"] + 128 * 2**20 > storage["budget_bytes"]:
        raise RuntimeError("Shared temporary budget cannot fit this one client")
    key = "UniversioTitleSkin"
    game, evidence = (FIXTURE / name / key for name in ("game", "evidence"))
    work = FIXTURE / "universio-title-scratch"
    receipt = FIXTURE / f"UniversioTitleSkin-{mode}-{SCRIPT[:8]}"
    if any(p.exists() for p in (work, receipt, game, evidence)):
        raise RuntimeError("Use a fresh owned fixture; existing data remains for review")
    for directory in (work, work / "classes", receipt, FIXTURE / "game"):
        directory.mkdir(exist_ok=True)
    skin = png_skin()
    png_sha = sha(skin)
    player = str(uuid.UUID("70254ec69d1f449b92def1ce35f8bcc4"))
    route = f"/skin/{player}/{png_sha}"
    # authlib 3.11.49 gets the filename; SkinManager hashes the Java UTF-16 code units with SHA-1.
    location = "minecraft:skins/" + hashlib.sha1(png_sha.encode("utf-16-le")).hexdigest()
    hits = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != route:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(skin)))
            self.end_headers()
            self.wfile.write(skin)
            hits.append(time.monotonic())

        def log_message(self, *args):
            pass

    try:
        subprocess.run(["python", "-B", str(FIXTURE / "stage_pack.py"), key, "UniversIO",
                        str(PACK), REVISION, MANIFEST, str(steam)], check=True)
        if file_sha(game / "config/fancymenu/customization/main_menu.txt") != MENU:
            raise RuntimeError("Invalid unchanged author title layout")
        if mode != "Control":
            destination = game / "kubejs/client_scripts" / CLIENT_SCRIPT.name
            destination.parent.mkdir(exist_ok=True)
            if destination.exists():
                raise RuntimeError("The published data already contains a candidate client script")
            shutil.copyfile(CLIENT_SCRIPT, destination)
        subprocess.run([str(JDK / "javac.exe"), "--release", "17", "-d", str(work / "classes"),
                        str(HERE / "UniversioTitleSkinAgent.java")], check=True)
        (work / "agent.mf").write_text("Premain-Class: UniversioTitleSkinAgent\n", encoding="ascii")
        agent = work / "skin-agent.jar"
        subprocess.run([str(JDK / "jar.exe"), "cfm", str(agent), str(work / "agent.mf"), "-C",
                        str(work / "classes"), "."], check=True)
        isolated_state = work / "adapter-state.json"
        isolated_state.write_text(json.dumps(adapter_state), encoding="utf-8")
        shutil.copyfile(ADAPTER, work / "portable-identity-adapter.jar")

        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                registry = work / "skin-profiles.properties"
                url = f"http://127.0.0.1:{server.server_port}{route}"
                model = "slim" if mode != "Classic" else "classic"
                registry.write_text(f"{player}|{png_sha}|{model}|{url}\n", encoding="ascii")
                with urllib.request.urlopen(url, timeout=5) as response:
                    if response.read() != skin:
                        raise RuntimeError("Synthetic PNG is not served byte for byte")
                prior = len(hits)
                props = ["-Dminecraft.portable.skin.registry=" + str(registry),
                         "-Dminecraft.portable.identity.localPlayer=" + player,
                         "-Dlanminecraft.steamqa.fixtureSkinLocation=" + location,
                         "-Dlanminecraft.steamqa.fixtureSkinSlim=" + str(model == "slim").lower(),
                         "-Dlanminecraft.steamqa.fixtureSkinNegative=" + str(mode == "Control").lower()]
                launcher_args = {
                    "Shared": str(LAUNCHER / "Shared"), "Profile": PROFILE, "Java": str(JAVA),
                    "Game": str(game), "Evidence": str(evidence), "AdapterState": str(isolated_state),
                    "Version": "1.19.2", "Agent": str(agent), "Heap": 4608, "Seconds": 530,
                    "Player": "LanMcPackQa", "HiddenStartup": True, "AssemblyPath": str(ASSEMBLY),
                    "TestProperties": props, "LowerPriority": True,
                }
                args_file = work / "launch.json"
                args_file.write_text(json.dumps(launcher_args), encoding="utf-8")
                command = '& ([IO.Path]::Combine($env:LANMC_QA_FIXTURE, "Start-ForgeFixture.ps1")) @options'
                # Sources stay outside the fixture. Absolute paths travel through environment/JSON, not shell text.
                env = dict(os.environ, LANMC_QA_FIXTURE=str(FIXTURE), LANMC_QA_LAUNCH=str(args_file))
                subprocess.run(["pwsh", "-NoProfile", "-Command",
                                "$options=Get-Content -LiteralPath $env:LANMC_QA_LAUNCH -Raw|ConvertFrom-Json -AsHashtable\n" + command],
                               env=env, check=True)
                native = (evidence / "native-menu-skin.properties").read_text(encoding="utf-8")
                inputs.update(mode=mode, model=model, texture=location, generatedPngSha256=png_sha,
                              agentSha256=file_sha(agent), minecraftHttpGetCount=len(hits) - prior)
                if not native.startswith("status=PASS\n"):
                    raise RuntimeError("The native menu did not show expected model/texture")
                if mode != "Control" and len(hits) <= prior:
                    raise RuntimeError("The game never fetched the selected synthetic PNG")
                print(native)
            finally:
                server.shutdown()
                thread.join()
    finally:
        (receipt / "inputs.json").write_text(json.dumps(inputs, indent=2), encoding="utf-8")
        for name in ("native-menu-skin.properties", "exit.json", "launcher.log"):
            if (evidence / name).is_file():
                shutil.copyfile(evidence / name, receipt / name)
        if (FIXTURE / f"{key}-stage.json").is_file():
            (FIXTURE / f"{key}-stage.json").replace(receipt / "stage.json")
        if (game / "logs/latest.log").is_file():
            with (game / "logs/latest.log").open(encoding="utf-8", errors="replace") as f:
                lines = [line[:400] for line in f if "lanmc_menu_player_skin" in line or "PortableIdentity" in line]
            (receipt / "skin-log.txt").write_text("".join(lines[-25:]), encoding="utf-8")
        # The isolated .NET launcher creates only this known temporary cache junction.
        if evidence.exists():
            for link in evidence.rglob("Content.IE5"):
                if link.is_junction() and link.is_relative_to(evidence):
                    link.rmdir()
        subprocess.run(["python", "-B", str(FIXTURE / "clean_owned.py"), f"game/{key}", f"evidence/{key}", work.name],
                       check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("Plan", "Control", "Classic", "Slim"), default="Plan", nargs="?")
    args = parser.parse_args()
    inputs, steam, state = checked_inputs()
    if args.mode == "Plan":
        print(json.dumps(inputs, indent=2))
    else:
        run_game(args.mode, inputs, steam, state)


if __name__ == "__main__":
    main()
