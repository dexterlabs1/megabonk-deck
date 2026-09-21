# Remote Deck workflow

Control an awake Steam Deck on the same LAN from this Windows PC. Commands use
authenticated SSH and return JSON. Gaming Mode screenshots, controller input,
launching and file deployment do not require a remote-desktop window.

## Pair once

The PC has Valve's official Devkit client source installed at
`%LOCALAPPDATA%\megabonk-deck\steamos-devkit`, pinned at
`e091c1761d761c77ee100fada5b272bfd2e591ad`, with its headless dependencies in the
adjacent `venv`. This uses the official pairing library, without opening its GUI.

1. On Deck, enable **Settings > System > Developer Mode**, then open
   **Settings > Developer > Pair new host**. Keep it awake on the PC's home network.
2. On PC, use PowerShell:

```powershell
& "$env:LOCALAPPDATA\megabonk-deck\venv\Scripts\python.exe" remote/pair.py discover
& "$env:LOCALAPPDATA\megabonk-deck\venv\Scripts\python.exe" remote/pair.py register --host DECK_IP
```

3. Approve the PC on the Deck when requested. Registration configures our CLI.
4. Run `python remote/deck.py bootstrap`, then `python remote/deck.py status`.

An existing paired key also works with `deck.cmd configure --host DECK_IP
--identity PATH_TO_KEY --user deck`. Keys are referenced, never embedded or copied
into this repo. Connection settings and SSH known-host fingerprints live under
`~/.config/megabonk-deck`; a changed fingerprint is refused. Initial contact trusts
the discovered/addressed host on the local network.

For another PC: clone Valve's source at the pinned commit into the directory
above, create a Python 3.11+ venv, and install `appdirs paramiko signalslot zeroconf`
there. Our normal CLI needs only Python and OpenSSH. Pairing uses Valve's installed
library. [Official setup](https://partner.steamgames.com/doc/steamdeck/loadgames).

## Commands

Run `deck.cmd --help` or `python remote/deck.py --help` from the repository.

```text
deck status
deck screenshot
deck stop
deck stop --force
deck deploy releases/megabonk-deck-beta5-test.zip
deck launch
deck logs
deck restore
deck push local-file /home/deck/Downloads/remote-file
deck pull /home/deck/Downloads/remote-file local-file
deck exec -- python3 --version
```

The updater adapter currently accepts the checksum-pinned published beta 5 test
bundle. It executes its verified updater without dialog prompts, preserving its
lock, unknown-mod refusal, running-game refusal and original backup checks. A
verified bundle is retained locally on Deck so restore can recheck its code.
Restore requires one remote deploy first. Other builds can be transferred with
`push`; supporting their deployment requires updating the adapter's pinned bundle.

Each command records results in ignored `remote/runs/` folders. Use
`deck --run-dir remote/runs/session-name screenshot` (and the same option on
later commands) to group a session's action log and uniquely named artifacts.
Screenshots are
downloaded as PNG files for direct image inspection; capture refuses stale or
incomplete output. These are actual game frames, unlike the earlier layout
diagrams. Do not claim live validation until an image has actually been captured
and viewed. Logs and transferred files are checksum-verified.

## Input

Input creates virtual devices through `/dev/uinput`, using the existing user
permissions. No system-wide input permissions or root daemon are installed.
If status reports that device unwritable, input remains unavailable pending a
one-time, specifically scoped setup; file operations and screenshots still work.

Save a JSON action in a file and use `deck input --file action.json` to avoid
PowerShell 5.1's embedded-quote handling. The inline JSON argument also works when
the calling shell preserves it. Text input supports ASCII with a US keyboard layout.

```json
{"action":"button","buttons":["A"],"duration_ms":100}
{"action":"axis","axis":"LY","value":1,"duration_ms":100}
{"action":"text","text":"ABCD1234","interval_ms":30}
{"action":"button","buttons":["STEAM","X"],"duration_ms":100}
{"action":"key","keys":["CTRL","A"],"duration_ms":100}
{"action":"mouse","dx":20,"dy":0}
{"action":"click","button":"LEFT","duration_ms":100}
{"action":"stop"}
{"action":"start"}
{"action":"status"}
```

The local input daemon keeps the virtual controller connected between requests
and exits after five idle minutes.
Actions have bounded durations and release controls afterward; errors/disconnects
must not leave keys held. Stop the daemon at the end of testing. A successful
virtual-controller test is not proof of the built-in Deck joystick behavior.

## First live acceptance session

1. Pair/bootstrap; record SteamOS version, display session, mod hash and input access.
2. Capture and view a fresh Gaming Mode screenshot.
3. Launch Megabonk and inspect its menu before sending input. Verify Steam sees
   the virtual gamepad and its player ordering. Do not blindly replay clicks.
4. Move down to Together and back up; capture both states. Open Friendlies, type
   into the code field, exercise Steam+X, and check Paste/Join remain separate.
5. Host, reveal the room code, select a character, and return. Collect logs.
   The solo-host Confirm gate remains intentional; two-player joining needs a
   second account and game instance.
6. Stop, deploy beta 5, relaunch and check its label. Restore and verify the DLL
   hash, then reinstall beta 5. Use test-session backups, never edit saves.
7. Reboot the Deck and verify reconnection without re-pairing. Sleep, power-off,
   lost Wi-Fi and a system-wide freeze can require physical intervention.

## Tests and removal

`python -m unittest discover -s remote/tests -v` runs host tests on Windows.
Linux-only tests also run in WSL; set `MEGABONK_OFFICIAL_ZIP` to the checksum-verified
official Proton 5.1.0 archive for deployment integration tests. Tests use temporary
fixtures; they do not control a real Deck or prove Gaming Mode compatibility.

Delivery verification (2026-09-21): 87 tests passed in WSL; Windows passed 65 with
22 Linux-only skips. This includes executing the actual JSON helper in a child
process to install beta 5 and restore the original DLL under a temporary HOME.
The official pairing library loads and LAN discovery finds the Deck. Pairing has
not yet completed. Native capture, virtual-controller recognition, game
navigation and reconnect after reboot remain unverified.

To remove the workflow, stop input, remove the deployed `remote` helper directory
under `~/.local/share/megabonk-deck` and the artifacts under
`~/.local/state/megabonk-deck/artifacts`, and revoke this PC's devkit key. Preserve
`~/.local/share/megabonk-deck/backups` and `deck-beta-backup.json` for mod recovery.
Remove the PC's local connection configuration only if no longer needed.
