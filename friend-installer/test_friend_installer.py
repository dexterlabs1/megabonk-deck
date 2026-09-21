"""Real-DLL Linux integration fixtures for the one-file installer."""
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REAL_POPEN = subprocess.Popen
CONFIG = '"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { "apps" { "123" { "LaunchOptions" "-windowed" } } } } } }'


class FriendInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = (ROOT / 'releases/megabonk-deck-beta5-test.zip').read_bytes()
        cls.package = (ROOT / 'releases/megabonk-deck-beta5.zip').read_bytes()
        cls.official_zip = Path(os.environ['MEGABONK_OFFICIAL_ZIP']).read_bytes()
        cls.loader_zip = Path(os.environ['MEGABONK_LOADER_ZIP']).read_bytes()
        with zipfile.ZipFile(io.BytesIO(cls.bundle)) as archive:
            cls.installer = types.ModuleType('installer')
            exec(archive.read('megabonk-deck-beta5-test/installer.py'), cls.installer.__dict__)
            sys.modules['installer'] = cls.installer
            cls.updater = types.ModuleType('candidate_updater')
            exec(archive.read('megabonk-deck-beta5-test/candidate_updater.py'), cls.updater.__dict__)
            sys.modules['candidate_updater'] = cls.updater
        cls.friend = types.ModuleType('friend_install')
        exec((ROOT / 'friend-installer/install.py').read_bytes(), cls.friend.__dict__)
        with zipfile.ZipFile(io.BytesIO(cls.official_zip)) as archive:
            cls.official = archive.read('MegabonkTogether/MegabonkTogether.dll')
        with zipfile.ZipFile(ROOT / 'releases/megabonk-deck-beta4-test.zip') as archive:
            cls.beta4 = types.ModuleType('beta4')
            exec(archive.read('megabonk-deck-beta4-test/candidate_updater.py'), cls.beta4.__dict__)
            cls.beta4_package = archive.read('megabonk-deck-beta4-test/megabonk-deck-beta4.zip')
        assert hashlib.sha256(cls.official_zip).hexdigest() == cls.installer.PACKAGES[1][2]
        assert hashlib.sha256(cls.loader_zip).hexdigest() == cls.installer.PACKAGES[0][2]

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='friend installer test ')
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.steam = self.home / '.local/share/Steam'
        self.game = self.steam / 'steamapps/common/Megabonk'
        self.game.mkdir(parents=True)
        (self.game / 'Megabonk.exe').write_bytes(b'fake executable')
        (self.steam / 'steamapps/appmanifest_123.acf').write_text('"AppState" { "appid" "123" "name" "Megabonk" "installdir" "Megabonk" }')
        self.config = self.steam / 'userdata/1/config/localconfig.vdf'
        self.config.parent.mkdir(parents=True)
        self.config.write_text(CONFIG)
        self.save = self.steam / 'steamapps/compatdata/123/pfx/drive_c/users/steamuser/AppData/LocalLow/Ved/Megabonk/save.dat'
        self.save.parent.mkdir(parents=True)
        self.save.write_bytes(b'precious game save')
        self.state = self.home / '.local/share/megabonk-deck'
        self.target = self.game / 'BepInEx/plugins/MegabonkTogether/MegabonkTogether.dll'
        self.dialogs = []
        def dialog(message, question=False):
            self.dialogs.append((message, question))
            return True
        patches = [patch.object(self.installer.Path, 'home', return_value=self.home),
                   patch.object(self.installer.os, 'geteuid', return_value=1000),
                   patch.object(self.installer.shutil, 'which', return_value='/bin/true'),
                   patch.object(self.installer, 'running', return_value=False),
                   patch.object(self.installer, 'dialog', side_effect=dialog),
                   patch.object(self.installer, 'download', side_effect=self.download),
                   patch.object(self.installer.subprocess, 'Popen'),
                   patch.object(self.updater, 'running', return_value=False),
                   patch.object(self.updater, 'dialog', return_value=True),
                   patch.object(self.beta4, 'running', return_value=False)]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def download(self, url, digest):
        data = (self.package if url == self.friend.PACKAGE_URL else
                self.loader_zip if 'bepinex' in url else self.official_zip)
        self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
        return data

    def managed(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(self.official)
        (self.game / '.megabonk-deck.json').write_text(json.dumps({'version': '5.1.0', 'backup': 'old official backup'}))
        self.state.mkdir(parents=True)

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes() for p in self.home.rglob('*') if p.is_file()}

    def test_fresh_install_single_confirmation_saves_and_restore(self):
        self.assertTrue(self.friend.main())
        self.assertEqual(self.updater.digest(self.target.read_bytes()), self.updater.BETA_DLL_SHA)
        self.assertTrue((self.game / 'winhttp.dll').is_file())
        self.assertEqual(sum(question for _, question in self.dialogs), 1)
        self.assertEqual(len(self.dialogs), 2)
        self.assertIn('Installed Deck beta 5!', self.dialogs[-1][0])
        self.assertEqual(self.save.read_bytes(), b'precious game save')
        self.assertIn('winhttp=n,b', self.config.read_text())
        base_backup = Path(json.loads((self.game / '.megabonk-deck.json').read_text())['backup'])
        self.assertEqual((base_backup / 'saves/0/save.dat').read_bytes(), b'precious game save')
        self.updater.restore(self.state)
        self.assertEqual(self.target.read_bytes(), self.official)

    def test_official_upgrade_and_idempotence(self):
        self.managed()
        with patch.object(self.installer, 'main', side_effect=AssertionError('must not reinstall base')):
            self.friend.main()
            marker = (self.state / 'deck-beta-backup.json').read_bytes()
            self.friend.main()
        self.assertEqual((self.state / 'deck-beta-backup.json').read_bytes(), marker)
        self.assertIn('already installed', self.dialogs[-1][0])
        self.updater.restore(self.state)
        self.assertEqual(self.target.read_bytes(), self.official)

    def test_beta4_upgrade_preserves_first_official_backup(self):
        self.managed()
        self.beta4.apply_update(self.game, self.state, self.beta4_package)
        original = json.loads((self.state / 'deck-beta-backup.json').read_text())['original']
        self.friend.main()
        self.assertEqual(json.loads((self.state / 'deck-beta-backup.json').read_text())['original'], original)
        self.updater.restore(self.state)
        self.assertEqual(self.target.read_bytes(), self.official)

    def test_decline_has_no_writes_or_downloads(self):
        before = self.snapshot()
        with patch.object(self.installer, 'dialog', return_value=False), patch.object(self.installer, 'download') as download:
            self.assertFalse(self.friend.main())
        download.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_corrupt_package_changes_nothing(self):
        before = self.snapshot()
        with patch.object(self.installer, 'download', return_value=self.package + b'bad'):
            with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                self.friend.main()
        self.assertEqual(self.snapshot(), before)

    def test_failed_official_download_no_game_changes(self):
        before = {str(p): p.read_bytes() for p in self.game.rglob('*') if p.is_file()}
        def fail(url, digest):
            if url == self.friend.PACKAGE_URL:
                return self.package
            raise RuntimeError('download checksum mismatch')
        with patch.object(self.installer, 'download', side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                self.friend.main()
        self.assertEqual({str(p): p.read_bytes() for p in self.game.rglob('*') if p.is_file()}, before)
        self.assertEqual(self.config.read_text(), CONFIG)
        self.assertEqual(len(self.dialogs), 1)

    def test_unknown_mod_refused(self):
        self.managed()
        self.target.write_bytes(b'unknown')
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'Unknown multiplayer'):
            self.friend.main()
        self.assertEqual(self.snapshot(), before)

    def test_unmanaged_loader_refused(self):
        (self.game / 'winhttp.dll').write_bytes(b'unmanaged')
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'unmanaged'):
            self.friend.main()
        self.assertEqual(self.snapshot(), before)

    def test_corrupt_original_backup_refused(self):
        self.managed()
        self.beta4.apply_update(self.game, self.state, self.beta4_package)
        original = json.loads((self.state / 'deck-beta-backup.json').read_text())['original']
        Path(original).write_bytes(b'bad')
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'verified'):
            self.friend.main()
        self.assertEqual(self.snapshot(), before)

    def test_running_game_refused(self):
        before = self.snapshot()
        with patch.object(self.installer, 'running', return_value=True):
            with self.assertRaisesRegex(RuntimeError, 'Close Megabonk'):
                self.friend.main()
        self.assertEqual(self.snapshot(), before)

    def test_installation_appearing_during_download_is_not_overwritten(self):
        def download(url, digest):
            data = self.download(url, digest)
            self.managed()
            self.target.write_bytes(b'another installation')
            return data
        with patch.object(self.installer, 'download', side_effect=download):
            with self.assertRaisesRegex(RuntimeError, 'Unknown multiplayer'):
                self.friend.main()
        self.assertEqual(self.target.read_bytes(), b'another installation')

    def test_real_launcher_payload_full_fresh_install(self):
        desktop = (ROOT / 'releases/Install-Megabonk-Deck-Beta5.desktop').read_text()
        line = next(line[5:] for line in desktop.splitlines() if line.startswith('Exec='))
        payload = shlex.split(line)[2]
        # Real new Python process, exact Desktop Exec payload, actual pinned
        # archives. Only network bytes, Steam startup, and root identity adapt.
        driver = '''
import io, os, pathlib, shutil, subprocess, urllib.request
os.geteuid = lambda: 1000
shutil.which = lambda command: '/bin/true'
real_popen = subprocess.Popen
def fake_popen(args, *a, **kw):
    return real_popen(['true'] if args == ['steam'] else args, *a, **kw)
subprocess.Popen = fake_popen
def download(request, **kwargs):
    url = request.full_url
    name = 'package' if 'megabonk-deck-beta5.zip' in url else 'loader' if 'bepinex' in url else 'official'
    return io.BytesIO(pathlib.Path(fixtures[name]).read_bytes())
urllib.request.urlopen = download
'''
        fixtures = {'package': str(ROOT / 'releases/megabonk-deck-beta5.zip'),
                    'loader': os.environ['MEGABONK_LOADER_ZIP'],
                    'official': os.environ['MEGABONK_OFFICIAL_ZIP']}
        code = 'fixtures=' + repr(fixtures) + '\n' + driver + '\n' + payload
        env = dict(os.environ, HOME=str(self.home), DISPLAY='', WAYLAND_DISPLAY='')
        with patch.object(subprocess, 'Popen', REAL_POPEN):
            result = subprocess.run([sys.executable, '-c', code], cwd='/tmp', env=env,
                                    input='y\n', text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.updater.digest(self.target.read_bytes()), self.updater.BETA_DLL_SHA)
        self.assertIn('Installed Deck beta 5!', result.stdout)
        self.assertEqual(result.stdout.count('Continue?'), 1)

    def test_real_launcher_payload_decline_in_unrelated_directory(self):
        desktop = (ROOT / 'releases/Install-Megabonk-Deck-Beta5.desktop').read_text()
        line = next(line[5:] for line in desktop.splitlines() if line.startswith('Exec='))
        args = shlex.split(line)
        self.assertEqual(args[:2], ['python3', '-c'])
        # Execute exactly the embedded payload in another process. Only platform
        # identity is adapted for the root-owned WSL test environment.
        code = "import os; os.geteuid=lambda:1000; " + args[2]
        env = dict(os.environ, HOME=str(self.home), DISPLAY='', WAYLAND_DISPLAY='')
        with patch.object(subprocess, 'Popen', REAL_POPEN):
            result = subprocess.run([sys.executable, '-c', code], cwd='/tmp', env=env,
                                    input='n\n', text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn('Deck beta 5', result.stdout)
        self.assertFalse(self.state.exists())


if __name__ == '__main__':
    unittest.main()
