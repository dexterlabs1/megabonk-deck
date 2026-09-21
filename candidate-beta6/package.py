"""Package the verified beta 6 build and its source-provided license/readme."""
import hashlib
from pathlib import Path
import sys
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
DLL_SHA = 'c79cf7d1abf4b25c02ee8b51d7d754f57a98a65fb213fad0464059d446af4580'


def build(source_root):
    dll = (Path(source_root) / 'src/plugin/bin/Release/net6.0/MegabonkTogether.dll').read_bytes()
    if hashlib.sha256(dll).hexdigest() != DLL_SHA:
        raise RuntimeError('Beta 6 DLL differs from the verified build.')
    with ZipFile(ROOT / 'mod-source/megabonk-deck-beta6-source.zip') as source:
        files = {'MegabonkTogether.dll': dll, 'LICENSE': source.read('LICENSE'),
                 'DECK-BETA.md': source.read('DECK-BETA.md')}
    output = ROOT / 'releases/megabonk-deck-beta6.zip'
    with ZipFile(output, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = ZipInfo(name, (2026, 9, 21, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)
    print(output)
    print('SHA256 ' + hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == '__main__':
    build(sys.argv[1])
