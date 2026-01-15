import json

DEFAULT_PORT = 54242
HOTKEY_ALIASES = {
    "ctrl": "<ctrl>",
    "control": "<ctrl>",
    "alt": "<alt>",
    "option": "<alt>",
    "shift": "<shift>",
    "cmd": "<cmd>",
    "command": "<cmd>",
    "win": "<cmd>",
    "super": "<cmd>",
}


def encode_message(message):
    return json.dumps(message, separators=(",", ":"), ensure_ascii=True) + "\n"


def decode_message(line):
    return json.loads(line)


def serialize_key(key):
    if hasattr(key, "char") and key.char is not None:
        return {"key_type": "char", "value": key.char}
    name = getattr(key, "name", None)
    if name:
        return {"key_type": "special", "value": name}
    text = str(key)
    if text.startswith("Key."):
        return {"key_type": "special", "value": text[4:]}
    return {"key_type": "special", "value": text}


def deserialize_key(payload, key_enum):
    key_type = payload.get("key_type")
    value = payload.get("value")
    if key_type == "char":
        return value
    if key_type == "special":
        return getattr(key_enum, value, None)
    return None


def serialize_button(button):
    name = getattr(button, "name", None)
    if name:
        return {"button": name}
    text = str(button)
    if text.startswith("Button."):
        return {"button": text[7:]}
    return {"button": text}


def deserialize_button(payload, button_enum):
    name = payload.get("button")
    if not name:
        return None
    return getattr(button_enum, name, None)


def normalize_hotkey(hotkey):
    if not hotkey:
        return hotkey
    parts = [part.strip() for part in hotkey.split("+") if part.strip()]
    if not parts:
        return hotkey
    normalized = []
    for part in parts:
        lower = part.lower()
        if lower.startswith("<") and lower.endswith(">"):
            normalized.append(lower)
            continue
        if lower in HOTKEY_ALIASES:
            normalized.append(HOTKEY_ALIASES[lower])
            continue
        if lower.startswith("f") and lower[1:].isdigit():
            normalized.append(f"<{lower}>")
            continue
        normalized.append(lower)
    return "+".join(normalized)
