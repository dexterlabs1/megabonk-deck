"""Package the built beta 5 candidate, preserving beta 4 source membership."""
import difflib
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

repo = Path(__file__).resolve().parents[2]
source = Path(sys.argv[1]).resolve()
changed = (
    "DECK-BETA.md",
    "src/plugin/Patches/MainMenu.cs",
    "src/plugin/Scripts/Modal/NetworkMenuTab.cs",
)
with ZipFile(repo / "mod-source/megabonk-deck-beta4-source.zip") as baseline:
    files = {name: baseline.read(name) for name in baseline.namelist()}

# No unexpected source edits may hide behind the archive's preserved membership.
for name, data in files.items():
    if name.endswith((".cs", ".csproj")) and name not in changed:
        assert (source / name).read_bytes() == data, name

patch = ["Deck beta 4 -> Deck beta 5 candidate (incremental, not upstream-to-beta).\n",
         "Apply with git apply -p1 from the extracted beta 4 source root.\n\n"]
for name in changed:
    data = (source / name).read_bytes()
    patch.extend(difflib.unified_diff(files[name].decode().splitlines(keepends=True),
                                    data.decode().splitlines(keepends=True),
                                    fromfile="a/" + name, tofile="b/" + name))
    files[name] = data
(repo / "mod-source/deck-beta5.patch").write_text("".join(patch), encoding="utf-8", newline="\n")

def archive(path, members):
    with ZipFile(path, "w", compression=ZIP_DEFLATED, compresslevel=9) as out:
        for name, data in sorted(members.items()):
            info = ZipInfo(name, (2026, 9, 21, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            out.writestr(info, data, compress_type=ZIP_DEFLATED, compresslevel=9)

source_zip = repo / "mod-source/megabonk-deck-beta5-source.zip"
binary_zip = repo / "releases/megabonk-deck-beta5.zip"
archive(source_zip, files)
dll = (source / "src/plugin/bin/Release/net6.0/MegabonkTogether.dll").read_bytes()
archive(binary_zip, {"MegabonkTogether.dll": dll, "LICENSE": files["LICENSE"],
                     "DECK-BETA.md": files["DECK-BETA.md"]})
hashes = {str(p.relative_to(repo)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in [binary_zip, source_zip, repo / "mod-source/deck-beta5.patch"]}
hashes["MegabonkTogether.dll"] = hashlib.sha256(dll).hexdigest()
(repo / "diagnostics/layout/candidate-sha256.json").write_text(json.dumps(hashes, indent=2) + "\n")
print(json.dumps(hashes, indent=2))
print(f"Source archive: {len(files)} members; binary archive: DLL, LICENSE, DECK-BETA.md")
