#!/usr/bin/env python3
"""Install/restore the optional client-side Deck beta over Together 5.1.0."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from installer import Transaction, atomic, dialog, discover, download, running, safe_extract

PACKAGE_URL = 'https://raw.githubusercontent.com/dexterlabs1/megabonk-deck/41acc23f09e6a61b34e3505cd673d63ac7f9c7c2/releases/megabonk-deck-beta1.zip'
PACKAGE_SHA = '271091b243916a602a5736d013a5b38a23cc58a02c6434e25a163a6e49fdc56f'
BETA_DLL_SHA = '0bac74d9f16165c63140f703e1e8489654120d83d54d15585b2b738ff765d60b'
ORIGINAL_DLL_SHA = 'a5ee8a76785068d1e1f8715b6fdd57d8801fbed3b9f1c62fa0c9e05ae7893a28'


def restore(state):
    marker = state / 'deck-beta-backup.json'
    if not marker.exists():
        raise RuntimeError('No Deck beta backup found. Nothing to restore.')
    info = json.loads(marker.read_text())
    target = Path(info['target'])
    if any(p.is_symlink() for p in [target, *target.parents]):
        raise RuntimeError('The game path has changed to a symlink. Restore manually from the backup.')
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != BETA_DLL_SHA:
        raise RuntimeError('The mod changed after this update. Keeping the newer file; your original is at ' + info['original'])
    original = Path(info['original']).read_bytes()
    if hashlib.sha256(original).hexdigest() != info['original_sha']:
        raise RuntimeError('Backup checksum does not match; nothing was changed.')
    if dialog('Restore the multiplayer mod version you had before the Deck beta?\nYour saves and Steam settings will stay as they are.', True):
        atomic(target, original)
        marker.unlink()
        dialog('Previous multiplayer mod restored. Launch Megabonk normally.')


def apply_update(game, state, package):
    target = game / 'BepInEx/plugins/MegabonkTogether/MegabonkTogether.dll'
    if not target.is_file():
        raise RuntimeError('Install Megabonk Together 5.1.0 with the original installer first.')
    current = target.read_bytes()
    current_sha = hashlib.sha256(current).hexdigest()
    if current_sha == BETA_DLL_SHA:
        return False
    if current_sha != ORIGINAL_DLL_SHA:
        raise RuntimeError('This is not the expected original 5.1.0 Proton mod. No files changed; restore that version first.')
    with tempfile.TemporaryDirectory(prefix='megabonk-deck-beta-') as temp:
        temp = Path(temp)
        safe_extract(package, temp)
        dll = (temp / 'MegabonkTogether.dll').read_bytes()
        if hashlib.sha256(dll).hexdigest() != BETA_DLL_SHA:
            raise RuntimeError('Beta DLL checksum mismatch. No files changed.')
        if running('Megabonk.exe'):
            raise RuntimeError('Close Megabonk before updating.')
        # Recheck after download/extraction in case another updater changed it.
        if target.read_bytes() != current:
            raise RuntimeError('Mod changed during the update. Run this again after the other update finishes.')
        backup = state / 'backups' / ('deck-beta1-' + time.strftime('%Y%m%d-%H%M%S'))
        tx = Transaction(backup)
        try:
            tx.write(target, dll)
            atomic(state / 'deck-beta-backup.json', json.dumps({
                'target': str(target), 'original': str(backup / '0'),
                'original_sha': current_sha, 'beta_sha': BETA_DLL_SHA,
            }, indent=2).encode())
        except BaseException:
            tx.rollback()
            raise
    return True


def main():
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise RuntimeError('Run on your Steam Deck in Desktop Mode, without sudo.')
    state = Path.home() / '.local/share/megabonk-deck'
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'install.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another installer is already running.')
        if running('Megabonk.exe'):
            raise RuntimeError('Close Megabonk, then run this again. Steam can stay open.')
        if '--restore' in sys.argv:
            restore(state)
            return
        _, _, game, _ = discover(Path.home())
        if not dialog('Install the Deck controls + Steam invites beta?\n\nAdds controller menu focus, Back navigation, text-entry helpers, Paste Code, and experimental Steam invites.\n\nCompiled and helper-tested; not yet tested on a physical Deck. Both players need this beta for automatic invite joining.\n\nOnly the mod DLL changes. Your previous DLL is backed up. Use Restore-Original-Multiplayer.desktop to undo this update. Steam will stay open.', True):
            return
        print('Downloading and verifying Deck beta…', flush=True)
        changed = apply_update(game, state, download(PACKAGE_URL, PACKAGE_SHA))
        dialog(('Updated!' if changed else 'This beta is already installed.') + '\n\nLaunch Megabonk in Gaming Mode. The menu version says Deck beta.\n\nHost a Friendlies room, then choose Invite Friends. Copy Code remains available.\n\nThe trackpad needs a Mouse binding in Steam Input; STEAM + right trackpad also works.\n\nUse Restore-Original-Multiplayer.desktop if needed.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        dialog('Deck update stopped: ' + str(exc))
        sys.exit(1)
