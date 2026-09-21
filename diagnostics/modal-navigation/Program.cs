using Mono.Cecil;
using Mono.Cecil.Cil;

if (args.Length < 2 || args.Length > 3)
{
    Console.Error.WriteLine("Usage: modal-navigation <candidate.dll> <beta5.dll> [Deck-UnityEngine.CoreModule.dll]");
    return 2;
}

int passed = 0, failed = 0;
void Check(bool condition, string label)
{
    Console.WriteLine($"{(condition ? "PASS" : "FAIL")}: {label}");
    if (condition) passed++; else failed++;
}

static MethodReference[] Calls(MethodDefinition method) => method.HasBody
    ? method.Body.Instructions.Where(i => i.OpCode == OpCodes.Call || i.OpCode == OpCodes.Callvirt)
        .Select(i => (MethodReference)i.Operand).ToArray()
    : Array.Empty<MethodReference>();

using var candidate = AssemblyDefinition.ReadAssembly(args[0]);
using var baseline = AssemblyDefinition.ReadAssembly(args[1]);
var controls = candidate.MainModule.Types.Single(t => t.FullName == "MegabonkTogether.Scripts.Modal.DeckMenuControls");
var previous = baseline.MainModule.Types.Single(t => t.FullName == controls.FullName);
var calls = controls.Methods.SelectMany(Calls).ToArray();
var oldCalls = previous.Methods.SelectMany(Calls).ToArray();
bool Direct(MethodReference method) => method.DeclaringType.FullName == "UnityEngine.GameObject"
    && method.Name == "GetComponentsInChildren";
bool Adapted(MethodReference method) => method.DeclaringType.FullName == "MegabonkTogether.Helpers.Il2CppFindHelper"
    && method.Name == "RuntimeGetComponentsInChildren";

Check(oldCalls.Count(Direct) == 3, "beta 5 negative control reproduces three incompatible direct calls");
Check(oldCalls.Where(Direct).All(m => m.ReturnType is ArrayType), "beta 5 references managed T[] return ABI");
Check(!calls.Any(Direct), "candidate contains no direct GameObject child-component calls");
Check(calls.Count(Adapted) == 3, "candidate routes all three calls through runtime adapter");
foreach (var (name, count) in new[] { ("get_IsEditingText", 1), ("Tick", 2) })
{
    var method = controls.Methods.Single(m => m.Name == name);
    Check(Calls(method).Count(Adapted) == count, $"{name} uses adapter at every scan");
}
var arguments = calls.Where(Adapted).Cast<GenericInstanceMethod>()
    .Select(m => m.GenericArguments.Single().FullName).OrderBy(s => s).ToArray();
Check(arguments.SequenceEqual(new[] { "MyButton", "TMPro.TMP_InputField", "TMPro.TMP_InputField" }),
    "adapter scans the expected button and input types");
Check(calls.Where(Adapted).All(m => m.Parameters.Count == 2
    && m.Parameters[1].ParameterType.FullName == "System.Boolean"), "adapter keeps includeInactive contract");
Check(candidate.Name.Version == baseline.Name.Version, "assembly/protocol version unchanged");
Check(candidate.MainModule.Types.SelectMany(t => t.Methods).Where(m => m.HasBody)
    .SelectMany(m => m.Body.Instructions).Any(i => i.OpCode == OpCodes.Ldstr
        && i.Operand is string text && text.Contains("Deck beta 6")), "candidate displays Deck beta 6");

var custom = candidate.MainModule.Types.Single(t => t.FullName == "MegabonkTogether.Scripts.Button.CustomButton");
foreach (var (name, color) in new[] { ("StartHover", "get_hoverColor"), ("StopHover", "get_defaultColor") })
{
    var method = custom.Methods.Single(m => m.Name == name);
    var hoverCalls = Calls(method);
    Check(!hoverCalls.Any(m => m.Name is "StartHover" or "StopHover"), $"{name} has no native base or recursive hover call");
    Check(hoverCalls.All(m => (m.DeclaringType.FullName == "MyButtonNormal" && m.Name is "get_background" or "get_hoverColor" or "get_defaultColor")
        || (m.DeclaringType.FullName == "UnityEngine.Object" && m.Name == "op_Inequality")
        || (m.DeclaringType.FullName == "UnityEngine.UI.Graphic" && m.Name == "set_color")
        || (m.DeclaringType.FullName == "System.Action" && m.Name == "Invoke")), $"{name} uses only graphic properties and managed callback");
    Check(hoverCalls.Any(m => m.Name == color) && hoverCalls.Count(m => m.Name == "set_color") == 1,
        $"{name} sets expected default visual color");
    Check(hoverCalls.Count(m => m.DeclaringType.FullName == "System.Action" && m.Name == "Invoke") == 1,
        $"{name} preserves one managed callback");
    Check(Array.FindIndex(hoverCalls, m => m.Name == "set_color") < Array.FindIndex(hoverCalls, m => m.Name == "Invoke"),
        $"{name} callback can override default feedback");
}

if (args.Length == 3)
{
    using var runtime = AssemblyDefinition.ReadAssembly(args[2]);
    var gameObject = runtime.MainModule.Types.Single(t => t.FullName == "UnityEngine.GameObject");
    var runtimeCalls = gameObject.Methods.Where(m => m.Name == "GetComponentsInChildren" && m.HasGenericParameters).ToArray();
    var actual = runtimeCalls.Single(m => m.Parameters.Count == 0);
    Check(actual.ReturnType.FullName == "Il2CppInterop.Runtime.InteropTypes.Arrays.Il2CppArrayBase`1<T>",
        "actual Deck zero-argument return differs from beta 5 managed array ABI");
    Check(runtimeCalls.Any(m => m.Parameters.Count == 1 && m.Parameters[0].ParameterType.FullName == "System.Boolean"
        && m.ReturnType.FullName == actual.ReturnType.FullName), "actual Deck exposes runtime adapter bool overload");
}
var network = candidate.MainModule.Types.Single(t => t.Name == "NetworkMenuTab");
foreach (var prefix in new[] { "<HandleFriendlies>", "<HandleConnectionStatus>" })
{
    var coroutine = network.NestedTypes.Single(t => t.Name.StartsWith(prefix));
    var moveNext = coroutine.Methods.Single(m => m.Name == "MoveNext");
    var instructions = moveNext.Body.Instructions.ToArray();
    int release = Array.FindIndex(instructions, i => i.Operand is MethodReference m
        && m.DeclaringType.Name == "DeckMenuControls" && m.Name == "ReleaseModal");
    int transition = Array.FindIndex(instructions, i => i.Operand is MethodReference m && m.Name == "GoToCharacterSelection");
    Check(release >= 0 && transition > release, $"{prefix} releases modal ownership before character transition");
    Check(instructions.Any(i => i.OpCode == OpCodes.Newobj && i.Operand is MethodReference m
        && m.DeclaringType.FullName == "UnityEngine.WaitForSecondsRealtime"), $"{prefix} cleanup wait does not depend on time scale");
}
Console.WriteLine($"{passed} passed; {failed} failed");
return failed == 0 ? 0 : 1;
