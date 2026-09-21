"""Discover/pair using Valve's official Devkit library, installed outside the repo."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types
import urllib.error


def discover(seconds=8):
    from zeroconf import Zeroconf, ServiceBrowser, IPVersion
    found = {}
    class Listener:
        def add_service(self, zc, kind, name):
            info = zc.get_service_info(kind, name, timeout=1500)
            if info:
                found[name] = {'name': name, 'addresses': info.parsed_addresses(IPVersion.V4Only),
                               'port': info.port, 'hostname': info.server}
        update_service = add_service
        def remove_service(self, zc, kind, name):
            found.pop(name, None)
    with Zeroconf(ip_version=IPVersion.V4Only) as zc:
        browser = ServiceBrowser(zc, '_steamos-devkit._tcp.local.', Listener())
        time.sleep(seconds)
        browser.cancel()
    return list(found.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['discover', 'register'])
    parser.add_argument('--host')
    parser.add_argument('--port', type=int, default=32000)
    parser.add_argument('--source', type=Path, default=Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'megabonk-deck/steamos-devkit')
    args = parser.parse_args()
    if args.action == 'discover':
        print(json.dumps({'devices': discover()}, indent=2))
        return
    if not args.host:
        parser.error('register requires --host from discovery or the Deck network settings')
    source = args.source / 'client'
    if not (source / 'devkit_client/__init__.py').is_file():
        raise RuntimeError('Official Devkit source is missing. See remote/README.md setup.')
    sys.path.insert(0, str(source))
    import devkit_client
    parameters = types.SimpleNamespace(machine=args.host,
        machine_name_type=devkit_client.MachineNameType.ADDRESS, http_port=args.port)
    print('Approve this PC on the Deck now.', file=sys.stderr, flush=True)
    try:
        response = devkit_client.register(parameters)
    except urllib.error.HTTPError as error:
        details = error.read(4096).decode('utf-8', errors='replace')
        raise RuntimeError(f'Deck pairing returned HTTP {error.code}: {details}') from error
    _, key_path, _ = devkit_client.ensure_devkit_key()
    machine = devkit_client.resolve_machine(args.host,
        name_type=devkit_client.MachineNameType.ADDRESS, need_devkit1=False, http_port=args.port)
    subprocess.run([sys.executable, str(Path(__file__).with_name('deck.py')), 'configure',
        '--host', args.host, '--identity', key_path, '--user', machine.login], check=True)
    print(json.dumps({'paired': True, 'response': response, 'host': args.host}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        sys.exit(1)
