# Isolated runtime defect reproductions

Requires Python 3.9+ and .NET SDK 8. Run from this directory:

```powershell
python prepare.py
dotnet run --project runtime.csproj
```

The script extracts the shipped beta 2 source archive to ignored `.source/`.
To use an existing extraction, run `python prepare.py --source-root PATH`, then
`dotnet run --project runtime.csproj -p:SourceRoot=PATH` with that absolute path.

The executable checks two existing defects. A successful run means they were
reproduced, not fixed:

- Links the actual updater and input patches with `PROTON` defined. Seeds the
  flag that a newer upstream release would set, then verifies all three button
  APIs suppress Jump, Pause, Submit, and Cancel even without an active modal.
  This condition is hypothetical while upstream and beta both report 5.1.0.
- Runs the exact extracted WebSocket reset method against a real localhost
  WebSocket peer that does not acknowledge closing. The synchronous caller
  remains blocked after 1.5 seconds; a watchdog aborts the socket so the test
  exits. This represents an open socket with no outstanding receive, not every
  possible disconnect state.

A third check uses the actual LiteNetLib 1.3.5 dependency over local UDP sockets:
the first peer ID is zero, a concurrent second peer gets one, and a new manager
starts at zero again. This rules out simple lobby reconnect as evidence for a
suspected `gamePeers[0]` lookup failure. NuGet may be contacted to restore this
dependency if it is not cached.

Unity, Harmony attributes, configuration, dependency injection and logging are
minimal stubs. The reset extraction's original file hash and line range are
recorded in `.generated/source-manifest.json`. No Steam, game, remote server or
GitHub release request is used. These tests do not reproduce the user's physical
Steam Deck or character-selection freeze.
