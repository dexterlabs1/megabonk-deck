# Remote testing on the physical Deck

The reusable controls live in the sibling `SteamDeckControl` project. This repo
owns the Megabonk adapter and checksum-pinned mod deployment under `remote/`.
Private connection settings, SSH keys, screenshots and logs are not release assets.

## September 21, 2026 acceptance

Pairing succeeded through Valve's official Devkit client. The physical Deck runs
SteamOS 3.8.16 (build 20260716.1), Gaming Mode at 1280x800, and Megabonk 1.0.69.
SSH commands, verified file transfer, screenshots, game launch/stop, logs,
virtual mouse and keyboard, and virtual controller navigation worked live.

Beta 5 was restored to the original official DLL and reinstalled remotely. The
original hash was `a5ee8a76785068d1e1f8715b6fdd57d8801fbed3b9f1c62fa0c9e05ae7893a28`;
the reinstalled beta 5 hash matched its published package. The backup remained
intact. No saves were restored or edited.

After a real reboot, SSH reconnected without pairing and a fresh Gaming Mode
screenshot was captured and viewed. The reboot command was Valve's
`/usr/bin/steamos-polkit-helpers/steamos-reboot-now`; plain `systemctl reboot`
required interactive authorization. Sleep, power-off, network loss and a complete
OS freeze remain outside unattended recovery.

## Observed mod behavior

- Main-menu D-pad navigation reached Together and returned to Shop.
- Friendlies rendered separate room-code, Paste, Join and Back controls.
- Remote keyboard input visibly entered `TEST1234` into the room-code field.
- Hosting and revealing the room code remained responsive at about 60 fps.
- Solo-host character confirmation was disabled, consistent with the two-player rule.

These are virtual-input tests on real hardware. They do not establish that the
built-in joystick behaves identically. A second account has not joined a room;
character confirmation, match start and extended multiplayer remain unverified.

## GOTCHA: virtual controller and Steam keyboard

A virtual controller created before launching the game was ignored by the game
after reboot. Restarting the input daemon after the main menu appeared restored
D-pad navigation. Start the virtual controller after game launch and inspect the
result; do not assume a successful input response proves the game received it.

The virtual STEAM+X chord opened Steam's menu instead of its keyboard, including
after staged Guide-button timing. Regular remote keyboard typing worked. The
physical Deck STEAM+X shortcut still needs separate verification.

## GOTCHA: modal input binary compatibility

Beta 5 logs showed repeated `MissingMethodException` failures from
`DeckMenuControls.IsEditingText`. Three direct component-array calls used the
compile reference's managed-array return signature, but the Deck-generated
interop assembly returns an IL2CPP array. The existing runtime compatibility
helper is required for these calls. See the retained
[compiled regression](../diagnostics/modal-navigation/README.md).

The first unpublished beta 6 candidate removed that exception, and manual typing
and Back worked. Controller focus could still reach background buttons. This
separate behavior was caught by live testing after the binary checks passed.

## GOTCHA: native navigation and hover callbacks are separate

Replacing `Window.allButtons` does not constrain Unity's Automatic navigation.
Beta 6 saves and disables background navigation, reapplies modal membership, and
repairs selection each frame. Restoring the window restores its exact saved
navigation and button collections.

The native hover callbacks did not produce a visible highlight in live captures,
even after direct color writes were added to the overrides. A managed gold marker
applied in the modal's late tick did render correctly. Friendlies and Close were
visibly highlighted in successive screenshots, and A activated the selected
control. The marker preserves and restores original graphic colors.

The next live host test found a separate transition issue: an empty, hidden
NetworkMenuTab remained eligible while `W_Character` was active. Its zero-button
list blocked controller character selection while the game kept animating.
Keep main-menu modal eligibility tied to the main-menu window; other in-game
modals must retain their own behavior.

Both connection-success coroutines originally opened character selection before
a scaled one-second cleanup delay. Menu time can stop advancing, leaving the
empty modal registered. Beta 6 releases ownership before opening characters,
uses a real-time cleanup delay and excludes NetworkMenuTab outside the main menu.

The final DLL (`c79cf7d1abf4b25c02ee8b51d7d754f57a98a65fb213fad0464059d446af4580`)
passed the live handoff: controller input hosted a room, moved from Fox to Sir
Oofie and selected him; room-code reveal remained responsive at 60 fps. The log
contained no modal missing-method or controller exceptions and no stale
NetworkMenuTab ownership of the character window. Final official restore and
beta 6 reinstall also passed. Testing ended with the game and virtual input
stopped and beta 6 installed.
