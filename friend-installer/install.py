#!/usr/bin/env python3
"""One confirmation for the audited official installer followed by Deck beta 6."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import installer
import candidate_updater as updater

PACKAGE_URL = 'https://github.com/dexterlabs1/megabonk-deck/releases/download/deck-beta6/megabonk-deck-beta6.zip'
PACKAGE_SHA = 'e3dcce4709644ddb6548ffbe3afe8a88f5c2d0e630503350e73ccfd91f7d474d'


def installed_kind(game, state):
    marker = game / '.megabonk-deck.json'
    updater.reject_symlinks(marker)
    target = game / 'BepInEx/plugins/MegabonkTogether/MegabonkTogether.dll'
    updater.reject_symlinks(target)
    if not marker.exists():
        if any((game / name).exists() for name in ('BepInEx', 'winhttp.dll', 'doorstop_config.ini', 'dotnet')):
            raise RuntimeError('An existing unmanaged mod loader was found. Nothing changed; restore a clean game or use the existing beta updater for your managed setup.')
        return 'fresh'
    if json.loads(marker.read_text()).get('version') != installer.VERSION:
        raise RuntimeError('A different installer version is present. Restore its backup before changing versions.')
    if not target.is_file():
        raise RuntimeError('The managed installation is incomplete. Restore its backup before reinstalling.')
    current = updater.digest(target.read_bytes())
    if current in updater.PREVIOUS_BETA_SHAS | {updater.BETA_DLL_SHA}:
        updater.verified_backup(state, target, current)
    elif current != updater.ORIGINAL_DLL_SHA:
        raise RuntimeError('Unknown multiplayer DLL. Nothing changed.')
    return 'managed'


def get_package():
    package = installer.download(PACKAGE_URL, PACKAGE_SHA)
    # Keep the boundary explicit even if a transport implementation changes.
    if hashlib.sha256(package).hexdigest() != PACKAGE_SHA:
        raise RuntimeError('Beta 6 download checksum mismatch. No game files changed.')
    if updater.digest(package) != updater.PACKAGE_SHA:
        raise RuntimeError('Beta 6 package checksum mismatch. No game files changed.')
    return package


def main():
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise RuntimeError('Open this installer on your Steam Deck in Desktop Mode, without sudo.')
    home = Path.home()
    _, _, game, _ = installer.discover(home)
    state = home / '.local/share/megabonk-deck'
    updater.reject_symlinks(state)
    updater.reject_symlinks(state / 'install.lock')
    if installer.running('Megabonk.exe'):
        raise RuntimeError('Close Megabonk before installing.')
    kind = installed_kind(game, state)
    message = ('Install Megabonk Together with Deck beta 6?\n\n'
               'Both players should install this version. Close Megabonk first.\n\n'
               + ('This downloads about 34 MB, backs up saves and changed files, and sets the Steam launch option. Steam will close and reopen. Finish other games/downloads first.\n\n'
                  if kind == 'fresh' else 'This updates the multiplayer DLL and preserves the official mod backup. Steam can stay open.\n\n')
               + 'Beta 6 is a test version. Deck typing and two-player play still need testing.\n\nGame: ' + str(game))
    if not installer.dialog(message, True):
        return False
    package = get_package()
    if kind == 'fresh':
        # The already-authorized original installer keeps its discovery, lock,
        # checksums, save backups, transactions, and Steam restart behavior.
        original_dialog = installer.dialog
        original_discover = installer.discover
        def fresh_discover(home):
            found = original_discover(home)
            if found[2] != game or installed_kind(game, state) != 'fresh':
                raise RuntimeError('The installation changed while downloading. Run this installer again.')
            return found
        installer.dialog = lambda message, question=False: True
        # Original main calls discover after acquiring its installation lock.
        installer.discover = fresh_discover
        try:
            installer.main()
        finally:
            installer.dialog = original_dialog
            installer.discover = original_discover
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'install.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another installer is running. Close it and try again.')
        if installer.running('Megabonk.exe'):
            raise RuntimeError('Close Megabonk and run this again to finish beta 6.')
        installed_kind(game, state)
        changed = updater.apply_update(game, state, package)
    installer.dialog(('Installed Deck beta 6!' if changed else 'Deck beta 6 is already installed.')
                     + '\n\nLaunch Megabonk normally in Gaming Mode. The first modded launch can take several minutes. The menu should say Deck beta 6.\n\n'
                     'Open Together! > Friendlies. One player hosts and shares the code; the other enters it and joins. Select the code field and press STEAM+X to type. Host Confirm needs two players.\n\n'
                     'Both players should use this same installer. If the game does not start, select Proton Experimental in Steam > Megabonk > Properties > Compatibility.\n\n'
                     'Original backups: ' + str(state / 'backups'))
    return True


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        installer.dialog('Installation stopped: ' + str(exc) + '\n\nBeta 6 completion was not confirmed. If Steam closed, reopen it normally. Your backups are retained.')
        sys.exit(1)
