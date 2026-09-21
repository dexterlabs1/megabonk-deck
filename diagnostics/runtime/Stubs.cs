namespace HarmonyLib
{
    [System.AttributeUsage(System.AttributeTargets.All, AllowMultiple=true)] public class HarmonyPatch : System.Attribute { public HarmonyPatch(object value) {} }
    public class HarmonyPrefix : System.Attribute {}
}
public class MyInputManager
{
    public const string UIHorizontal="h", UIVertical="v", UICancel="cancel", UIAbort="abort", UISubmit="submit";
    public static void GetAxis() {} public static void GetButtonDown() {} public static void GetButtonUp() {} public static void GetButton() {}
}
namespace UnityEngine { public static class Time { public static float unscaledTime=100; } }
namespace MegabonkTogether.Scripts.Modal
{
    public static class DeckMenuControls { public static bool IsEditingText=false, IsModalActive=false; }
    public static class ModalBase { public static float SubmitReadyAt=0; }
}
namespace BepInEx.Logging
{
    public class ManualLogSource { public void LogInfo(object text) {} public void LogWarning(object text) {} public void LogError(object text) {} }
}
namespace MegabonkTogether
{
    public static class MyPluginInfo { public const string PLUGIN_VERSION="5.1.0"; }
    public static class Plugin { public static object Services; public static BepInEx.Logging.ManualLogSource Log=new(); }
}
namespace MegabonkTogether.Services { public static class ChangelogService { public const string CHANGELOG_FILENAME="CHANGELOG.toml"; } }
namespace MegabonkTogether.Configuration
{
    public class Entry<T> { public T Value; }
    public static class ModConfig
    {
        public static Entry<string> PreviousVersion=new(); public static Entry<bool> ShowChangelog=new();
        public static void Save() {}
    }
}
namespace Microsoft.Extensions.DependencyInjection
{
    public static class Extensions { public static T GetService<T>(this object services) => (T)services; }
}
