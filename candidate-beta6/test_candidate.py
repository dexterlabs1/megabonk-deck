"""Linux integration tests with real DLLs. Run after candidate-beta6/build.py.

MEGABONK_OFFICIAL_ZIP=/path/to/Proton-5.1.0.zip python3 -m unittest discover -s candidate-beta6 -v
No installed game is touched; every case uses a temporary directory.
"""
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
sys.path.insert(0, str(ROOT))
import deck_update


def sha(data):
    return hashlib.sha256(data).hexdigest()


class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = zipfile.ZipFile(ROOT / 'releases/megabonk-deck-beta6-test.zip')
        cls.prefix = 'megabonk-deck-beta6-test/'
        cls.u = types.ModuleType('candidate_updater')
        exec(cls.bundle.read(cls.prefix + 'candidate_updater.py'), cls.u.__dict__)
        cls.package = cls.bundle.read(cls.prefix + 'megabonk-deck-beta6.zip')
        with zipfile.ZipFile(os.environ['MEGABONK_OFFICIAL_ZIP']) as archive:
            cls.official = archive.read('MegabonkTogether/MegabonkTogether.dll')
        assert sha(cls.official) == cls.u.ORIGINAL_DLL_SHA
        cls.betas = {}
        for version in (1, 2, 3, 4, 5):
            package = (ROOT / f'releases/megabonk-deck-beta{version}.zip').read_bytes()
            with zipfile.ZipFile(io.BytesIO(package)) as archive:
                cls.betas[version] = (package, archive.read('MegabonkTogether.dll'))
        cls.previous_updaters = {}
        for version in (3, 4, 5):
            with zipfile.ZipFile(ROOT / f'releases/megabonk-deck-beta{version}-test.zip') as previous:
                module = types.ModuleType(f'beta{version}_updater')
                exec(previous.read(f'megabonk-deck-beta{version}-test/candidate_updater.py'), module.__dict__)
                cls.previous_updaters[version] = module

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='megabonk candidate test ')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        steam = self.home / '.local/share/Steam'
        self.game = steam / 'steamapps/common/Megabonk'
        self.target = self.game / 'BepInEx/plugins/MegabonkTogether/MegabonkTogether.dll'
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(self.official)
        (self.game / 'Megabonk.exe').write_bytes(b'test fixture only')
        (steam / 'steamapps/appmanifest_3405340.acf').write_text(
            '"AppState" { "appid" "3405340" "name" "Megabonk" "installdir" "Megabonk" }')
        self.state = self.home / '.local/share/megabonk-deck'
        self.state.mkdir(parents=True)
        self.marker = self.state / 'deck-beta-backup.json'
        for module in (self.u, deck_update, *self.previous_updaters.values()):
            for name, value in [('running', False), ('dialog', True)]:
                mock = patch.object(module, name, return_value=value)
                mock.start()
                self.addCleanup(mock.stop)

    def old_beta(self, version):
        package, dll = self.betas[version]
        if version in self.previous_updaters:
            self.previous_updaters[version].apply_update(self.game, self.state, package)
        else:
            with patch.object(deck_update, 'BETA_DLL_SHA', sha(dll)):
                deck_update.apply_update(self.game, self.state, package)
        return json.loads(self.marker.read_text())['original']

    def test_official_install_reinstall_restore(self):
        self.assertTrue(self.u.apply_update(self.game, self.state, self.package))
        self.assertEqual(sha(self.target.read_bytes()), self.u.BETA_DLL_SHA)
        self.assertFalse(self.u.apply_update(self.game, self.state, self.package))
        self.u.restore(self.state)
        self.assertEqual(self.target.read_bytes(), self.official)
        self.assertFalse(self.marker.exists())

    def test_beta1_upgrade_restore(self):
        self.check_upgrade(1)

    def test_beta2_upgrade_restore(self):
        self.check_upgrade(2)

    def test_beta3_upgrade_restore(self):
        self.check_upgrade(3)

    def test_beta4_upgrade_restore(self):
        self.check_upgrade(4)

    def test_beta5_upgrade_restore(self):
        self.check_upgrade(5)

    def check_upgrade(self, version):
        original = self.old_beta(version)
        self.u.apply_update(self.game, self.state, self.package)
        self.assertEqual(json.loads(self.marker.read_text())['original'], original)
        self.u.restore(self.state)
        self.assertEqual(self.target.read_bytes(), self.official)

    def test_beta1_beta2_beta3_beta4_beta5_beta6_restore(self):
        original = self.old_beta(1)
        deck_update.apply_update(self.game, self.state, self.betas[2][0])
        for version in (3, 4, 5):
            self.previous_updaters[version].apply_update(self.game, self.state, self.betas[version][0])
        self.u.apply_update(self.game, self.state, self.package)
        self.assertEqual(json.loads(self.marker.read_text())['original'], original)
        self.u.restore(self.state)
        self.assertEqual(self.target.read_bytes(), self.official)

    def test_bad_package_refused(self):
        with self.assertRaises(RuntimeError):
            self.u.apply_update(self.game, self.state, self.package + b'changed')
        self.assertEqual(self.target.read_bytes(), self.official)

    def test_missing_backup_refused(self):
        self.old_beta(2)
        self.marker.unlink()
        with self.assertRaises(RuntimeError):
            self.u.apply_update(self.game, self.state, self.package)
        self.assertEqual(self.target.read_bytes(), self.betas[2][1])

    def test_corrupt_backup_refused(self):
        original = self.old_beta(2)
        Path(original).write_bytes(b'broken')
        with self.assertRaises(RuntimeError):
            self.u.apply_update(self.game, self.state, self.package)
        self.assertEqual(self.target.read_bytes(), self.betas[2][1])

    def test_unknown_mod_refused(self):
        self.target.write_bytes(b'unknown mod')
        with self.assertRaises(RuntimeError):
            self.u.apply_update(self.game, self.state, self.package)
        self.assertEqual(self.target.read_bytes(), b'unknown mod')

    def test_running_game_refused(self):
        with patch.object(self.u, 'running', return_value=True), self.assertRaises(RuntimeError):
            self.u.apply_update(self.game, self.state, self.package)
        self.assertEqual(self.target.read_bytes(), self.official)

    def test_marker_failure_rolls_back_dll_and_old_marker(self):
        self.old_beta(4)
        before = self.marker.read_bytes()
        real_write = self.u.Transaction.write

        def fail_marker(tx, path, data):
            real_write(tx, path, data)
            if path == self.marker:
                raise OSError('injected after marker write')

        with patch.object(self.u.Transaction, 'write', fail_marker), self.assertRaises(OSError):
            self.u.apply_update(self.game, self.state, self.package)
        self.assertEqual(self.target.read_bytes(), self.betas[4][1])
        self.assertEqual(self.marker.read_bytes(), before)

    def test_restore_preserves_later_changes(self):
        self.u.apply_update(self.game, self.state, self.package)
        self.target.write_bytes(b'newer mod')
        with self.assertRaises(RuntimeError):
            self.u.restore(self.state)
        self.assertEqual(self.target.read_bytes(), b'newer mod')

    def test_bundle_manifest_and_source_license(self):
        manifest = json.loads(self.bundle.read(self.prefix + 'SHA256SUMS.json'))
        self.assertEqual(set(manifest), {name[len(self.prefix):] for name in self.bundle.namelist()} - {'SHA256SUMS.json'})
        for name, digest in manifest.items():
            self.assertEqual(sha(self.bundle.read(self.prefix + name)), digest)
        self.assertEqual(self.bundle.read(self.prefix + 'megabonk-deck-beta6-source.zip'), (ROOT / 'mod-source/megabonk-deck-beta6-source.zip').read_bytes())
        self.assertEqual(self.package, (ROOT / 'releases/megabonk-deck-beta6.zip').read_bytes())
        self.assertEqual(self.u.PREVIOUS_BETA_SHAS, {sha(dll) for _, dll in self.betas.values()})
        with zipfile.ZipFile(io.BytesIO(self.bundle.read(self.prefix + 'megabonk-deck-beta6-source.zip'))) as source:
            self.assertTrue(any(Path(name).name == 'LICENSE' for name in source.namelist()))

    def test_original_installer_is_unchanged(self):
        included = self.bundle.read(self.prefix + 'Install-Megabonk-Together.desktop')
        self.assertEqual(included, (ROOT / 'Install-Megabonk-Together.desktop').read_bytes())
        tracked = subprocess.run(['git', 'show', 'HEAD:Install-Megabonk-Together.desktop'], cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
        self.assertEqual(included.replace(b'\r\n', b'\n'), tracked.replace(b'\r\n', b'\n'))
        self.assertEqual(self.bundle.getinfo(self.prefix + 'Install-Megabonk-Together.desktop').external_attr >> 16 & 0o777, 0o755)

    def test_actual_launcher_install_restore_from_other_cwd(self):
        self.bundle.extractall(self.home / 'Downloads')
        folder = self.home / 'Downloads/megabonk-deck-beta6-test'
        for uri in (False, True):
            with self.subTest(file_uri=uri):
                original = self.old_beta(4)
                for filename in ('Test-Deck-Beta6.desktop', 'Restore-Official-Multiplayer.desktop'):
                    launcher = folder / filename
                    command = next(line[5:] for line in launcher.read_text().splitlines() if line.startswith('Exec='))
                    args = shlex.split(command)
                    self.assertEqual(args[-1], '%k')
                    args[-1] = launcher.as_uri() if uri else str(launcher)
                    result = subprocess.run(args, cwd='/', env={**os.environ, 'HOME': str(self.home),
                        'DISPLAY': '', 'WAYLAND_DISPLAY': ''}, input='y\n', text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stdout)
                    expected = self.u.BETA_DLL_SHA if filename.startswith('Test') else self.u.ORIGINAL_DLL_SHA
                    self.assertEqual(sha(self.target.read_bytes()), expected)
                    if filename.startswith('Test'):
                        self.assertEqual(json.loads(self.marker.read_text())['original'], original)
                    else:
                        self.assertFalse(self.marker.exists())


if __name__ == '__main__':
    unittest.main()
