"""Embed the updater plus installer helpers; never require a downloaded script."""
import base64
import json
from pathlib import Path
import zlib
root=Path(__file__).resolve().parent
bundle=base64.b64encode(zlib.compress(json.dumps({
    'installer':(root/'installer.py').read_text(),
    'updater':(root/'deck_update.py').read_text(),
}).encode(),9)).decode()
for filename,name,restore in [
    ('Update-Deck-Controls.desktop','Update Megabonk Deck Controls (Beta)',False),
    ('Restore-Original-Multiplayer.desktop','Restore Previous Megabonk Multiplayer',True),
]:
    code="import sys,types,zlib,base64,json;d=json.loads(zlib.decompress(base64.b64decode('"+bundle+"')));m=types.ModuleType('installer');sys.modules['installer']=m;exec(d['installer'],m.__dict__);"
    if restore: code+="sys.argv.append('--restore');"
    code+="exec(compile(d['updater'],'deck_update.py','exec'))"
    path=root/filename
    path.write_text('[Desktop Entry]\nType=Application\nName='+name+'\nIcon=applications-games\nTerminal=true\nExec=python3 -c "'+code+'"\nCategories=Game;\n')
    path.chmod(0o755)
    assert len(code.encode()) < 100000, 'Keep below Linux argument-size limit'
    print(path)
