"""Compatibility loader; reusable implementation lives in SteamDeckControl."""
import importlib.util
from pathlib import Path
import runpy
import sys

CONTROL_ROOT = Path(__file__).resolve().parents[2] / 'SteamDeckControl'


def load(filename):
    path = CONTROL_ROOT / filename
    if not path.is_file():
        raise RuntimeError('SteamDeckControl sibling project is required: ' + str(path))
    sys.path.insert(0, str(CONTROL_ROOT))
    spec = importlib.util.spec_from_file_location('steam_deck_control_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def forward(namespace, filename):
    if namespace['__name__'] == '__main__':
        sys.path.insert(0, str(CONTROL_ROOT))
        runpy.run_path(str(CONTROL_ROOT / filename), run_name='__main__')
    else:
        module = load(filename)
        namespace.update({name: value for name, value in vars(module).items() if not name.startswith('__')})
