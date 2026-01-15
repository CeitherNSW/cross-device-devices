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

Toggle remote mode with the hotkey (default: `<ctrl>+<alt>+f9`).

### Options

- `--hotkey "<ctrl>+<alt>+f9"`: change toggle hotkey (pynput format)
- `--suppress-local`: suppress local input while remote mode is active
- `--verbose`: extra logs

## Notes

- This is a LAN prototype: no encryption, no authentication.
- The controller sends relative mouse movement; different screen sizes will feel slightly different.
- If `--suppress-local` is enabled, local input is blocked only while remote mode is active.

## Roadmap Ideas

- Add device discovery (mDNS) and pairing
- TLS + shared key auth
- Multi-client switching and seamless edges
