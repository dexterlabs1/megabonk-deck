import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import installer as m

CONFIG = '''"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { "apps" {
"123" { "Other" "untouched" %s }
"999" { "LaunchOptions" "different game" }
} } } } }'''

class InstallerTests(unittest.TestCase):
    def test_launch_options_preserve_args_and_wrapper(self):
        for old in ['', '-windowed', 'gamemoderun %command% -x', 'env FOO=bar %command%']:
            text = CONFIG % ('"LaunchOptions" ' + m.quote(old))
            result = m.patch_localconfig(text, '123')
            node = m.descend(m.parse_vdf(result), ['UserLocalConfigStore','Software','Valve','Steam','apps','123'])
            actual = m.entry(node['children'], 'LaunchOptions')['value']
            self.assertEqual(actual, m.launch_options(old))
            self.assertIn('"Other" "untouched"', result)
            self.assertIn('"LaunchOptions" "different game"', result)
            self.assertEqual(m.patch_localconfig(result,'123'),result)

    def test_insert_option_and_missing_game(self):
        result = m.patch_localconfig(CONFIG % '', '123')
        self.assertEqual(m.patch_localconfig(result,'123'), result)
        self.assertIsNone(m.patch_localconfig(result,'456'))

    def test_conflicting_override(self):
        with self.assertRaises(RuntimeError):
            m.launch_options('WINEDLLOVERRIDES="dinput8=n,b" %command%')

    def test_bad_vdf_rejected(self):
        for text in ['"foo" {', '"foo" }', '}']:
            with self.assertRaises(ValueError): m.parse_vdf(text)

    def test_archive_traversal_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ['../outside','/absolute','a\\..\\outside','C:/outside']:
                b=io.BytesIO()
                with zipfile.ZipFile(b,'w') as z: z.writestr(name,b'bad')
                with self.assertRaises(RuntimeError): m.safe_extract(b.getvalue(),Path(d))
            b=io.BytesIO()
            with zipfile.ZipFile(b,'w') as z:
                i=zipfile.ZipInfo('link');i.external_attr=0o120777<<16;z.writestr(i,'/etc/passwd')
            with self.assertRaises(RuntimeError): m.safe_extract(b.getvalue(),Path(d))

    def test_transaction_rolls_back_replacements_and_additions(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);old=root/'old';old.write_bytes(b'original')
            t=m.Transaction(root/'backup');t.write(old,b'changed');t.write(root/'new',b'new')
            t.rollback()
            self.assertEqual(old.read_bytes(),b'original');self.assertFalse((root/'new').exists())

    def test_symlink_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'real').write_bytes(b'keep');(root/'link').symlink_to(root/'real')
            t=m.Transaction(root/'backup')
            with self.assertRaises(RuntimeError):t.write(root/'link',b'bad')
            self.assertEqual((root/'real').read_bytes(),b'keep')

    def test_sd_card_discovery(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);root=home/'.local/share/Steam';sd=home/'SD Card';apps=sd/'steamapps';game=apps/'common/Megabonk'
            game.mkdir(parents=True);(root/'steamapps').mkdir(parents=True)
            (root/'steamapps/libraryfolders.vdf').write_text('"libraryfolders" { "0" { "path" '+m.quote(str(sd))+' } }')
            (apps/'appmanifest_123.acf').write_text('"AppState" { "appid" "123" "name" "Megabonk" "installdir" "Megabonk" }')
            (game/'Megabonk.exe').touch()
            self.assertEqual(m.discover(home),(root,sd,game,'123'))

    def test_real_packages_full_install_and_rerun(self):
        assets=Path('/tmp/megabonk-assets')
        if not (assets/'mod.zip').exists(): self.skipTest('Downloaded upstream fixtures unavailable')
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);root=home/'.local/share/Steam';game=root/'steamapps/common/Megabonk'
            game.mkdir(parents=True);(game/'Megabonk.exe').touch()
            (root/'steamapps/appmanifest_123.acf').write_text('"AppState" { "appid" "123" "name" "Megabonk" "installdir" "Megabonk" }')
            config=root/'userdata/1/config/localconfig.vdf';config.parent.mkdir(parents=True);config.write_text(CONFIG % '')
            save=root/'steamapps/compatdata/123/pfx/drive_c/users/steamuser/AppData/LocalLow/Ved/Megabonk';save.mkdir(parents=True);(save/'save.dat').write_bytes(b'precious')
            def dl(url,digest):
                data=(assets/('bepinex.zip' if 'bepinex' in url else 'mod.zip')).read_bytes()
                self.assertEqual(m.hashlib.sha256(data).hexdigest(),digest)
                return data
            with patch.object(m.Path,'home',return_value=home),patch.object(m.os,'geteuid',return_value=1000),patch.object(m.shutil,'which',return_value='/bin/true'),patch.object(m,'running',return_value=False),patch.object(m,'dialog',return_value=True),patch.object(m,'download',side_effect=dl),patch.object(m.subprocess,'Popen'),patch.object(m.time,'strftime',side_effect=['first','second']):
                m.main();m.main()
            self.assertTrue((game/'winhttp.dll').exists())
            self.assertTrue((game/'BepInEx/plugins/MegabonkTogether/MegabonkTogether.dll').exists())
            self.assertEqual((save/'save.dat').read_bytes(),b'precious')
            self.assertEqual((home/'.local/share/megabonk-deck/backups/first/saves/0/save.dat').read_bytes(),b'precious')
            self.assertEqual(config.read_text().count('winhttp=n,b'),1)
            backup=home/'.local/share/megabonk-deck/backups/first'
            self.assertTrue(json.loads((backup/'changes.json').read_text()))

if __name__=='__main__': unittest.main()
