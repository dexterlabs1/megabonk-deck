import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'remote')]


@unittest.skipUnless(sys.platform == 'linux', 'Deck deployment runs on Linux')
class DeploymentTests(unittest.TestCase):
    def setUp(self):
        import deployment
        self.d = deployment
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.bundle = ROOT / 'releases/megabonk-deck-beta6-test.zip'
        self.request = {'op': 'deploy', 'path': str(self.bundle), 'sha256': self.d.BUNDLE_SHA}
        self.state = self.home / '.local/share/megabonk-deck'
        self.game = self.home / '.local/share/Steam/steamapps/common/Megabonk'
        self.target = self.game / 'BepInEx/plugins/MegabonkTogether/MegabonkTogether.dll'
        self.target.parent.mkdir(parents=True)
        with zipfile.ZipFile(os.environ['MEGABONK_OFFICIAL_ZIP']) as archive:
            self.original = archive.read('MegabonkTogether/MegabonkTogether.dll')
        self.assertEqual(hashlib.sha256(self.original).hexdigest(), 'a5ee8a76785068d1e1f8715b6fdd57d8801fbed3b9f1c62fa0c9e05ae7893a28')
        self.target.write_bytes(self.original)
        for obj, name, kwargs in [
            (Path, 'home', {'return_value': self.home}),
            (self.d.installer, 'running', {'return_value': False}),
            (self.d.installer, 'discover', {'return_value': (None, None, self.game, '3405340')}),
            (self.d.installer, 'dialog', {'side_effect': AssertionError('Interactive dialog called')})]:
            item = patch.object(obj, name, **kwargs)
            item.start()
            self.addCleanup(item.stop)

    def test_deploy_repeat_restore_no_prompts(self):
        result = self.d.handle(self.request)
        self.assertTrue(result['changed'])
        self.assertEqual(result['sha256'], 'c79cf7d1abf4b25c02ee8b51d7d754f57a98a65fb213fad0464059d446af4580')
        marker = json.loads((self.state / 'deck-beta-backup.json').read_text())
        self.assertEqual(Path(marker['original']).read_bytes(), self.original)
        self.assertFalse(self.d.handle(self.request)['changed'])
        self.assertTrue(self.d.handle({'op': 'restore'})['restored'])
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_reject_changed_hash(self):
        with self.assertRaisesRegex(RuntimeError, 'published'):
            self.d.handle(dict(self.request, sha256='0' * 64))
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_beta5_upgrade_restore_preserves_original_backup(self):
        self.state.mkdir(parents=True)
        with zipfile.ZipFile(ROOT / 'releases/megabonk-deck-beta5-test.zip') as archive:
            updater = types.ModuleType('beta5_updater')
            exec(archive.read('megabonk-deck-beta5-test/candidate_updater.py'), updater.__dict__)
            package = archive.read('megabonk-deck-beta5-test/megabonk-deck-beta5.zip')
        updater.apply_update(self.game, self.state, package)
        original = json.loads((self.state / 'deck-beta-backup.json').read_text())['original']
        self.assertTrue(self.d.handle(self.request)['changed'])
        self.assertEqual(json.loads((self.state / 'deck-beta-backup.json').read_text())['original'], original)
        self.assertTrue(self.d.handle({'op': 'restore'})['restored'])
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_reject_corrupt_bundle(self):
        bad = self.home / 'bad.zip'
        bad.write_bytes(b'not the bundle')
        with self.assertRaisesRegex(RuntimeError, 'published'):
            self.d.handle(dict(self.request, path=str(bad)))

    def test_reject_running_game(self):
        with patch.object(self.d.installer, 'running', return_value=True):
            with self.assertRaisesRegex(RuntimeError, 'Stop Megabonk'):
                self.d.handle(self.request)
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_restore_rechecks_cached_code(self):
        self.d.handle(self.request)
        cache = self.state / 'remote/verified-beta6-test.zip'
        cache.write_bytes(b'corrupted')
        with self.assertRaisesRegex(RuntimeError, 'published'):
            self.d.handle({'op': 'restore'})

    def test_lock_refusal(self):
        import fcntl
        self.state.mkdir(parents=True)
        with (self.state / 'install.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, 'Another installer'):
                self.d.handle(self.request)

    def test_unknown_mod_is_preserved(self):
        self.target.write_bytes(b'unknown mod')
        with self.assertRaisesRegex(RuntimeError, 'Unknown mod'):
            self.d.handle(self.request)
        self.assertEqual(self.target.read_bytes(), b'unknown mod')

    def test_reject_fifo_without_blocking(self):
        fifo = self.home / 'bundle.fifo'
        os.mkfifo(fifo)
        with self.assertRaisesRegex(RuntimeError, 'regular file'):
            self.d.handle(dict(self.request, path=str(fifo)))

    def test_agent_subprocess_deploy_restore(self):
        # Exercise actual manifest discovery and the JSON boundary, no monkeypatches
        # are inherited by these children; all writes stay in this temporary HOME.
        (self.game / 'Megabonk.exe').write_bytes(b'game-fixture')
        manifest = self.game.parents[1] / 'appmanifest_3405340.acf'
        manifest.write_text('"AppState" { "appid" "3405340" "name" "Megabonk" "installdir" "Megabonk" }')
        adapter_root = self.home / 'adapters'
        adapter = adapter_root / 'megabonk'
        adapter.mkdir(parents=True)
        for name in ('adapter.py', 'deployment.py'):
            shutil.copy2(ROOT / 'remote' / name, adapter / name)
        shutil.copy2(ROOT / 'installer.py', adapter / 'installer.py')
        env = dict(os.environ, HOME=str(self.home), DECK_ADAPTER_ROOT=str(adapter_root))
        def call(request):
            completed = subprocess.run([sys.executable, str(ROOT.parent / 'SteamDeckControl/agent.py')],
                                       input=json.dumps(dict(request, adapter='megabonk')), text=True, capture_output=True,
                                       env=env, timeout=15)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(completed.stderr, '')
            parsed = json.loads(completed.stdout)
            self.assertTrue(parsed['ok'])
            return parsed['result']
        installed = call(self.request)
        self.assertTrue(installed['changed'])
        self.assertEqual(hashlib.sha256(self.target.read_bytes()).hexdigest(), installed['sha256'])
        restored = call({'op': 'restore'})
        self.assertTrue(restored['restored'])
        self.assertEqual(self.target.read_bytes(), self.original)


if __name__ == '__main__':
    unittest.main()
