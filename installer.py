#!/usr/bin/env python3
"""Megabonk Together Steam Deck installer. Python standard library only."""
import base64
import fcntl
import hashlib
import html
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

VERSION = '5.1.0'
PACKAGES = [
    ('BepInEx 6 build 752', 'https://builds.bepinex.dev/projects/bepinex_be/752/BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.752%2Bdd0655f.zip', 'f9d128e162269579b67e91a4923764f3d54fa8c8162a238ce6657d704084334c'),
    ('Megabonk Together Proton 5.1.0', 'https://github.com/Fcornaire/megabonk-together/releases/download/5.1.0/Megabonk-Together-Proton-5.1.0.zip', 'e23a4cc3ce124946a81248e59055465e3f0897d49433db21bd2b9622dcdacd3d'),
]
OVERRIDE = 'WINEDLLOVERRIDES="winhttp=n,b"'


def dialog(message, question=False):
    if shutil.which('zenity') and (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        return subprocess.run(['zenity', '--question' if question else '--info', '--title=Megabonk Together', '--width=520', '--text=' + html.escape(message)]).returncode == 0
    print(message, flush=True)
    return not question or input('\nContinue? [y/N] ').strip().lower() == 'y'


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.megabonk-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            os.chmod(tmp, stat.S_IMODE(path.stat().st_mode))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# Parse KeyValues with source spans so only the intended scalar changes.
TOKEN = re.compile(r'\s+|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[{}]|\[[^\]\r\n]*\]|[^\s{}"\[\]\x00\ufeff]+')


class VDFError(ValueError):
    pass


def vdf_tokens(text, source):
    # Keep original character offsets, including a UTF-8 BOM, for surgical edits.
    pos = 1 if text.startswith('\ufeff') else 0
    end = len(text.rstrip('\x00'))
    result = []
    while pos < end:
        match = TOKEN.match(text, pos, end)
        if match is None:
            line = text.count('\n', 0, pos) + 1
            raise VDFError(f'{source}, line {line}: unrecognized or unterminated VDF token')
        raw = match.group()
        if not raw.isspace() and not raw.startswith(('//', '/*')):
            result.append((raw, pos, match.end()))
        pos = match.end()
    return result


def read_vdf(path):
    # Avoid universal-newline conversion: unrelated bytes must remain unchanged.
    return path.read_bytes().decode('utf-8', errors='surrogateescape')


def unquote(raw):
    if not raw.startswith('"'):
        return raw
    return re.sub(r'\\([\\"])', r'\1', raw[1:-1])


def quote(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def parse_vdf(text, source='Steam settings'):
    tokens = vdf_tokens(text, source)

    def fail(message, offset):
        line = text.count('\n', 0, offset) + 1
        raise VDFError(f'{source}, line {line}: {message}')

    def block(i, nested=False):
        entries = []
        while i < len(tokens):
            key, start, end = tokens[i]
            if key == '}':
                if not nested:
                    fail('unexpected closing brace', start)
                return entries, i + 1, start
            if key == '{' or key.startswith('[') or i + 1 >= len(tokens):
                fail('expected a key and value', start)
            value, vs, ve = tokens[i + 1]
            if value == '{':
                children, i, close = block(i + 2, True)
                node = dict(key=unquote(key), children=children, close=close)
            elif value == '}' or value.startswith('['):
                fail('missing value', vs)
            else:
                node = dict(key=unquote(key), value=unquote(value), start=vs, end=ve)
                i += 2
            # Preserve conditional annotations on unrelated data. Do not guess
            # their meaning when selecting a setting that will be edited.
            if i < len(tokens) and tokens[i][0].startswith('['):
                node['condition'] = tokens[i][0]
                i += 1
            entries.append(node)
        if nested:
            fail('unclosed section', len(text))
        return entries, i, len(text)
    return block(0)[0]


def entry(entries, key):
    matches = [x for x in entries if x['key'].lower() == key.lower()]
    if len(matches) > 1:
        raise ValueError('Duplicate Steam setting: ' + key)
    if matches and 'condition' in matches[0]:
        raise VDFError('Conditional Steam setting requires manual configuration: ' + key)
    return matches[0] if matches else None


def descend(entries, keys):
    node = None
    for key in keys:
        node = entry(entries, key)
        if node is None or 'children' not in node:
            return None
        entries = node['children']
    return node


def launch_options(old):
    if OVERRIDE in old:
        return old
    if 'WINEDLLOVERRIDES' in old:
        raise RuntimeError('Existing custom WINEDLLOVERRIDES found. No changes made. Merge winhttp=n,b into that setting, then run again.')
    if not old.strip():
        return OVERRIDE + ' %command%'
    if '%command%' in old:
        return OVERRIDE + ' ' + old
    return OVERRIDE + ' %command% ' + old


def patch_localconfig(text, appid, source="Steam settings"):
    node = descend(parse_vdf(text, source), ['UserLocalConfigStore', 'Software', 'Valve', 'Steam', 'apps', appid])
    if node is None:
        return None
    option = entry(node['children'], 'LaunchOptions')
    old = option['value'] if option else ''
    new = launch_options(old)
    if option:
        return text[:option['start']] + quote(new) + text[option['end']:]
    pos = node['close']
    return text[:pos] + '\n\t\t\t\t\t"LaunchOptions"\t\t' + quote(new) + '\n\t\t\t\t' + text[pos:]


def discover(home):
    roots = [home / '.local/share/Steam', home / '.steam/steam', home / '.steam/root']
    roots = list(dict.fromkeys(p.resolve() for p in roots if p.exists()))
    games = {}
    for root in roots:
        libraries = [root]
        vdf = root / 'steamapps/libraryfolders.vdf'
        if vdf.exists():
            node = descend(parse_vdf(read_vdf(vdf), str(vdf)), ['libraryfolders'])
            if node:
                for lib in node['children']:
                    if 'children' in lib:
                        p = entry(lib['children'], 'path')
                        if p:
                            libraries.append(Path(p['value']))
        for lib in dict.fromkeys(libraries):
            for manifest in (lib / 'steamapps').glob('appmanifest_*.acf'):
                # A broken manifest for another game must not block this game.
                manifest_text = read_vdf(manifest)
                if not re.search(r'"name"\s+"Megabonk"', manifest_text, re.IGNORECASE):
                    continue
                node = descend(parse_vdf(manifest_text, str(manifest)), ['AppState'])
                if not node:
                    continue
                fields = {e['key'].lower(): e.get('value') for e in node['children']}
                if str(fields.get('name', '')).lower() != 'megabonk':
                    continue
                folder = fields.get('installdir', '')
                if not folder or Path(folder).name != folder:
                    raise RuntimeError('Unsafe game install path in Steam manifest')
                game = (lib / 'steamapps/common' / folder).resolve()
                appid = fields.get('appid', '')
                if not appid.isdigit():
                    raise RuntimeError('Invalid Steam game ID')
                if (game / 'Megabonk.exe').is_file():
                    games[str(game)] = (root, lib, game, appid)
    if len(games) != 1:
        raise RuntimeError('Could not find exactly one Windows Megabonk installation. Install and launch Megabonk once in Steam, then close it. If needed, choose Proton Experimental in Properties > Compatibility. Mounted SD cards are supported.')
    return next(iter(games.values()))


def running(name):
    return subprocess.run(['pgrep', '-u', str(os.getuid()), '-x', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def safe_extract(data, dest):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if sum(i.file_size for i in z.infolist()) > 700 * 1024 * 1024:
            raise RuntimeError('Archive is unexpectedly large')
        seen = set()
        for info in z.infolist():
            p = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (p.is_absolute() or '..' in p.parts or '\\' in info.filename or ':' in info.filename
                    or stat.S_ISLNK(mode) or info.filename in seen):
                raise RuntimeError('Unsafe archive entry: ' + info.filename)
            seen.add(info.filename)
            target = dest.joinpath(*p.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, target.open('wb') as dst:
                    shutil.copyfileobj(src, dst)


def download(url, digest):
    req = urllib.request.Request(url, headers={'User-Agent': 'Megabonk-Deck-Installer/1.0'})
    with urllib.request.urlopen(req, timeout=90) as response:
        data = response.read(100 * 1024 * 1024 + 1)
    if len(data) > 100 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError('Download checksum did not match. No game files changed; try again later.')
    return data


class Transaction:
    def __init__(self, backup):
        self.backup = backup
        backup.mkdir(parents=True, exist_ok=False)
        self.records = []
        self.save()

    def save(self):
        atomic(self.backup / 'changes.json', json.dumps(self.records, indent=2).encode())

    def write(self, path, data):
        path = Path(path).absolute()
        if any(p.is_symlink() for p in [path, *path.parents]):
            raise RuntimeError('Refusing to overwrite symlink: ' + str(path))
        existed = path.exists()
        original = str(len(self.records)) if existed else None
        if existed:
            shutil.copy2(path, self.backup / original)
        self.records.append({'path': str(path), 'backup': original, 'installed_sha256': hashlib.sha256(data).hexdigest()})
        self.save()  # Journal before mutation, so interrupted writes are recoverable.
        atomic(path, data)

    def rollback(self):
        for r in reversed(self.records):
            p = Path(r['path'])
            if r['backup'] is not None:
                atomic(p, (self.backup / r['backup']).read_bytes())
            elif p.is_file():
                p.unlink()


def main():
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise RuntimeError('Run this on your Steam Deck in Desktop Mode as your normal user, without sudo.')
    for command in ['steam', 'pgrep']:
        if not shutil.which(command):
            raise RuntimeError('Required SteamOS command is missing: ' + command)
    home = Path.home()
    state = home / '.local/share/megabonk-deck'
    state.mkdir(parents=True, exist_ok=True)
    lock = (state / 'install.lock').open('w')
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another Megabonk installer is already running.')
        root, lib, game, appid = discover(home)
        if running('Megabonk.exe'):
            raise RuntimeError('Close Megabonk first, then open this installer again.')
        if not dialog('Install Megabonk Together ' + VERSION + '?\n\nThis downloads about 34 MB, backs up your saves and changed files, and sets the Steam launch option. Steam will close and reopen. Finish other games/downloads first.\n\nThe mod is experimental. Both players should use this installer.\n\nGame: ' + str(game), True):
            return
        with tempfile.TemporaryDirectory(prefix='megabonk-') as tmp:
            tmp = Path(tmp)
            for i, (name, url, digest) in enumerate(PACKAGES):
                print('Downloading and checking ' + name + '…', flush=True)
                safe_extract(download(url, digest), tmp / str(i))
            loader, mod = tmp / '0', tmp / '1'
            if not (loader / 'winhttp.dll').is_file() or not (mod / 'MegabonkTogether/MegabonkTogether.dll').is_file():
                raise RuntimeError('Unexpected package layout. No changes made.')
            # Refuse an unmanaged loader/mod installation rather than mixing versions.
            marker = game / '.megabonk-deck.json'
            managed = marker.exists()
            if not managed and any((game / p).exists() for p in ['BepInEx', 'winhttp.dll', 'doorstop_config.ini', 'dotnet']):
                raise RuntimeError('Existing mod loader found. This installer needs a clean mod setup to avoid mixing loaders. Your installation was left unchanged.')
            if managed and json.loads(marker.read_text()).get('version') != VERSION:
                raise RuntimeError('A different installer version is present. Restore its backup before changing versions.')
            if running('steam'):
                subprocess.run(['steam', '-shutdown'], check=True, timeout=20)
                deadline = time.monotonic() + 60
                while running('steam') and time.monotonic() < deadline:
                    time.sleep(1)
                if running('steam'):
                    raise RuntimeError('Steam did not finish closing. Exit Steam yourself and run this again.')
            if running('Megabonk.exe'):
                raise RuntimeError('Megabonk is still running. Close it and try again.')
            configs = []
            for config in (root / 'userdata').glob('*/config/localconfig.vdf'):
                original = read_vdf(config)
                updated = patch_localconfig(original, appid, str(config))
                if updated is not None:
                    configs.append((config.resolve(), updated))
            if not configs:
                raise RuntimeError('Launch Megabonk once from your Steam account before installing. Steam settings were not changed.')
            backup = state / 'backups' / time.strftime('%Y%m%d-%H%M%S')
            tx = Transaction(backup)
            try:
                # Back up all local Proton save copies and Steam cloud cache before mutation.
                saves = list((lib / ('steamapps/compatdata/' + appid + '/pfx/drive_c/users')).glob('*/AppData/LocalLow/Ved/Megabonk'))
                saves += list((root / 'userdata').glob('*/' + appid + '/remote'))
                for i, save in enumerate(saves):
                    shutil.copytree(save, backup / 'saves' / str(i), symlinks=True)
                atomic(backup / 'save-locations.json', json.dumps([str(s) for s in saves], indent=2).encode())
                for source, destination in [(loader, game), (mod, game / 'BepInEx/plugins')]:
                    for p in sorted(source.rglob('*')):
                        if p.is_file():
                            tx.write(destination / p.relative_to(source), p.read_bytes())
                for config, updated in configs:
                    if running('steam'):
                        raise RuntimeError('Steam reopened during installation; closing it is required.')
                    tx.write(config, updated.encode('utf-8', errors='surrogateescape'))
                tx.write(marker, json.dumps({'version': VERSION, 'backup': str(backup)}, indent=2).encode())
            except BaseException:
                tx.rollback()
                raise
            print('Installed. Backups: ' + str(backup), flush=True)
        subprocess.Popen(['steam'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        dialog('Installed!\n\nLaunch Megabonk normally, including in Gaming Mode. The first launch can take several minutes while BepInEx prepares files.\n\nTap Together! with the touchscreen, then Friendlies. One player hosts and shares the room code; the other joins.\n\nIf the game does not start, select Proton Experimental under Steam > Megabonk > Properties > Compatibility.\n\nBackup: ' + str(backup))

    finally:
        lock.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        dialog('Installation stopped: ' + str(exc) + '\n\nIf Steam was closed, reopen it normally. See README for backup recovery.')
        sys.exit(1)
