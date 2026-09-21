"""Build the offline candidate test bundle, with fixed ZIP timestamps and permissions."""
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]


def launcher(updater, restore=False):
    bundle = base64.b64encode(zlib.compress(json.dumps({
        'installer': (ROOT / 'installer.py').read_text(encoding='utf-8'),
        'updater': updater,
    }, sort_keys=True).encode(), 9)).decode()
    code = ("import sys,types,zlib,base64,json;d=json.loads(zlib.decompress(base64.b64decode('"
            + bundle + "')));m=types.ModuleType('installer');sys.modules['installer']=m;exec(d['installer'],m.__dict__);")
    if restore:
        code += "sys.argv.append('--restore');"
    code += "exec(compile(d['updater'],'candidate_updater.py','exec'))"
    assert len(code.encode()) < 100000
    name = 'Restore Official Megabonk Multiplayer' if restore else 'Test Megabonk Deck Beta 4'
    # %k is its own argument, never inside quotes. It may expand to a file URI.
    return ('[Desktop Entry]\nType=Application\nName=' + name
            + '\nIcon=applications-games\nTerminal=true\nExec=python3 -c "' + code
            + '" %k\nCategories=Game;\n').encode()


def build():
    package = (ROOT / 'releases/megabonk-deck-beta4.zip').read_bytes()
    source = (ROOT / 'mod-source/megabonk-deck-beta4-source.zip').read_bytes()
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        dll = archive.read('MegabonkTogether.dll')
    updater = (ROOT / 'candidate-beta4/updater.py').read_text(encoding='utf-8')
    updater = updater.replace('@PACKAGE_SHA@', hashlib.sha256(package).hexdigest())
    updater = updater.replace('@BETA_DLL_SHA@', hashlib.sha256(dll).hexdigest())
    files = {
        'Test-Deck-Beta4.desktop': (launcher(updater), 0o755),
        'Restore-Official-Multiplayer.desktop': (launcher(updater, restore=True), 0o755),
        'megabonk-deck-beta4.zip': (package, 0o644),
        'megabonk-deck-beta4-source.zip': (source, 0o644),
        'candidate_updater.py': (updater.encode(), 0o644),
        'installer.py': ((ROOT / 'installer.py').read_bytes(), 0o644),
        'README.txt': ((ROOT / 'candidate-beta4/README.txt').read_bytes(), 0o644),
    }
    manifest = {name: hashlib.sha256(data).hexdigest() for name, (data, _) in files.items()}
    files['SHA256SUMS.json'] = (json.dumps(manifest, indent=2, sort_keys=True).encode() + b'\n', 0o644)
    out = ROOT / 'releases/megabonk-deck-beta4-test.zip'
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, (data, mode) in sorted(files.items()):
            info = zipfile.ZipInfo('megabonk-deck-beta4-test/' + name, (2026, 9, 21, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)
    print(out)
    print('SHA256 ' + hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == '__main__':
    build()
