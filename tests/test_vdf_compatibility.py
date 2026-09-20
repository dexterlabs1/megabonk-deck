import tempfile
from pathlib import Path
import unittest
import installer as m
from test_installer import CONFIG


class VDFCompatibilityTests(unittest.TestCase):
    def test_bom_crlf_and_trailing_padding_preserved(self):
        text = '\ufeff' + (CONFIG % '').replace('\n', '\r\n') + '\x00\x00'
        result = m.patch_localconfig(text, '123')
        self.assertTrue(result.startswith('\ufeff'))
        self.assertTrue(result.endswith('\x00\x00'))
        self.assertEqual(m.patch_localconfig(result, '123'), result)
        self.assertIn('"999" { "LaunchOptions" "different game" }', result)
        self.assertEqual(result.count('\r\n'), text.count('\r\n'))

    def test_comments_and_conditions_on_unrelated_settings(self):
        text = (CONFIG % '"LaunchOptions" "-windowed"').replace(
            '"Other" "untouched"',
            '/* comment { ignored } */ "Other" "untouched" [$LINUX] // trailing comment\n')
        result = m.patch_localconfig(text, '123')
        self.assertIn('"Other" "untouched" [$LINUX]', result)
        self.assertIn('/* comment { ignored } */', result)
        self.assertIn('-windowed', result)
        self.assertEqual(m.patch_localconfig(result,'123'), result)

    def test_ambiguous_conditional_target_refused(self):
        with self.assertRaises(m.VDFError):
            m.patch_localconfig(CONFIG % '"LaunchOptions" "x" [$LINUX]', '123')

    def test_no_silent_skipping_of_unterminated_quotes(self):
        with self.assertRaisesRegex(m.VDFError, 'localconfig.vdf, line 2'):
            m.parse_vdf('"root" {\n"unterminated', 'localconfig.vdf')

    def test_unrelated_bytes_roundtrip(self):
        data = (CONFIG % '"Unrelated" "\udcff"').encode('utf-8', 'surrogateescape')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'localconfig.vdf'; p.write_bytes(data)
            result = m.patch_localconfig(m.read_vdf(p),'123').encode('utf-8','surrogateescape')
            self.assertIn(b'"Unrelated" "\xff"',result)

    def test_bom_manifests_and_unrelated_broken_game(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);root=home/'.local/share/Steam';apps=root/'steamapps';game=apps/'common/Megabonk'
            game.mkdir(parents=True);(game/'Megabonk.exe').touch()
            (apps/'libraryfolders.vdf').write_text('\ufeff"libraryfolders" { "0" { "path" '+m.quote(str(root))+' } }')
            (apps/'appmanifest_999.acf').write_text('"AppState" { "name" "Another game" BAD {')
            (apps/'appmanifest_123.acf').write_text('\ufeff"AppState" { "appid" "123" "name" "Megabonk" "installdir" "Megabonk" }')
            self.assertEqual(m.discover(home),(root,root,game,'123'))

if __name__ == '__main__': unittest.main()
