using Mono.Cecil;
using Mono.Cecil.Cil;

if (args.Length < 1 || args.Length > 2)
{
    Console.Error.WriteLine("Usage: dotnet run --project diagnostics/hover -- <MegabonkTogether.dll> [beta2.dll]");
    return 2;
}

using var assembly = AssemblyDefinition.ReadAssembly(args[0]);
var button = assembly.MainModule.Types.Single(t => t.FullName == "MegabonkTogether.Scripts.Button.CustomButton");
int passed = 0, failed = 0;
void Check(bool condition, string name)
{
    Console.WriteLine($"{(condition ? "PASS" : "FAIL")}: {name}");
    if (condition) passed++; else failed++;
}

foreach (var (methodName, callback) in new[] { ("StartHover", "onStartHover"), ("StopHover", "onEndHover") })
{
    var method = button.Methods.Single(m => m.Name == methodName);
    Check(method.IsVirtual && method.HasBody, $"{methodName} remains an implemented override");
    var calls = method.Body.Instructions
        .Where(i => i.OpCode == OpCodes.Call || i.OpCode == OpCodes.Callvirt)
        .Select(i => (MethodReference)i.Operand).ToArray();
    // Only Action.Invoke belongs in these overrides. A C# base call uses 'call',
    // but its generated IL2CPP wrapper can still perform virtual redispatch.
    Check(calls.All(m => m.DeclaringType.FullName == "System.Action" && m.Name == "Invoke"),
        $"{methodName} has no native/base hover call or other redispatch path");
    Check(calls.Count(m => m.DeclaringType.FullName == "System.Action" && m.Name == "Invoke") == 1 &&
        method.Body.Instructions.Any(i => i.OpCode == OpCodes.Ldfld && ((FieldReference)i.Operand).Name == callback),
        $"{methodName} preserves its managed callback");
}
Check(assembly.Name.Version.ToString() == "5.1.0.0", "assembly version remains 5.1.0.0");
if (args.Length == 2)
{
    using var baseline = AssemblyDefinition.ReadAssembly(args[1]);
    Check(assembly.MainModule.AssemblyReferences.Select(r => r.FullName).OrderBy(n => n)
        .SequenceEqual(baseline.MainModule.AssemblyReferences.Select(r => r.FullName).OrderBy(n => n)),
        "dependency assembly identities match shipped beta 2");
}
Console.WriteLine($"{passed} passed, {failed} failed. Static compiled-IL checks; no Unity runtime was executed.");
return failed == 0 ? 0 : 1;
