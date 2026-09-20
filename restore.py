#!/usr/bin/env python3
"""Restore an installer transaction; refuses files changed since installation."""
import json
from pathlib import Path
import sys
from installer import atomic, dialog, hashlib, running


def main():
    if len(sys.argv) != 2:
        raise RuntimeError('Usage: python3 restore.py /path/to/backup')
    if running('steam') or running('Megabonk.exe'):
        raise RuntimeError('Exit Steam and Megabonk before restoring.')
    backup = Path(sys.argv[1]).resolve()
    records = json.loads((backup / 'changes.json').read_text())
    for r in records:
        p = Path(r['path'])
        if p.is_symlink() or any(x.is_symlink() for x in p.parents):
            raise RuntimeError('Symlink changed: ' + str(p))
        if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() != r['installed_sha256']:
            raise RuntimeError('File changed since installation; automatic restore would overwrite newer changes: ' + str(p) + '. Original copies are in the backup; see changes.json for the mapping.')
    if not dialog('Restore the files and Steam settings from this backup? Saves will remain unchanged.\n' + str(backup), True):
        return
    for r in reversed(records):
        p = Path(r['path'])
        if r['backup'] is not None:
            atomic(p, (backup / r['backup']).read_bytes())
        elif p.is_file():
            p.unlink()
    dialog('Original files restored. Generated BepInEx cache folders can remain; the loader has been removed. Saves were not changed.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        dialog(str(exc))
        sys.exit(1)
