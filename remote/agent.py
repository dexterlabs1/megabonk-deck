#!/usr/bin/env python3
"""One-request SSH helper. No daemon, shell interpolation, or third-party packages."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import zlib

PROC = Path('/proc')
SCREEN_DIR = Path('/tmp')
MAX_IMAGE = 64 * 1024 * 1024
SESSION_KEYS = ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'XDG_RUNTIME_DIR',
                'DBUS_SESSION_BUS_ADDRESS', 'XDG_SESSION_TYPE', 'XDG_CURRENT_DESKTOP')


def bounded(value, default, maximum):
    value = float(default if value is None else value)
    if not math.isfinite(value) or not 0 < value <= maximum:
        raise ValueError('Timeout/duration out of range')
    return value


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def process(pid):
    """An identity includes start ticks, preventing signals to a reused PID."""
    directory = PROC / str(int(pid))
    try:
        if directory.stat().st_uid != os.getuid():
            return None
        fields = (directory / 'stat').read_text().rsplit(')', 1)[1].split()
        if fields[0] == 'Z':
            return None
        name = (directory / 'comm').read_text().strip()
        env = {}
        for part in (directory / 'environ').read_bytes().split(b'\0'):
            key, sep, value = part.partition(b'=')
            if sep:
                env[key.decode(errors='replace')] = value.decode(errors='replace')
        try:
            cwd = str((directory / 'cwd').resolve(strict=True))
        except OSError:
            cwd = None
        try:
            exe = str((directory / 'exe').resolve(strict=True))
        except OSError:
            exe = None
        return {'pid': int(pid), 'start': fields[19], 'name': name,
                'env': env, 'cwd': cwd, 'exe': exe}
    except (OSError, ValueError, IndexError):
        return None


def processes():
    return [item for p in PROC.iterdir() if p.name.isdigit()
            if (item := process(int(p.name))) is not None]


def unchanged(item):
    current = process(item['pid'])
    return bool(current and current['start'] == item['start']
                and current['name'] == item['name'] and current['exe'] == item['exe'])


def signal_process(item, sig):
    if not unchanged(item):
        raise RuntimeError('Process exited or changed before signal')
    # pidfd closes the PID-reuse race on SteamOS kernels/Python versions supporting it.
    if hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'):
        fd = os.pidfd_open(item['pid'])
        try:
            if not unchanged(item):
                raise RuntimeError('Process changed before signal')
            signal.pidfd_send_signal(fd, sig)
        finally:
            os.close(fd)
    else:
        os.kill(item['pid'], sig)


def session_environment(items=None):
    items = processes() if items is None else items
    candidates = [p for p in items if p['name'] in ('steam', 'gamescope')]
    candidates.sort(key=lambda p: (p['name'] != 'steam', -int(p['start'])))
    env = os.environ.copy()
    for item in candidates:
        if item['env'].get('DISPLAY') or item['env'].get('WAYLAND_DISPLAY'):
            env.update({k: item['env'][k] for k in SESSION_KEYS if k in item['env']})
            break
    return env


def vdf_pairs(text):
    # Only quoted leaf values are needed; reject unsafe install paths separately.
    return [(a.replace('\\\\', '\\').replace('\\"', '"'),
             b.replace('\\\\', '\\').replace('\\"', '"'))
            for a, b in re.findall(r'"((?:\\.|[^"\\])*)"\s*"((?:\\.|[^"\\])*)"', text)]


def discover_game(home=None):
    home = Path.home() if home is None else Path(home)
    roots = [home / '.local/share/Steam', home / '.steam/steam', home / '.steam/root']
    libraries = set()
    for root in roots:
        if not root.is_dir():
            continue
        libraries.add(root.resolve())
        vdf = root / 'steamapps/libraryfolders.vdf'
        if vdf.is_file():
            for key, value in vdf_pairs(vdf.read_text(errors='replace')):
                if key.lower() == 'path' and Path(value).is_absolute():
                    libraries.add(Path(value).resolve())
    found = {}
    for library in libraries:
        for manifest in (library / 'steamapps').glob('appmanifest_*.acf'):
            values = dict((k.lower(), v) for k, v in vdf_pairs(manifest.read_text(errors='replace')))
            if values.get('name', '').lower() != 'megabonk':
                continue
            folder, appid = values.get('installdir', ''), values.get('appid', '')
            if not folder or folder in ('.', '..') or '/' in folder or '\\' in folder or not appid.isdigit():
                raise RuntimeError('Unsafe Megabonk Steam manifest')
            game = (library / 'steamapps/common' / folder).resolve()
            if (game / 'Megabonk.exe').is_file():
                found[str(game)] = {'path': str(game), 'appid': appid}
    if len(found) != 1:
        raise RuntimeError('Expected one Windows Megabonk installation; install and launch it once in Steam')
    return next(iter(found.values()))


def selected_game(request):
    game = discover_game()
    if request.get('appid') is not None and str(request['appid']) != game['appid']:
        raise ValueError('Requested appid does not match installed Megabonk')
    return game


def game_processes(game, items=None):
    items = processes() if items is None else items
    return [p for p in items if p['name'].lower() == 'megabonk.exe'
            and (p['env'].get('SteamAppId') == game['appid']
                 or p['env'].get('SteamGameId') == game['appid']
                 or p['cwd'] == game['path'])]


def status(_request):
    items = processes()
    env = session_environment(items)
    os_info = {}
    try:
        for line in Path('/etc/os-release').read_text().splitlines():
            key, sep, value = line.partition('=')
            if sep and key in ('NAME', 'VERSION_ID', 'PRETTY_NAME', 'BUILD_ID'):
                os_info[key] = value.strip('"')
    except OSError:
        pass
    result = {'os': os_info, 'session': {k: env[k] for k in SESSION_KEYS if k in env},
              'gamescope_pids': [p['pid'] for p in items if p['name'] == 'gamescope'],
              'uinput': {'exists': Path('/dev/uinput').exists(),
                         'writable': os.access('/dev/uinput', os.W_OK)}}
    try:
        game = discover_game()
        dll = Path(game['path']) / 'BepInEx/plugins/MegabonkTogether/MegabonkTogether.dll'
        game['pids'] = [p['pid'] for p in game_processes(game, items)]
        game['mod_sha256'] = sha256(dll) if dll.is_file() else None
        result['game'] = game
    except RuntimeError as exc:
        result['game'] = None
        result['game_error'] = str(exc)
    return result


def complete_image(data):
    """Check container completeness, not visual correctness/decoder validity."""
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        offset, chunks = 8, []
        while offset + 12 <= len(data):
            length = struct.unpack('>I', data[offset:offset + 4])[0]
            end = offset + length + 12
            if end > len(data):
                return None
            kind = data[offset + 4:offset + 8]
            payload = data[offset + 4:end - 4]
            if zlib.crc32(payload) != struct.unpack('>I', data[end - 4:end])[0]:
                return None
            chunks.append(kind)
            if kind == b'IEND':
                return 'png' if chunks[0] == b'IHDR' and b'IDAT' in chunks and end == len(data) else None
            offset = end
    if data.startswith(b'\xff\xd8\xff') and data.endswith(b'\xff\xd9'):
        return 'jpg'
    if len(data) >= 16 and data[4:8] == b'ftyp' and b'avif' in data[8:40]:
        offset, kinds = 0, set()
        while offset + 8 <= len(data):
            length, kind = struct.unpack('>I4s', data[offset:offset + 8])
            header = 8
            if length == 1:
                if offset + 16 > len(data):
                    return None
                length = struct.unpack('>Q', data[offset + 8:offset + 16])[0]
                header = 16
            if length == 0 or length < header or offset + length > len(data):
                return None
            kinds.add(kind)
            offset += length
        if offset == len(data) and {b'ftyp', b'meta', b'mdat'} <= kinds:
            return 'avif'
    return None


def screenshot_files():
    files = {}
    for path in SCREEN_DIR.glob('gamescope*'):
        try:
            info = path.lstat()
            if (stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                    and 0 < info.st_size <= MAX_IMAGE):
                files[path] = (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        except OSError:
            pass
    return files


def artifact_dir():
    directory = Path.home() / '.local/state/megabonk-deck/artifacts'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def request_screenshot(target):
    # Valve's devkit uses this property; full composition includes Steam overlays.
    xprop = shutil.which('xprop')
    if xprop:
        env = session_environment()
        env['DISPLAY'] = target['env'].get('DISPLAY', ':0')
        result = subprocess.run([xprop, '-root', '-f', 'GAMESCOPECTRL_DEBUG_REQUEST_SCREENSHOT',
                                 '32c', '-set', 'GAMESCOPECTRL_DEBUG_REQUEST_SCREENSHOT', '3'],
                                env=env, capture_output=True, timeout=5)
        if result.returncode == 0:
            return 'xprop-full-composition'
    proc_status = (PROC / str(target['pid']) / 'status').read_text()
    match = re.search(r'^SigCgt:\s*([0-9a-fA-F]+)$', proc_status, re.M)
    if not match or not (int(match[1], 16) & (1 << (signal.SIGUSR2 - 1))):
        raise RuntimeError('Gamescope has no SIGUSR2 screenshot handler; refusing to signal it')
    signal_process(target, signal.SIGUSR2)
    return 'sigusr2'


def screenshot(request):
    timeout = bounded(request.get('timeout'), 10, 30)
    candidates = [p for p in processes() if p['name'] == 'gamescope'
                  and p['exe'] and Path(p['exe']).name == 'gamescope']
    if request.get('pid') is not None:
        candidates = [p for p in candidates if p['pid'] == int(request['pid'])]
    if len(candidates) != 1:
        raise RuntimeError('Expected one same-user Gamescope process; Gaming Mode required (or specify pid)')
    target = candidates[0]
    before = screenshot_files()
    backend = request_screenshot(target)
    deadline, previous = time.monotonic() + timeout, {}
    while time.monotonic() < deadline:
        current = screenshot_files()
        for path, signature in current.items():
            if signature == before.get(path) or signature != previous.get(path):
                continue
            try:
                # O_NOFOLLOW prevents a symlink swap between listing and reading.
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd, 'rb') as stream:
                    info = os.fstat(stream.fileno())
                    if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode):
                        continue
                    data = stream.read(MAX_IMAGE + 1)
                if len(data) > MAX_IMAGE or screenshot_files().get(path) != signature:
                    continue
                image_format = complete_image(data)
                if image_format != 'png':
                    continue
                dest = artifact_dir() / ('screen-' + uuid.uuid4().hex + '.' + image_format)
                with dest.open('xb') as output:
                    output.write(data)
                return {'path': str(dest), 'sha256': hashlib.sha256(data).hexdigest(),
                        'size': len(data), 'format': image_format, 'pid': target['pid'], 'backend': backend}
            except OSError:
                continue
        previous = current
        time.sleep(0.2)
    raise RuntimeError('Timed out waiting for a fresh complete Gamescope PNG screenshot')


def execute(request):
    argv = request.get('argv')
    if (not isinstance(argv, list) or not argv or len(argv) > 256
            or any(not isinstance(x, str) or '\0' in x for x in argv)):
        raise ValueError('argv must be a nonempty list of strings')
    timeout = bounded(request.get('timeout'), 30, 300)
    limit = 1024 * 1024
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                 env=session_environment(), cwd=request.get('cwd'), start_new_session=True)
        timed_out = False
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
        streams, truncated = [], False
        for stream in (out, err):
            size = stream.seek(0, os.SEEK_END)
            truncated |= size > limit
            stream.seek(max(0, size - limit))
            streams.append(stream.read(limit).decode(errors='replace'))
    return {'exit_code': child.returncode, 'stdout': streams[0], 'stderr': streams[1],
            'timed_out': timed_out, 'output_truncated': truncated}


def launch(request):
    game = selected_game(request)
    existing = game_processes(game)
    if existing:
        return {'appid': game['appid'], 'already_running': True, 'pids': [p['pid'] for p in existing]}
    if not any(p['name'] == 'steam' for p in processes()):
        raise RuntimeError('Steam must already be running in the Deck display session')
    steam = shutil.which('steam')
    if not steam:
        raise RuntimeError('Steam launcher is not on PATH')
    result = execute({'argv': [steam, '-applaunch', game['appid']], 'timeout': 15})
    if result['exit_code'] != 0:
        raise RuntimeError('Steam launch request failed: ' + result['stderr'][-2000:])
    deadline = time.monotonic() + bounded(request.get('timeout'), 30, 120)
    while time.monotonic() < deadline:
        running = game_processes(game)
        if running:
            return {'appid': game['appid'], 'already_running': False,
                    'pids': [p['pid'] for p in running]}
        time.sleep(0.5)
    raise RuntimeError('Steam accepted the launch request but Megabonk did not appear before timeout')


def stop(request):
    game = selected_game(request)
    targets = game_processes(game)
    for target in targets:
        signal_process(target, signal.SIGTERM)
    deadline = time.monotonic() + bounded(request.get('timeout'), 10, 30)
    remaining = targets
    while remaining and time.monotonic() < deadline:
        remaining = [p for p in remaining if unchanged(p)]
        if remaining:
            time.sleep(0.2)
    if remaining and request.get('force') is True:
        for target in remaining:
            signal_process(target, signal.SIGKILL)
        deadline = time.monotonic() + 3
        while remaining and time.monotonic() < deadline:
            remaining = [p for p in remaining if unchanged(p)]
            time.sleep(0.1)
    if remaining:
        raise RuntimeError('Megabonk did not exit; explicit force=true is required for escalation')
    return {'stopped_pids': [p['pid'] for p in targets], 'appid': game['appid']}


def logs(request):
    game = selected_game(request)
    limit = int(request.get('max_bytes', 2 * 1024 * 1024))
    if not 1 <= limit <= 8 * 1024 * 1024:
        raise ValueError('max_bytes must be between 1 and 8388608')
    results = []
    for name in ('BepInEx/LogOutput.log', 'BepInEx/LogOutput.log.1'):
        path = Path(game['path']) / name
        if not path.is_file() or path.is_symlink():
            continue
        with path.open('rb') as stream:
            size = stream.seek(0, os.SEEK_END)
            stream.seek(max(0, size - limit))
            data = stream.read(limit)
        dest = artifact_dir() / ('log-' + uuid.uuid4().hex + '.txt')
        dest.write_bytes(data)
        results.append({'path': str(dest), 'source': str(path), 'size': len(data),
                        'truncated': size > limit, 'sha256': hashlib.sha256(data).hexdigest()})
    return {'files': results}


def handle(request):
    if not isinstance(request, dict):
        raise ValueError('Request must be a JSON object')
    operation = request.get('op')
    if operation in ('deploy', 'restore'):
        import deployment
        return deployment.handle(request)
    if operation == 'file_hash':
        path = Path(request['path']).expanduser()
        if not path.is_absolute():
            path = Path.home() / path
        path = path.resolve(strict=True)
        if not path.is_file():
            raise ValueError('Expected a regular file')
        return {'path': str(path), 'sha256': sha256(path), 'size': path.stat().st_size}
    if operation == 'input':
        import input_agent
        result = input_agent.handle({key: value for key, value in request.items() if key != 'op'})
        if result.get('ok') is False:
            raise RuntimeError(result.get('error', 'Input request failed'))
        return result
    handlers = {'status': status, 'screenshot': screenshot, 'exec': execute,
                'launch': launch, 'stop': stop, 'logs': logs}
    if operation not in handlers:
        raise ValueError('Unknown operation: ' + str(operation))
    return handlers[operation](request)


def main():
    try:
        raw = sys.stdin.buffer.read(128 * 1024 + 1)
        if len(raw) > 128 * 1024:
            raise ValueError('Request is too large')
        result = handle(json.loads(raw))
        print(json.dumps({'ok': True, 'result': result}))
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
