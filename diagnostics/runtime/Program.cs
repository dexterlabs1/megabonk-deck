using System.Net;
using System.Net.Sockets;
using System.Net.WebSockets;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using MegabonkTogether;
using MegabonkTogether.Common;
using MegabonkTogether.Patches;

var updater = new AutoUpdaterService(new());
updater.Initialize();
Plugin.Services = updater;
if (!updater.IsCustomBuild()) throw new Exception("Harness must compile as PROTON");
bool inputResult = true;
if (!MyInputManagerPatches.GetButtonDown_Prefix("Jump", ref inputResult)) throw new Exception("Baseline input unexpectedly blocked");
// Seed exactly the state CheckAndUpdate sets on finding a newer Proton release.
typeof(AutoUpdaterService).GetField("isUpdateAvailable", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(updater, true);
foreach (string action in new[]{"Jump", "Pause", MyInputManager.UISubmit, MyInputManager.UICancel})
{
    inputResult=true;
    bool down = MyInputManagerPatches.GetButtonDown_Prefix(action, ref inputResult);
    if (down || inputResult) throw new Exception("Expected existing update lockout");
    inputResult=true;
    bool held = MyInputManagerPatches.GetButton_Prefix(action, ref inputResult);
    if (held || inputResult) throw new Exception("Expected existing update lockout");
    inputResult=true;
    bool up = MyInputManagerPatches.GetButtonUp_Prefix(action, ref inputResult);
    if (up || inputResult) throw new Exception("Expected existing update lockout");
}
if (!await updater.CheckAndUpdate()) throw new Exception("Existing update state not sticky");
Console.WriteLine("REPRODUCED: Actual Proton updater + input patches suppress down/held/up for Jump, Pause, Submit, Cancel even with NO modal active. Subsequent update check leaves lockout set.");

var listener = new TcpListener(IPAddress.Loopback, 0);
listener.Start();
using var client = new ClientWebSocket();
var connectTask = client.ConnectAsync(new Uri($"ws://127.0.0.1:{((IPEndPoint)listener.LocalEndpoint).Port}/"), CancellationToken.None);
using var accepted = await listener.AcceptTcpClientAsync();
using var stream = accepted.GetStream();
var header = new StringBuilder();
var one = new byte[1];
while (!header.ToString().EndsWith("\r\n\r\n"))
{
    if (await stream.ReadAsync(one) == 0) throw new Exception("Unexpected EOF");
    header.Append((char)one[0]);
}
string key = header.ToString().Split("\r\n").Single(s => s.StartsWith("Sec-WebSocket-Key:", StringComparison.OrdinalIgnoreCase)).Split(':', 2)[1].Trim();
string accept = Convert.ToBase64String(SHA1.HashData(Encoding.ASCII.GetBytes(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")));
await stream.WriteAsync(Encoding.ASCII.GetBytes($"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n"));
await connectTask;
var service = new ExtractedWebsocketReset(client);
var simulatedUnityCall = Task.Run(() =>
{
    // This is the exact synchronous waiting structure in NetworkHandler.ResetNetworking.
    Task.Run(async () => { await service.Reset(); }).Wait();
});
bool blocked = await Task.WhenAny(simulatedUnityCall, Task.Delay(1500)) != simulatedUnityCall;
Console.WriteLine($"REPRODUCED: Extracted, unchanged WebsocketClientService.Reset body with open peer that never acknowledges close: synchronous caller still blocked at 1500ms = {blocked}; socket state={client.State}");
// Watchdog prevents this test process from hanging indefinitely.
client.Abort();
await simulatedUnityCall.WaitAsync(TimeSpan.FromSeconds(3));
listener.Stop();
if (!blocked) throw new Exception("Reset hang not reproduced");
Console.WriteLine("2 isolated defect reproductions passed. These prove code paths, not an in-game Steam Deck reproduction.");

// Check the reconnect hypothesis against the exact dependency version.
var udpServerOne = new LiteNetLib.NetManager(new LiteNetLib.EventBasedNetListener());
var udpServerTwo = new LiteNetLib.NetManager(new LiteNetLib.EventBasedNetListener());
var udpClient = new LiteNetLib.NetManager(new LiteNetLib.EventBasedNetListener());
var freshClient = new LiteNetLib.NetManager(new LiteNetLib.EventBasedNetListener());
try
{
    udpServerOne.Start(0); udpServerTwo.Start(0); udpClient.Start(0); freshClient.Start(0);
    var first = udpClient.Connect("127.0.0.1", udpServerOne.LocalPort, "test");
    var second = udpClient.Connect("127.0.0.1", udpServerTwo.LocalPort, "test");
    var fresh = freshClient.Connect("127.0.0.1", udpServerOne.LocalPort, "test");
    Console.WriteLine($"LiteNetLib 1.3.5 peer IDs: first={first.Id}, second concurrent={second.Id}, new manager={fresh.Id}. Normal lobby reset constructs a new manager, so simple reconnect does NOT prove the gamePeers[0] hypothesis.");
    if (first.Id != 0 || second.Id != 1 || fresh.Id != 0) throw new Exception("Unexpected dependency peer allocation");
}
finally
{
    udpClient.Stop(); freshClient.Stop(); udpServerOne.Stop(); udpServerTwo.Stop();
}
