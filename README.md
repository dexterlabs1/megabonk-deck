# Megabonk Together — easy Steam Deck installer

A downloadable launcher that installs **Megabonk Together 5.1.0 (Proton)** and **BepInEx 6 build 752**. No terminal commands, sudo, password, or disabling SteamOS read-only mode needed.

## Installer update — Steam VDF compatibility

If the previous installer stopped with **Invalid Steam VDF**, download a fresh copy using the button below. This update handles UTF-8 byte-order markers, trailing NUL padding, comments, and conditional annotations on unrelated settings. It skips unrelated game manifests and reports the file and line on parsing errors. Do not delete or reset Steam settings.

## Download

**[Download the Steam Deck installer](https://github.com/dexterlabs1/megabonk-deck/raw/refs/heads/main/Install-Megabonk-Together.desktop)**

Share this repository with your buddy: https://github.com/dexterlabs1/megabonk-deck

## Install on your Deck

1. Install **Megabonk** in Steam and launch it once, then close the game.
2. Switch to **Desktop Mode** (Steam > Power > Switch to Desktop).
3. Download **Install-Megabonk-Together.desktop** from this repository using GitHub's **Download raw file** button. Open it in Dolphin, accept **Execute / Trust and Launch** if prompted, and click **Yes** in the installer.

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

The `.desktop` file contains the compressed, self-contained `installer.py`; it does not fetch an executable installer script from a moving GitHub branch. `python3 build.py` regenerates it. Python 3 and the normal SteamOS `steam`, `pgrep`, and `zenity` commands are used. If Zenity is unavailable, the terminal asks for confirmation.

## Compatibility and limits

This is an unofficial convenience installer, not the multiplayer mod itself. [Megabonk Together](https://github.com/Fcornaire/megabonk-together#linux-support-proton--steam-deck) describes Proton/Steam Deck support as experimental and documents the mod against game **1.0.49**. Later game updates may break the mod. No claim is made that every current game build works. The installer does not downgrade the game, install Proton, alter your Steam account, or bypass game ownership.

Tested here: real archive checksums/layouts; simulated install and reinstall using those archives; SD-card library detection; Steam configuration preservation; unsafe archive rejection; symlink protection; backups and rollback. **Not tested on a physical Steam Deck or in a live multiplayer session.** Normal initial SteamOS setup and an installed, previously launched Windows/Proton game are prerequisites. Multiple Megabonk installations and Flatpak Steam are not supported.

## Recovery / uninstall

Exit Megabonk and Steam first. In the downloaded source folder, run:

```bash
python3 restore.py "$HOME/.local/share/megabonk-deck/backups/YOUR-BACKUP-FOLDER"
```

Use the backup from the first installation to return to your original state. If you reinstalled, restore backups in reverse order. Restore refuses files that have changed since the corresponding install rather than overwriting newer settings or mod updates. In that case, `changes.json` maps each changed path to its numbered original backup. You can restore those individual files yourself while Steam is closed. Backups may contain account identifiers and saves; keep them private.

For a quick disable, remove only `WINEDLLOVERRIDES="winhttp=n,b"` from Megabonk's Steam launch options (keep any other options). This stops the loader from being selected by this installer. Generated BepInEx cache folders can remain harmlessly after removal.

Save backups are separate and are **not** restored automatically, so uninstalling does not discard later game progress. `save-locations.json` records where each numbered save copy came from. Restore saves only with the game closed and be mindful of Steam Cloud conflict prompts.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 build.py
```

The real-archive integration check runs when `/tmp/megabonk-assets/bepinex.zip` and `mod.zip` are available; otherwise it explicitly skips. Other checks run offline. Download URLs and SHA-256 values are in `installer.py`.

Credits: [DShad / Fcornaire's Megabonk Together](https://github.com/Fcornaire/megabonk-together), [BepInEx](https://github.com/BepInEx/BepInEx). This repository ships installer code only; upstream binaries are downloaded at install time and retain their own licenses.
