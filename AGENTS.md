# Megabonk Deck

## What it is

An unofficial Steam Deck installer for Megabonk Together Proton 5.1.0 and BepInEx build 752, with small client UI changes packaged as Deck betas. Repository: `dexterlabs1/megabonk-deck`.

Read [knowledge/index.md](knowledge/index.md) and the [test report](TEST-REPORT-2026-09-21.md) before changing the mod. Shared project conventions come from the parent AGENTS.md.

## Confirmed decisions

- Retain multiplayer protocol/assembly version 5.1.0; identify local UI changes through the displayed Deck beta number.
- Keep every published beta archive and checksum immutable. New changes get a new beta number and GitHub prerelease.
- Offline test bundles contain install/restore launchers, the DLL package, matching GPL source, and instructions. Upgrade from older betas must preserve the original official DLL backup.
- The host needs at least two players before character confirmation. Do not change that rule to address menu navigation bugs.
- Never call native virtual base hover methods from injected button overrides; see the IL2CPP knowledge entry.

## Stack and source layout

- Python 3 installer/updaters run on Linux. The tests use Ubuntu WSL on this Windows workspace.
- C# plugin builds with .NET SDK 8, targeting net6.0, with `CI=true` and `PROTON_BUILD=true`.
- `mod-source/megabonk-deck-betaN-source.zip` is each beta's matching source. Build in an extracted scratch directory with the documented stripped compile references. Do not ship game assemblies, bin/obj, or changed runtime dependencies.
- `releases/` contains immutable binary/test bundles; `diagnostics/` holds isolated regression checks. The original standalone updater still targets beta 2.
- Source base and compile-reference commit: `009e4bac2731364cbcebe8324f1fbce34c528806` from `Fcornaire/megabonk-together`.

## Key commands

```text
python3 -m unittest discover -s tests -v
dotnet build src/plugin/MegabonkTogether.Plugin.csproj -c Release
dotnet run --project diagnostics/hover -- <candidate.dll> <beta2.dll>
python diagnostics/menu/reproduce.py
python remote/deck.py --help
python -m unittest discover -s remote/tests -v
```

Run the C# build inside extracted source with the environment flags above. The menu reproduction intentionally fails against beta 2. Read each diagnostic README for setup and limits. Candidate-specific builders/tests live in their candidate directories.

## Golden rules

- Do not equate compilation or stub tests with Unity/Deck verification. Record the user's exact live results separately.
- Test candidate upgrade/restore with actual prior DLLs and temporary Steam fixtures. Never use real saves or a live Steam installation as test fixtures.
- WSL temporary downloads can disappear when the distro stops. Download/checksum fixtures and run tests in the same WSL session, or use a persistent test-fixture directory.
- Python urllib fixture downloads have stalled in this environment; `curl -4` retrieved the pinned files successfully. Always verify their expected SHA-256 before testing.
- Preserve source line endings when patching archived code. Verify the incremental patch reproduces the source archive byte for byte.
- Publish the tested bundle unchanged, then download it from the public release URL and verify its SHA-256.
- Reusable remote control lives in the independent sibling `../SteamDeckControl` project. `remote/deck.py` forwards to it; this repo owns the Megabonk adapter and deployment pins. Read `remote/README.md`. Connection configuration and keys live outside Git, and run artifacts are ignored. Do not equate a virtual gamepad test with physical Deck controls. Never remove installer backups when removing remote helpers.

## Current status

Beta 7 fixes the built-in controller startup regression: cursor ownership now requires an active multiplayer modal instead of forcing cursor state on the main menu. The user confirmed immediate physical D-pad/A navigation after cold launch. Unmodded Megabonk and official Together 5.1.0 worked in comparison tests; beta 6 required opening/closing Steam's menu. The same Steam `uses xinput : false` log appeared in working vanilla, so it was not diagnostic. The candidate passed 45 source-harness and 26 compiled-IL checks.

Beta 7 retains beta 6's generated-array correction, modal focus confinement, gold selection marker and character-screen handoff, plus earlier hover-freeze and layout fixes. Beta 6 live tests covered hosting, character selection, room-code reveal and restore/reinstall. Two-player joining, match start, extended play, a friend's fresh physical install and physical STEAM+X still need confirmation.

Valve pairing is complete. Actual Deck screenshots, SSH transfer/commands, launch/stop, keyboard/mouse/controller input, original-mod restore and reinstall, and reconnection after reboot were verified. Reusable controls now live in `../SteamDeckControl` (88 WSL tests pass); this repo retains adapter/forwarder and deployment integration tests. The split was bootstrapped and verified live. See `knowledge/remote-live-testing.md` for evidence and limitations. Virtual STEAM+X opens Steam's menu, so the software keyboard shortcut remains unverified.

`friend-installer/` builds the one-file launcher. It combines fresh official installation and the beta update with one install confirmation, downloads runtime packages only, and also upgrades existing managed installations. Published release files are immutable. See the current artifact manifest and test report for packaging verification.
