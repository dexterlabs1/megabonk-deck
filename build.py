"""Build the self-contained KDE launcher from the reviewable Python source."""
from pathlib import Path
import base64
import zlib

root = Path(__file__).resolve().parent
payload = base64.b64encode(zlib.compress((root / 'installer.py').read_bytes(), 9)).decode()
code = "import base64,zlib;exec(compile(zlib.decompress(base64.b64decode('" + payload + "')),'megabonk-installer','exec'))"
launcher = root / 'Install-Megabonk-Together.desktop'
launcher.write_text('[Desktop Entry]\nType=Application\nName=Install Megabonk Together\nComment=Install the Steam Deck multiplayer mod with automatic backups\nIcon=applications-games\nTerminal=true\nExec=python3 -c "' + code + '"\nCategories=Game;\n')
launcher.chmod(0o755)
print(launcher)
