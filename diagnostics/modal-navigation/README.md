# Modal controller array compatibility

Live beta 5 testing on the Deck found background menu buttons selected while
Together was open. Logs repeatedly reported `MissingMethodException` for
`!!0[] UnityEngine.GameObject.GetComponentsInChildren()` from `IsEditingText`.
The compiled Unity reference returns managed `T[]`; the generated Deck interop
returns `Il2CppArrayBase<T>`. Matching names and parameters do not make these
binary signatures interchangeable.

Three direct calls in `DeckMenuControls` bypassed the existing runtime helper.
The modal tick catches its exception and restores the underlying window buttons;
input prefixes calling `IsEditingText` repeatedly throw. Beta 6 routes all three
calls through `Il2CppFindHelper.RuntimeGetComponentsInChildren`, which reflects
the runtime bool overload and converts its IL2CPP array. A subsequent live test
confirmed that clearing the exception alone still allowed background selection.
The existing focus clamp ran only when modal button membership changed. Beta 6
now disables background Unity navigation while retaining the complete original
navigation structs, reapplies modal window lists every tick, and repairs escaped
focus even when membership is unchanged. Close/Back restores the saved lists,
navigation and focus. One entry log records the modal, window and button count.
Live testing then confirmed directional selection but no visible hover. Custom
buttons now set their background graphic's hover/default color directly before
optional callbacks. No native virtual base hover method is called. The historic
beta 3-5 hover checker deliberately permits only callbacks; use this beta 6 IL
checker for the new property-access implementation.
Because native selection still did not reliably dispatch visible hover feedback
on Deck, the controller also paints the selected modal graphic gold each
LateUpdate. It captures original graphic colors before initial focus, restores
the previous selection on each tick, and restores all originals on close.
Entry diagnostics include the number of captured graphics and selected ID.
Another live test found the success coroutine leaving this entry modal registered
after opening character selection. Its controls were hidden, and the delayed
close used scaled time. Both connection success paths now release ownership
before changing windows and use a real-time cleanup delay. `TopModal` also
excludes `NetworkMenuTab` outside the main menu, without restricting other modal
types. Text editing clears the button marker until editing ends.
Protocol and assembly version remain 5.1.0.

```text
dotnet run --project diagnostics/modal-navigation -- <beta6.dll> <beta5.dll> [Deck-UnityEngine.CoreModule.dll]
dotnet run --project diagnostics/modal-navigation/focus -p:ProductionSource=<absolute-path-to-DeckMenuControls.cs> -p:ProductionButton=<absolute-path-to-CustomButton.cs>
python diagnostics/modal-navigation/package.py <extracted-built-source>
```

The checker reproduces beta 5's incompatible references as negative controls,
checks all corrected call sites in compiled IL, and can inspect the actual Deck
interop signature. Do not ship or commit game/interop assemblies. The optional
runtime reference inspected during diagnosis has SHA-256
`af00f610e23e10b5271f179f124f1c49adce950edf15f6e0b3fb030a20ae5545`.

The focus harness compiles the complete production controller against managed
test doubles. Its 38 checks cover stable-membership escape, native list
replacement, inactive controls, text-edit Back, modal Back, full navigation
struct restoration, exact original list restoration, repeated cleanup, visible
hover/default colors, null graphics, callback ordering and unchanged clicks.
They also check explicit marker repaint after a native color reset, selection
changes, and exact original graphic-color restoration on Back.
Character transition checks preserve the native character collections/selection,
stop stale network-modal input suppression, and retain other modal types' ability
to own the character window. Compiled IL verifies release-before-transition and
real-time cleanup in both success coroutines (26 checks with the runtime reference).
It does not simulate Unity's native navigation implementation.

Packaging retains all 299 source members and checks that unchanged C#/project
files match beta 5. It applies the incremental patch to a temporary extraction
and verifies every member byte-for-byte before writing the source ZIP.

These checks establish the binary correction, not native UI behavior. On Deck,
verify that Together holds controller focus, Friendlies input accepts typing,
Back restores the prior menu, and logs contain no new missing-method exceptions.
Then test hosting/joining with a second player.
