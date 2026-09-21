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

Deck acceptance test: confirm the beta 4 label, move down to Together and back up repeatedly, compare its apparent size with the native menu, then host and exercise Show Room Code and character selection again. Confirm needs another player in the lobby. No physical beta 4 result has been reported yet.
