# Megabonk Together — easy Steam Deck installer

A downloadable launcher that installs **Megabonk Together 5.1.0 (Proton)** and **BepInEx 6 build 752**. No terminal commands, sudo, password, or disabling SteamOS read-only mode needed.

## Install Deck beta 6

**[Download the one-file installer](https://github.com/dexterlabs1/megabonk-deck/releases/download/deck-beta6/Install-Megabonk-Deck-Beta6.desktop)** — about 13 KB. Send this link to your friend. No ZIP extraction or separate update is needed.

Beta 6 fixes modal controller compatibility and focus, adds visible selection feedback, and retains the separate room-code field and earlier hover-freeze corrections. Select the field, press **STEAM+X**, enter the host's code, then select **Join**. Direct keyboard entry has been tested on a physical Deck; the built-in keyboard shortcut and two-player joining still need confirmation.

1. Install Megabonk through Steam and launch it once, then close it.
2. In Desktop Mode, download and open **Install-Megabonk-Deck-Beta6.desktop**. Accept **Execute / Trust and Launch** if prompted, then confirm the installation.
3. Return to Gaming Mode, launch Megabonk, and check for **Deck beta 6**. Both players use this same installer.

Internet is required. A fresh setup downloads about 34 MB and restarts Steam. Existing managed official/beta installations update only the multiplayer DLL and preserve the original backup. The launcher downloads the runtime files only; source and diagnostics are separate. Host character confirmation requires at least two players in the lobby.

The [full test bundle](https://github.com/dexterlabs1/megabonk-deck/releases/download/deck-beta6/megabonk-deck-beta6-test.zip) remains available for offline updates, matching source, and **Restore-Official-Multiplayer.desktop**. [Test results and remaining validation](TEST-REPORT-2026-09-21.md). Steam invites remain disabled; share the room code manually. The trackpad needs a Mouse binding in Steam Input.

## Original upstream-only installer

The older `Install-Megabonk-Together.desktop` installs official Together 5.1.0 without the Deck beta fixes; `Update-Deck-Controls.desktop` installs beta 2. Use the one-file beta 6 installer above for current testing. The current installer retains the Steam VDF compatibility fixes; do not delete or reset Steam settings.

## Launching and troubleshooting

If Dolphin opens it as text or won't launch it: right-click the file > Properties > Permissions > **Is executable**, then open it again. Steam will close and reopen during installation. Let the installer finish before reopening Steam yourself. An internet connection and about 500 MB of free space are recommended; backups on reruns need additional space.

Then return to Gaming Mode and launch Megabonk normally. The first modded launch may take several minutes to generate BepInEx interop files. Tap **Together!** on the touchscreen, choose **Friendlies**, and share the room code with your buddy. Both players should run the same installer. The upstream GitHub mod also has its own auto-update behavior, so compare versions if joining fails.

If the mod does not load, choose **Proton Experimental** in Steam > Megabonk > Properties > Compatibility, then try again. The installer sets the required `WINEDLLOVERRIDES="winhttp=n,b" %command%` launch option automatically; it uses your existing Steam compatibility selection rather than forcing a particular Proton build.

## What it does

- Finds a single installed Windows copy using Steam manifests, including libraries on mounted SD cards.
- Downloads directly from the original authors and verifies pinned SHA-256 checksums before changing files.
- Gracefully exits Steam, sets the game's launch option for Steam accounts with an existing game entry, and reopens Steam.
- Preserves other launch arguments and unrelated Steam settings. A conflicting DLL override stops installation with an explanation.
- Backs up local Proton saves, Steam cloud cache, original files, and changed Steam configuration under `~/.local/share/megabonk-deck/backups/`.
- Journals file changes and rolls them back on ordinary installation errors. Hard power loss requires manual recovery from the journal.
- Refuses an existing unmanaged BepInEx installation to avoid mixing loaders. Does not remove your existing mods to make room.
- Installs the loader and plugin together. BepInEx generates its assemblies on launch before loading plugins. This combined installation flow is not hardware-validated here; upstream documents a loader-only first run.

The beta 6 `.desktop` file embeds the audited installer, updater and a small coordinator; it does not fetch executable installer code from a moving branch. `python3 friend-installer/build.py` regenerates it. Python 3 and the normal SteamOS commands are used. If Zenity is unavailable, the terminal asks for confirmation.

## Compatibility and limits

This is an unofficial convenience installer, not the multiplayer mod itself. [Megabonk Together](https://github.com/Fcornaire/megabonk-together#linux-support-proton--steam-deck) describes Proton/Steam Deck support as experimental and documents the mod against game **1.0.49**. Later game updates may break the mod. No claim is made that every current game build works. The installer does not downgrade the game, install Proton, alter your Steam account, or bypass game ownership.

Tested here: real archive checksums/layouts; simulated fresh install and reinstall; SD-card library detection; Steam configuration preservation; unsafe archive rejection; symlink protection; backups and rollback. Physical Deck testing covers remote updates/restores, menus, text entry and solo hosting. **A fresh installation on a second Deck and two-player gameplay remain unverified.** Normal initial SteamOS setup and an installed, previously launched Windows/Proton game are prerequisites. Multiple Megabonk installations and Flatpak Steam are not supported.

## Recovery / uninstall

Exit Megabonk and Steam first. In the downloaded source folder, run:

```bash
python3 restore.py "$HOME/.local/share/megabonk-deck/backups/YOUR-BACKUP-FOLDER"
```

Use the backup from the first installation to return to your original state. If you reinstalled, restore backups in reverse order. Restore refuses files that have changed since the corresponding install rather than overwriting newer settings or mod updates. In that case, `changes.json` maps each changed path to its numbered original backup. You can restore those individual files yourself while Steam is closed. Backups may contain account identifiers and saves; keep them private.

For a quick disable, remove only `WINEDLLOVERRIDES="winhttp=n,b"` from Megabonk's Steam launch options (keep any other options). This stops the loader from being selected by this installer. Generated BepInEx cache folders can remain harmlessly after removal.

Save backups are separate and are **not** restored automatically, so uninstalling does not discard later game progress. `save-locations.json` records where each numbered save copy came from. Restore saves only with the game closed and be mindful of Steam Cloud conflict prompts.

## Development

[Remote Deck workflow](remote/README.md): pair once, then transfer builds, capture screenshots, send virtual input, and collect logs through `deck.cmd`. Actual Deck acceptance is recorded separately from automated tests.

```bash
python3 -m unittest discover -s tests -v
python3 build.py
```

The real-archive integration check runs when `/tmp/megabonk-assets/bepinex.zip` and `mod.zip` are available; otherwise it explicitly skips. Other checks run offline. Download URLs and SHA-256 values are in `installer.py`.

Credits: [DShad / Fcornaire's Megabonk Together](https://github.com/Fcornaire/megabonk-together), [BepInEx](https://github.com/BepInEx/BepInEx). Upstream dependencies are downloaded at install time. Deck beta binaries and their matching GPL source are available in Releases; upstream licenses remain applicable.
