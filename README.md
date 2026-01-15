# Cross-Device Input Switch (Prototype)

Minimal cross-platform tool to switch a keyboard/mouse between devices on the same LAN.
One machine runs the controller (captures input), the other runs the client (injects input).

## Requirements

- Python 3.9+
- `pip install -r requirements.txt`

Note: On macOS you may need to grant Accessibility permissions to your terminal.

## Usage

Start the client on the target device:

```bash
python -m src.client --bind 0.0.0.0 --port 54242
```

Start the controller on the device with the keyboard/mouse:

```bash
python -m src.controller --host <client-ip> --port 54242
```

Toggle remote mode with the hotkey (default: `<ctrl>+<alt>+q`).
When remote mode is active, press the same hotkey on the client to switch back.

### Options

Controller:
- `--hotkey "<ctrl>+<alt>+q"`: change toggle hotkey (pynput format)
- `--allow-local`: allow local input while remote mode is active (default suppresses)
- `--verbose`: extra logs

Client:
- `--toggle-hotkey "<ctrl>+<alt>+q"`: send toggle request to the controller
- `--verbose`: extra logs

## Notes

- This is a LAN prototype: no encryption, no authentication.
- The controller sends relative mouse movement; different screen sizes will feel slightly different.
- Local input is suppressed by default while remote mode is active.

## Roadmap Ideas

- Add device discovery (mDNS) and pairing
- TLS + shared key auth
- Multi-client switching and seamless edges
