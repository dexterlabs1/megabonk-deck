"""Megabonk integration for the standalone SteamDeckControl runtime."""
import os
import hashlib
from pathlib import Path
import re
import shutil
import signal
import time
import uuid


def bind(runtime):
    for name in ('processes', 'signal_process', 'unchanged', 'execute', 'artifact_dir', 'bounded', 'sha256'):
        globals()[name] = getattr(runtime, name)


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



def status(request):
    try:
        game = discover_game()
        dll = Path(game['path']) / 'BepInEx/plugins/MegabonkTogether/MegabonkTogether.dll'
        game['pids'] = [p['pid'] for p in game_processes(game)]
        game['mod_sha256'] = sha256(dll) if dll.is_file() else None
        return {'game': game}
    except RuntimeError as exc:
        return {'game': None, 'game_error': str(exc)}


def handle(request, runtime):
    bind(runtime)
    operation = request.get('op')
    if operation in ('deploy', 'restore'):
        import deployment
        return deployment.handle(request)
    handlers = {'status': status, 'launch': launch, 'stop': stop, 'logs': logs}
    if operation not in handlers:
        raise ValueError('Unsupported Megabonk adapter operation: ' + str(operation))
    return handlers[operation](request)
