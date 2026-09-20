# Deck controls and Steam invites — beta 1

Unofficial GPL-2.0 modification of Megabonk Together 5.1.0. The source base is
Fcornaire/megabonk-together commit 009e4bac2731364cbcebe8324f1fbce34c528806;
its plugin and common source match tag 5.1.0 (041881b79682a7845c5afc2ebf6887f809808a03).
Only client UI, local input and Steam invitation integration are changed.
The protocol and version sent to matchmaking remain 5.1.0.

## Changes

- Register Together in the game's native controller navigation.
- Restrict native navigation to visible mod-dialog buttons while a dialog is open;
  restore the previous button list, button lookup set, and focus on close.
- Restore hover feedback, prevent duplicate Together dialogs, and block clicks
  through dialog backgrounds.
- B backs out of text input, submenus, and dialogs; while connecting it cancels.
- Make room-code/name fields controller selectable; request Steam's floating
  keyboard when supported (STEAM+X is the fallback).
- Keep the cursor unlocked and visible in the main menu and mod dialogs.
  Steam Input must still map the right trackpad to Mouse to send mouse movement.
- On-screen control hints; Paste Code; remember the last attempted join code for
  this game session only; validate codes; 200 ms submit guard on opening dialogs.
- Host's lobby has Invite Friends. It opens Steam's invite picker using the room
  code as the connect string. Starting through an accepted invite queues the room;
  a GameRichPresenceJoinRequested callback handles an already-running client when
  the game's Steam callback pump dispatches it. Neither path interrupts a run.
- If the Steam API or picker is unavailable, the lobby button copies the room code.
  No invites are sent until the player chooses a recipient in Steam.

## Validation and limits

Compiled in Release with PROTON=true against the upstream project and stripped
reference assemblies. Invite parsing and the callback payload decoding are tested
without Steam; no test sends invitations. The installer has filesystem tests.
**No physical Steam Deck/controller, in-game Unity UI, Steam overlay, or two-account
invite acceptance test was possible here. This is a beta, not a verified fix.**

The live invite callback uses the Windows x64 Steam callback ABI, including while
running under Proton. A game using only Steam's manual callback dispatcher might
not deliver that callback; close the receiving game and accept the invite again
in that case, or join with the code. Both players need this beta for automatic
invite-to-room handling. Normal code-based joining remains the fallback.

## Build

Install .NET SDK 8. Fetch the exact upstream source to obtain the compile-only
stripped reference DLLs (not full game DLLs):

```sh
git clone https://github.com/Fcornaire/megabonk-together.git upstream-refs
git -C upstream-refs checkout 009e4bac2731364cbcebe8324f1fbce34c528806
cp -R upstream-refs/src/plugin/stripped-libs src/plugin/
CI=true PROTON_BUILD=true dotnet build src/plugin/MegabonkTogether.Plugin.csproj -c Release
```

Publish only `src/plugin/bin/Release/net6.0/MegabonkTogether.dll` over an existing
5.1.0 Proton installation. Keep the existing dependencies. Do not distribute full
original game assemblies. The source archive includes all modified and unmodified
plugin/common C# sources, project files, tests and the upstream GPL license;
compile-only reference binaries and generated build outputs are excluded.

Run the pure invite/callback checks, supplying BepInEx core and reference folders:

```sh
dotnet run --project tests/DeckSmoke -- \
  src/plugin/bin/Release/net6.0/MegabonkTogether.dll \
  /path/to/BepInEx/core src/plugin/stripped-libs/interop src/plugin/stripped-libs/unity-libs
```

Before calling the beta stable, verify: D-pad reaches Together; A opens once;
Friendlies/Host/Join/name/code/Paste can be selected; B backs out once; menus behind
popups do not react; cursor works with a Mouse trackpad binding; gameplay controls
are unchanged; invites join from both running and closed clients; overlay-disabled
fallback works; restore launcher restores the prior DLL.

## Inspiration and credits

Built from DShad/Fcornaire's Megabonk Together; see LICENSE (GPL version 2).
Quality-of-life ideas reviewed: SpacebarBlock's protection against accidental
confirmations; SimpleUITweaks' readability emphasis; MoreKeybinds' faster UI access.
No code from those mods was copied. No damage, loot, experience, or progression
cheats were added.

- https://thunderstore.io/c/megabonk/p/guarnecessities/SpacebarBlock/
- https://thunderstore.io/c/megabonk/p/Maskoliver/SimpleUITweaks/
- https://thunderstore.io/c/megabonk/p/bedlesssleeper/MoreKeybinds/
