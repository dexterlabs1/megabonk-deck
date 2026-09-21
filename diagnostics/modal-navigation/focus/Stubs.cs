namespace UnityEngine
{
    public class MonoBehaviour { }
    public struct Color
    {
        public float r, g, b, a;
        public Color(float r, float g, float b, float a) { this.r = r; this.g = g; this.b = b; this.a = a; }
    }
    public class GameObject
    {
        public bool activeInHierarchy = true;
        public readonly List<object> children = new();
        public object component;
        public T GetComponent<T>() where T : class => component as T;
    }
    public enum CursorLockMode { None, Locked }
    public static class Cursor
    {
        public static bool visible;
        public static CursorLockMode lockState = CursorLockMode.Locked;
    }
}
namespace UnityEngine.UI
{
    public struct Navigation
    {
        public enum Mode { None, Automatic, Explicit }
        public Mode mode;
        public bool wrapAround;
        public Button selectOnUp;
    }
    public class Button { public Navigation navigation; }
    public class MaskableGraphic { public UnityEngine.Color color; }
}
namespace TMPro
{
    public class TMP_InputField
    {
        public bool isFocused;
        public void DeactivateInputField() { isFocused = false; }
    }
}
namespace Il2CppSystem.Collections.Generic
{
    public class List<T> : System.Collections.Generic.List<T> { }
    public class HashSet<T> : System.Collections.Generic.HashSet<T> { }
}
public class MyButton
{
    public enum EButtonState { Active, Inactive }
    public EButtonState state;
    public UnityEngine.GameObject gameObject = new();
    public UnityEngine.UI.Button button = new();
    private static int nextId;
    private readonly int id = ++nextId;
    public int GetInstanceID() => id;
}
public class Window
{
    public string name = "Menu";
    public Il2CppSystem.Collections.Generic.List<MyButton> allButtons = new();
    public Il2CppSystem.Collections.Generic.HashSet<UnityEngine.GameObject> allButtonsHashed = new();
}
public class MyButtonNormal : MyButton
{
    public UnityEngine.UI.MaskableGraphic background;
    public UnityEngine.Color hoverColor, defaultColor;
    public virtual void StartHover() { throw new Exception("Unsafe native base hover invoked"); }
    public virtual void StopHover() { throw new Exception("Unsafe native base hover invoked"); }
    public virtual void OnClick() { throw new Exception("Unexpected native base click invoked"); }
}
public static class WindowManager { public static Window activeWindow; }
namespace Assets.Scripts.Managers
{
    public static class ButtonManager
    {
        public static MyButton selectedButton2;
        public static void ForceHoverButton(MyButton button) { selectedButton2 = button; }
        public static void SetNull() { selectedButton2 = null; }
    }
}
public class Player
{
    public bool cancel;
    public bool GetButtonDown(string action) { bool result = cancel; cancel = false; return result; }
}
public static class MyInputManager
{
    public static string UICancel = "cancel";
    public static Player player = new();
    public static Player GetPlayer() => player;
}
namespace MegabonkTogether
{
    public static class Plugin { public static Logger Log = new(); }
    public class Logger
    {
        public List<string> info = new();
        public void LogInfo(string text) { info.Add(text); }
        public void LogError(string text) { throw new Exception(text); }
    }
}
namespace MegabonkTogether.Helpers
{
    public static class Il2CppFindHelper
    {
        public static T[] RuntimeGetComponentsInChildren<T>(this UnityEngine.GameObject gameObject, bool includeInactive = false)
            => gameObject.children.OfType<T>().ToArray();
    }
}
namespace MegabonkTogether.Scripts.Modal
{
    public class ModalBase
    {
        public UnityEngine.GameObject NavigationPanel = new();
        public MyButton DefaultControllerButton;
        public int backCount;
        public void ControllerBack() { backCount++; DeckMenuControls.ReleaseModal(this); }
    }
}
namespace MegabonkTogether.Scripts
{
    public class NetworkMenuTab : Modal.ModalBase { }
}
