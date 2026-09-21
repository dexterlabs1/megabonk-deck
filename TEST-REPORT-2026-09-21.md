# Beta 2 test and freeze investigation

Tested repository commit `782740bf07ded9e6a672a90abbe49083b1c109b8` and its checked-in beta 2 binary. Reported symptom: the host becomes completely unresponsive, with no animation, when selecting a character in the multiplayer menu. The user confirmed the host role and stopped animation after the initial audit. No Steam Deck, live game, or multiplayer session was available to reproduce that exact symptom.

## Character-selection finding

Beta 2 adds `base.StartHover()` and `base.StopHover()` inside the injected `CustomButton` overrides. The original upstream button class does not make those calls. IL2CPP's generated virtual dispatch can route a base call back into the managed override; [Il2CppInterop issue 109](https://github.com/BepInEx/Il2CppInterop/issues/109) documents this recursion pattern. This is the strongest code-level hard-freeze/stack-overflow candidate found, when controller focus enters or leaves a custom button, including Show Room Code in the host's character screen.

Cecil inspection of the supplied reference assembly confirms `MyButtonNormal` is unsealed and both hover methods are virtual and non-final. The [Il2CppInterop 1.5.0 generator](https://github.com/BepInEx/Il2CppInterop/blob/v1.5.0/Il2CppInterop.Generator/Passes/Pass50GenerateMethods.cs#L180-L191) uses `il2cpp_object_get_virtual_method` for this combination, supporting recursive redispatch into the injected override. Reference method bodies are stripped (`ldnull; throw`), so the installed Deck wrapper and actual native stack have not been inspected. This is strong mechanism evidence, not a live reproduction. The first targeted correction should remove those two added base calls, then verify controller hover and character selection on the Deck; any replacement hover feedback must avoid native virtual redispatch.

`MainMenu.GoToMapSelection_Prefix` calls `SynchronizationService.OnSelectedCharacter`. A guest then opens a `LoadingModal` saying "Waiting for the host..." and suppresses the normal map-selection transition. The modal has no buttons, and its `ControllerBack` override does nothing. That waiting path has no timeout of its own.

Beta 2's `DeckMenuControls` replaces the active window's navigation list with the modal's buttons, which is an empty list for this dialog. Whether native game navigation tolerates that empty list has not been tested in Unity. This is a trigger-matched hypothesis, not a proven hard-freeze cause.

The user's confirmation that this is the host and animation stops makes the guest waiting dialog a poor explanation for this incident. Prioritize the custom-button hover recursion and obtain the game log/native stack if the targeted correction does not resolve it. Empty-list navigation remains an unverified guest-side concern.

Upstream has a related unresolved report: [guest stuck after character selection, issue 91](https://github.com/Fcornaire/megabonk-together/issues/91). Its maintainer observed a disconnect in the reporter's logs. This does not establish the cause of Dexter's freeze.

## Build and existing checks

- Release build of the archived beta 2 source with `CI=true`, `PROTON_BUILD=true`, .NET SDK 8.0.301, and the documented upstream stripped references: succeeded, 0 errors and 37 warnings.
- `DeckSmoke` against the actual shipped beta 2 DLL: all 12 room-parser and removed-Steam-bridge checks passed. These do not execute Unity UI or networking.
- Python installer tests require Linux (`fcntl`); Windows cannot import them. Under Ubuntu WSL / Python 3.14.4, all 25 passed with zero skips, including installation and reinstallation using freshly downloaded, checksum-verified upstream BepInEx and mod archives.
- Four additional temporary integration checks using real official/beta 1/beta 2 DLLs passed: upgrade/restore paths and rollback after an injected backup-marker write failure.
- All three desktop launchers contain the matching source payloads. Isolated rebuilds match the checked-in launchers after normalizing Windows checkout line endings.

## Additional defects reproduced in isolation

The diagnostic harnesses use source methods and limited substitutes for Unity/game services. They establish failures in those code paths, not physical Steam Deck reproduction.

1. **Connection timeouts throw instead of recovering.** Both connection coroutines dereference a nullable connection result after the timeout can expire without a result.
2. **Back after a failed connection leaves overlapping menus.** The coroutine reference remains set after completion; Back takes the cancellation path instead of leaving the submenu cleanly.
3. **Closing the changelog leaves original buttons disabled.** The changelog disables the original list, the Deck navigation code substitutes modal buttons, and the close handler re-enables the substituted list before restoring the still-disabled original list.
4. **Network reset can block the caller.** `NetworkHandler.ResetNetworking` synchronously waits for a WebSocket reset whose close handshake has no cancellation deadline. A real local WebSocket peer that never acknowledges close kept the test caller blocked until the watchdog aborted the socket.
5. **A newer-release notification can lock out input.** With the update-available flag seeded, the actual Proton updater/input patches block button down/held/up even without a modal. This is conditional: upstream's latest release at test time is still 5.1.0, so this test does not explain a normal current beta 2 session by itself.

Run the retained harnesses under `diagnostics/menu` and `diagnostics/runtime`; read their instructions for extraction, prerequisites, expected outcomes, and limitations. Tests that assert healthy behavior against broken beta 2 code are expected to fail. Runtime reproductions assert the observed defect and therefore report success when reproduced.

## Changes and next evidence

The investigation did not change installed game files, saves, or Steam settings. Diagnostic tools, this report, and the beta 3 candidate artifacts are included in the repository.

For the reported freeze, the remaining missing evidence is the installed beta/game version and `BepInEx/LogOutput.log` from that run (ideally both players). The beta 3 candidate removes only the two hover base calls and changes the display label. Its purpose is to test the strongest mechanism against the now-confirmed host hard-freeze symptom; it is not a verified stability release.

## Beta 3 candidate

The [beta 3 release download](https://github.com/dexterlabs1/megabonk-deck/releases/download/deck-beta3/megabonk-deck-beta3-test.zip) and [repository copy of the offline test bundle](./releases/megabonk-deck-beta3-test.zip) contain install and restore desktop launchers, the candidate package, matching GPL source, and [instructions](./candidate/README.txt). Extract the whole ZIP in Deck Desktop Mode, close Megabonk, and open `Test-Deck-Beta3.desktop`; confirm the game menu says **Deck beta 3**. The regular standalone updater remains on beta 2.

The candidate's compiled-IL check passes all 8 assertions, including absence of native base hover calls, preservation of managed callbacks, and dependency assembly identities matching shipped beta 2. The shipped beta 2 DLL fails the two native-call assertions as the negative control. All 12 existing DLL smoke checks pass. Resolved NuGet dependency versions match the archived beta 2 manifest.

Thirteen Linux candidate integration tests cover real official/beta 1/beta 2 upgrades, restore to the original official DLL, rollback after a marker-write failure, rejected invalid inputs, and execution of the embedded desktop launcher commands with paths and file URIs containing spaces. No real Steam installation is used. The unchanged original Python suite was also rerun: 24 passed, with its real-BepInEx install test skipped because that temporary fixture was no longer available; the earlier audit completed that same test successfully.

Physical validation remains: host a room, move controller focus onto and away from Show Room Code, select a character, continue to map selection, and start with a second player. Some native hover highlighting may be absent. If the game still freezes, retain `BepInEx/LogOutput.log` from that run before restarting.

## User's beta 3 Deck test

The user reports that hosting, showing the room code, and selecting a character no longer freeze. The lobby contained only the host, so character confirmation could not proceed. The code in `WindowManagerPatches.Update_Postix` deliberately disables host confirmation while `GetAllPlayers().Count() < 2`; that observation is consistent with the existing lobby requirement.

The test exposed two additional menu problems: joystick focus becomes stuck after moving down to Together on first launch (mouse input still works), and Together is too large. The beta 4 candidate targets navigation and button sizing. Multiplayer start with a second player and extended gameplay remain unverified.

## Beta 4 candidate

The [beta 4 test bundle](https://github.com/dexterlabs1/megabonk-deck/releases/download/deck-beta4/megabonk-deck-beta4-test.zip) preserves the cloned button's native references and visual settings, uses Automatic navigation for Together, and matches Play's local geometry. It keeps the beta 3 hover correction and the existing requirement for two players before host confirmation.

Verification: Release PROTON build passed with 15 existing warnings and no errors. A managed harness executes the actual clone setup against Unity substitutes: 24 beta 4 assertions pass, and nine beta 3 negative controls expose the missing setup. Ten compiled navigation checks and seven compiled hover checks pass. These verify source setup and generated code, not native navigation or rendered appearance.

All 14 Linux candidate integration tests pass, including beta 3 upgrades, the full beta 1 → 2 → 3 → 4 → official restore chain, rollback, and execution of the embedded launchers with filename and file-URI paths. The bundle includes matching GPL source and the beta 4 restore launcher. Published beta 3 artifacts are unchanged.

Deck acceptance test: confirm the beta 4 label, move down to Together and back up repeatedly, compare its apparent size with the native menu, then host and exercise Show Room Code and character selection again. Confirm needs another player in the lobby. The later screenshot below reports a layout issue; it does not confirm these navigation checks.

## Beta 4 screenshot: room-code entry obstructed

The user supplied a Deck photo showing the beta 4 label and game version 1.0.69. In Friendlies, Paste Code covers the manual-entry field and overlaps Join; status text also collides with that row. The photo does not establish whether the earlier joystick-navigation issue is resolved.

The source explains the collision: with a 550-unit panel, input and Join use anchor Y 0.35 plus offset -20, placing their centers at -102.5 relative to the panel center. Paste is centered at -95. Status is centered at -110. Separate anchors obscure the fact that these controls share one row.

Beta 5 separates the room-code field, keyboard hint, Paste/Join actions, status, and Back into measured rows, makes the Friendlies panel opaque, and explicitly wires the field's viewport and focus action. The prior hover and main-menu clone corrections remain. Root and Friendlies buttons share the bound clone helper; the separate netplay-options toggles remain outside this fix. A [source-derived layout diagram](diagnostics/layout/beta5-layout-diagram.png) was visually reviewed. It is not a native game render.

Beta 5 validation: Release build passed with 15 existing warnings and no errors; 41 layout/input/control checks and five beta 4 negative controls passed. Thirteen compiled-IL checks, seven hover checks, and the prior 24 clone-setup assertions with nine beta 3 negative controls passed. The source archive retains all 299 members; only NetworkMenuTab.cs, MainMenu.cs, and DECK-BETA.md changed from beta 4.

All 16 candidate integration tests and all 25 original installer tests passed using checksum-verified upstream fixtures. The [beta 5 download](https://github.com/dexterlabs1/megabonk-deck/releases/download/deck-beta5/megabonk-deck-beta5-test.zip) includes the unchanged original installer for the friend's first setup, followed by the beta updater, plus matching GPL source and restore launcher. Existing installations use only Test-Deck-Beta5.desktop. New installations need internet for the original installer.

Remaining physical test: Together > Friendlies, select the visible code field, press STEAM+X, type a real host code, dismiss the keyboard, and select Join. Test two-player character confirmation and a short run. No successful native beta 5 entry or multiplayer session has been reported yet.

## One-file friend installer and remote workflow

The new 13,081-byte `Install-Megabonk-Deck-Beta5.desktop` embeds the audited original installer, beta 5 updater, and a coordinator. It downloads only the pinned runtime ZIP (187,542 bytes) plus upstream dependencies for fresh setups. There is one installation confirmation and no separate beta-update step. Existing published ZIPs are unchanged.

Thirteen Linux integration tests passed with real archives, including execution of the exact Desktop launcher payload in a separate process from an unrelated working directory. They cover fresh setup, saves/backups, existing official and beta 4 upgrades, idempotence, restore, cancellation, corruption and concurrent installation changes.

All 87 remote workflow tests passed in WSL; Windows passed 65 with 22 Linux-only skips. Tests cover SSH command construction and transfer failures, stale/incomplete screenshot rejection, process selection, virtual-input cleanup, and the actual helper subprocess installing beta 5 and restoring the original DLL under a temporary HOME. Pairing, actual Gaming Mode capture/input and reboot reconnection are tracked in [the remote workflow](remote/README.md).

## Physical Deck session and project separation

Valve pairing subsequently completed. The Deck runs SteamOS 3.8.16 build
20260716.1 and Megabonk 1.0.69. Real Gaming Mode screenshots, commands, verified
transfers, virtual mouse/keyboard/controller input, launch/stop and logs were
tested. Original-mod restore and beta reinstall preserved the original backup.
The Deck rebooted and reconnected without another pairing prompt; a fresh Gaming
Mode screenshot was captured and inspected afterward.

Reusable controls now live in the independent local `SteamDeckControl` project.
Its 88 tests pass in WSL (74 pass on Windows with 14 Linux-only skips). This repo
retains the Megabonk adapter and deployment pins; 11 adapter/forwarder tests pass.
The separated core and adapter were bootstrapped and verified against the Deck.
See [live testing notes](knowledge/remote-live-testing.md).

## Beta 6 controller corrections

Live beta 5 logs exposed three component-array calls whose compiled return type
does not match the generated Deck IL2CPP assembly. Beta 6 uses the existing runtime
compatibility helper. It also confines modal navigation, restores the underlying
window's navigation when closing, and draws a managed gold selection marker.
Native hover callbacks alone did not render that marker in live tests.

The physical Deck showed the marker moving between Friendlies and Close. A opened
Friendlies, direct keyboard input appeared in the room-code field, B returned to
the parent menu, and controller activation of Host opened character selection.
The game remained responsive around 60 fps. A later host-transition check caught
stale modal ownership while the character window was active; the retained live
notes explain that additional correction.

The final handoff correction passed on the Deck: after hosting entirely by
controller, Right and A changed Fox to Sir Oofie. Room-code reveal remained
responsive at 60 fps. Logs contained no modal missing-method/controller errors
or stale ownership of the character window. Final official restore and beta 6
reinstall passed. The C# changes pass 38 production-source harness checks and
26 compiled-IL checks; the Release build has zero errors and 15 existing warnings.

The one-file beta 6 launcher is about 13 KB and downloads only runtime packages.
Seventeen candidate, 14 friend-installer and 10 deployment integration tests use
the real pinned archives, including subprocess launchers, beta 5 upgrades,
rollback, and official restore. Matching GPL source is packaged separately and
inside the offline test bundle. Previously published artifacts remain unchanged.

Remaining acceptance requires a second account: joining by a real room code,
two-player character confirmation, match start and extended play. Fresh setup on
a second physical Deck, built-in joystick behavior and physical STEAM+X also need
confirmation. Virtual STEAM+X opened Steam's menu instead; direct remote typing
worked. These results support a test release, not a claim of complete stability.

Published as `deck-beta6` from commit `33d0315`. All five package/source assets
were downloaded from the public release URLs and matched `candidate-beta6/artifacts.json`.
The one-file launcher's SHA-256 is
`d4a70d248edf9ceb0fed5abe95f537ee8c4eb6ab36315ea3bbf4cc0a9fe191cf`.

## Beta 7 built-in controller startup fix

The user reported that physical Deck controls worked in Steam but not in beta 6
after a cold game launch. Opening and closing Steam's menu restored them. Tests
with the loader temporarily disabled, then with official Together 5.1.0, both
accepted physical controls immediately. Steam logged `uses xinput : false` in
working vanilla as well, so that message did not identify the defect.

Beta 7 limits cursor ownership to active multiplayer modals. Beta 6 forced an
unlocked, visible cursor every frame on the normal main menu. The user confirmed
that beta 7 immediately accepted D-pad navigation down to Together, back up,
and A to open Together without first opening Steam's menu. This is physical
input confirmation, separate from the earlier virtual-controller tests.

The tested DLL SHA-256 is
`70f17f04dc145ccdf3236dbb27ba04efb6105e495c793821dab20c41741f3061`.
The only code changes from beta 6 are the cursor condition and displayed beta
number. Protocol/assembly version remains 5.1.0. All 45 source-harness checks and
26 compiled-IL checks pass. Released beta 6 fails the new native cursor-state
preservation test, as expected. The Release build succeeds with no errors.

All 18 candidate, 15 friend-installer and 21 remote integration checks pass using
real pinned archives in WSL. The 13,265-byte friend launcher downloads runtime
packages only. The source archive retains 299 members with exactly three changed
from beta 6, and the incremental patch reproduces it byte for byte.

On the actual Deck, beta 6 upgraded to the final beta 7 bundle while preserving
the original backup path. Official restore returned the expected original DLL
hash. Beta 7 reinstall and launch then succeeded, with no new startup errors.
The installed DLL is identical to the candidate the user physically tested.

Published as prerelease `deck-beta7` from `4beb033`. All six public assets,
including the artifact manifest, were downloaded without authentication and
matched their recorded hashes. The one-file installer SHA-256 is
`01c5a26f698c40bf2bd5c334d5932f48cf9ac06e22a2844a65a544cfab1faf9c`.

Two-player joining, match start, extended play, a fresh install on a friend's
physical Deck and physical STEAM+X remain unverified.
