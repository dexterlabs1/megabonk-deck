"""Megabonk convenience wrapper around the independent SteamDeckControl CLI."""
from pathlib import Path
import sys
from _control import load

_adapter_dir = Path(__file__).resolve().parent
_core = load('deck.py')
globals().update({name: value for name, value in vars(_core).items() if not name.startswith('__')})


class Transport(_core.Transport):
    def __init__(self, config, config_dir=CONFIG_DIR, runner=subprocess.run, adapter='megabonk'):
        super().__init__(config, config_dir, runner, adapter=adapter)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if '--adapter' not in args and not any(arg.startswith('--adapter=') for arg in args):
        args = ['--adapter', 'megabonk', *args]
    parsed = _core.parser().parse_args(args)
    if parsed.command == 'bootstrap' and parsed.adapter_dir is None:
        args.extend(['--adapter-dir', str(_adapter_dir)])
    return _core.main(args)


if __name__ == '__main__':
    sys.exit(main())
