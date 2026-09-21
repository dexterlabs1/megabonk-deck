# Compiled hover regression

Checks the actual plugin DLL with Mono.Cecil without loading Unity, Steam, or
IL2CPP. Requires .NET SDK 8 and NuGet access for Mono.Cecil 0.11.4.

From the repository root, after extracting the two release ZIPs:

```powershell
dotnet run --project diagnostics/hover -- /path/to/beta3/MegabonkTogether.dll /path/to/beta2/MegabonkTogether.dll
dotnet run --project diagnostics/hover -- /path/to/beta2/MegabonkTogether.dll
```

The candidate must pass all eight checks: each hover override remains virtual,
calls only its managed Action callback, and preserves that callback; the assembly
version remains 5.1.0.0; dependency assembly identities match beta 2. The second
command intentionally exits 1: beta 2 fails both unsafe-call checks, with five
other checks passing.

A C# `base.StartHover()` uses an IL `call` instruction, but its generated native
wrapper can still perform virtual dispatch back into the managed override. This
test checks both `call` and `callvirt`. It establishes removal of the suspect
instructions, not reproduction or resolution of the user's freeze.

## Verification recorded 2026-09-21

- `CI=true`, `PROTON_BUILD=true`, .NET SDK 8.0.301: Release plugin build succeeded,
  15 existing warnings and zero errors. Command:
  `dotnet build src/plugin/MegabonkTogether.Plugin.csproj -c Release --no-restore`.
- Final candidate DLL: eight compiled-IL checks passed. Shipped beta 2: the two
  native/base hover call checks failed as expected.
- Existing `tests/DeckSmoke` from the source archive: all 12 checks passed against
  the final candidate DLL, using BepInEx Core, BepInEx Unity IL2CPP,
  Il2CppInterop.Runtime, and the original stripped interop/Unity reference folders
  as resolver search paths. These checks exercise room parsing and confirm the
  Steam invite bridge remains absent.
- `src/plugin/obj/project.assets.json` library identities exactly match
  `DECK-BUILD-DEPENDENCIES.json`: no transitive package changes. The DLL's assembly
  references also exactly match the shipped beta 2 DLL.
- Applying `mod-source/deck-beta3.patch` to freshly extracted beta 2 source with
  `git -c core.autocrlf=false apply` reproduced all 299 candidate source files
  byte for byte. Only `CustomButton.cs`, `MainMenu.cs`, and `DECK-BETA.md` differ.
  The archive includes LICENSE and excludes DLLs, bin, and obj.

The candidate was not run inside Unity, on a Steam Deck, or in live multiplayer.
Other failures recorded by the menu/network diagnostics remain unresolved.

## Packaging

`package.py <built-source-root>` writes the beta 3 binary ZIP, source ZIP, and
incremental beta 2-to-beta 3 patch. Build first with the flags above. It preserves
the beta 2 source membership and refuses unexpected C#/project changes. The
source files in the built tree must use their original LF line endings. Git's
Windows `core.autocrlf` setting can otherwise expand an applied patch to CRLF.

The binary archive contains only the replacement DLL, LICENSE, and candidate
notes; no runtime dependencies are replaced. `candidate-sha256.json` records the
final DLL, binary ZIP, source ZIP, and patch hashes.
