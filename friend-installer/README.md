# One-file Deck beta 7 installer

Download **Install-Megabonk-Deck-Beta7.desktop** onto the Deck in Desktop Mode and open it. KDE may first ask you to trust or execute the downloaded launcher. Confirm the install once. No ZIP extraction or separate beta updater is needed.

Megabonk must already be installed and launched once from that Steam account, then closed. Internet is required. A fresh mod installation downloads about 34 MB and closes/reopens Steam; existing managed official/beta installations update only the multiplayer DLL. Both players use this same installer.

After installation, launch Megabonk normally. The menu must say **Deck beta 7**. Use Together > Friendlies; select the code field and STEAM+X to type. The host needs a second player before character confirmation.

Beta 7 leaves cursor ownership with the native main menu. The user verified cold-launch navigation down to Together, back up, and A activation using the physical Deck controls. Two-player joining, match start, extended play, a fresh physical installation, and the built-in STEAM+X keyboard still need testing.

This composes the unchanged official installer and pinned beta 7 updater, embedded from the published bundle. Downloaded code is not executed. All archives and DLLs retain their SHA-256 checks, save backups, locks, and update rollback behavior. Unknown mods and unverified backups are refused. If the official install completes but the beta step fails, the error says completion was not confirmed; run the launcher again after fixing the reported cause.

The [beta 7 release](https://github.com/dexterlabs1/megabonk-deck/releases/tag/deck-beta7) includes matching GPL source and the older ZIP with its **Restore-Official-Multiplayer.desktop** launcher. No published ZIP was changed.

Build: `python friend-installer/build.py`. Linux tests: set `MEGABONK_OFFICIAL_ZIP` and `MEGABONK_LOADER_ZIP` to the pinned upstream archives, then run `python3 -m unittest discover -s friend-installer -v`. Tests use temporary Steam fixtures, not a physical Deck.
