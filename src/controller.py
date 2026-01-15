import argparse
import queue
import socket
import sys
import threading
import time

from pynput import keyboard, mouse

from src.common import (
    DEFAULT_PORT,
    decode_message,
    encode_message,
    normalize_hotkey,
    serialize_button,
    serialize_key,
)


class NetworkSender(threading.Thread):
    def __init__(self, host, port, verbose, on_message=None, on_disconnect=None):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.verbose = verbose
        self.queue = queue.Queue(maxsize=5000)
        self.stop_event = threading.Event()
        self.connected = threading.Event()
        self.socket = None
        self.on_message = on_message
        self.on_disconnect = on_disconnect

    def log(self, message):
        if self.verbose:
            print(message)

    def stop(self):
        self.stop_event.set()
        self.connected.clear()
        if self.socket:
            try:
                self.socket.close()
            except OSError:
                pass

    def enqueue(self, message):
        if not self.connected.is_set():
            return False
        try:
            self.queue.put_nowait(message)
            return True
        except queue.Full:
            self.log("queue full, dropping event")
            return False

    def _notify_disconnect(self):
        if self.connected.is_set():
            self.connected.clear()
            if self.on_disconnect:
                self.on_disconnect()

    def _read_loop(self, sock):
        file = sock.makefile("r", encoding="utf-8")
        for line in file:
            if self.stop_event.is_set():
                break
            line = line.strip()
            if not line:
                continue
            try:
                message = decode_message(line)
            except ValueError:
                self.log(f"bad message: {line}")
                continue
            if self.on_message:
                self.on_message(message)
        self._notify_disconnect()

    def run(self):
        while not self.stop_event.is_set():
            try:
                self.socket = socket.create_connection((self.host, self.port), timeout=3)
                self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.connected.set()
                self.log(f"connected to {self.host}:{self.port}")
                hello = {"type": "hello", "role": "controller"}
                self.socket.sendall(encode_message(hello).encode("utf-8"))
                reader = threading.Thread(
                    target=self._read_loop, args=(self.socket,), daemon=True
                )
                reader.start()
                while not self.stop_event.is_set() and self.connected.is_set():
                    try:
                        message = self.queue.get(timeout=0.25)
                    except queue.Empty:
                        continue
                    payload = encode_message(message).encode("utf-8")
                    self.socket.sendall(payload)
            except OSError as exc:
                self.log(f"connection error: {exc}")
            finally:
                self._notify_disconnect()
                if self.socket:
                    try:
                        self.socket.close()
                    except OSError:
                        pass
                    self.socket = None
                if not self.stop_event.is_set():
                    time.sleep(1)


class InputController:
    def __init__(self, sender, suppress_local):
        self.sender = sender
        self.suppress_local = suppress_local
        self.active = False
        self.last_mouse_pos = None
        self.state_lock = threading.Lock()
        self.keyboard_listener = None
        self.mouse_listener = None

    def set_active(self, active, source="local", force=False):
        with self.state_lock:
            if self.active == active:
                return
            if (
                not force
                and source == "local"
                and self.active
                and self.sender.connected.is_set()
            ):
                return
            self.active = active
            self.last_mouse_pos = None
        if self.active:
            self.start_capture()
            status = "REMOTE"
        else:
            self.stop_capture()
            status = "LOCAL"
        self.sender.enqueue({"type": "state", "active": self.active})
        print(f"mode: {status}")

    def toggle_active(self, source="local"):
        with self.state_lock:
            target = not self.active
        self.set_active(target, source=source)

    def force_local(self):
        self.set_active(False, source="system", force=True)

    def start_capture(self):
        if self.keyboard_listener or self.mouse_listener:
            return
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_key_press,
            on_release=self.on_key_release,
            suppress=self.suppress_local,
        )
        self.mouse_listener = mouse.Listener(
            on_move=self.on_move,
            on_click=self.on_click,
            on_scroll=self.on_scroll,
            suppress=self.suppress_local,
        )
        self.keyboard_listener.start()
        self.mouse_listener.start()

    def stop_capture(self):
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None

    def on_key_press(self, key):
        if not self.active:
            return
        payload = serialize_key(key)
        self.sender.enqueue({"type": "key_press", "key": payload})

    def on_key_release(self, key):
        if not self.active:
            return
        payload = serialize_key(key)
        self.sender.enqueue({"type": "key_release", "key": payload})

    def on_move(self, x, y):
        if not self.active:
            return
        with self.state_lock:
            if self.last_mouse_pos is None:
                self.last_mouse_pos = (x, y)
                return
            last_x, last_y = self.last_mouse_pos
            self.last_mouse_pos = (x, y)
        dx = x - last_x
        dy = y - last_y
        if dx or dy:
            self.sender.enqueue({"type": "mouse_move", "dx": dx, "dy": dy})

    def on_click(self, x, y, button, pressed):
        if not self.active:
            return
        payload = serialize_button(button)
        self.sender.enqueue(
            {
                "type": "mouse_click",
                "button": payload["button"],
                "pressed": pressed,
            }
        )

    def on_scroll(self, x, y, dx, dy):
        if not self.active:
            return
        self.sender.enqueue({"type": "mouse_scroll", "dx": dx, "dy": dy})


def parse_args():
    parser = argparse.ArgumentParser(description="LAN input controller")
    parser.add_argument("--host", required=True, help="Client host or IP")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--hotkey",
        default="<ctrl>+<alt>+q",
        help="Toggle hotkey in pynput format (special keys like <tab>)",
    )
    local_group = parser.add_mutually_exclusive_group()
    local_group.add_argument(
        "--suppress-local",
        dest="suppress_local",
        action="store_true",
        help="Suppress local input while remote mode is active (default)",
    )
    local_group.add_argument(
        "--allow-local",
        dest="suppress_local",
        action="store_false",
        help="Allow local input while remote mode is active",
    )
    parser.set_defaults(suppress_local=True)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    sender = NetworkSender(args.host, args.port, args.verbose)
    controller = InputController(sender, args.suppress_local)

    def handle_message(message):
        msg_type = message.get("type")
        if msg_type == "toggle":
            controller.toggle_active(source="remote")
            return
        if msg_type == "set_active":
            active = message.get("active")
            if isinstance(active, bool):
                controller.set_active(active, source="remote")
            return
        sender.log(f"unknown message: {message}")

    sender.on_message = handle_message
    sender.on_disconnect = controller.force_local
    sender.start()
    hotkey = normalize_hotkey(args.hotkey)
    try:
        hotkeys = keyboard.GlobalHotKeys(
            {hotkey: lambda: controller.toggle_active(source="local")}
        )
    except ValueError:
        print(f"invalid hotkey: {args.hotkey}")
        print("example: <ctrl>+<alt>+q (function keys must use <...>)")
        sys.exit(2)
    hotkeys.start()

    print("controller running")
    print(f"toggle hotkey: {hotkey}")
    print("press Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        hotkeys.stop()
        controller.stop_capture()
        sender.stop()


if __name__ == "__main__":
    main()
