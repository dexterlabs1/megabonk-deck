"""Run beta-2 C# menu regression assertions with deterministic runtime doubles."""
from pathlib import Path
import argparse
import hashlib
import subprocess
import tempfile
import zipfile


def extract_method(source, signature):
    # These specific methods have balanced braces in their strings/comments too.
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, help='Extracted source root containing src/plugin; defaults to the tracked beta-2 source archive.')
    args = parser.parse_args()
    sources = {}
    archive = here.parents[1] / 'mod-source' / 'megabonk-deck-beta2-source.zip'
    for name in ['NetworkMenuTab', 'ChangelogModal', 'DeckMenuControls']:
        relative = f'src/plugin/Scripts/Modal/{name}.cs'
        if args.source_root:
            raw = (args.source_root / relative).read_bytes()
        else:
            with zipfile.ZipFile(archive) as source_zip:
                raw = source_zip.read(relative)
        sources[name] = raw.decode('utf-8-sig')
        print(name, 'SHA256', hashlib.sha256(raw).hexdigest(), flush=True)

    method = lambda name, signature: extract_method(sources[name], signature)
    network = '\n'.join(method('NetworkMenuTab', sig) for sig in [
        'internal override void ControllerBack()',
        'private void OnStopClicked()',
        'private void UpdateModalContents(bool isVisible)',
        'private void UpdateFriendliesUI(bool isVisible)',
        'private void UpdateNetplayOptionsUI(bool isVisible)',
        'private IEnumerator HandleConnectionStatus()',
        'private IEnumerator HandleFriendlies()',
    ])
    changelog = '\n'.join(method('ChangelogModal', sig) for sig in [
        'private void OnCloseClicked()',
        'public static void Show(ICollection<VersionChanges> changes)',
    ])
    restore = method('DeckMenuControls', 'private void RestoreWindow()')
    template = (here / 'Harness.template').read_text()
    program = template.replace('/*NETWORK_METHODS*/', network).replace('/*CHANGELOG_METHODS*/', changelog).replace('/*RESTORE_METHOD*/', restore)
    with tempfile.TemporaryDirectory(prefix='megabonk-menu-regressions-') as folder:
        output = Path(folder)
        (output / 'Program.cs').write_text(program)
        project = output / 'Regressions.csproj'
        project.write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><NoWarn>CS0649;CS0414;CS8632</NoWarn></PropertyGroup></Project>')
        return subprocess.call(['dotnet', 'run', '--project', str(project)])


if __name__ == '__main__':
    raise SystemExit(main())
