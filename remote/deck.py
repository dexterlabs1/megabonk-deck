#!/usr/bin/env python3
"""Steam Deck control from Windows, using Python and OpenSSH only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time
import uuid

HERE = Path(__file__).resolve().parent
CONFIG_DIR = Path.home() / '.config' / 'megabonk-deck'
REMOTE_DIR = '.local/share/megabonk-deck/remote'


class DeckError(Exception):
    pass


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def validate_config(config):
    if not isinstance(config, dict):
        raise DeckError('Connection configuration must be a JSON object.')
    host = config.get('host', '')
    user = config.get('user', 'deck')
    if not isinstance(host, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]*', host):
        raise DeckError('Host must be a hostname or IP address, without SSH options.')
    if not isinstance(user, str) or not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_-]*', user):
        raise DeckError('Invalid SSH user.')
    identity = Path(config.get('identity', '')).expanduser().resolve()
    if not identity.is_file():
        raise DeckError('SSH identity file does not exist. Use the paired Devkit key or your own SSH key.')
    return {'host': host, 'user': user, 'identity': str(identity)}


def configure(host, identity, user='deck', config_dir=CONFIG_DIR):
    config = validate_config({'host': host, 'identity': identity, 'user': user})
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    destination = config_dir / 'remote.json'
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=config_dir,
                                     delete=False) as stream:
        json.dump(config, stream, indent=2)
        temporary = Path(stream.name)
    temporary.replace(destination)
    return {'ok': True, 'config': str(destination), 'host': host, 'user': user}


class Transport:
    def __init__(self, config, config_dir=CONFIG_DIR, runner=subprocess.run):
        self.config = validate_config(config)
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.runner = runner

    def options(self):
        return ['-i', self.config['identity'], '-o', 'BatchMode=yes',
                '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=accept-new',
                '-o', 'UserKnownHostsFile=' + str(self.config_dir / 'known_hosts'),
                '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=5',
                '-o', 'ServerAliveCountMax=2']

    @property
    def destination(self):
        return self.config['user'] + '@' + self.config['host']

    def run(self, argv, stdin=None, timeout=60):
        try:
            result = self.runner(argv, input=stdin, capture_output=True,
                                 text=True, encoding='utf-8', timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise DeckError(f'Remote operation timed out after {timeout}s.') from error
        except OSError as error:
            raise DeckError(f'Cannot run {argv[0]}: {error}') from error
        if result.returncode:
            detail = (result.stderr or result.stdout or '').strip()[-2000:]
            raise DeckError(f'{Path(argv[0]).name} failed ({result.returncode}): {detail}')
        return result.stdout

    def ssh(self, command, stdin=None, timeout=60):
        return self.run(['ssh', *self.options(), self.destination, command], stdin, timeout)

    def request(self, payload, timeout=60):
        output = self.ssh('python3 ' + shlex.quote(REMOTE_DIR + '/agent.py'),
                          json.dumps(payload), timeout)
        try:
            result = json.loads(output)
        except ValueError as error:
            raise DeckError('Remote helper returned invalid JSON; run deck bootstrap if it is missing.') from error
        if not isinstance(result, dict) or result.get('ok') is not True:
            raise DeckError(str(result.get('error', 'Remote operation failed.'))
                            if isinstance(result, dict) else 'Invalid remote response.')
        payload = result.get('result')
        if not isinstance(payload, dict):
            raise DeckError('Remote helper returned an invalid result object.')
        return {'ok': True, **payload}

    def scp(self, source, target, upload, timeout=180):
        # -O makes quoting explicit and consistent on OpenSSH releases before/after
        # the switch to SFTP. No user string is interpolated into a local shell.
        remote = target if upload else source
        if '\x00' in remote or '\n' in remote or '\r' in remote:
            raise DeckError('Remote paths cannot contain control characters.')
        if remote.startswith('~/'):
            remote = remote[2:]
        if remote.startswith('-'):
            remote = './' + remote
        host = self.config['host']
        if ':' in host:
            host = '[' + host + ']'
        remote_spec = self.config['user'] + '@' + host + ':' + shlex.quote(remote)
        local = str(Path(source if upload else target).expanduser().resolve())
        args = [local, remote_spec] if upload else [remote_spec, local]
        self.run(['scp', '-O', *self.options(), *args], timeout=timeout)

    def push(self, local, remote):
        local = Path(local).expanduser().resolve()
        expected = sha256(local)
        self.scp(str(local), remote, True)
        result = self.request({'op': 'file_hash', 'path': remote})
        if result.get('sha256') != expected:
            raise DeckError('Uploaded file checksum mismatch; do not install it.')
        return {'ok': True, 'path': result.get('path', remote), 'sha256': expected}

    def pull(self, remote, local, expected=None):
        metadata = self.request({'op': 'file_hash', 'path': remote})
        digest = metadata.get('sha256')
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise DeckError('Remote helper returned an invalid SHA-256.')
        if expected and digest != expected:
            raise DeckError('Remote file changed before download.')
        local = Path(local).expanduser().resolve()
        local.parent.mkdir(parents=True, exist_ok=True)
        temporary = local.with_name(local.name + '.partial-' + uuid.uuid4().hex)
        try:
            self.scp(metadata.get('path', remote), str(temporary), False)
            if sha256(temporary) != digest:
                raise DeckError('Downloaded file checksum mismatch.')
            temporary.replace(local)
        finally:
            temporary.unlink(missing_ok=True)
        return {'ok': True, 'path': str(local), 'sha256': digest}

    def bootstrap(self):
        names = ['agent.py', 'input_agent.py', 'deployment.py', 'installer.py']
        sources = [HERE / name if name != 'installer.py' else HERE.parent / name for name in names]
        for source in sources:
            if not source.is_file():
                raise DeckError('Missing bootstrap file: ' + str(source))
        script = 'import os; os.makedirs(' + repr(REMOTE_DIR) + ', exist_ok=True)'
        self.ssh('python3 -c ' + shlex.quote(script))
        uploaded = []
        for source, name in zip(sources, names):
            remote = REMOTE_DIR + '/' + name
            self.scp(str(source), remote, True)
            # Bootstrap cannot assume an already installed helper can hash files.
            script = 'import hashlib; print(hashlib.sha256(open(' + repr(remote) + ", 'rb').read()).hexdigest())"
            actual = self.ssh('python3 -c ' + shlex.quote(script)).strip()
            if actual != sha256(source):
                raise DeckError('Bootstrap checksum mismatch: ' + name)
            uploaded.append(name)
        return {'ok': True, 'uploaded': uploaded, 'status': self.request({'op': 'status'})}


class Session:
    def __init__(self, transport, runs_dir=None, run_dir=None):
        self.transport = transport
        if run_dir is not None:
            self.directory = Path(run_dir).expanduser().resolve()
            self.directory.mkdir(parents=True, exist_ok=True)
        else:
            self.directory = Path(runs_dir or HERE / 'runs') / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
            self.directory.mkdir(parents=True, exist_ok=False)

    def record(self, request, result):
        event = {'time': time.time(), 'request': request, 'result': result}
        with (self.directory / 'actions.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event) + '\n')

    def execute(self, args):
        request = {'op': args.command}
        try:
            result = self._execute(args, request)
        except Exception as error:
            self.record(request, {'ok': False, 'error': str(error)})
            raise
        self.record(request, result)
        result['run_directory'] = str(self.directory)
        return result

    def _execute(self, args, request):
        transport = self.transport
        if args.command == 'bootstrap':
            return transport.bootstrap()
        if args.command == 'push':
            request.update(local=args.local, remote=args.remote)
            return transport.push(args.local, args.remote)
        if args.command == 'pull':
            request.update(remote=args.remote, local=args.local)
            return transport.pull(args.remote, args.local)
        if args.command == 'exec':
            argv = args.argv[1:] if args.argv[:1] == ['--'] else args.argv
            if not argv:
                raise DeckError('exec needs a program and optional arguments after --.')
            request.update(argv=argv, timeout=args.timeout)
        elif args.command == 'input':
            try:
                text = args.json_file.read_text(encoding='utf-8-sig') if args.json_file else args.json
                payload = json.loads(text)
            except ValueError as error:
                raise DeckError('input expects valid JSON.') from error
            if not isinstance(payload, dict):
                raise DeckError('input expects one JSON action object.')
            request.update(payload)
            request['op'] = 'input'
        elif args.command == 'deploy':
            remote = REMOTE_DIR + '/candidate-' + uuid.uuid4().hex + '.zip'
            transfer = transport.push(args.bundle, remote)
            request.update(path=transfer['path'], sha256=transfer['sha256'])
        elif args.command == 'stop' and args.force:
            request['force'] = True
        elif args.command == 'screenshot' and args.pid is not None:
            if args.pid < 1:
                raise DeckError('Gamescope PID must be positive.')
            request['pid'] = args.pid
        result = transport.request(request, timeout=args.timeout + 15)
        if args.command == 'screenshot':
            filename = 'screen-' + uuid.uuid4().hex + '.png'
            downloaded = transport.pull(result['path'], self.directory / filename, result['sha256'])
            result.update(downloaded)
        elif args.command == 'logs':
            local_files = []
            capture_id = uuid.uuid4().hex
            for index, file in enumerate(result.get('files', [])):
                name = Path(file['path']).name.replace('\\', '_')
                local_files.append(transport.pull(file['path'], self.directory / f'{capture_id}-{index:02d}-{name}', file['sha256']))
            result['files'] = local_files
        return result


def parser():
    app = argparse.ArgumentParser(description=__doc__, epilog='Every operation emits JSON. Configure/pair once, bootstrap, then status. Keys and configuration stay outside Git.')
    app.add_argument('--config-dir', type=Path, default=CONFIG_DIR, help='Local private configuration directory')
    app.add_argument('--run-dir', type=Path, help='Reuse this artifact folder and append its action log across commands')
    commands = app.add_subparsers(dest='command', required=True)
    setup = commands.add_parser('configure', help='Save paired Deck connection details locally; never copies the private key')
    setup.add_argument('--host', required=True)
    setup.add_argument('--identity', required=True)
    setup.add_argument('--user', default='deck')
    descriptions = {'bootstrap': 'Upload and verify the remote helpers',
                    'status': 'Inspect connection, display, game and input capability',
                    'screenshot': 'Capture a fresh screen and download it into this run folder',
                    'launch': 'Launch installed Megabonk through Steam',
                    'stop': 'Explicitly stop Megabonk', 'logs': 'Download game and mod logs',
                    'restore': 'Restore the preserved original multiplayer plugin'}
    for name, description in descriptions.items():
        command = commands.add_parser(name, help=description)
        command.add_argument('--timeout', type=int, default=180 if name == 'restore' else 60,
                             help='Host command timeout in seconds')
        if name == 'stop':
            command.add_argument('--force', action='store_true', help='Escalate to SIGKILL if Megabonk does not exit after SIGTERM')
        elif name == 'screenshot':
            command.add_argument('--pid', type=int, help='Select a Gamescope process when more than one is running')
    upload = commands.add_parser('push', help='Upload a file and verify SHA-256; remote parent must exist')
    upload.add_argument('local')
    upload.add_argument('remote')
    download = commands.add_parser('pull', help='Download a file and verify SHA-256 before replacing the destination')
    download.add_argument('remote')
    download.add_argument('local')
    execute = commands.add_parser('exec', help='Run a bounded remote command: exec -- program arg ...')
    execute.add_argument('--timeout', type=int, default=60, help='Remote process execution timeout in seconds')
    execute.add_argument('argv', nargs=argparse.REMAINDER)
    controls = commands.add_parser('input', help='Send one JSON action object; see remote/README.md for the schema')
    input_source = controls.add_mutually_exclusive_group(required=True)
    input_source.add_argument('json', nargs='?', help='One JSON input action')
    input_source.add_argument('--file', dest='json_file', type=Path, help='Read the JSON action from a UTF-8 file (avoids shell quoting)')
    controls.add_argument('--timeout', type=int, default=60, help='Host command timeout in seconds')
    deploy = commands.add_parser('deploy', help='Upload a candidate bundle, verify it, and install; stop the game first')
    deploy.add_argument('bundle')
    deploy.add_argument('--timeout', type=int, default=180, help='Host command timeout in seconds')
    return app


def main(argv=None):
    app = parser()
    args = app.parse_args(argv)
    try:
        if hasattr(args, 'timeout') and not 1 <= args.timeout <= 300:
            raise DeckError('Timeout must be between 1 and 300 seconds.')
        if args.command == 'configure':
            result = configure(args.host, args.identity, args.user, args.config_dir)
        else:
            config_file = args.config_dir / 'remote.json'
            if not config_file.is_file():
                raise DeckError('Run deck configure --host HOST --identity KEY first.')
            config = json.loads(config_file.read_text(encoding='utf-8'))
            result = Session(Transport(config, args.config_dir), run_dir=args.run_dir).execute(args)
        print(json.dumps(result, indent=2))
        return 0
    except (DeckError, OSError, ValueError, KeyError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
