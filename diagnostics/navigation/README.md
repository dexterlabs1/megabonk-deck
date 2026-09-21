# Main-menu clone diagnostics

Beta 4 changes only the main-menu clone setup and PlayTogetherButton initialization
(relative to beta 3); protocol/assembly version remains 5.1.0.

The supplied stripped reference assembly exposes MyButton.button, scaleOnHover,
hoverScale, state, disabledOverlay and customSfx; MyButtonNormal also has background
and color fields. Replacing the clone's native component did not explicitly preserve
these fields. Its Unity Button also inherited Play's navigation. The new setup binds
that cloned Button, copies the cloned native fields before destroying the template,
and assigns default automatic navigation to Together only.

The clone is now instantiated under Play's parent with worldPositionStays=false.
Its local scale/rotation and rectangle geometry match Play. Previously an unparented
clone was reparented with worldPositionStays=true, which compensates parent scale.
ButtonTextWrapper contains rect/text and padding properties, with Refresh/OnValidate
methods; it has no MyButton reference or Update/LateUpdate method in these refs.

## Run

Use an extracted beta 4 source tree with the documented game/BepInEx build references:

```powershell
$env:CI='true'
$env:PROTON_BUILD='true'
dotnet build <source>/src/plugin/MegabonkTogether.Plugin.csproj -c Release
python diagnostics/navigation/reproduce.py <source>
dotnet run --project diagnostics/navigation -- <source>/src/plugin/bin/Release/net6.0/MegabonkTogether.dll
dotnet run --project diagnostics/hover -- <source>/src/plugin/bin/Release/net6.0/MegabonkTogether.dll
```

`reproduce.py` extracts the exact production clone setup and compiles the full
PlayTogetherButton source against the managed stubs in Harness.cs. It exercises
Canvas scales 0.5, 1 and 1.75. Beta 3 is the negative control from its archived source.
Native Awake is deliberately not modeled: a null button in this fixture shows the
missing explicit initialization, not proof that native Awake leaves it null in game.
Automatic navigation is checked as configuration; actual directional movement is
not simulated or claimed as verified.

The compiled-IL checker verifies parent/local geometry setup, field assignment,
initialization-before-destruction order, native window refresh, beta label and
assembly version. `--inspect <Assembly-CSharp.dll> MyButton MyButtonNormal
ButtonTextWrapper Window` prints the available reference metadata.

## September 21 results

- PROTON Release build: passed, 15 existing compiler warnings, 0 errors.
- Managed clone checks: 24 beta 4 checks and 9 beta 3 negative-control checks passed.
- Compiled navigation IL: 10 checks passed.
- Compiled hover IL: 7 checks passed; no recursive native/base hover calls added.
- Packaging: 299 source members retained, unrelated .cs/.csproj bytes unchanged.

No native Unity/IL2CPP runtime, physical joystick, rendered UI or multiplayer game
was executed. The user must still verify moving down to Together and back up,
its apparent size, opening/closing Together and returning from a hosted lobby.
The exact controller trap remains a hypothesis until that Deck check.

`package.py <source>` reproduces the binary/source ZIPs and incremental beta3-to-beta4
patch, rejecting unrelated source changes. Final checksums are in candidate-sha256.json.
