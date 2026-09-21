"""Hardware-free uinput ABI, validation, and disconnect cleanup regression tests."""
import importlib.util
import json
import multiprocessing
from pathlib import Path
import socket
import struct
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("deck_input_agent", ROOT / "input_agent.py")
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


class FakeKernel:
    def __init__(self):
        self.next_fd = 10
        self.events = []
        self.calls = []
        self.closed = []
        self.devices = {}
        self.fail_write = False

    def open(self, path, flags):
        self.next_fd += 1
        return self.next_fd

    def write(self, fd, data):
        if self.fail_write:
            raise OSError("simulated device failure")
        self.events.append((fd, *struct.unpack("@llHHi", data)[2:]))
        return len(data)

    def ioctl(self, fd, operation, argument=None):
        self.calls.append((fd, operation, argument))

    def factory(self, kind):
        result = agent.UInputDevice(kind, self.open, self.write, self.closed.append, self.ioctl)
        self.devices[kind] = result
        return result


class InputTests(unittest.TestCase):
    def setUp(self):
        flags = mock.patch.object(agent.os, "O_NONBLOCK", 0x800, create=True)
        flags.start()
        self.addCleanup(flags.stop)
        self.kernel = FakeKernel()
        self.controller = agent.InputController(self.kernel.factory)

    def tearDown(self):
        self.controller.close()

    def execute(self, request):
        return self.controller.execute(request, wait=lambda seconds: None)

    def test_modern_ioctl_device_setup(self):
        setups = [arg for fd, operation, arg in self.kernel.calls if operation == agent.UI_DEV_SETUP]
        self.assertEqual(len(setups), 3)
        bus, vendor, product, version, name, effects = struct.unpack("@HHHH80sI", setups[0])
        self.assertEqual((bus, vendor, product), (3, 0x045E, 0x028E))
        self.assertEqual(name.rstrip(b"\0"), b"Deck Remote gamepad")
        self.assertEqual(sum(op == agent.UI_ABS_SETUP for fd, op, arg in self.kernel.calls), 8)

    def test_device_persists_between_commands(self):
        before = len(self.kernel.calls)
        self.execute({"action": "button", "buttons": ["A"]})
        self.execute({"action": "button", "buttons": ["B"]})
        self.assertEqual(len(self.kernel.calls), before)
        self.assertEqual(self.kernel.closed, [])

    def test_steam_x_hotkey_and_release(self):
        self.execute({"action": "button", "buttons": ["STEAM", "X"]})
        keys = [(code, value) for fd, kind, code, value in self.kernel.events if kind == agent.EV_KEY]
        self.assertIn((316, 1), keys)
        self.assertIn((307, 1), keys)
        self.assertIn((316, 0), keys)
        self.assertIn((307, 0), keys)
        self.assertFalse(self.kernel.devices["gamepad"].held)

    def test_axis_releases_to_neutral(self):
        self.execute({"action": "axis", "axis": "LY", "value": -1, "duration_ms": 100})
        events = [(code, value) for fd, kind, code, value in self.kernel.events if kind == agent.EV_ABS]
        self.assertEqual(events, [(1, -32768), (1, 0)])

    def test_trigger_range(self):
        self.execute({"action": "axis", "axis": "RT", "value": 1})
        self.assertIn((self.kernel.devices["gamepad"].fd, agent.EV_ABS, 5, 255), self.kernel.events)
        with self.assertRaises(ValueError):
            self.execute({"action": "axis", "axis": "RT", "value": -1})

    def test_dpad_uses_hat_and_releases(self):
        self.execute({"action": "button", "buttons": ["DPAD_DOWN"]})
        self.assertIn((self.kernel.devices["gamepad"].fd, agent.EV_ABS, 17, 1), self.kernel.events)
        self.assertIn((self.kernel.devices["gamepad"].fd, agent.EV_ABS, 17, 0), self.kernel.events)

    def test_all_printable_ascii_has_mapping(self):
        self.assertTrue(all(chr(code) in agent.CHARACTERS for code in range(32, 127)))
        self.assertEqual(agent.CHARACTERS["A"], (30, True))
        self.assertEqual(agent.CHARACTERS["!"], (2, True))
        self.assertEqual(agent.CHARACTERS["`"], (41, False))
        self.assertEqual(agent.CHARACTERS["\\"], (43, False))

    def test_text_shift_released_between_letters(self):
        self.execute({"action": "text", "text": "Aa1!"})
        keys = [(code, value) for fd, kind, code, value in self.kernel.events if kind == agent.EV_KEY]
        self.assertEqual(keys, [(42, 1), (30, 1), (30, 0), (42, 0), (30, 1), (30, 0),
                                (2, 1), (2, 0), (42, 1), (2, 1), (2, 0), (42, 0)])

    def test_disconnect_releases_held_hotkey(self):
        def disconnected(seconds):
            raise ConnectionError("disconnected")
        with self.assertRaises(ConnectionError):
            self.controller.execute({"action": "key", "keys": ["CTRL", "A"]}, wait=disconnected)
        self.assertFalse(self.kernel.devices["keyboard"].held)
        for code in (29, 30):
            self.assertIn((self.kernel.devices["keyboard"].fd, agent.EV_KEY, code, 0), self.kernel.events)

    def test_text_disconnect_releases_shift_and_key(self):
        with self.assertRaises(ConnectionError):
            self.controller.execute({"action": "text", "text": "ABC"}, wait=mock.Mock(side_effect=ConnectionError()))
        self.assertFalse(self.kernel.devices["keyboard"].held)

    def test_injection_failure_destroys_device(self):
        self.kernel.fail_write = True
        with self.assertRaises(OSError):
            self.execute({"action": "button", "buttons": ["A"]})
        self.assertIsNone(self.kernel.devices["gamepad"].fd)
        self.assertEqual(len(self.kernel.closed), 3)

    def test_partial_initialization_closes_prior_devices(self):
        kernel = FakeKernel()
        def factory(kind):
            if kind == "keyboard":
                raise PermissionError("denied")
            return kernel.factory(kind)
        with self.assertRaises(PermissionError):
            agent.InputController(factory)
        self.assertEqual(kernel.closed, [11])

    def test_ioctl_failure_closes_fd(self):
        closed = []
        with self.assertRaises(OSError):
            agent.UInputDevice("gamepad", opener=lambda path, flags: 99, closer=closed.append,
                               ioctl=mock.Mock(side_effect=OSError("no uinput")))
        self.assertEqual(closed, [99])

    def test_mouse_and_click(self):
        self.execute({"action": "mouse", "dx": 12, "dy": -20})
        self.execute({"action": "click", "button": "RIGHT"})
        fd = self.kernel.devices["mouse"].fd
        for event in ((fd, agent.EV_REL, 0, 12), (fd, agent.EV_REL, 1, -20),
                      (fd, agent.EV_KEY, 273, 1), (fd, agent.EV_KEY, 273, 0)):
            self.assertIn(event, self.kernel.events)

    def test_validate_before_injecting_any_events(self):
        invalid = [
            {"action": "button", "buttons": ["A", "BAD"]},
            {"action": "button", "buttons": ["DPAD_UP", "DPAD_DOWN"]},
            {"action": "key", "keys": []},
            {"action": "key", "keys": ["A"], "duration_ms": 5001},
            {"action": "key", "keys": ["A"], "duration_ms": True},
            {"action": "axis", "axis": "LX", "value": float("nan")},
            {"action": "axis", "axis": "LX", "value": float("inf")},
            {"action": "axis", "axis": "LX", "value": 1.1},
            {"action": "mouse", "dx": 2001},
            {"action": "mouse", "dx": 10 ** 400},
            {"action": "mouse", "dx": 1.5},
            {"action": "text", "text": "a" * 257},
            {"action": "text", "text": "a" * 101, "interval_ms": 100},
            {"action": "text", "text": "ABC\u2603"},
            {"action": "click", "button": "OTHER"},
            {"action": "start", "command": "bad"},
        ]
        for request in invalid:
            with self.subTest(request=request), self.assertRaises(ValueError):
                self.execute(request)
        self.assertEqual(self.kernel.events, [])

    def test_handle_errors_are_json_serializable(self):
        result = agent.handle({"action": "bad"})
        self.assertFalse(json.loads(json.dumps(result))["ok"])

    def test_connection_watchdog_detects_disconnect(self):
        if not hasattr(socket, "socketpair"):
            self.skipTest("socketpair unavailable")
        connection, peer = socket.socketpair()
        with connection:
            peer.close()
            with self.assertRaises(ConnectionError):
                agent._connected_wait(connection, 1)

    def test_oversized_request_rejected(self):
        connection = mock.Mock()
        connection.recv.side_effect = [b"x" * 4096] * 5
        with self.assertRaises(ValueError):
            agent._receive(connection)

    def test_incomplete_request_disconnect_rejected(self):
        connection = mock.Mock()
        connection.recv.side_effect = [b'{"action":', b""]
        with self.assertRaises(ConnectionError):
            agent._receive(connection)


def run_fake_daemon(path, logfile, idle_seconds):
    kernel = FakeKernel()
    original_write = kernel.write
    def write(fd, data):
        result = original_write(fd, data)
        with open(logfile, "a") as log:
            log.write(json.dumps(kernel.events[-1]) + "\n")
        return result
    kernel.write = write
    original_controller = agent.InputController
    agent.InputController = lambda: original_controller(kernel.factory)
    agent.IDLE_SECONDS = idle_seconds
    agent._serve(Path(path))


@unittest.skipUnless(sys.platform.startswith("linux"), "Unix daemon lifecycle requires Linux")
class DaemonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "input.sock"
        self.logfile = Path(self.temp.name) / "events.jsonl"
        self.process = None

    def start(self, idle_seconds=5):
        self.process = multiprocessing.get_context("fork").Process(
            target=run_fake_daemon, args=(str(self.path), str(self.logfile), idle_seconds))
        self.process.start()
        self.addCleanup(self.cleanup_process)
        deadline = time.monotonic() + 3
        while not self.path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(self.path.exists())

    def cleanup_process(self):
        if self.process.is_alive():
            self.process.terminate()
        self.process.join(3)

    def request(self, request):
        with agent._connect(self.path) as connection:
            connection.sendall(json.dumps(request).encode() + b"\n")
            return agent._receive(connection)

    def test_persistent_daemon_start_status_input_stop(self):
        self.start()
        self.assertFalse(self.request({"action": "status"})["devices_ready"])
        self.assertTrue(self.request({"action": "start"})["devices_ready"])
        self.assertTrue(self.request({"action": "button", "buttons": ["A"]})["ok"])
        self.assertTrue(self.request({"action": "status"})["devices_ready"])
        self.assertFalse(self.request({"action": "stop"})["running"])
        self.process.join(3)
        self.assertEqual(self.process.exitcode, 0)
        self.assertFalse(self.path.exists())

    def test_client_disconnect_neutralizes_before_duration_expires(self):
        self.start()
        self.request({"action": "start"})
        with agent._connect(self.path) as connection:
            connection.sendall(b'{"action":"button","buttons":["A"],"duration_ms":5000}\n')
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if self.logfile.exists() and "[11, 1, 304, 1]" in self.logfile.read_text():
                    break
                time.sleep(0.01)
            else:
                self.fail("button press was never injected")
        started = time.monotonic()
        self.assertFalse(self.request({"action": "status"})["devices_ready"])
        self.assertLess(time.monotonic() - started, 1)
        self.assertIn("[11, 1, 304, 0]", self.logfile.read_text())

    def test_idle_lifetime_closes_socket(self):
        self.start(idle_seconds=0.1)
        self.process.join(3)
        self.assertEqual(self.process.exitcode, 0)
        self.assertFalse(self.path.exists())

    def test_sigterm_releases_pressed_button(self):
        self.start()
        self.request({"action": "start"})
        with agent._connect(self.path) as connection:
            connection.sendall(b'{"action":"button","buttons":["A"],"duration_ms":5000}\n')
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if self.logfile.exists() and "[11, 1, 304, 1]" in self.logfile.read_text():
                    break
                time.sleep(0.01)
            else:
                self.fail("button press was never injected")
            self.process.terminate()
            self.process.join(3)
        self.assertEqual(self.process.exitcode, 0)
        self.assertIn("[11, 1, 304, 0]", self.logfile.read_text())
        self.assertFalse(self.path.exists())

    def test_permission_preflight_does_not_spawn_daemon(self):
        with mock.patch.dict(agent.os.environ, {"XDG_RUNTIME_DIR": self.temp.name}), \
                mock.patch.object(agent.os, "access", return_value=False), \
                mock.patch.object(agent.subprocess, "Popen") as spawn:
            result = agent.handle({"action": "start"})
        self.assertFalse(result["ok"])
        self.assertIn("/dev/uinput", result["error"])
        spawn.assert_not_called()

    def test_stopped_status_does_not_create_devices(self):
        with mock.patch.dict(agent.os.environ, {"XDG_RUNTIME_DIR": self.temp.name}), \
                mock.patch.object(agent.subprocess, "Popen") as spawn:
            result = agent.handle({"action": "status"})
        self.assertEqual(result, {"ok": True, "running": False, "devices_ready": False})
        spawn.assert_not_called()

    def test_insecure_runtime_directory_rejected(self):
        runtime = Path(self.temp.name) / "megabonk-deck-input"
        runtime.mkdir(mode=0o755)
        with mock.patch.dict(agent.os.environ, {"XDG_RUNTIME_DIR": self.temp.name}):
            result = agent.handle({"action": "status"})
        self.assertFalse(result["ok"])
        self.assertIn("0700", result["error"])


if __name__ == "__main__":
    unittest.main()
