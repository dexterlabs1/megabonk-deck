"""Prepare an isolated harness from the shipped source, without editing it."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--source-root", type=Path)
args = parser.parse_args()
root = args.source_root.resolve() if args.source_root else HERE / ".source"
if not args.source_root:
    archive = HERE.parent.parent / "mod-source" / "megabonk-deck-beta2-source.zip"
    with zipfile.ZipFile(archive) as source_zip:
        for entry in source_zip.infolist():
            target = (root / entry.filename).resolve()
            if not target.is_relative_to(root.resolve()):
                raise ValueError("Archive member escapes source directory")
        source_zip.extractall(root)

relative = "src/plugin/Services/WebsocketClientService.cs"
path = root / relative
source = path.read_text(encoding="utf-8-sig")
start = source.index("        public async Task Reset()")
end = source.index("        public async Task SendRunStatistics", start)
method = source[start:end]
prefix = """using System.Net.WebSockets;
using MegabonkTogether;
public class ExtractedWebsocketReset
{
    private ClientWebSocket ws;
    private CancellationTokenSource cts = new();
    private bool isMessageLoopRunning;
    private uint connectionId, currentRdvServerPort;
    private string currentServerUrl;
    public ExtractedWebsocketReset(ClientWebSocket socket) { ws=socket; }
"""
generated = HERE / ".generated"
generated.mkdir(exist_ok=True)
(generated / "ExtractedReset.cs").write_text(prefix + method + "\n}\n", encoding="utf-8")
manifest = {
    "source_root": str(root),
    "source_path": relative,
    "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "first_line": source[:start].count("\n") + 1,
    "last_line": source[:end].count("\n"),
    "extraction": "Exact Reset method; surrounding fields and logger are harness stubs.",
}
(generated / "source-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps(manifest, indent=2))
