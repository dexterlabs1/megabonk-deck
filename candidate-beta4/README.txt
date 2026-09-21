Megabonk Deck beta 4 - test candidate

Targets controller navigation getting stuck on Together! and the oversized
Together! button. Keeps beta 3's hover fix, which the tester reports stopped the host
freeze when showing a room code and selecting a character. Beta 4 still needs
physical Steam Deck and live multiplayer testing.

On your Deck:
1. Switch to Desktop Mode and close Megabonk. Steam can stay open.
2. Extract the WHOLE megabonk-deck-beta4-test.zip archive in Downloads.
3. Open the extracted folder and double-click Test-Deck-Beta4.desktop.
   If KDE asks whether to trust/execute the launcher, allow it. If required,
   right-click > Properties > Permissions > Is executable, then launch it.
4. Confirm the update, then launch Megabonk in Gaming Mode. Check that the
   menu says Deck beta 4.
5. Move down to Together! with the joystick, then back up. Repeat several times.
   Check the button size. Host a room, show its room code, and select a character.
   Host Confirm requires at least two players in the lobby.

Keep the launcher beside megabonk-deck-beta4.zip. Do not launch it directly
inside the ZIP viewer or move the launcher alone onto the Desktop.

Requires an existing official Together Proton 5.1.0 or Deck beta 1, 2, or 3
installation. No downloads, terminal commands, sudo, or Steam restart are needed.
Only the multiplayer DLL changes; game saves and Steam settings are untouched.

To undo:
Close Megabonk, return to this folder in Desktop Mode, and double-click
Restore-Official-Multiplayer.desktop. It restores official Together 5.1.0,
including after upgrading from earlier betas. The original backup is kept
under ~/.local/share/megabonk-deck/backups. Use THIS restore launcher for beta 4;
older restore launchers do not recognize the beta 4 DLL.

If installation stops, read the displayed reason. Unknown versions, missing or
damaged original backups, modified packages, and a running game are refused.

Included megabonk-deck-beta4-source.zip contains matching modified mod source
and its GPL license. candidate_updater.py and installer.py are the Python
sources embedded in both desktop launchers. SHA256SUMS.json lists bundle hashes.
This test bundle is separate from the regular installer.
