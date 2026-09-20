import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import deck_update as u


class DeckUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.game=self.root/'Megabonk';self.state=self.root/'state';self.state.mkdir()
        self.target=self.game/'BepInEx/plugins/MegabonkTogether/MegabonkTogether.dll'
        self.target.parent.mkdir(parents=True);self.target.write_bytes(b'original DLL')
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr('MegabonkTogether.dll',b'beta DLL')
        self.package=b.getvalue()
        self.patches=[patch.object(u,'ORIGINAL_DLL_SHA',hashlib.sha256(b'original DLL').hexdigest()),patch.object(u,'BETA_DLL_SHA',hashlib.sha256(b'beta DLL').hexdigest()),patch.object(u,'running',return_value=False),patch.object(u,'dialog',return_value=True)]
        for p in self.patches:p.start()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def test_install_reinstall_restore_preserves_original(self):
        self.assertTrue(u.apply_update(self.game,self.state,self.package))
        self.assertEqual(self.target.read_bytes(),b'beta DLL')
        self.assertFalse(u.apply_update(self.game,self.state,self.package))
        u.restore(self.state)
        self.assertEqual(self.target.read_bytes(),b'original DLL')
        self.assertFalse((self.state/'deck-beta-backup.json').exists())

    def test_unknown_version_not_overwritten(self):
        self.target.write_bytes(b'other mod')
        with self.assertRaises(RuntimeError):u.apply_update(self.game,self.state,self.package)
        self.assertEqual(self.target.read_bytes(),b'other mod')

    def test_bad_checksum_not_installed(self):
        with patch.object(u,'BETA_DLL_SHA','0'*64):
            with self.assertRaises(RuntimeError):u.apply_update(self.game,self.state,self.package)
        self.assertEqual(self.target.read_bytes(),b'original DLL')

    def test_running_game_not_modified(self):
        with patch.object(u,'running',return_value=True):
            with self.assertRaises(RuntimeError):u.apply_update(self.game,self.state,self.package)
        self.assertEqual(self.target.read_bytes(),b'original DLL')

    def test_restore_keeps_later_mod_changes(self):
        u.apply_update(self.game,self.state,self.package);self.target.write_bytes(b'newer mod')
        with self.assertRaises(RuntimeError):u.restore(self.state)
        self.assertEqual(self.target.read_bytes(),b'newer mod')

    def install_old_beta(self):
        old = b'old beta DLL'
        with patch.object(u, 'BETA_DLL_SHA', hashlib.sha256(old).hexdigest()):
            package = io.BytesIO()
            with zipfile.ZipFile(package, 'w') as z: z.writestr('MegabonkTogether.dll', old)
            u.apply_update(self.game, self.state, package.getvalue())
        return hashlib.sha256(old).hexdigest()

    def test_upgrade_beta1_restores_official_not_beta1(self):
        old_sha = self.install_old_beta()
        original = json.loads((self.state/'deck-beta-backup.json').read_text())['original']
        with patch.object(u, 'PREVIOUS_BETA_SHA', old_sha):
            self.assertTrue(u.apply_update(self.game, self.state, self.package))
            self.assertEqual(json.loads((self.state/'deck-beta-backup.json').read_text())['original'], original)
            u.restore(self.state)
        self.assertEqual(self.target.read_bytes(), b'original DLL')

    def test_old_beta_restore_supported(self):
        old_sha = self.install_old_beta()
        with patch.object(u, 'PREVIOUS_BETA_SHA', old_sha): u.restore(self.state)
        self.assertEqual(self.target.read_bytes(), b'original DLL')

    def test_missing_old_backup_refuses_upgrade(self):
        old_sha = self.install_old_beta()
        (self.state/'deck-beta-backup.json').unlink()
        with patch.object(u, 'PREVIOUS_BETA_SHA', old_sha):
            with self.assertRaises(RuntimeError): u.apply_update(self.game, self.state, self.package)
        self.assertEqual(self.target.read_bytes(), b'old beta DLL')

    def test_corrupt_original_backup_refuses_upgrade(self):
        old_sha = self.install_old_beta()
        info = json.loads((self.state/'deck-beta-backup.json').read_text())
        Path(info['original']).write_bytes(b'corrupt')
        with patch.object(u, 'PREVIOUS_BETA_SHA', old_sha):
            with self.assertRaises(RuntimeError): u.apply_update(self.game, self.state, self.package)
        self.assertEqual(self.target.read_bytes(), b'old beta DLL')

    def test_real_release_archive_matches_hashes(self):
        p=Path(__file__).resolve().parents[1]/'releases/megabonk-deck-beta2.zip'
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),u.PACKAGE_SHA)
        # Use the unmocked pinned digest from source for the built artifact.
        import ast
        tree=ast.parse((p.parents[1]/'deck_update.py').read_text())
        digest=next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BETA_DLL_SHA' for t in n.targets))
        with zipfile.ZipFile(p) as z:
            self.assertEqual(hashlib.sha256(z.read('MegabonkTogether.dll')).hexdigest(),digest)

if __name__=='__main__':unittest.main()
