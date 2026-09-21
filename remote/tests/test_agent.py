import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
import zlib

SPEC = importlib.util.spec_from_file_location('deck_agent', Path(__file__).parents[1] / 'agent.py')
agent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent)


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


PNG = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
       + chunk(b'IDAT', zlib.compress(b'\0\xff\0\0')) + chunk(b'IEND', b''))


def proc(pid=12, name='gamescope', **overrides):
    item = {'pid': pid, 'name': name, 'start': '123', 'exe': '/usr/bin/' + name,
            'env': {}, 'cwd': '/tmp'}
    item.update(overrides)
    return item


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def fixture_game(self, library=None):
        steam = self.directory / '.local/share/Steam'
        library = steam if library is None else library
        (steam / 'steamapps').mkdir(parents=True, exist_ok=True)
        (library / 'steamapps').mkdir(parents=True, exist_ok=True)
        if library != steam:
            (steam / 'steamapps/libraryfolders.vdf').write_text(
                '"libraryfolders" { "0" { "path" "' + str(library) + '" } }')
        game = library / 'steamapps/common/Megabonk'
        game.mkdir(parents=True)
        (game / 'Megabonk.exe').write_bytes(b'fixture')
        (library / 'steamapps/appmanifest_3405340.acf').write_text(
            '"AppState" { "appid" "3405340" "name" "Megabonk" "installdir" "Megabonk" }')
        return game

    def test_discover_mounted_library_with_spaces(self):
        game = self.fixture_game(self.directory / 'mounted sd card')
        self.assertEqual(agent.discover_game(self.directory), {'path': str(game.resolve()), 'appid': '3405340'})

    def test_discover_rejects_traversal(self):
        game = self.fixture_game()
        manifest = game.parents[1] / 'appmanifest_3405340.acf'
        manifest.write_text('"name" "Megabonk" "appid" "3405340" "installdir" "../other"')
        with self.assertRaisesRegex(RuntimeError, 'Unsafe'):
            agent.discover_game(self.directory)

    def test_discover_rejects_ambiguous_installations(self):
        self.fixture_game()
        self.fixture_game(self.directory / 'second')
        with self.assertRaisesRegex(RuntimeError, 'Expected one'):
            agent.discover_game(self.directory)

    def test_game_processes_do_not_match_helpers_or_other_app(self):
        game = {'path': '/games/Megabonk', 'appid': '123'}
        items = [proc(1, 'Megabonk.exe', env={'SteamAppId': '123'}),
                 proc(2, 'wine', env={'SteamAppId': '123'}),
                 proc(3, 'Megabonk.exe', env={'SteamAppId': '456'}),
                 proc(4, 'Megabonk.exe', cwd='/games/Megabonk')]
        self.assertEqual([p['pid'] for p in agent.game_processes(game, items)], [1, 4])

    def test_reused_pid_is_not_signalled(self):
        original = proc()
        with mock.patch.object(agent, 'process', return_value=proc(start='999')), mock.patch.object(agent.os, 'kill') as kill:
            with self.assertRaisesRegex(RuntimeError, 'changed'):
                agent.signal_process(original, 15)
            kill.assert_not_called()

    def test_session_only_copies_display_keys(self):
        items = [proc(name='steam', env={'DISPLAY': ':1', 'SECRET_TOKEN': 'do-not-copy'})]
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(agent.session_environment(items), {'DISPLAY': ':1'})

    def test_complete_png_and_partial_or_corrupt_rejection(self):
        self.assertEqual(agent.complete_image(PNG), 'png')
        self.assertIsNone(agent.complete_image(PNG[:-1]))
        self.assertIsNone(agent.complete_image(PNG[:45] + b'X' + PNG[46:]))
        self.assertIsNone(agent.complete_image(PNG + b'junk'))

    def screenshot_context(self):
        patches = [mock.patch.object(agent, 'SCREEN_DIR', self.directory),
                   mock.patch.object(agent, 'processes', return_value=[proc()]),
                   mock.patch.object(agent, 'artifact_dir', return_value=self.directory),
                   mock.patch.object(agent, 'request_screenshot', return_value='mock')]
        started = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)
        return started[-1]

    @unittest.skipUnless(hasattr(os, 'getuid'), 'Linux file ownership')
    def test_stale_screenshot_never_returned(self):
        (self.directory / 'gamescope.png').write_bytes(PNG)
        self.screenshot_context()
        with self.assertRaisesRegex(RuntimeError, 'fresh complete'):
            agent.screenshot({'timeout': 0.05})

    @unittest.skipUnless(hasattr(os, 'getuid'), 'Linux file ownership')
    def test_new_partial_screenshot_never_returned(self):
        request = self.screenshot_context()
        request.side_effect = lambda _p: (self.directory / 'gamescope.png').write_bytes(PNG[:-12])
        with self.assertRaisesRegex(RuntimeError, 'fresh complete'):
            agent.screenshot({'timeout': 0.3})

    @unittest.skipUnless(hasattr(os, 'getuid'), 'Linux file ownership')
    def test_new_screenshot_snapshotted_and_hashed(self):
        stale = self.directory / 'gamescope-old.png'
        stale.write_bytes(PNG)
        request = self.screenshot_context()
        request.side_effect = lambda _p: (self.directory / 'gamescope.png').write_bytes(PNG)
        result = agent.screenshot({'timeout': 1})
        self.assertEqual(Path(result['path']).read_bytes(), PNG)
        self.assertEqual(result['sha256'], hashlib.sha256(PNG).hexdigest())
        self.assertNotEqual(result['path'], str(self.directory / 'gamescope.png'))
        self.assertTrue(stale.exists())

    @unittest.skipUnless(hasattr(os, 'getuid'), 'Linux file ownership')
    def test_screenshot_symlinks_ignored(self):
        actual = self.directory / 'private.png'
        actual.write_bytes(PNG)
        (self.directory / 'gamescope.png').symlink_to(actual)
        with mock.patch.object(agent, 'SCREEN_DIR', self.directory):
            self.assertEqual(agent.screenshot_files(), {})

    def test_multiple_gamescopes_require_explicit_pid(self):
        with mock.patch.object(agent, 'processes', return_value=[proc(1), proc(2)]), \
                mock.patch.object(agent, 'request_screenshot') as request:
            with self.assertRaisesRegex(RuntimeError, 'Expected one'):
                agent.screenshot({})
            request.assert_not_called()

    @unittest.skipUnless(hasattr(signal := agent.signal, 'SIGUSR2'), 'Linux signal')
    def test_screenshot_refuses_signal_without_handler(self):
        directory = self.directory / '12'
        directory.mkdir()
        (directory / 'status').write_text('SigCgt:\t0000000000000000\n')
        with mock.patch.object(agent, 'PROC', self.directory), \
                mock.patch.object(agent.shutil, 'which', return_value=None), \
                mock.patch.object(agent, 'signal_process') as send:
            with self.assertRaisesRegex(RuntimeError, 'no SIGUSR2'):
                agent.request_screenshot(proc())
            send.assert_not_called()

    def test_screenshot_prefers_valve_xprop(self):
        with mock.patch.object(agent.shutil, 'which', return_value='/usr/bin/xprop'), \
                mock.patch.object(agent, 'session_environment', return_value={}), \
                mock.patch.object(agent.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(agent.request_screenshot(proc()), 'xprop-full-composition')
            self.assertEqual(run.call_args.args[0][-1], '3')
            self.assertEqual(run.call_args.kwargs['env']['DISPLAY'], ':0')

    def test_stop_only_signals_selected_identity(self):
        game = {'appid': '123', 'path': '/game'}
        target = proc(12, 'Megabonk.exe')
        with mock.patch.object(agent, 'selected_game', return_value=game), \
                mock.patch.object(agent, 'game_processes', return_value=[target]), \
                mock.patch.object(agent, 'signal_process') as send, \
                mock.patch.object(agent, 'unchanged', return_value=False):
            self.assertEqual(agent.stop({})['stopped_pids'], [12])
            send.assert_called_once_with(target, agent.signal.SIGTERM)

    def test_stop_does_not_escalate_without_force(self):
        with mock.patch.object(agent, 'selected_game', return_value={'appid': '1'}), \
                mock.patch.object(agent, 'game_processes', return_value=[proc()]), \
                mock.patch.object(agent, 'signal_process') as send, \
                mock.patch.object(agent, 'unchanged', return_value=True):
            with self.assertRaisesRegex(RuntimeError, 'force=true'):
                agent.stop({'timeout': 0.01})
            self.assertEqual(send.call_count, 1)

    def test_exec_literal_argv_and_exit_code(self):
        with mock.patch.object(agent, 'session_environment', return_value=os.environ.copy()):
            result = agent.execute({'argv': [sys.executable, '-c', 'import sys; print(sys.argv[1]);sys.exit(7)', '$(echo secret); &']})
        self.assertEqual(result['exit_code'], 7)
        self.assertEqual(result['stdout'].strip(), '$(echo secret); &')

    @unittest.skipUnless(hasattr(os, 'killpg'), 'Linux process groups')
    def test_exec_timeout(self):
        with mock.patch.object(agent, 'session_environment', return_value=os.environ.copy()):
            result = agent.execute({'argv': [sys.executable, '-c', 'import time;time.sleep(20)'], 'timeout': 0.05})
        self.assertTrue(result['timed_out'])
        self.assertNotEqual(result['exit_code'], 0)

    def test_exec_rejects_shell_string(self):
        with self.assertRaises(ValueError):
            agent.execute({'argv': 'echo hi'})

    def test_bounded_rejects_infinity_nan_negative(self):
        for value in (float('nan'), float('inf'), -1, 301):
            with self.assertRaises(ValueError):
                agent.bounded(value, 30, 300)

    def test_logs_bounded_snapshot_not_userdata(self):
        game = self.fixture_game()
        log = game / 'BepInEx/LogOutput.log'
        log.parent.mkdir()
        log.write_bytes(b'secret-old-tail')
        with mock.patch.object(agent, 'selected_game', return_value={'path': str(game)}), \
                mock.patch.object(agent, 'artifact_dir', return_value=self.directory):
            result = agent.logs({'max_bytes': 4})
        self.assertEqual(len(result['files']), 1)
        self.assertEqual(Path(result['files'][0]['path']).read_bytes(), b'tail')
        self.assertTrue(result['files'][0]['truncated'])

    def test_file_hash_resolves_home_relative(self):
        (self.directory / 'test file').write_bytes(b'contents')
        with mock.patch.object(agent.Path, 'home', return_value=self.directory):
            result = agent.handle({'op': 'file_hash', 'path': 'test file'})
        self.assertEqual(result['path'], str((self.directory / 'test file').resolve()))
        self.assertEqual(result['sha256'], hashlib.sha256(b'contents').hexdigest())

    def test_protocol_failure_is_json_and_nonzero(self):
        result = subprocess.run([sys.executable, str(Path(agent.__file__))], input='{"op":"unknown"}',
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)['ok'])
        self.assertEqual(result.stderr, '')

    def test_input_routing_strips_transport_operation(self):
        handle = mock.Mock(return_value={'ok': True, 'sent': 1})
        with mock.patch.dict(sys.modules, {'input_agent': types.SimpleNamespace(handle=handle)}):
            result = agent.handle({'op': 'input', 'action': 'button', 'buttons': ['A']})
        handle.assert_called_once_with({'action': 'button', 'buttons': ['A']})
        self.assertEqual(result['sent'], 1)

    def test_input_failure_becomes_transport_error(self):
        handle = mock.Mock(return_value={'ok': False, 'error': 'uinput permission required'})
        with mock.patch.dict(sys.modules, {'input_agent': types.SimpleNamespace(handle=handle)}):
            with self.assertRaisesRegex(RuntimeError, 'uinput permission'):
                agent.handle({'op': 'input', 'action': 'start'})

    def test_launch_uses_existing_steam_configuration(self):
        game = {'appid': '123', 'path': '/game'}
        with mock.patch.object(agent, 'selected_game', return_value=game), \
                mock.patch.object(agent, 'game_processes', side_effect=[[], [proc(42, 'Megabonk.exe')]]), \
                mock.patch.object(agent, 'processes', return_value=[proc(name='steam')]), \
                mock.patch.object(agent.shutil, 'which', return_value='/usr/bin/steam'), \
                mock.patch.object(agent, 'execute', return_value={'exit_code': 0}) as execute:
            result = agent.launch({})
        self.assertEqual(execute.call_args.args[0]['argv'], ['/usr/bin/steam', '-applaunch', '123'])
        self.assertEqual(result['pids'], [42])

    def test_selected_game_rejects_other_appid(self):
        with mock.patch.object(agent, 'discover_game', return_value={'appid': '123'}):
            with self.assertRaisesRegex(ValueError, 'does not match'):
                agent.selected_game({'appid': '456'})


if __name__ == '__main__':
    unittest.main()
