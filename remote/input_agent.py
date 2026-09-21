"""Bounded Linux virtual input, served over a private, local Unix socket.

No root service or system configuration is installed. The logged-in user must
already have write access to /dev/uinput. Linux ABI: linux/input.h, linux/uinput.h;
see https://docs.kernel.org/input/uinput.html. Keyboard text assumes US layout.
"""
import contextlib
import json
import math
import os
from pathlib import Path
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import time

IDLE_SECONDS = 300
MAX_MESSAGE = 16384
EV_SYN, EV_KEY, EV_REL, EV_ABS = 0, 1, 2, 3
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
UI_DEV_SETUP, UI_ABS_SETUP = 0x405C5503, 0x401C5504
UI_SET_EVBIT, UI_SET_KEYBIT = 0x40045564, 0x40045565
UI_SET_RELBIT, UI_SET_ABSBIT = 0x40045566, 0x40045567
BUTTONS = {"A": 304, "B": 305, "X": 307, "Y": 308,
           "LB": 310, "RB": 311, "SELECT": 314, "START": 315,
           "MODE": 316, "STEAM": 316, "L3": 317, "R3": 318}
DPAD = {"DPAD_UP": (17, -1), "DPAD_DOWN": (17, 1),
        "DPAD_LEFT": (16, -1), "DPAD_RIGHT": (16, 1)}
AXES = {"LX": 0, "LY": 1, "RX": 3, "RY": 4, "LT": 2, "RT": 5}
MOUSE = {"LEFT": 272, "RIGHT": 273, "MIDDLE": 274}
KEYS = {"ESC": 1, "BACKSPACE": 14, "TAB": 15, "ENTER": 28,
        "CTRL": 29, "SHIFT": 42, "ALT": 56, "SPACE": 57,
        "UP": 103, "LEFT": 105, "RIGHT": 106, "DOWN": 108,
        "DELETE": 111, "HOME": 102, "END": 107, "META": 125}
CHARACTERS = {}
for _row, _start in (("1234567890-=", 2), ("qwertyuiop[]", 16),
                     ("asdfghjkl;'`", 30), ("zxcvbnm,./", 44)):
    for _offset, _char in enumerate(_row):
        CHARACTERS[_char] = (_start + _offset, False)
CHARACTERS.update({"\\": (43, False), " ": (57, False), "\n": (28, False), "\t": (15, False)})
for _char in "abcdefghijklmnopqrstuvwxyz":
    CHARACTERS[_char.upper()] = (CHARACTERS[_char][0], True)
    KEYS[_char.upper()] = CHARACTERS[_char][0]
for _plain, _shifted in zip("1234567890-=[];'`,./\\", "!@#$%^&*()_+{}:\"~<>?|", strict=True):
    CHARACTERS[_shifted] = (CHARACTERS[_plain][0], True)
for _char in "0123456789":
    KEYS[_char] = CHARACTERS[_char][0]


def _number(value, low, high, name, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (isinstance(value, float) and not math.isfinite(value)):
        raise ValueError(name + " must be a finite number")
    if integer and not isinstance(value, int):
        raise ValueError(name + " must be an integer")
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def validate(request):
    """Validate the whole request before creating a device or injecting events."""
    if not isinstance(request, dict):
        raise ValueError("input request must be an object")
    if any(not isinstance(key, str) for key in request):
        raise ValueError("input field names must be strings")
    action = request.get("action")
    if action not in ("start", "status", "stop", "button", "axis", "text", "key", "mouse", "click"):
        raise ValueError("unknown input action")
    result = {"action": action}
    if action in ("button", "key"):
        field = "buttons" if action == "button" else "keys"
        names = request.get(field)
        allowed = (BUTTONS.keys() | DPAD.keys()) if action == "button" else KEYS.keys()
        if not isinstance(names, list) or not 1 <= len(names) <= 8:
            raise ValueError(field + " must contain 1 to 8 names")
        if any(not isinstance(name, str) or name.upper() not in allowed for name in names):
            raise ValueError("unknown " + field + " name")
        result[field] = list(dict.fromkeys(name.upper() for name in names))
        if action == "button":
            dpad_axes = [DPAD[name][0] for name in result[field] if name in DPAD]
            if len(dpad_axes) != len(set(dpad_axes)):
                raise ValueError("opposite D-pad directions cannot be pressed together")
    if action == "axis":
        axis = request.get("axis")
        if not isinstance(axis, str) or axis.upper() not in AXES:
            raise ValueError("unknown axis")
        result["axis"] = axis.upper()
        result["value"] = _number(request.get("value"), 0 if axis.upper() in ("LT", "RT") else -1, 1, "value")
    if action in ("button", "axis", "key", "click"):
        result["duration_ms"] = _number(request.get("duration_ms", 100), 10, 5000, "duration_ms", True)
    if action == "text":
        value = request.get("text")
        if not isinstance(value, str) or not 1 <= len(value) <= 256 or any(c not in CHARACTERS for c in value):
            raise ValueError("text must be 1 to 256 US-layout ASCII characters (printable, newline, or tab)")
        interval = _number(request.get("interval_ms", 30), 10, 100, "interval_ms", True)
        if len(value) * interval > 10000:
            raise ValueError("text operation must finish within 10 seconds")
        result.update(text=value, interval_ms=interval)
    if action == "mouse":
        result["dx"] = _number(request.get("dx", 0), -2000, 2000, "dx", True)
        result["dy"] = _number(request.get("dy", 0), -2000, 2000, "dy", True)
    if action == "click":
        button = request.get("button", "LEFT")
        if not isinstance(button, str) or button.upper() not in MOUSE:
            raise ValueError("unknown mouse button")
        result["button"] = button.upper()
    unknown = set(request) - set(result)
    if unknown:
        raise ValueError("unknown input fields: " + ", ".join(sorted(unknown)))
    return result


class UInputDevice:
    """One kernel input device; injectable syscalls allow hardware-free tests."""
    def __init__(self, kind, opener=os.open, writer=os.write, closer=os.close, ioctl=None):
        if ioctl is None:
            import fcntl
            ioctl = fcntl.ioctl
        self.writer, self.closer, self.ioctl = writer, closer, ioctl
        self.fd, self.created = None, False
        self.held, self.axes = set(), {}
        try:
            self.fd = opener("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
            ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
            if kind == "gamepad":
                keycodes = set(BUTTONS.values())
                ioctl(self.fd, UI_SET_EVBIT, EV_ABS)
                for code in (*AXES.values(), 16, 17):
                    low, high = ((0, 255) if code in (2, 5) else (-1, 1) if code in (16, 17) else (-32768, 32767))
                    ioctl(self.fd, UI_SET_ABSBIT, code)
                    ioctl(self.fd, UI_ABS_SETUP, struct.pack("@H2xiiiiii", code, 0, low, high, 0, 0, 0))
                    self.axes[code] = 0
                vendor, product = 0x045E, 0x028E  # Xbox-compatible evdev layout.
            elif kind == "keyboard":
                keycodes = set(KEYS.values()) | {code for code, shift in CHARACTERS.values()}
                vendor, product = 0x1209, 0xD001
            elif kind == "mouse":
                keycodes = set(MOUSE.values())
                ioctl(self.fd, UI_SET_EVBIT, EV_REL)
                for code in (0, 1):
                    ioctl(self.fd, UI_SET_RELBIT, code)
                vendor, product = 0x1209, 0xD002
            else:
                raise ValueError("unknown device kind")
            for code in sorted(keycodes):
                ioctl(self.fd, UI_SET_KEYBIT, code)
            name = ("Deck Remote " + kind).encode("ascii")
            ioctl(self.fd, UI_DEV_SETUP, struct.pack("@HHHH80sI", 3, vendor, product, 1, name, 0))
            ioctl(self.fd, UI_DEV_CREATE)
            self.created = True
        except BaseException:
            self.close()
            raise

    def emit(self, event_type, code, value):
        data = struct.pack("@llHHi", 0, 0, event_type, code, value)
        if self.writer(self.fd, data) != len(data):
            raise OSError("incomplete uinput event write")

    def sync(self):
        self.emit(EV_SYN, 0, 0)

    def key(self, code, pressed):
        # Track before writing: even a failed/partial write gets a release attempt.
        if pressed:
            self.held.add(code)
        self.emit(EV_KEY, code, int(pressed))
        if not pressed:
            self.held.discard(code)

    def axis(self, code, value):
        self.axes[code] = value
        self.emit(EV_ABS, code, value)

    def release(self):
        failure = None
        for code in list(self.held):
            try:
                self.key(code, False)
            except OSError as exc:
                failure = exc
        for code, value in list(self.axes.items()):
            if value:
                try:
                    self.axis(code, 0)
                except OSError as exc:
                    failure = exc
        try:
            self.sync()
        except OSError as exc:
            failure = exc
        if failure:
            raise failure

    def close(self):
        if self.fd is not None:
            if self.created:
                with contextlib.suppress(OSError):
                    self.release()
                with contextlib.suppress(OSError):
                    self.ioctl(self.fd, UI_DEV_DESTROY)
            self.closer(self.fd)
            self.fd = None


class InputController:
    def __init__(self, factory=UInputDevice):
        self.devices = {}
        try:
            for kind in ("gamepad", "keyboard", "mouse"):
                self.devices[kind] = factory(kind)
        except BaseException:
            self.close()
            raise

    def release(self):
        failure = None
        for device in self.devices.values():
            try:
                device.release()
            except OSError as exc:
                # Destroying the device is the final release guarantee on I/O failure.
                device.close()
                failure = exc
        if failure:
            raise failure

    def close(self):
        for device in self.devices.values():
            with contextlib.suppress(OSError):
                device.close()

    def execute(self, request, wait=time.sleep):
        request = validate(request)
        action = request["action"]
        try:
            if action in ("button", "axis"):
                device = self.devices["gamepad"]
                if action == "button":
                    for name in request["buttons"]:
                        if name in DPAD:
                            device.axis(*DPAD[name])
                        else:
                            device.key(BUTTONS[name], True)
                else:
                    name, value = request["axis"], request["value"]
                    scale = 255 if name in ("LT", "RT") else (32767 if value >= 0 else 32768)
                    device.axis(AXES[name], round(value * scale))
                device.sync()
                wait(request["duration_ms"] / 1000)
            elif action in ("key", "click"):
                device = self.devices["keyboard" if action == "key" else "mouse"]
                codes = [KEYS[name] for name in request["keys"]] if action == "key" else [MOUSE[request["button"]]]
                for code in codes:
                    device.key(code, True)
                device.sync()
                wait(request["duration_ms"] / 1000)
            elif action == "text":
                device = self.devices["keyboard"]
                for char in request["text"]:
                    code, shift = CHARACTERS[char]
                    if shift:
                        device.key(KEYS["SHIFT"], True)
                    device.key(code, True)
                    device.sync()
                    wait(request["interval_ms"] / 2000)
                    device.key(code, False)
                    if shift:
                        device.key(KEYS["SHIFT"], False)
                    device.sync()
                    wait(request["interval_ms"] / 2000)
            elif action == "mouse":
                device = self.devices["mouse"]
                device.emit(EV_REL, 0, request["dx"])
                device.emit(EV_REL, 1, request["dy"])
                device.sync()
            return {"ok": True, "action": action}
        finally:
            self.release()


def _runtime_dir():
    base = Path(os.environ.get("XDG_RUNTIME_DIR") or (Path.home() / ".local" / "state"))
    path = base / "megabonk-deck-input"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise RuntimeError("input runtime directory must be owned by this user with mode 0700")
    return path


def _receive(connection):
    message = bytearray()
    while b"\n" not in message:
        part = connection.recv(min(4096, MAX_MESSAGE + 1 - len(message)))
        if not part:
            raise ConnectionError("input client disconnected")
        message.extend(part)
        if len(message) > MAX_MESSAGE:
            raise ValueError("input message too large")
    line, rest = message.split(b"\n", 1)
    if rest:
        raise ValueError("only one input request per connection")
    return json.loads(line)


def _connected_wait(connection, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        ready, _, _ = select.select([connection], [], [], max(0, min(0.05, deadline - time.monotonic())))
        if ready:
            if not connection.recv(1, socket.MSG_PEEK):
                raise ConnectionError("input client disconnected; controls released")
            raise ValueError("unexpected data during input; controls released")


def _serve(path):
    controller = None
    bound = False
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    def terminate(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        server.bind(str(path))
        bound = True
        os.chmod(path, 0o600)
        server.listen(4)
        server.settimeout(IDLE_SECONDS)
        while True:
            try:
                connection, _ = server.accept()
            except socket.timeout:
                return
            with connection:
                connection.settimeout(2)
                stop = False
                try:
                    _, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid != os.getuid():
                        raise PermissionError("input client uid mismatch")
                    request = validate(_receive(connection))
                    action = request["action"]
                    if action == "stop":
                        stop = True
                        result = {"ok": True, "running": False}
                    elif action == "status":
                        result = {"ok": True, "running": True, "devices_ready": controller is not None, "idle_timeout_seconds": IDLE_SECONDS}
                    else:
                        if controller is None:
                            controller = InputController()
                            _connected_wait(connection, 1)  # Allow Steam/udev to discover new devices.
                        result = controller.execute(request, lambda seconds: _connected_wait(connection, seconds))
                        result["devices_ready"] = True
                except (OSError, ValueError, RuntimeError) as exc:
                    if controller is not None:
                        controller.close()
                        controller = None
                    result = {"ok": False, "error": str(exc)}
                with contextlib.suppress(OSError):
                    connection.sendall(json.dumps(result).encode("utf-8") + b"\n")
                if stop:
                    return
    finally:
        if controller is not None:
            controller.close()
        server.close()
        if bound:
            with contextlib.suppress(FileNotFoundError):
                path.unlink()


def _connect(path):
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(15)
    try:
        connection.connect(str(path))
        return connection
    except OSError:
        connection.close()
        raise


def handle(request):
    """Dispatch one bounded action; returns errors as JSON instead of tracebacks."""
    try:
        request = validate(request)
        if not sys.platform.startswith("linux"):
            raise RuntimeError("virtual input must run on the Linux Deck")
        import fcntl
        directory = _runtime_dir()
        path = directory / "input.sock"
        # Serialize connection/bootstrap so concurrent SSH commands cannot start two daemons.
        with (directory / "startup.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                connection = _connect(path)
            except (FileNotFoundError, ConnectionRefusedError):
                if request["action"] in ("status", "stop"):
                    return {"ok": True, "running": False, "devices_ready": False}
                if not os.access("/dev/uinput", os.W_OK):
                    raise PermissionError("Deck user cannot write /dev/uinput. One-time device permission setup is required; no permission changes were made.")
                with contextlib.suppress(FileNotFoundError):
                    path.unlink()
                process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--serve", str(path)],
                                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           start_new_session=True, close_fds=True)
                deadline = time.monotonic() + 5
                while True:
                    try:
                        connection = _connect(path)
                        break
                    except (FileNotFoundError, ConnectionRefusedError):
                        if process.poll() is not None or time.monotonic() >= deadline:
                            raise RuntimeError("input daemon failed to start")
                        time.sleep(0.05)
        with connection:
            connection.sendall(json.dumps(request).encode("utf-8") + b"\n")
            return _receive(connection)
    except (OSError, ValueError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc)}


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--serve":
        _serve(Path(sys.argv[2]))
    else:
        print(json.dumps(handle(json.load(sys.stdin))))
