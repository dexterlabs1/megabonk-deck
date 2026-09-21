"""Package beta 6 source and prove its incremental patch reproduces every byte."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

repo = Path(__file__).resolve().parents[2]
source = Path(sys.argv[1]).resolve()
changed = ("DECK-BETA.md", "src/plugin/Patches/MainMenu.cs",
           "src/plugin/Scripts/Modal/DeckMenuControls.cs", "src/plugin/Scripts/Button/CustomButton.cs",
           "src/plugin/Scripts/Modal/NetworkMenuTab.cs")
baseline_path = repo / "mod-source/megabonk-deck-beta5-source.zip"
with ZipFile(baseline_path) as baseline:
    files = {name: baseline.read(name) for name in baseline.namelist()}
for name, data in files.items():
    if name.endswith((".cs", ".csproj")) and name not in changed:
        assert (source / name).read_bytes() == data, name

patch = ["Deck beta 5 -> Deck beta 6 candidate (incremental, not upstream-to-beta).\n",
         "Apply with git -c core.autocrlf=false apply -p1 from the extracted beta 5 source root.\n\n"]
for name in changed:
    data = (source / name).read_bytes()
    patch.extend(difflib.unified_diff(files[name].decode().splitlines(keepends=True),
                                    data.decode().splitlines(keepends=True),
                                    fromfile="a/" + name, tofile="b/" + name))
    files[name] = data
patch_path = repo / "mod-source/deck-beta6.patch"
patch_path.write_text("".join(patch), encoding="utf-8", newline="\n")
with tempfile.TemporaryDirectory(prefix="megabonk-beta6-patch-") as temporary:
    with ZipFile(baseline_path) as baseline:
        baseline.extractall(temporary)
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "-p1", str(patch_path)],
                   cwd=temporary, check=True)
    for name, data in files.items():
        assert (Path(temporary) / name).read_bytes() == data, name

source_zip = repo / "mod-source/megabonk-deck-beta6-source.zip"
with ZipFile(source_zip, "w", compression=ZIP_DEFLATED, compresslevel=9) as out:
    for name, data in sorted(files.items()):
        info = ZipInfo(name, (2026, 9, 21, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        out.writestr(info, data, compress_type=ZIP_DEFLATED, compresslevel=9)
dll = source / "src/plugin/bin/Release/net6.0/MegabonkTogether.dll"
hashes = {str(p.relative_to(repo)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in (source_zip, patch_path)}
hashes["MegabonkTogether.dll"] = hashlib.sha256(dll.read_bytes()).hexdigest()
(repo / "diagnostics/modal-navigation/candidate-sha256.json").write_text(json.dumps(hashes, indent=2) + "\n")
print(json.dumps(hashes, indent=2))
print(f"Verified {len(files)} source members; only {len(changed)} changed; patch reproduces all bytes.")
