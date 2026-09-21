# Menu regression reproductions

Requires Python 3 and .NET SDK 8 or newer. From the repository root:

```text
python diagnostics/menu/reproduce.py
python diagnostics/menu/reproduce.py --source-root C:\path\to\extracted-source
```

The default reads the tracked beta-2 source ZIP. The script extracts the named C#
methods verbatim into a temporary test program, prints source SHA-256 hashes, and
executes the methods against small UI/network doubles. It leaves no build outputs
in the repository. Exit code 1 means a regression assertion failed.

On beta 2, all four assertions fail:

- Random matchmaking with no response after 30 seconds throws
  `InvalidOperationException: Nullable object must have a value`.
- Friendlies matchmaking with no response throws the same exception.
- After a failed Friendlies connection, pressing B enables the root menu without
  hiding the Friendlies menu because the completed coroutine reference remains.
- Closing the changelog restores the original main-menu button list with its
  buttons still disabled. Its close handler enables the replacement modal list
  before restoring the originals.

These are code-level reproductions, not a Unity, IL2CPP, Proton, or physical Steam
Deck test. The coroutines advance without real delays. Audio, rendering, networking,
and configuration persistence are doubles. The changelog test models the list
capture/replacement from `DeckMenuControls.Tick`; it executes the actual Show,
OnCloseClicked, and RestoreWindow method bodies. The Friendlies Back fallback
handlers are doubles matching the visibility behavior; the branch under test is
the actual ControllerBack and OnStopClicked code.

These failures do not establish the cause of the reported freeze when selecting a
character. That trigger needs an in-game trace. A relevant unverified path is the
client's confirmation opening the non-cancellable LoadingModal; DeckMenuControls
then supplies an empty button list to the game's native navigation.
