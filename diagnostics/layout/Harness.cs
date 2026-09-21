using UnityEngine;
using UnityEngine.UI;
using TMPro;
using MegabonkTogether.Scripts.Button;
using System.Text.Json;

var setup = new Setup();
setup.Run();
setup.Verify(args[0], args[1]);

partial class Setup {
 GameObject panel, friendliesTitle, codeLabel, codeKeyboardHint, controlHints;
 CustomButton hostButton, joinButton, friendliesBackButton, pasteButton;
 CustomButton randomButton, friendliesButton, netplayOptionsButton, closeButton, stopButton;
 TMP_InputField codeInput;
 TextMeshProUGUI statusText;
 MainMenu mainMenu = new();
 void OnHostClicked() {} void OnJoinClicked() {} void OnFriendliesBackClicked() {}
 void OnRandomClicked() {} void OnFriendliesClicked() {} void OnNetplayOptionsClicked() {}
 void OnCloseClicked() {} void OnStopClicked() {}
 int passed;
 void Check(bool ok, string message) { if (!ok) throw new Exception(message); passed++; Console.WriteLine("PASS: " + message); }
 public void Verify(string beta, string output) {
  var nodes = new Dictionary<string,GameObject> { ["Title"]=friendliesTitle,["Host"]=hostButton.gameObject,
   ["Room code"]=codeLabel,["Input"]=codeInput.gameObject,["Paste"]=pasteButton.gameObject,
   ["Join"]=joinButton.gameObject,["Status"]=statusText.gameObject,["Back"]=friendliesBackButton.gameObject };
  if(beta=="beta5") { nodes["Keyboard hint"]=codeKeyboardHint; nodes["Controls"]=controlHints; }
  var boxes = nodes.ToDictionary(p=>p.Key,p=>Bounds(p.Value));
  var collisions = new List<string>();
  foreach(var a in boxes) foreach(var b in boxes) if(string.CompareOrdinal(a.Key,b.Key)<0 &&
   a.Value[0]<b.Value[2] && a.Value[2]>b.Value[0] && a.Value[1]<b.Value[3] && a.Value[3]>b.Value[1]) collisions.Add(a.Key+" / "+b.Key);
  if(beta=="beta4") {
   Check(collisions.Contains("Input / Paste"), "beta4 negative control: Paste overlaps manual input");
   Check(collisions.Contains("Join / Paste"), "beta4 negative control: Paste overlaps Join");
   Check(collisions.Contains("Input / Status"), "beta4 negative control: status overlaps manual input");
   Check(codeInput.textViewport==null && codeInput.targetGraphic==null,"beta4 negative control: missing explicit input viewport/graphic");
   Check(codeInput.characterLimit==10,"beta4 negative control: input truncates valid 32-character codes");
  } else {
   Check(collisions.Count==0,"beta5 all ten visible rows/controls have non-overlapping bounds");
   foreach(var b in boxes) Check(b.Value[0]>=-350 && b.Value[2]<=350 && b.Value[1]>=-275 && b.Value[3]<=275,"within panel: "+b.Key);
   foreach(var n in nodes) { var r=n.Value.GetComponent<RectTransform>(); Check(r.anchorMin==new Vector2(.5f,.5f) && r.anchorMax==r.anchorMin && r.localScale==Vector3.one,"center anchors and local scale: "+n.Key); }
   Check(codeInput.targetGraphic==codeInput.GetComponent<Image>() && codeInput.targetGraphic.raycastTarget,"input owns clickable background graphic");
   Check(codeInput.textViewport!=null && codeInput.textComponent.transform.parent==codeInput.textViewport,"input text lies within explicit viewport");
   Check(codeInput.textViewport.GetComponent<RectMask2D>()!=null,"viewport clips long input and caret");
   Check(!codeInput.textComponent.raycastTarget && !codeInput.placeholder.raycastTarget,"text does not intercept pointer hits");
   Check(codeInput.characterLimit==32 && codeInput.lineType==TMP_InputField.LineType.SingleLine,"manual input accepts validation's full 32-character limit on one line");
   var proxy=codeInput.gameObject.Children.Single(n=>n.Name=="ControllerInputFocus");
   Check(codeInput.gameObject.Components.OfType<Selectable>().Count()==1,"no second Selectable attached to TMP_InputField");
   var button=proxy.GetComponent<CustomButton>(); button.OnClick();
   Check(codeInput.Selected && codeInput.Activated,"actual production input proxy selects and activates input");
   button.StartHover(); Check(proxy.GetComponent<Image>().color.a>0,"managed focus callback shows field highlight");
   button.StopHover(); Check(proxy.GetComponent<Image>().color.a==0,"managed focus callback clears field highlight");
   foreach(var b in new[]{hostButton,joinButton,pasteButton,friendliesBackButton,randomButton,friendliesButton,netplayOptionsButton,closeButton,stopButton})
    Check(b.button==b.gameObject.GetComponent<UnityEngine.UI.Button>() && b.button.navigation.mode==Navigation.Mode.Automatic,"native navigation reference bound: "+b.gameObject.GetComponent<ButtonTextWrapper>().t_text.text);
   Check(statusText.overflowMode==TextOverflowModes.Ellipsis && statusText.enableAutoSizing,"status text constrained within its row");
   UpdateFriendliesUI(false); Check(!codeInput.gameObject.activeSelf && !codeKeyboardHint.activeSelf && !pasteButton.gameObject.activeSelf,"leaving Friendlies hides its entry controls and hint");
  }
  File.WriteAllText(Path.Combine(output,beta+"-geometry.json"),JsonSerializer.Serialize(new{beta,panel=new[]{700,550},boxes,collisions},new JsonSerializerOptions{WriteIndented=true}));
  Console.WriteLine($"{passed} {beta} checks passed. Managed stubs, not native Unity rendering/input.");
 }
 float[] Bounds(GameObject go) { var r=go.GetComponent<RectTransform>(); float x=(r.anchorMin.x-.5f)*700+r.anchoredPosition.x,y=(r.anchorMin.y-.5f)*550+r.anchoredPosition.y;return new[]{x-r.sizeDelta.x/2,y-r.sizeDelta.y/2,x+r.sizeDelta.x/2,y+r.sizeDelta.y/2}; }
}
class MainMenu { public MyButtonNormal btnPlay;
 public MainMenu() { var go=new GameObject("Play"); go.AddComponent<RectTransform>(); go.AddComponent<UnityEngine.UI.Button>(); go.AddComponent<ButtonTextWrapper>(); btnPlay=go.AddComponent<MyButtonNormal>(); btnPlay.background=go.AddComponent<Image>(); }
}
public class ButtonTextWrapper:Component { public TextMeshProUGUI t_text=new(); }
public class MyButton:Component {
 public enum EButtonState { Active, Disabled } public EButtonState state;
 public UnityEngine.UI.Button button; public Transform scaleOnHover; public float hoverScale;
 public GameObject disabledOverlay; public object customSfx;
 public virtual void OnClick(){} public virtual void StartHover(){throw new Exception("unsafe native base hover");} public virtual void StopHover(){throw new Exception("unsafe native base hover");}
 public void SetInteractable(bool value){state=value?EButtonState.Active:EButtonState.Disabled;}
}
public class MyButtonNormal:MyButton { public Graphic background; public Color defaultColor,hoverColor; public bool colorInited; }
namespace UnityEngine {
 public record struct Vector2(float x,float y) {public static Vector2 zero=>new(0,0);public static Vector2 one=>new(1,1);}
 public record struct Vector3(float x,float y,float z){public static Vector3 one=>new(1,1,1);}
 public record struct Vector4(float x,float y,float z,float w);
 public record struct Quaternion {public static Quaternion identity=>new();}
 public record struct Color(float r,float g,float b,float a){public static Color white=>new(1,1,1,1);}
 public class Object {
  public static void DestroyImmediate(Object o){if(o is Component c)c.gameObject.Components.Remove(c);}
  public static GameObject Instantiate(GameObject original){var go=new GameObject("Clone");go.AddComponent<RectTransform>();go.AddComponent<UnityEngine.UI.Button>();go.AddComponent<MyButtonNormal>();go.AddComponent<ButtonTextWrapper>();return go;}
  public static GameObject Instantiate(GameObject original,Transform parent,bool worldPositionStays){var go=Instantiate(original);go.transform.SetParent(parent,worldPositionStays);return go;}
 }
 public class Component:Object {public GameObject gameObject; public Transform transform=>gameObject.transform;public T GetComponent<T>() where T:class=>gameObject.GetComponent<T>();}
 public class Transform:Component {public Transform parent;public Vector3 localScale=Vector3.one;public Quaternion localRotation;public void SetParent(Transform p,bool stay=false){parent=p;p.gameObject.Children.Add(gameObject);}}
 public class RectTransform:Transform {public Vector2 anchorMin=new(.5f,.5f),anchorMax=new(.5f,.5f),pivot=new(.5f,.5f),sizeDelta,anchoredPosition;}
 public class GameObject:Object {
  public string Name;public List<Component> Components=new();public List<GameObject> Children=new();public bool activeSelf=true;public Transform transform;
  public GameObject(string name){Name=name;transform=new Transform{gameObject=this};}
  public T AddComponent<T>()where T:Component,new(){var c=new T{gameObject=this};Components.Add(c);if(c is RectTransform r){r.parent=transform.parent;transform=r;}return c;}
  public T GetComponent<T>()where T:class=>Components.OfType<T>().FirstOrDefault();
  public T GetComponentInChildren<T>()where T:class=>GetComponent<T>();
  public void SetActive(bool value){activeSelf=value;}
 }
}
namespace UnityEngine.UI {
 public class Graphic:Component {public Color color;public bool raycastTarget=true;}
 public class Image:Graphic {}
 public class RectMask2D:Component {}
 public class Selectable:Component {public Graphic targetGraphic;public Navigation navigation;}
 public struct Navigation {public enum Mode{None,Automatic,Explicit}public Mode mode;public static Navigation defaultNavigation=>new(){mode=Mode.Automatic};}
 public class Button:Selectable {public class ClickEvent{}public ClickEvent onClick;}
}
namespace UnityEngine.Localization.Components {public class LocalizeStringEvent:Component{}}
namespace TMPro {
 public enum TextAlignmentOptions{Center,Left}public enum VerticalAlignmentOptions{Middle}public enum TextOverflowModes{Overflow,Ellipsis}
 public class TextMeshProUGUI:Graphic {public string text;public float fontSize,fontSizeMin,fontSizeMax;public bool enableWordWrapping,enableAutoSizing;public TextAlignmentOptions alignment;public VerticalAlignmentOptions verticalAlignment;public Vector4 margin;public TextOverflowModes overflowMode;}
 public class TMP_InputField:Selectable {public enum LineType{SingleLine,MultiLine}public LineType lineType;public RectTransform textViewport;public TextMeshProUGUI textComponent;public Graphic placeholder;public int characterLimit,caretWidth;public Color caretColor,selectionColor;public bool customCaretColor,enabled,Selected,Activated;public float caretBlinkRate;public void Select(){Selected=true;}public void ActivateInputField(){Activated=true;}}
}
