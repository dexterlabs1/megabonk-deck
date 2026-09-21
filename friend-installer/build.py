"""Build a single downloadable Desktop launcher without changing old releases."""
import base64
import hashlib
import json
from pathlib import Path
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_SHA = '1b4fcf2b0f21d8e4fb85c9deb291e5f8c726a997bb17db9fcb2825d141f7a8af'


def build():
    bundle = ROOT / 'releases/megabonk-deck-beta6-test.zip'
    if hashlib.sha256(bundle.read_bytes()).hexdigest() != BUNDLE_SHA:
        raise RuntimeError('Published beta 6 bundle changed; refusing to build.')
    with zipfile.ZipFile(bundle) as archive:
        prefix = 'megabonk-deck-beta6-test/'
        sources = {'installer': archive.read(prefix + 'installer.py').decode(),
                   'candidate_updater': archive.read(prefix + 'candidate_updater.py').decode(),
                   'friend_install': (ROOT / 'friend-installer/install.py').read_text(encoding='utf-8')}
    encoded = base64.b64encode(zlib.compress(json.dumps(sources, sort_keys=True).encode(), 9)).decode()
    code = ("import sys,types,zlib,base64,json;d=json.loads(zlib.decompress(base64.b64decode('" + encoded + "')));"
            "m=types.ModuleType('installer');sys.modules['installer']=m;exec(d['installer'],m.__dict__);"
            "u=types.ModuleType('candidate_updater');sys.modules['candidate_updater']=u;exec(d['candidate_updater'],u.__dict__);"
            "exec(compile(d['friend_install'],'friend_install.py','exec'))")
    output = ROOT / 'releases/Install-Megabonk-Deck-Beta6.desktop'
    data = ('[Desktop Entry]\nType=Application\nName=Install Megabonk Together - Deck Beta 6\n'
            'Icon=applications-games\nTerminal=true\nExec=python3 -c "' + code + '"\nCategories=Game;\n').encode()
    if len(data) > 100000:
        raise RuntimeError('Launcher too large.')
    output.write_bytes(data)
    print(output)
    print('SHA256 ' + hashlib.sha256(data).hexdigest())


if __name__ == '__main__':
    build()
