import argparse
import queue
import socket
import threading
import time

from pynput import keyboard, mouse

from src.common import (
    DEFAULT_PORT,
    encode_message,
    serialize_button,
    serialize_key,
)


class NetworkSender(threading.Thread):
    def __init__(self, host, port, verbose):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.verbose = verbose
        self.queue = queue.Queue(maxsize=5000)
        self.stop_event = threading.Event()
        self.connected = threading.Event()
        self.socket = None

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

    def run(self):
        while not self.stop_event.is_set():
            try:
                self.socket = socket.create_connection((self.host, self.port), timeout=3)
                self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.connected.set()
                self.log(f"connected to {self.host}:{self.port}")
                hello = {"type": "hello", "role": "controller"}
                self.socket.sendall(encode_message(hello).encode("utf-8"))
                while not self.stop_event.is_set():
                    try:
                        message = self.queue.get(timeout=0.25)
                    except queue.Empty:
                        continue
                    payload = encode_message(message).encode("utf-8")
                    self.socket.sendall(payload)
            except OSError as exc:
                self.log(f"connection error: {exc}")
            finally:
                self.connected.clear()
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

    def toggle_active(self):
        with self.state_lock:
            self.active = not self.active
            self.last_mouse_pos = None
        if self.active:
            self.start_capture()
            status = "REMOTE"
        else:
            self.stop_capture()
            status = "LOCAL"
        self.sender.enqueue({"type": "state", "active": self.active})
        print(f"mode: {status}")

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
        default="<ctrl>+<alt>+f9",
        help="Toggle hotkey in pynput format",
    )
    parser.add_argument(
        "--suppress-local",
        action="store_true",
        help="Suppress local input while remote mode is active",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    sender = NetworkSender(args.host, args.port, args.verbose)
    sender.start()

    controller = InputController(sender, args.suppress_local)
    hotkeys = keyboard.GlobalHotKeys({args.hotkey: controller.toggle_active})
    hotkeys.start()

    print("controller running")
    print(f"toggle hotkey: {args.hotkey}")
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
