"""Unattended adapter for the immutable, checksum-pinned beta 5 bundle."""
import contextlib
import fcntl
import hashlib
import io
import os
from pathlib import Path
import stat
import types
import zipfile

import installer

BUNDLE_SHA = '550a6caf0dbe23f2511417ff3ec48a1cc0a1dc8ec54a021ba69faae3fb3cacb2'
PREFIX = 'megabonk-deck-beta5-test/'
MAX_BUNDLE = 2 * 1024 * 1024


def verified_bundle(path, expected=BUNDLE_SHA):
    path = Path(path).expanduser()
    if not path.is_absolute() or path.is_symlink():
        raise RuntimeError('Bundle must be an absolute regular file path.')
    # Nonblocking open lets us reject FIFOs/devices without hanging on read.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise RuntimeError('Bundle must be an absolute regular file path.')
        if info.st_size > MAX_BUNDLE:
            raise RuntimeError('Bundle exceeds the beta 5 size limit.')
        data = stream.read(MAX_BUNDLE + 1)
    if len(data) > MAX_BUNDLE:
        raise RuntimeError('Bundle exceeds the beta 5 size limit.')
    if expected != BUNDLE_SHA or hashlib.sha256(data).hexdigest() != BUNDLE_SHA:
        raise RuntimeError('Expected the published, unchanged beta 5 test bundle.')
    return data


def load_updater(data):
    # Code is executed only AFTER the entire immutable archive is verified.
    if hashlib.sha256(data).hexdigest() != BUNDLE_SHA:
        raise RuntimeError('Unverified updater bundle.')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        source = archive.read(PREFIX + 'candidate_updater.py')
        package = archive.read(PREFIX + 'megabonk-deck-beta5.zip')
    module = types.ModuleType('verified_beta5_updater')
    exec(compile(source, 'verified_beta5_updater.py', 'exec'), module.__dict__)
    return module, package


def handle(request):
    op = request.get('op')
    if op not in ('deploy', 'restore'):
        raise ValueError('Expected deploy or restore.')
    state = Path.home() / '.local/share/megabonk-deck'
    # Reuse the updater's path checks before creating state or opening its lock.
    for path in [state, *state.parents]:
        if path.is_symlink():
            raise RuntimeError('Installer state must not contain symlinks.')
    state.mkdir(parents=True, exist_ok=True)
    cache = state / 'remote' / 'verified-beta5-test.zip'
    if op == 'deploy':
        data = verified_bundle(request['path'], request.get('sha256'))
    else:
        if not cache.is_file():
            raise RuntimeError('Bootstrap deployment once before remote restore; use the existing restore launcher otherwise.')
        data = verified_bundle(cache)
    updater, package = load_updater(data)
    updater.reject_symlinks(state / 'install.lock')
    messages = []
    # Only this explicit unattended adapter bypasses interactive dialogs.
    updater.dialog = lambda message, question=False: messages.append(message) or True
    with (state / 'install.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another installer is already running.')
        if installer.running('Megabonk.exe'):
            raise RuntimeError('Stop Megabonk before deployment or restore.')
        with contextlib.redirect_stdout(io.StringIO()):
            if op == 'restore':
                updater.restore(state)
                return {'restored': True, 'version': 'official 5.1.0', 'messages': messages}
            _, _, game, _ = installer.discover(Path.home())
            updater.reject_symlinks(cache)
            cache.parent.mkdir(parents=True, exist_ok=True)
            # Cache first so successful deployment always has a restore adapter.
            installer.atomic(cache, data)
            changed = updater.apply_update(game, state, package)
    target = game / 'BepInEx/plugins/MegabonkTogether/MegabonkTogether.dll'
    return {'changed': changed, 'version': 'Deck beta 5', 'sha256': updater.digest(target.read_bytes()),
            'bundle_sha256': BUNDLE_SHA, 'backup_preserved': True}
