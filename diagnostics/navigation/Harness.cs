using MegabonkTogether.Scripts.Button;
using UnityEngine;
using UnityEngine.UI;

bool baseline = args[0] == "beta3";
int passed = 0;
void Check(bool condition, string label) {
    if (!condition) throw new Exception(label);
    Console.WriteLine("PASS: " + label); passed++;
}
foreach (float canvasScale in new[] { 0.5f, 1f, 1.75f }) {
    var parent = new GameObject(); parent.transform.localScale = new Vector3(canvasScale, canvasScale, canvasScale);
    var source = new GameObject(); source.transform.SetParent(parent.transform, false);
    source.transform.localScale = new Vector3(0.8f, 0.8f, 0.8f);
    source.Rect.sizeDelta = new Vector2(300, 64); source.Rect.pivot = new Vector2(.4f,.6f);
    source.Rect.anchorMin = new Vector2(.1f,.2f); source.Rect.anchorMax = new Vector2(.8f,.9f);
    source.Rect.anchoredPosition3D = new Vector3(2,3,4); source.transform.localRotation = new Quaternion(1,2,3,4);
    source.Normal.button = source.Ui; source.Normal.hoverScale = 1.12f; source.Normal.scaleOnHover = source.transform;
    source.Normal.background = new MaskableGraphic(); source.Normal.disabledOverlay = new GameObject(); source.Normal.customSfx = new AudioClip();
    source.Normal.state = MyButton.EButtonState.Active; source.Normal.defaultColor = new Color(1,2,3,4);
    source.Normal.hoverColor = new Color(4,3,2,1); source.Normal.colorInited = true;
    source.Ui.navigation = new Navigation { mode = Navigation.Mode.Explicit }; // Play is first row: no Up target.
    var together = CloneSetup.Run(new MainMenu { btnPlay = source.Normal });
    var clone = together.gameObject;
    if (baseline) {
        Check(together.button == null, "beta3 setup never binds cloned Unity Button (Awake not modeled)");
        Check(clone.Ui.navigation.mode == Navigation.Mode.Explicit, "beta3 retains Play's explicit navigation");
        Check(Math.Abs(clone.transform.localScale.x - 0.8f / canvasScale) < .0001f, "beta3 reparenting compensates Canvas scale");
        continue;
    }
    Check(together.button == clone.Ui && together.button != source.Ui, "beta4 binds cloned Unity Button");
    Check(clone.Ui.navigation.mode == Navigation.Mode.Automatic && clone.Ui.navigation.selectOnUp == null, "beta4 clears stale explicit links for automatic neighbour search");
    Check(clone.transform.parent == parent.transform && clone.transform.localScale == source.transform.localScale, "beta4 retains local size at Canvas scale " + canvasScale);
    Check(clone.transform.localRotation == source.transform.localRotation && clone.Rect.sizeDelta == source.Rect.sizeDelta && clone.Rect.pivot == source.Rect.pivot && clone.Rect.anchorMin == source.Rect.anchorMin && clone.Rect.anchorMax == source.Rect.anchorMax && clone.Rect.anchoredPosition3D == source.Rect.anchoredPosition3D, "beta4 preserves clone rectangle geometry");
    Check(together.scaleOnHover == clone.transform && together.scaleOnHover != source.transform && together.hoverScale == 1.12f, "beta4 hover scale targets clone");
    Check(together.background == clone.Normal.background && together.background != source.Normal.background && together.defaultColor == source.Normal.defaultColor && together.hoverColor == source.Normal.hoverColor && together.colorInited, "beta4 preserves clone graphics and colors");
    Check(together.disabledOverlay == clone.Normal.disabledOverlay && together.disabledOverlay != source.Normal.disabledOverlay && together.state == source.Normal.state && together.customSfx == source.Normal.customSfx, "beta4 preserves disabled state overlay and sound");
    Check(clone.Normal.Destroyed && !source.Normal.Destroyed && clone.Ui.onClick != null && source.Ui.navigation.mode == Navigation.Mode.Explicit, "beta4 removes only old clone component and leaves Play navigation unchanged");
}
Console.WriteLine($"{passed} {args[0]} checks passed. Managed stubs; no native Awake, navigation runtime or rendering executed.");

public class MainMenu { public MyButton btnPlay; }
public class MyButton : Component {
 public enum EButtonState { Active, Disabled }
 public UnityEngine.UI.Button button; public Transform scaleOnHover; public float hoverScale; public EButtonState state;
 public GameObject disabledOverlay; public AudioClip customSfx;
 public virtual void OnClick() {}
}
public class MyButtonNormal : MyButton { public MaskableGraphic background; public Color defaultColor, hoverColor; public bool colorInited; }
namespace MegabonkTogether {
 public class Plugin { public static Plugin Instance = new(); public Scripts.NetworkMenuTab NetworkTab; }
}
namespace MegabonkTogether.Scripts { public class NetworkMenuTab : Component { public void SetMainMenu(MainMenu menu) {} } }
namespace UnityEngine {
 public record struct Vector2(float x, float y);
 public record struct Vector3(float x, float y, float z);
 public record struct Quaternion(float x, float y, float z, float w);
 public record struct Color(float r, float g, float b, float a);
 public class AudioClip {}
 public class Object {
  public bool Destroyed;
  public static void DestroyImmediate(Object o) { o.Destroyed = true; }
  public static GameObject Instantiate(GameObject original) => Clone(original);
  public static GameObject Instantiate(GameObject original, Transform parent, bool worldPositionStays) { var c=Clone(original); c.transform.SetParent(parent, worldPositionStays); return c; }
  static GameObject Clone(GameObject o) {
   var c=new GameObject(); c.transform.localScale=o.transform.localScale; c.transform.localRotation=o.transform.localRotation;
   c.Rect.anchorMin=o.Rect.anchorMin; c.Rect.anchorMax=o.Rect.anchorMax; c.Rect.pivot=o.Rect.pivot; c.Rect.sizeDelta=o.Rect.sizeDelta; c.Rect.anchoredPosition3D=o.Rect.anchoredPosition3D;
   c.Ui.navigation=o.Ui.navigation;
   c.Normal.button=c.Ui; c.Normal.scaleOnHover=c.transform; c.Normal.hoverScale=o.Normal.hoverScale;
   c.Normal.background=new MaskableGraphic(); c.Normal.disabledOverlay=new GameObject(); c.Normal.customSfx=o.Normal.customSfx; c.Normal.state=o.Normal.state;
   c.Normal.defaultColor=o.Normal.defaultColor; c.Normal.hoverColor=o.Normal.hoverColor; c.Normal.colorInited=o.Normal.colorInited;
   return c;
  }
 }
 public class Component : Object {
  public GameObject gameObject;
  public Transform transform => gameObject.transform;
  public T GetComponent<T>() where T:class => gameObject.GetComponent<T>();
 }
 public class Transform : Component {
  public Transform parent; public Vector3 localScale = new(1,1,1); public Quaternion localRotation;
  public void SetParent(Transform p, bool worldPositionStays=true) { if(worldPositionStays) localScale=new(localScale.x/p.localScale.x,localScale.y/p.localScale.y,localScale.z/p.localScale.z); parent=p; }
 }
 public class RectTransform : Transform { public Vector2 anchorMin,anchorMax,pivot,sizeDelta; public Vector3 anchoredPosition3D; }
 public class GameObject : Object {
  public RectTransform Rect; public Transform transform=>Rect; public MyButtonNormal Normal; public UnityEngine.UI.Button Ui;
  public GameObject(string name="") { Rect=new RectTransform{gameObject=this}; Normal=new MyButtonNormal{gameObject=this}; Ui=new UnityEngine.UI.Button{gameObject=this}; }
  public T GetComponent<T>() where T:class => typeof(T)==typeof(MyButtonNormal)?Normal as T:typeof(T)==typeof(RectTransform)?Rect as T:Ui as T;
  public T GetComponentInChildren<T>() where T:class=>GetComponent<T>();
  public T AddComponent<T>() where T:Component,new()=>new T{gameObject=this};
 }
}
namespace UnityEngine.UI {
 public class MaskableGraphic {}
 public struct Navigation { public enum Mode { None, Automatic, Explicit }; public Mode mode; public object selectOnUp; public static Navigation defaultNavigation => new(){mode=Mode.Automatic}; }
 public class Button : Component { public class ButtonClickedEvent{} public ButtonClickedEvent onClick; public Navigation navigation; }
}
