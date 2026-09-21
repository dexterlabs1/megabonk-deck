import importlib.util
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
# remote -> megabonk-deck -> Projects
CONTROL = ROOT.parents[1] / 'SteamDeckControl'
spec = importlib.util.spec_from_file_location('megabonk_adapter', ROOT / 'adapter.py')
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)
core_spec = importlib.util.spec_from_file_location('control_runtime', CONTROL / 'agent.py')
core = importlib.util.module_from_spec(core_spec)
core_spec.loader.exec_module(core)


def proc(pid=12, name='gamescope', **overrides):
    item = {'pid': pid, 'name': name, 'start': '123', 'exe': '/usr/bin/' + name, 'env': {}, 'cwd': '/tmp'}
    item.update(overrides)
    return item


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        agent.bind(core)

    def test_legacy_deck_import_forwards_with_megabonk_default(self):
        environment = os.environ.copy()
        environment['PYTHONPATH'] = str(ROOT)
        result = subprocess.run([sys.executable, '-c',
            'import deck; print(deck.HERE); print(deck.Transport.__init__.__defaults__[-1])'],
            cwd=self.directory, env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(CONTROL), 'megabonk'])

    def test_legacy_cli_help_works_outside_repository(self):
        result = subprocess.run([sys.executable, str(ROOT / 'deck.py'), '--help'],
                                cwd=self.directory, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--adapter', result.stdout)

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


if __name__ == "__main__":
    unittest.main()
