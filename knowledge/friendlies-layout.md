# GOTCHA: mixed anchors hide overlapping menu rows

The user's beta 4 Deck screenshot shows Paste Code covering manual room entry and overlapping Join, with status text on the same row. The screenshot also identifies game version 1.0.69. It does not verify whether beta 4's joystick changes worked.

The old room-code field and Join used anchor Y 0.35 with offset -20 inside a 550-unit panel. Their center relative to the panel center was `(0.35 - 0.5) * 550 - 20 = -102.5`. Paste used a center anchor with Y -95; status used anchor Y 0.3 with zero offset, or -110. Their differently written coordinates described overlapping rectangles.

Beta 5 uses a common center anchor and explicit rows for title, Host, room-code label, field, keyboard hint, Paste/Join, status, Back, and navigation hints. The panel is opaque. Status text stays within its reserved bounds and does not intercept pointer input. Back clears Friendlies feedback before returning to the root menu.

Manual input has an explicit graphic, clipped viewport, and 32-character limit matching existing validation. The controller proxy remains on a child because TMP_InputField already inherits Selectable; adding another Selectable to the same object is invalid. Its action selects and activates the input. Hover highlighting uses managed callbacks, with no native virtual base hover call.

Cloned root/Friendlies buttons use a shared utility that preserves native button references and visual settings before removing the cloned original. The separate netplay-options toggles are outside this fix.

Geometry checks and the layout diagram must read the production setup. They prove spacing and wiring under their documented assumptions; they do not render Unity, simulate the Steam keyboard, or prove a successful multiplayer join. Verify typing, keyboard dismissal, and Join on the physical Deck with a host's real code.
