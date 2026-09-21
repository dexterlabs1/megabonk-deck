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
```

Run the C# build inside extracted source with the environment flags above. The menu reproduction intentionally fails against beta 2. Read each diagnostic README for setup and limits. Candidate-specific builders/tests live in their candidate directories.

## Golden rules

- Do not equate compilation or stub tests with Unity/Deck verification. Record the user's exact live results separately.
- Test candidate upgrade/restore with actual prior DLLs and temporary Steam fixtures. Never use real saves or a live Steam installation as test fixtures.
- WSL temporary downloads can disappear when the distro stops. Download/checksum fixtures and run tests in the same WSL session, or use a persistent test-fixture directory.
- Preserve source line endings when patching archived code. Verify the incremental patch reproduces the source archive byte for byte.
- Publish the tested bundle unchanged, then download it from the public release URL and verify its SHA-256.

## Current status

Beta 3 was published as `deck-beta3`. The user reports that hosting, showing the room code, and selecting a character no longer freeze. Beta 4 (`deck-beta4`) targets controller focus getting trapped on Together and its oversized geometry. Its candidate and automated checks are complete; native navigation and appearance still need a Deck test. Multiplayer start and extended gameplay remain unverified.
