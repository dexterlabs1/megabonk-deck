using Assets.Scripts.Managers;
using MegabonkTogether;
using MegabonkTogether.Scripts.Modal;
using MegabonkTogether.Scripts.Button;
using UnityEngine.UI;

int checks = 0;
void Check(bool condition, string label)
{
    if (!condition) throw new Exception(label);
    Console.WriteLine("PASS: " + label);
    checks++;
}
var background = new MyButton();
var neighbor = new UnityEngine.UI.Button();
background.button.navigation = new Navigation { mode = Navigation.Mode.Explicit, wrapAround = true, selectOnUp = neighbor };
var backgroundAutomatic = new MyButton();
backgroundAutomatic.button.navigation = new Navigation { mode = Navigation.Mode.Automatic };
var window = new Window();
window.allButtons.Add(background);
window.allButtons.Add(backgroundAutomatic);
window.allButtonsHashed.Add(background.gameObject);
window.allButtonsHashed.Add(backgroundAutomatic.gameObject);
var originalButtons = window.allButtons;
var originalSet = window.allButtonsHashed;
WindowManager.activeWindow = window;
ButtonManager.selectedButton2 = background;
var first = new MyButtonNormal { background = new MaskableGraphic() };
var second = new MyButtonNormal { background = new MaskableGraphic() };
first.gameObject.component = first;
second.gameObject.component = second;
var firstColor = new UnityEngine.Color(0.1f, 0.2f, 0.3f, 1f);
var secondColor = new UnityEngine.Color(0.2f, 0.3f, 0.4f, 1f);
first.background.color = firstColor;
second.background.color = secondColor;
var markerColor = new UnityEngine.Color(0.95f, 0.65f, 0.12f, 1f);
var field = new TMPro.TMP_InputField();
var modal = new ModalBase { DefaultControllerButton = second };
modal.NavigationPanel.children.AddRange(new object[] { first, second, field });
DeckMenuControls.Modals.Add(modal);
var controls = new DeckMenuControls();
controls.Awake();
controls.LateUpdate();
Check(background.button.navigation.mode == Navigation.Mode.None, "explicit background navigation disabled");
Check(backgroundAutomatic.button.navigation.mode == Navigation.Mode.None, "automatic background navigation disabled");
Check(window.allButtons.SequenceEqual(new[] { first, second }), "native window contains only modal buttons");
Check(ButtonManager.selectedButton2 == second, "modal default receives initial focus");
Check(second.background.color.Equals(markerColor) && first.background.color.Equals(firstColor), "selected modal graphic marked independently of hover callbacks");
Check(Plugin.Log.info.Count == 1 && Plugin.Log.info[0].Contains("buttons=2"), "entry diagnostics emitted once with count");
ButtonManager.selectedButton2 = background;
second.background.color = secondColor;
controls.LateUpdate();
Check(ButtonManager.selectedButton2 == second, "escaped focus repaired with unchanged membership");
Check(second.background.color.Equals(markerColor), "stable tick repaints marker after native color reset");
Check(Plugin.Log.info.Count == 1, "stable tick does not repeat entry diagnostics");
window.allButtons = originalButtons;
window.allButtonsHashed = originalSet;
controls.LateUpdate();
Check(window.allButtons.SequenceEqual(new[] { first, second }), "native list replacement repaired on next tick");
Check(window.allButtonsHashed.Count == 2 && window.allButtonsHashed.Contains(first.gameObject), "native button set repaired");
second.state = MyButton.EButtonState.Inactive;
controls.LateUpdate();
Check(window.allButtons.SequenceEqual(new[] { first }), "inactive controls excluded after membership change");
Check(ButtonManager.selectedButton2 == first, "inactive default falls back to available modal control");
Check(first.background.color.Equals(markerColor) && second.background.color.Equals(secondColor), "selection change restores prior graphic and marks new one");
field.isFocused = true;
Check(DeckMenuControls.IsEditingText, "runtime adapter finds focused input");
controls.LateUpdate();
Check(first.background.color.Equals(firstColor) && second.background.color.Equals(secondColor), "text editing clears button gold marker");
MyInputManager.player.cancel = true;
controls.LateUpdate();
Check(!field.isFocused && modal.backCount == 0, "first Back exits text editing without closing modal");
MyInputManager.player.cancel = true;
controls.LateUpdate();
Check(modal.backCount == 1 && !DeckMenuControls.IsModalActive, "second Back closes modal");
Check(ReferenceEquals(window.allButtons, originalButtons), "original window button list restored exactly");
Check(ReferenceEquals(window.allButtonsHashed, originalSet), "original window button lookup restored exactly");
var restored = background.button.navigation;
Check(restored.mode == Navigation.Mode.Explicit && restored.wrapAround && restored.selectOnUp == neighbor,
    "full original navigation struct restored, including explicit neighbor");
Check(backgroundAutomatic.button.navigation.mode == Navigation.Mode.Automatic, "automatic navigation restored");
Check(ButtonManager.selectedButton2 == background, "original menu focus restored");
Check(first.background.color.Equals(firstColor) && second.background.color.Equals(secondColor), "Back restores exact original colors for all modal graphics");
controls.OnDestroy();
Check(background.button.navigation.mode == Navigation.Mode.Explicit, "repeated cleanup preserves restored navigation");
var custom = new CustomButton
{
    background = new MaskableGraphic(),
    hoverColor = new UnityEngine.Color(1, 0, 0, 1),
    defaultColor = new UnityEngine.Color(0, 0, 1, 1)
};
custom.StartHover();
Check(custom.background.color.Equals(custom.hoverColor), "default hover color visible without callback");
custom.StopHover();
Check(custom.background.color.Equals(custom.defaultColor), "default color restored without callback");
int starts = 0, stops = 0, clicks = 0;
var callbackColor = new UnityEngine.Color(0, 1, 0, 1);
custom.OverrideStartHoverAction(() => { starts++; if (custom.background != null) custom.background.color = callbackColor; });
custom.OverrideEndHoverAction(() => { stops++; if (custom.background != null) custom.background.color = callbackColor; });
custom.SetOnClickAction(() => clicks++);
custom.StartHover();
Check(starts == 1 && custom.background.color.Equals(callbackColor), "start callback runs once after default feedback");
custom.StopHover();
Check(stops == 1 && custom.background.color.Equals(callbackColor), "stop callback runs once after default feedback");
custom.background = null;
custom.StartHover();
custom.StopHover();
Check(starts == 2 && stops == 2, "missing graphic remains safe and preserves callbacks");
custom.OnClick();
Check(clicks == 1, "managed click callback unchanged");

var network = new MegabonkTogether.Scripts.NetworkMenuTab();
network.NavigationPanel.children.AddRange(new object[] { first, field });
network.DefaultControllerButton = first;
DeckMenuControls.Modals.Add(network);
WindowManager.activeWindow = window;
ButtonManager.selectedButton2 = background;
controls.LateUpdate();
Check(DeckMenuControls.IsModalActive, "network dialog owns main menu before transition");
var character = new Window { name = "W_Character" };
var characterButton = new MyButton();
character.allButtons.Add(characterButton);
character.allButtonsHashed.Add(characterButton.gameObject);
var characterButtons = character.allButtons;
var characterSet = character.allButtonsHashed;
WindowManager.activeWindow = character;
ButtonManager.selectedButton2 = characterButton;
field.isFocused = true;
Check(!DeckMenuControls.IsModalActive && !DeckMenuControls.IsEditingText, "lingering network dialog cannot intercept character input");
controls.LateUpdate();
Check(ReferenceEquals(character.allButtons, characterButtons) && ReferenceEquals(character.allButtonsHashed, characterSet),
    "character window button collections remain untouched");
Check(ButtonManager.selectedButton2 == characterButton, "character window keeps its native selection");
Check(background.button.navigation.mode == Navigation.Mode.Explicit && ReferenceEquals(window.allButtons, originalButtons),
    "main menu ownership restored when character window opens");
DeckMenuControls.ReleaseModal(network);
field.isFocused = false;
var unrelated = new ModalBase { DefaultControllerButton = first };
unrelated.NavigationPanel.children.Add(first);
DeckMenuControls.Modals.Add(unrelated);
controls.LateUpdate();
Check(DeckMenuControls.IsModalActive && character.allButtons.Contains(first), "other modal types may still own character window");
DeckMenuControls.ReleaseModal(unrelated);
Check(ReferenceEquals(character.allButtons, characterButtons) && ButtonManager.selectedButton2 == characterButton,
    "other modal close restores character collections and selection");
Console.WriteLine($"{checks} passed; production DeckMenuControls with managed test doubles, not Unity runtime.");
