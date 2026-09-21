"""Host CLI tests; SSH/SCP are executable local fakes, not a physical Deck."""
import argparse
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('deck', Path(__file__).resolve().parents[1] / 'deck.py')
deck = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deck)

FAKE = r'''
import hashlib, json, os, pathlib, shlex, shutil, sys
root = pathlib.Path(sys.argv[1])
mode = sys.argv[2]
args = sys.argv[3:]
def emit(payload): print(json.dumps({'ok': True, 'result': payload}))
if mode == 'offline':
    print('connection refused', file=sys.stderr); sys.exit(255)
def path(value):
    value = value.removeprefix('~/')
    return pathlib.Path(value) if pathlib.Path(value).is_absolute() else root / value
if args[0] == 'scp':
    source, target = args[-2:]
    if source.startswith('deck@'):
        source = path(shlex.split(source.split(':', 1)[1])[0])
        shutil.copyfile(source, target)
        if mode == 'corrupt': pathlib.Path(target).write_bytes(b'corrupt')
    else:
        target = path(shlex.split(target.split(':', 1)[1])[0])
        shutil.copyfile(source, target)
        if mode == 'corrupt': target.write_bytes(b'corrupt')
elif args[0] == 'ssh':
    request = json.load(sys.stdin)
    if mode == 'badjson': print('not JSON'); sys.exit(0)
    if request['op'] == 'file_hash':
        file = path(request['path'])
        emit({'path': str(file), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
    elif request['op'] == 'exec':
        result = subprocess_run = __import__('subprocess').run(request['argv'], capture_output=True, text=True)
        emit({'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    elif request['op'] == 'screenshot':
        file = root / 'screen.png'
        file.write_bytes(b'fresh screen bytes')
        emit({'path': str(file), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
    elif request['op'] == 'deploy':
        emit({'request': request})
    else: emit({'received': request})
'''


class HostTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='deck host tests ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.remote = self.root / 'remote home'
        self.remote.mkdir()
        self.identity = self.root / 'private key'
        self.identity.write_text('test key placeholder')
        self.config = {'host': 'steamdeck.local', 'user': 'deck', 'identity': str(self.identity)}
        self.fake = self.root / 'fake.py'
        self.fake.write_text(FAKE)
        self.mode = 'normal'
        self.calls = []
        self.transport = deck.Transport(self.config, self.root / 'config', self.run_fake)

    def run_fake(self, argv, **kwargs):
        self.calls.append(argv)
        return subprocess.run([sys.executable, str(self.fake), str(self.remote), self.mode, *argv], **kwargs)

    def test_config_external_and_key_not_copied(self):
        result = deck.configure('steamdeck.local', str(self.identity), config_dir=self.root / 'settings')
        saved = json.loads(Path(result['config']).read_text())
        self.assertEqual(saved['identity'], str(self.identity))
        self.assertEqual(list((self.root / 'settings').iterdir()), [Path(result['config'])])

    def test_reject_option_injection(self):
        for host in ['-oProxyCommand=bad', 'host;command', 'host\ncommand', 'x@host']:
            with self.subTest(host=host), self.assertRaises(deck.DeckError):
                deck.validate_config({**self.config, 'host': host})

    def test_security_options(self):
        self.transport.request({'op': 'status'})
        command = self.calls[-1]
        self.assertIn('BatchMode=yes', command)
        self.assertIn('IdentitiesOnly=yes', command)
        self.assertIn('StrictHostKeyChecking=accept-new', command)
        self.assertIn('ConnectTimeout=10', command)
        self.assertIn('UserKnownHostsFile=' + str(self.root / 'config' / 'known_hosts'), command)

    def test_upload_spaces_apostrophe_and_metacharacters(self):
        local = self.root / 'candidate build.zip'
        local.write_bytes(b'candidate')
        name = "my code's $(touch hacked);.zip"
        result = self.transport.push(local, name)
        self.assertEqual((self.remote / name).read_bytes(), b'candidate')
        self.assertEqual(result['sha256'], deck.sha256(local))
        self.assertFalse((self.remote / 'hacked').exists())

    def test_download_spaces_atomic_and_verified(self):
        remote = self.remote / 'log file.txt'
        remote.write_bytes(b'log')
        target = self.root / 'output folder' / 'download.txt'
        result = self.transport.pull('~/log file.txt', target)
        self.assertEqual(target.read_bytes(), b'log')
        self.assertEqual(result['sha256'], deck.sha256(remote))

    def test_corrupt_download_preserves_old_destination(self):
        (self.remote / 'log.txt').write_bytes(b'new')
        target = self.root / 'log.txt'
        target.write_bytes(b'old')
        self.mode = 'corrupt'
        with self.assertRaisesRegex(deck.DeckError, 'checksum mismatch'):
            self.transport.pull('log.txt', target)
        self.assertEqual(target.read_bytes(), b'old')
        self.assertEqual(list(self.root.glob('*.partial-*')), [])

    def test_corrupt_upload_fails(self):
        source = self.root / 'candidate.zip'
        source.write_bytes(b'candidate')
        self.mode = 'corrupt'
        with self.assertRaisesRegex(deck.DeckError, 'checksum mismatch'):
            self.transport.push(source, 'candidate.zip')

    def test_remote_changed_before_capture_download(self):
        (self.remote / 'screen.png').write_bytes(b'changed')
        with self.assertRaisesRegex(deck.DeckError, 'changed before download'):
            self.transport.pull('screen.png', self.root / 'screen.png', '0' * 64)

    def test_connection_failure_is_bounded_and_reported(self):
        self.mode = 'offline'
        with self.assertRaisesRegex(deck.DeckError, 'connection refused'):
            self.transport.request({'op': 'status'})

    def test_timeout_is_reported(self):
        def timeout(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, kwargs['timeout'])
        self.transport.runner = timeout
        with self.assertRaisesRegex(deck.DeckError, 'timed out after 2s'):
            self.transport.request({'op': 'status'}, timeout=2)

    def test_invalid_json_is_actionable(self):
        self.mode = 'badjson'
        with self.assertRaisesRegex(deck.DeckError, 'invalid JSON'):
            self.transport.request({'op': 'status'})

    def test_exec_does_not_shell_interpolate(self):
        args = deck.parser().parse_args(['exec', '--', sys.executable, '-c', 'import sys; print(sys.argv[1])', '$(untouched);literal'])
        result = deck.Session(self.transport, self.root / 'runs').execute(args)
        self.assertEqual(result['stdout'].strip(), '$(untouched);literal')

    def test_screenshot_artifact_and_action_log(self):
        session = deck.Session(self.transport, self.root / 'runs')
        result = session.execute(deck.parser().parse_args(['screenshot']))
        self.assertEqual(Path(result['path']).read_bytes(), b'fresh screen bytes')
        event = json.loads((session.directory / 'actions.jsonl').read_text())
        self.assertEqual(event['result']['sha256'], deck.sha256(result['path']))
        self.assertEqual(event['request']['op'], 'screenshot')

    def test_deploy_verifies_before_calling_deployment(self):
        (self.remote / deck.REMOTE_DIR).mkdir(parents=True)
        local = self.root / 'candidate.zip'
        local.write_bytes(b'candidate')
        result = deck.Session(self.transport, self.root / 'runs').execute(deck.parser().parse_args(['deploy', str(local)]))
        self.assertEqual(result['request']['sha256'], deck.sha256(local))
        self.assertEqual(result['request']['op'], 'deploy')
        self.assertFalse(any('stop' in arg for command in self.calls for arg in command))

    def test_error_action_is_retained(self):
        self.mode = 'offline'
        session = deck.Session(self.transport, self.root / 'runs')
        with self.assertRaises(deck.DeckError):
            session.execute(deck.parser().parse_args(['status']))
        event = json.loads((session.directory / 'actions.jsonl').read_text())
        self.assertFalse(event['result']['ok'])

    def test_cli_help_real_process(self):
        result = subprocess.run([sys.executable, str(Path(deck.__file__)), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        for command in ['bootstrap', 'screenshot', 'deploy', 'restore', 'configure']:
            self.assertIn(command, result.stdout)

    def test_input_schema_cannot_override_operation(self):
        args = deck.parser().parse_args(['input', '{"op":"stop","action":"button","buttons":["A"],"duration_ms":100}'])
        result = deck.Session(self.transport, self.root / 'runs').execute(args)
        self.assertEqual(result['received']['op'], 'input')
        self.assertEqual(result['received']['buttons'], ['A'])

    def test_input_json_file_preserves_quotes_and_accepts_utf8_bom(self):
        action = self.root / 'input action.json'
        action.write_text(json.dumps({'action': 'text', 'text': 'CODE"123'}), encoding='utf-8-sig')
        args = deck.parser().parse_args(['input', '--file', str(action)])
        result = deck.Session(self.transport, self.root / 'runs').execute(args)
        self.assertEqual(result['received'], {'op': 'input', 'action': 'text', 'text': 'CODE"123'})

    def test_input_sources_are_required_and_mutually_exclusive(self):
        for argv in (['input'], ['input', '{}', '--file', 'action.json']):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                deck.parser().parse_args(argv)

    def test_invalid_input_file_is_logged_without_remote_execution(self):
        action = self.root / 'input.json'
        action.write_text('not json')
        session = deck.Session(self.transport, self.root / 'runs')
        with self.assertRaisesRegex(deck.DeckError, 'valid JSON'):
            session.execute(deck.parser().parse_args(['input', '--file', str(action)]))
        self.assertFalse(self.calls)
        event = json.loads((session.directory / 'actions.jsonl').read_text())
        self.assertFalse(event['result']['ok'])

    def test_grouped_commands_append_actions_and_keep_both_screenshots(self):
        directory = self.root / 'shared test session'
        first_args = deck.parser().parse_args(['--run-dir', str(directory), 'screenshot'])
        first_session = deck.Session(self.transport, run_dir=first_args.run_dir)
        first = first_session.execute(first_args)
        second_session = deck.Session(self.transport, run_dir=directory)
        second_session.execute(deck.parser().parse_args(['input', '{"action":"button","buttons":["A"]}']))
        second = second_session.execute(deck.parser().parse_args(['screenshot']))
        self.assertEqual(first['run_directory'], second['run_directory'])
        self.assertNotEqual(first['path'], second['path'])
        self.assertEqual(len(list(directory.glob('screen-*.png'))), 2)
        for result in (first, second):
            self.assertEqual(Path(result['path']).read_bytes(), b'fresh screen bytes')
        events = [json.loads(line) for line in (directory / 'actions.jsonl').read_text().splitlines()]
        self.assertEqual([event['request']['op'] for event in events], ['screenshot', 'input', 'screenshot'])
        self.assertEqual(events[0]['result']['path'], first['path'])
        self.assertEqual(events[2]['result']['path'], second['path'])

    def test_default_sessions_remain_separate(self):
        first = deck.Session(self.transport, self.root / 'runs')
        second = deck.Session(self.transport, self.root / 'runs')
        self.assertNotEqual(first.directory, second.directory)

    def test_stop_force_is_explicit_and_forwarded(self):
        session = deck.Session(self.transport, self.root / 'runs')
        normal = session.execute(deck.parser().parse_args(['stop']))
        forced = session.execute(deck.parser().parse_args(['stop', '--force']))
        self.assertEqual(normal['received'], {'op': 'stop'})
        self.assertEqual(forced['received'], {'op': 'stop', 'force': True})

    def test_screenshot_pid_is_forwarded_and_validated(self):
        session = deck.Session(self.transport, self.root / 'runs')
        session.execute(deck.parser().parse_args(['screenshot', '--pid', '1234']))
        event = json.loads((session.directory / 'actions.jsonl').read_text())
        self.assertEqual(event['request'], {'op': 'screenshot', 'pid': 1234})
        with self.assertRaisesRegex(deck.DeckError, 'PID must be positive'):
            session.execute(deck.parser().parse_args(['screenshot', '--pid', '0']))

    def test_real_agent_protocol_file_hash(self):
        agent = Path(deck.__file__).with_name('agent.py')
        def local_agent(argv, **kwargs):
            return subprocess.run([sys.executable, str(agent)], **kwargs)
        self.transport.runner = local_agent
        result = self.transport.request({'op': 'file_hash', 'path': str(self.identity)})
        self.assertEqual(result['sha256'], deck.sha256(self.identity))
        self.assertEqual(result['path'], str(self.identity))


if __name__ == '__main__':
    unittest.main()
