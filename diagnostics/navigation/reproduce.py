"""Run actual beta3/beta4 clone setup source against minimal managed Unity stubs."""
from pathlib import Path
from zipfile import ZipFile
import subprocess
import sys
here = Path(__file__).resolve().parent
repo = here.parents[1]
source = Path(sys.argv[1]).resolve()
generated = here / '.generated'
generated.mkdir(exist_ok=True)
(generated / 'harness.csproj').write_bytes((here / 'Harness.csproj.template').read_bytes())
for label in ('beta3', 'beta4'):
    if label == 'beta3':
        with ZipFile(repo / 'mod-source/megabonk-deck-beta3-source.zip') as z:
            main = z.read('src/plugin/Patches/MainMenu.cs').decode()
            button = z.read('src/plugin/Scripts/Button/PlayTogetherButton.cs')
    else:
        main = (source / 'src/plugin/Patches/MainMenu.cs').read_text()
        button = (source / 'src/plugin/Scripts/Button/PlayTogetherButton.cs').read_bytes()
    # Exact production clone setup. Version label is outside this bounded block.
    block = main[main.index('            var playBtn = __instance.btnPlay;'):main.index('            var textWrapper = go.GetComponent<ButtonTextWrapper>();')]
    # beta3 reparented after building its label. Execute that exact statement too.
    if label == 'beta3':
        statement = '            go.transform.SetParent(playBtn.transform.parent);'
        assert statement in main
        block += statement + '\n'
    (generated / 'Clone.cs').write_text('using MegabonkTogether.Scripts.Button;\nstatic class CloneSetup { internal static PlayTogetherButton Run(MainMenu __instance) {\n' + block + '\nreturn customButton; } }')
    (generated / 'PlayTogetherButton.cs').write_bytes(button)
    subprocess.run(['dotnet', 'run', '--project', str(generated / 'harness.csproj'), '--', label], check=True)
