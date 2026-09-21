Megabonk Deck beta 5 - test candidate

Targets overlapping controls in the Together/Friendlies menu and makes the
manual room-code field visible. Keeps the earlier hover and navigation changes.
Physical Steam Deck layout, typing, and two-player gameplay still need testing.

EXISTING Together installation (official Proton 5.1.0 or Deck beta 1-4):
1. Switch to Desktop Mode and close Megabonk. Steam can stay open.
2. Extract the WHOLE megabonk-deck-beta5-test.zip archive in Downloads.
3. Open the extracted folder and double-click Test-Deck-Beta5.desktop.
   If KDE asks whether to trust/execute the launcher, allow it. If required,
   right-click > Properties > Permissions > Is executable, then launch it.
4. Confirm the update. Launch Megabonk in Gaming Mode and check Deck beta 5.
This update uses the included package and needs no download or Steam restart.

NEW installation (for your friend):
1. Install Megabonk through Steam and launch it once, then close the game.
2. Switch to Desktop Mode and extract the WHOLE test bundle in Downloads.
3. Double-click Install-Megabonk-Together.desktop and follow its prompts.
   This is the unchanged original installer. It needs internet to download
   pinned BepInEx build 752 and Together Proton 5.1.0 packages. It closes and
   reopens Steam to apply the launch setting; finish other games/downloads first.
4. After the original installer succeeds, double-click Test-Deck-Beta5.desktop
   in the same folder. Confirm the update, then launch the game in Gaming Mode.
5. Check that the menu says Deck beta 5.
A new installation is NOT fully offline; only the beta update is bundled.

TEST WITH YOUR FRIEND:
- Open Together! > Friendlies. Check that Host, the room-code field, Paste Code, Join, and
  Back are separate and readable, with no main-menu buttons covering them.
- Select the room-code field, press STEAM+X for the keyboard, and type a code.
  Close the keyboard, check the text, and choose Join. Paste Code is optional.
- Have one player host and show the room code; the other enters it to join.
- Select characters and continue together. Host Confirm requires at least
  two players in the lobby. Starting a match and extended play are unverified.
- Check Back and reopen Together!; then check joystick movement up and down.

Keep every launcher beside the included packages. Do not launch directly
inside the ZIP viewer or move the beta launcher alone onto the Desktop.
No terminal commands or sudo are needed. The beta updater changes only the
multiplayer DLL; it preserves the original official backup and game saves.

TO UNDO THE BETA:
Close Megabonk and double-click Restore-Official-Multiplayer.desktop from THIS
folder. It restores official Together 5.1.0, including after upgrading from
older betas. It does not uninstall the base multiplayer mod or BepInEx.
Original backups remain under ~/.local/share/megabonk-deck/backups. Earlier
restore launchers do not recognize the beta 5 DLL.

If installation stops, read the displayed reason. Unknown versions, missing or
damaged original backups, modified packages, and a running game are refused.

megabonk-deck-beta5-source.zip contains the matching modified mod source and
GPL license. candidate_updater.py and installer.py are the Python sources
embedded in the beta update/restore launchers. SHA256SUMS.json lists hashes.
This test bundle is separate from the regular installer and standalone updater.
