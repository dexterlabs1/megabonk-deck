# GOTCHA: native virtual base calls can re-enter injected overrides

## Symptom

The user reports a complete freeze, with animation stopped, while hosting and selecting a character in the multiplayer menu. Beta 2 added `base.StartHover()` and `base.StopHover()` to `CustomButton`; the original upstream class omits both calls. CustomButton is also used for Show Room Code on the host character-selection screen.

## Mechanism and evidence

The supplied game reference assembly marks `MyButtonNormal` as unsealed, and its hover methods as virtual and non-final. Il2CppInterop 1.5.0's [method generator](https://github.com/BepInEx/Il2CppInterop/blob/v1.5.0/Il2CppInterop.Generator/Passes/Pass50GenerateMethods.cs#L180-L191) resolves this combination through `il2cpp_object_get_virtual_method`. A managed `base` call therefore need not bypass the injected override: native virtual dispatch can re-enter it recursively. [Upstream issue 109](https://github.com/BepInEx/Il2CppInterop/issues/109) documents the same base-call recursion pattern.

The game references are stripped; their method bodies do not reproduce the native runtime. A successful compilation or a normal C# stub test cannot prove that a native virtual call is safe.

## Targeted correction and validation limits

The beta 3 candidate removes only the two native virtual base calls and changes the displayed beta label. Existing managed hover callbacks remain. The callbacks may not provide all of the game's default visual hover feedback; do not restore that feedback by reintroducing these calls.

Check the compiled CustomButton hover method IL, using the old beta as the negative control. A corrected binary must contain no calls to the base native hover methods. Then test entering and leaving custom buttons, Show Room Code, and character confirmation on a physical Deck as host.

This correction removes a supported recursion mechanism. In a subsequent beta 3 Deck test, the user reported that hosting, showing the room code, and selecting a character no longer froze. This confirms those interactions in that test, not full multiplayer stability. Other menu and networking defects remain documented in the test report.

The same test exposed a separate controller issue: moving down to Together traps joystick focus, although mouse input works. The Together button also appears too large. Do not reintroduce native virtual hover calls to fix controller navigation or visuals.
