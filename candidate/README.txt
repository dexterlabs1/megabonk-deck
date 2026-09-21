Megabonk Deck beta 3 - local test candidate

This candidate removes recursive button hover calls suspected in the host's
character-selection freeze. It has not been verified on a physical Steam Deck.

On your Deck:
1. Switch to Desktop Mode and close Megabonk. Steam can stay open.
2. Extract the WHOLE megabonk-deck-beta3-test.zip archive in Downloads.
3. Open the extracted folder and double-click Test-Deck-Beta3.desktop.
   If KDE asks whether to trust/execute the launcher, allow it. If required,
   right-click > Properties > Permissions > Is executable, then launch it.
4. Confirm the update, then launch Megabonk in Gaming Mode. Check that the
   menu says Deck beta 3. Host a room and try selecting a character.

Custom-button hover highlighting may be reduced because this candidate removes
native hover callbacks. Check D-pad focus and selection during your Deck test.

Keep the launcher beside megabonk-deck-beta3.zip. Do not launch it directly
inside the ZIP viewer or move the launcher alone onto the Desktop.

Requires an existing official Together Proton 5.1.0, Deck beta 1, or beta 2
installation. No downloads, terminal commands, sudo, or Steam restart are needed.
Only the multiplayer DLL changes; game saves and Steam settings are untouched.

To undo:
Close Megabonk, return to this folder in Desktop Mode, and double-click
Restore-Official-Multiplayer.desktop. It restores official Together 5.1.0,
including after upgrading from beta 1 or beta 2. The original backup is kept
under ~/.local/share/megabonk-deck/backups. Use THIS restore launcher for beta 3;
the older beta 2 restore launcher does not recognize the beta 3 DLL.

If installation stops, read the displayed reason. Unknown versions, missing or
damaged original backups, modified packages, and a running game are refused.

Included megabonk-deck-beta3-source.zip contains matching modified mod source
and its GPL license. candidate_updater.py and installer.py are the Python
sources embedded in both desktop launchers. SHA256SUMS.json lists bundle hashes.
This is a local candidate, not a published update to the regular installer.
