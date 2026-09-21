"""Execute extracted production Friendlies setup against managed Unity geometry stubs."""
from pathlib import Path
from zipfile import ZipFile
import re
import subprocess
import sys

here = Path(__file__).resolve().parent
repo = here.parents[1]
source = Path(sys.argv[1]).resolve()
generated = here / '.generated'
generated.mkdir(exist_ok=True)
(generated / 'harness.csproj').write_text('''<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>
<OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework>
<ImplicitUsings>enable</ImplicitUsings><EnableDefaultCompileItems>false</EnableDefaultCompileItems>
</PropertyGroup><ItemGroup><Compile Include="../Harness.cs"/><Compile Include="Setup.cs"/>
<Compile Include="CustomButton.cs"/></ItemGroup></Project>''')

def method(s, name):
    start = re.search(r'^        (?:private|protected).*\b'+name+r'\(', s, re.M).start()
    pos = s.index('{', start) + 1
    depth = 1
    while depth:
        depth += (s[pos] == '{') - (s[pos] == '}')
        pos += 1
    return s[start:pos]

for label in ('beta4', 'beta5'):
    def read(name):
        if label == 'beta4':
            with ZipFile(repo / 'mod-source/megabonk-deck-beta4-source.zip') as z:
                return z.read(name).decode()
        return (source / name).read_text(encoding='utf-8')
    network = read('src/plugin/Scripts/Modal/NetworkMenuTab.cs')
    modal = read('src/plugin/Scripts/Modal/ModalBase.cs')
    methods = ['CreateFriendliesUI', 'CreateCodeInputText', 'CreateCodePlaceholderText',
               'CreateUtilityButton', 'MakeInputNavigable', 'UpdateFriendliesUI']
    if label == 'beta5':
        methods += ['CreateFriendliesLabel', 'SetLayout', 'ApplyFriendliesLayout',
                    'CreateMatchButtons', 'CreateCloseButton', 'CreateStopButton']
    body = '\n'.join(method(network, name) for name in methods)
    body += '\n' + method(modal, 'CreateStatusText')
    props = '\n'.join(re.findall(r'        protected virtual (?:Vector2|float) (?:PanelSize|StatusTextSize|StatusTextFontSize) => .*;', modal))
    pastepos = re.search(r'pasteButton = CreateUtilityButton\("Paste Code", (new Vector2\([^)]*\))', network).group(1)
    hints = network[network.index('            var hints = new GameObject("DeckControlHints");'):network.index('\n        }', network.index('            var hints = new GameObject("DeckControlHints");'))]
    setup = '''using UnityEngine; using UnityEngine.UI; using TMPro;
using UnityEngine.Localization.Components; using MegabonkTogether.Scripts.Button;
partial class Setup : UnityEngine.Object {
''' + props + '\n' + body + '''
public void Run() {
 panel = new GameObject("Panel"); panel.AddComponent<RectTransform>().sizeDelta = PanelSize;
 CreateStatusText(); CreateFriendliesUI(); MakeInputNavigable(codeInput);
 pasteButton = CreateUtilityButton("Paste Code", ''' + pastepos + ''', () => {});
''' + hints + '''
 UpdateFriendliesUI(true);
'''+ ('CreateMatchButtons(); CreateCloseButton(); CreateStopButton();\n' if label=='beta5' else '') + '''
}
}'''
    (generated / 'Setup.cs').write_text(setup, encoding='utf-8')
    (generated / 'CustomButton.cs').write_text(read('src/plugin/Scripts/Button/CustomButton.cs'), encoding='utf-8')
    subprocess.run(['dotnet', 'run', '--project', str(generated / 'harness.csproj'), '--', label, str(here)], check=True)
