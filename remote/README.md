# Megabonk integration for Steam Deck Control

Reusable Deck control code now lives in the independent sibling project
[`SteamDeckControl`](../../SteamDeckControl/README.md). This directory owns only
Megabonk integration and release-specific deployment. Its old Python entrypoints
are thin compatibility forwarders; edit reusable controls and their tests in the
new project.

## Existing workflow

From the Megabonk repository, existing commands still work:

```text
python remote/deck.py bootstrap
python remote/deck.py status
python remote/deck.py launch
python remote/deck.py screenshot
python remote/deck.py logs
python remote/deck.py stop
python remote/deck.py deploy releases/megabonk-deck-beta7-test.zip
python remote/deck.py restore
```

`deck.cmd` forwards to the same wrapper. It selects the `megabonk` adapter and
supplies this directory's adapter manifest during bootstrap. The sibling
SteamDeckControl checkout must be present. To use the independent CLI directly:

```text
python ../SteamDeckControl/deck.py --adapter megabonk bootstrap --adapter-dir remote
python ../SteamDeckControl/deck.py --adapter megabonk status
```

The existing paired key and private PC configuration remain at their old paths;
no new pairing is required. Old ignored `remote/runs/` artifacts remain here. New
commands default to the independent project's ignored `runs/` directory. Explicit
`--run-dir` still groups artifacts wherever requested.

## Adapter ownership

- `adapter.py` discovers Megabonk, identifies only its game process, launches it
  through the existing Steam configuration, and selects bounded game logs.
- `deployment.py` owns the published bundle checksum, backup and restore behavior.
- `adapter.json` explicitly maps these files and the repository's `installer.py`
  into the deployed `adapters/megabonk` directory.

The generic core imports none of these files without explicit adapter selection.
The updater runs without dialogs after verifying the pinned complete bundle. It
retains installation locking, running-game refusal, unknown-mod refusal, and
original-backup checks. Published mod archives remain immutable.

## Live findings and tests

The paired SteamOS 3.8.16 Deck has provided actual Gaming Mode screenshots,
controller navigation, mouse input, and typed text. SSH reconnected after reboot
without another pairing. The extracted core and adapter were bootstrapped and
read back successfully; a standalone screenshot was captured and inspected.

Launch Megabonk before starting virtual input. After reboot, a controller connected
before launch was ignored until the input daemon was stopped and started at the
main menu. Virtual Steam+X currently opens Steam's menu rather than the keyboard;
direct text input works. Full details belong in the control project's
[SteamOS notes](../../SteamDeckControl/knowledge/steam-os.md).

Run the control suite from `../SteamDeckControl` with
`python -m unittest discover -s tests -v`. Run this integration suite here with
`python -m unittest discover -s remote/tests -v`. Deployment integration tests need
Linux/WSL and `MEGABONK_OFFICIAL_ZIP` pointing to the checksum-verified official
Proton 5.1.0 fixture. Tests use temporary Steam homes, never the live Deck.
