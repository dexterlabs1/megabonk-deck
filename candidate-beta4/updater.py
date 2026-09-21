#!/usr/bin/env python3
"""Offline beta 4 candidate updater. Bundled hashes are inserted by build.py."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import unquote, urlsplit
from installer import Transaction, atomic, dialog, discover, running, safe_extract

PACKAGE_SHA = '@PACKAGE_SHA@'
BETA_DLL_SHA = '@BETA_DLL_SHA@'
PREVIOUS_BETA_SHAS = {
    '0bac74d9f16165c63140f703e1e8489654120d83d54d15585b2b738ff765d60b',
    'e63b944809f4b3d23adbfda7dec19ae99ea732b89c406d6aaa34b6832f6d5a9f',
    'fe33a93735301f802e3eae9b15cbddd5fe5e43640a7dcd28e0b367779bee6da7',
}
ORIGINAL_DLL_SHA = 'a5ee8a76785068d1e1f8715b6fdd57d8801fbed3b9f1c62fa0c9e05ae7893a28'
PACKAGE_NAME = 'megabonk-deck-beta4.zip'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def reject_symlinks(path):
    if not path.is_absolute() or any(p.is_symlink() for p in [path, *path.parents]):
        raise RuntimeError('Expected an absolute path without symlinks: ' + str(path))


def bundle_directory(location):
    """Desktop Entry %k can be an absolute filename or a local file URI."""
    if not location:
        raise RuntimeError('Extract the whole test bundle, then launch its desktop file.')
    if location.startswith('file:'):
        uri = urlsplit(location)
        if uri.netloc not in ('', 'localhost') or uri.query or uri.fragment:
            raise RuntimeError('The launcher must be on this computer.')
        location = unquote(uri.path)
    path = Path(location)
    if not path.is_absolute() or not path.is_file():
        raise RuntimeError('Cannot locate the launcher. Extract the entire bundle first.')
    return path.resolve().parent


def verified_backup(state, target, current_sha):
    marker = state / 'deck-beta-backup.json'
    reject_symlinks(marker)
    if not marker.is_file():
        raise RuntimeError('Original backup record is missing. No files changed.')
    info = json.loads(marker.read_text())
    original = Path(info['original'])
    reject_symlinks(original)
    if (info.get('target') != str(target) or info.get('beta_sha') != current_sha
            or info.get('original_sha') != ORIGINAL_DLL_SHA
            or digest(original.read_bytes()) != ORIGINAL_DLL_SHA):
        raise RuntimeError('Original backup could not be verified. No files changed.')
    return info


def restore(state):
    marker = state / 'deck-beta-backup.json'
    reject_symlinks(marker)
    if not marker.is_file():
        raise RuntimeError('No Deck beta backup found. Nothing to restore.')
    info = json.loads(marker.read_text())
    target = Path(info['target'])
    reject_symlinks(target)
    current = target.read_bytes()
    current_sha = digest(current)
    if current_sha not in PREVIOUS_BETA_SHAS | {BETA_DLL_SHA}:
        raise RuntimeError('The mod changed after this update. No files changed.')
    info = verified_backup(state, target, current_sha)
    original = Path(info['original']).read_bytes()
    if not dialog('Restore official Megabonk Together 5.1.0?\nYour saves and Steam settings will stay as they are.', True):
        return
    if running('Megabonk.exe') or target.read_bytes() != current:
        raise RuntimeError('Close Megabonk and any other updater, then try again.')
    if digest(original) != ORIGINAL_DLL_SHA:
        raise RuntimeError('Original backup checksum mismatch. Nothing changed.')
    atomic(target, original)
    marker.unlink()
    dialog('Official multiplayer mod restored. Launch Megabonk normally.')


def apply_update(game, state, package):
    if digest(package) != PACKAGE_SHA:
        raise RuntimeError('Local candidate package checksum mismatch. No files changed.')
    target = game / 'BepInEx/plugins/MegabonkTogether/MegabonkTogether.dll'
    reject_symlinks(target)
    reject_symlinks(state)
    if not target.is_file():
        raise RuntimeError('Install official Megabonk Together 5.1.0 first.')
    current = target.read_bytes()
    current_sha = digest(current)
    prior = None
    if current_sha in PREVIOUS_BETA_SHAS | {BETA_DLL_SHA}:
        prior = verified_backup(state, target, current_sha)
        if current_sha == BETA_DLL_SHA:
            return False
    elif current_sha != ORIGINAL_DLL_SHA:
        raise RuntimeError('Unknown mod version. Expected official 5.1.0 or Deck beta 1, 2, or 3. No files changed.')
    with tempfile.TemporaryDirectory(prefix='megabonk-deck-candidate-') as temp:
        temp = Path(temp)
        safe_extract(package, temp)
        dll = (temp / 'MegabonkTogether.dll').read_bytes()
        if digest(dll) != BETA_DLL_SHA:
            raise RuntimeError('Candidate DLL checksum mismatch. No files changed.')
        if running('Megabonk.exe') or target.read_bytes() != current:
            raise RuntimeError('Close Megabonk and any other updater, then try again.')
        backup = state / 'backups' / ('deck-beta4-' + str(time.time_ns()))
        reject_symlinks(backup)
        tx = Transaction(backup)
        try:
            tx.write(target, dll)
            tx.write(state / 'deck-beta-backup.json', json.dumps({
                'target': str(target), 'original': prior['original'] if prior else str(backup / '0'),
                'original_sha': ORIGINAL_DLL_SHA, 'beta_sha': BETA_DLL_SHA,
            }, indent=2).encode())
        except BaseException:
            tx.rollback()
            raise
    return True


def main():
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise RuntimeError('Run on your Steam Deck in Desktop Mode, without sudo.')
    state = Path.home() / '.local/share/megabonk-deck'
    reject_symlinks(state)
    state.mkdir(parents=True, exist_ok=True)
    reject_symlinks(state / 'install.lock')
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
        folder = bundle_directory(sys.argv[1] if len(sys.argv) > 1 else '')
        package = (folder / PACKAGE_NAME).read_bytes()
        if digest(package) != PACKAGE_SHA:
            raise RuntimeError('Local candidate package checksum mismatch. No files changed.')
        _, _, game, _ = discover(Path.home())
        if not dialog('Install Deck beta 4 test candidate?\n\nTargets controller navigation getting stuck on Together! and its oversized button. Keeps the beta 3 hover freeze fix. Beta 4 still needs testing on a physical Deck.\n\nOnly the multiplayer DLL changes; your official 5.1.0 backup is preserved. Use the Restore-Official-Multiplayer launcher in this bundle to undo it. Steam can stay open.', True):
            return
        changed = apply_update(game, state, package)
        dialog(('Updated!' if changed else 'This candidate is already installed.') + '\n\nLaunch Megabonk in Gaming Mode. The menu should say Deck beta 4.\n\nMove down to Together!, then back up with the joystick. Check its size, then host a room and test character selection. Host Confirm requires at least two players in the lobby. Use this bundle\'s Restore-Official-Multiplayer launcher if needed.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        dialog('Candidate update stopped: ' + str(exc))
        sys.exit(1)
