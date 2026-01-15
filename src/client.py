import argparse
import socket
import sys
import threading

from pynput import keyboard, mouse

from src.common import (
    DEFAULT_PORT,
    decode_message,
    deserialize_button,
    deserialize_key,
    encode_message,
    normalize_hotkey,
)


class ToggleSender:
    def __init__(self, verbose):
        self.verbose = verbose
        self.lock = threading.Lock()
        self.conn = None

    def log(self, message):
        if self.verbose:
            print(message)

    def set_connection(self, conn):
        with self.lock:
            self.conn = conn

    def clear_connection(self):
        with self.lock:
            self.conn = None

    def send_toggle(self):
        with self.lock:
            if not self.conn:
                self.log("no controller connection")
                return
            try:
                payload = encode_message({"type": "toggle"}).encode("utf-8")
                self.conn.sendall(payload)
            except OSError as exc:
                self.log(f"failed to send toggle: {exc}")


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip:
                return ip
    except OSError:
        pass
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip:
            return ip
    except OSError:
        pass
    return "127.0.0.1"


class InputReceiver:
    def __init__(self, verbose):
        self.verbose = verbose
        self.keyboard = keyboard.Controller()
        self.mouse = mouse.Controller()

    def log(self, message):
        if self.verbose:
            print(message)

    def handle_message(self, message):
        msg_type = message.get("type")
        if msg_type == "key_press":
            payload = message.get("key", {})
            key = deserialize_key(payload, keyboard.Key)
            if key is not None:
                self.keyboard.press(key)
            return
        if msg_type == "key_release":
            payload = message.get("key", {})
            key = deserialize_key(payload, keyboard.Key)
            if key is not None:
                self.keyboard.release(key)
            return
        if msg_type == "mouse_move":
            dx = message.get("dx", 0)
            dy = message.get("dy", 0)
            if dx or dy:
                self.mouse.move(dx, dy)
            return
        if msg_type == "mouse_click":
            button = deserialize_button(message, mouse.Button)
            if button is None:
                return
            if message.get("pressed"):
                self.mouse.press(button)
            else:
                self.mouse.release(button)
            return
        if msg_type == "mouse_scroll":
            dx = message.get("dx", 0)
            dy = message.get("dy", 0)
            if dx or dy:
                self.mouse.scroll(dx, dy)
            return
        if msg_type == "state":
            active = message.get("active")
            self.log(f"controller state: {active}")
            return
        if msg_type == "hello":
            self.log("controller connected")
            return
        self.log(f"unknown message: {message}")


def parse_args():
    parser = argparse.ArgumentParser(description="LAN input client")
    parser.add_argument("--bind", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--toggle-hotkey",
        default="<ctrl>+<alt>+q",
        help="Toggle remote mode on the controller (pynput format)",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def serve(bind, port, receiver, toggle_sender):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((bind, port))
    server.listen(1)
    print(f"listening on {bind}:{port}")

    while True:
        conn, addr = server.accept()
        print(f"connection from {addr[0]}:{addr[1]}")
        toggle_sender.set_connection(conn)
        with conn:
            file = conn.makefile("r", encoding="utf-8")
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    message = decode_message(line)
                except ValueError:
                    receiver.log(f"bad message: {line}")
                    continue
                receiver.handle_message(message)
        toggle_sender.clear_connection()
        print("connection closed")


def main():
    args = parse_args()
    receiver = InputReceiver(args.verbose)
    toggle_sender = ToggleSender(args.verbose)
    toggle_hotkey = normalize_hotkey(args.toggle_hotkey)
    try:
        hotkeys = keyboard.GlobalHotKeys({toggle_hotkey: toggle_sender.send_toggle})
    except ValueError:
        print(f"invalid toggle hotkey: {args.toggle_hotkey}")
        print("example: <ctrl>+<alt>+q (function keys must use <...>)")
        sys.exit(2)
    hotkeys.start()
    print(f"local ip: {get_local_ip()}")
    print(f"toggle hotkey (client): {toggle_hotkey}")
    try:
        serve(args.bind, args.port, receiver, toggle_sender)
    except KeyboardInterrupt:
        pass
    finally:
        hotkeys.stop()


if __name__ == "__main__":
    main()
