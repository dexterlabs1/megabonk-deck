using Mono.Cecil;
using Mono.Cecil.Cil;

if (args[0] == "--inspect") {
 using var refs = AssemblyDefinition.ReadAssembly(args[1]);
 foreach (var type in refs.MainModule.Types.Where(t => args.Skip(2).Contains(t.Name))) {
  Console.WriteLine("TYPE " + type.FullName + " : " + type.BaseType);
  foreach(var property in type.Properties) Console.WriteLine(" PROP " + property.FullName);
  foreach(var method in type.Methods.Where(m=>!m.IsGetter&&!m.IsSetter&&!m.IsConstructor)) Console.WriteLine(" METHOD " + method.FullName + " virtual=" + method.IsVirtual);
 }
 return 0;
}
using var assembly = AssemblyDefinition.ReadAssembly(args[0]);
var main = assembly.MainModule.Types.Single(t=>t.Name=="MainMenuPatches").Methods.Single(m=>m.Name=="Start_Postfix");
var together = assembly.MainModule.Types.Single(t=>t.Name=="PlayTogetherButton");
var init = together.Methods.Single(m=>m.Name=="InitializeFrom");
int passed=0;
void Check(bool condition,string label) { if(!condition) throw new Exception(label); Console.WriteLine("PASS: "+label); passed++; }
IEnumerable<Instruction> Calls(MethodDefinition m) => m.Body.Instructions.Where(i=>i.OpCode==OpCodes.Call || i.OpCode==OpCodes.Callvirt);
bool CallsName(MethodDefinition m,string name)=>Calls(m).Any(i=>((MethodReference)i.Operand).Name==name);
var instantiate = Calls(main).Single(i=>((MethodReference)i.Operand).Name=="Instantiate");
Check(((MethodReference)instantiate.Operand).Parameters.Count==3 && instantiate.Previous.OpCode==OpCodes.Ldc_I4_0,"clone created in parent with worldPositionStays=false");
Check(CallsName(main,"set_localScale") && CallsName(main,"set_sizeDelta") && CallsName(main,"set_anchoredPosition3D"),"explicit local scale and rectangle geometry assignment compiled");
var instructions=main.Body.Instructions;
var initCall=Calls(main).Single(i=>((MethodReference)i.Operand).Name=="InitializeFrom");
var destroyCall=Calls(main).Single(i=>((MethodReference)i.Operand).Name=="DestroyImmediate");
Check(instructions.IndexOf(initCall)<instructions.IndexOf(destroyCall),"clone initialization occurs before native template destruction");
Check(CallsName(init,"set_button"),"native Unity Button reference explicitly initialized");
Check(new[]{"scaleOnHover","hoverScale","state","disabledOverlay","customSfx","background","defaultColor","hoverColor","colorInited"}.All(n=>CallsName(init,"set_"+n)),"native serialized hover visual and state fields preserved");
Check(CallsName(init,"get_defaultNavigation") && CallsName(init,"set_navigation"),"Together receives fresh automatic navigation");
Check(CallsName(main,"FindAllButtonsInWindow"),"native window button refresh retained");
Check(!together.Methods.Any(m=>m.Name=="StartHover"||m.Name=="StopHover"),"Together adds no native virtual hover override");
Check(main.Body.Instructions.Any(i=>i.OpCode==OpCodes.Ldstr && ((string)i.Operand).Contains("Deck beta 4")),"visible beta4 label compiled");
Check(assembly.Name.Version.ToString()=="5.1.0.0","protocol-compatible assembly version unchanged");
Console.WriteLine($"{passed} compiled-IL checks passed. Native runtime not executed.");
return 0;
