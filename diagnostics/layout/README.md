# Friendlies layout checks

Beta 4 put the code input and Join at panel y=-102.5, Paste at y=-95, and
status at y=-110. Their rectangles overlap. The user's Deck screenshot also
shows the underlying menu through the panel.

Beta 5 uses panel-centered rows for the title, Host, label, input, keyboard
hint, Paste/Join, status, Back and controls. The existing 700x550 panel is opaque.
The input owns a raycast graphic and masked text viewport; its child controller
proxy selects and activates it, with managed hover tint. Manual entry accepts
32 characters, matching existing validation. Root menu, Close, Stop and Friendlies
buttons explicitly bind the cloned native Unity Button before removing the old
component. Network protocol and assembly version remain 5.1.0.

Run against extracted beta 5 source built with the documented stripped refs:

```text
python diagnostics/layout/reproduce.py <source>
dotnet run --project diagnostics/layout -- <source>/src/plugin/bin/Release/net6.0/MegabonkTogether.dll
python diagnostics/layout/preview.py
python diagnostics/layout/package.py <source>
```

`reproduce.py` extracts the production creation, layout, input-proxy and button
helper methods unchanged and compiles them with the actual CustomButton class
against small managed Unity stubs. Beta 4 is read from its immutable source ZIP.
Results: 5 beta 4 negative checks; 41 beta 5 bounds, input and button checks.
The compiled-IL checker passes 13 checks, including the actual activation lambda,
explicit viewport and navigation references, and absence of native hover calls.
The existing hover checker passes 7 checks. Main-menu clone regression passes
24 preserved candidate checks and 9 beta 3 negative checks.

The Proton Release build succeeds with 15 existing warnings and zero errors.
All 299 source members are retained; only DECK-BETA.md, MainMenu.cs and
NetworkMenuTab.cs differ from beta 4. Other source/project bytes are unchanged.
`deck-beta5.patch` reproduces every beta 5 member byte-for-byte from beta 4.
On Windows use `git -c core.autocrlf=false apply` for that byte comparison.

`beta5-layout-diagram.png` renders the rectangles emitted by the production-method
harness. It is a layout diagram, **not a native game render**. Stub tests do not
simulate Unity text metrics, native navigation, Steam's keyboard or multiplayer.
Verify actual manual typing, controller navigation and two-player joining on Deck.
Existing network timeout defects and Netplay Options toggle wiring are outside
this correction. Hashes are recorded in candidate-sha256.json.
