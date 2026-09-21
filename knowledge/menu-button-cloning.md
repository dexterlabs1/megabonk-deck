# GOTCHA: replacing a cloned native button loses component fields

## Symptom

On beta 3, the user can move down to Together with the joystick but cannot move back up. Mouse input still works. Together also appears too large. The same Deck test confirms that hosting, showing the room code, and selecting a character no longer freeze.

## Code findings

The original implementation clones Play's GameObject, destroys its MyButtonNormal, and adds PlayTogetherButton. Adding the component does not copy the destroyed component's fields. In particular, the replacement has no explicit binding to the cloned Unity UI Button and loses scale, overlay, and visual settings. The new row can also retain Unity navigation settings copied from Play's original position.

The clone was created without a parent and later reparented with worldPositionStays=true. On a scaled UI this can produce the wrong local scale. The supplied ButtonTextWrapper has no native MyButton reference and exposes Refresh/OnValidate rather than a per-frame update; do not invent a text-wrapper rebinding requirement.

## Beta 4 correction

- Clone directly under Play's parent with worldPositionStays=false, then explicitly preserve local scale, rotation, anchors, pivot, size, and anchored position.
- Bind PlayTogetherButton to the cloned Unity UI Button and copy settings from the cloned MyButtonNormal before destroying that component.
- Give the new row Automatic Unity navigation and refresh the containing Window's button inventory. Leave the existing menu rows and game input mappings alone.
- Preserve beta 3's removal of unsafe native virtual base hover calls.

Source/compiled checks can verify that initialization and references are present. Native Unity navigation and rendered size still require a Deck test; stripped game references do not execute the real navigation implementation.

## Lobby confirmation is separate

`WindowManagerPatches.Update_Postix` disables character confirmation for a Friendlies host while the player count is below two. The host cannot confirm a solo lobby by design. A UI/navigation fix should not remove that check.
