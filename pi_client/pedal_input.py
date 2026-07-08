"""
Reads AirTurn pedal presses. The AirTurn pairs as a standard Bluetooth
HID keyboard, so once paired it shows up as a /dev/input/event* device
like any other keyboard — evdev just needs to find that device and
listen for key-down events.

Run this file directly to see what the pedal actually sends:
    python pedal_input.py --probe
then set PEDAL_KEY_NEXT / PEDAL_KEY_PREV (env vars, see config.py) if it
doesn't match the KEY_RIGHT/KEY_LEFT defaults.
"""
import argparse

from evdev import InputDevice, categorize, ecodes, list_devices

from config import PEDAL_DEVICE_NAME_HINT, KEY_NEXT_PAGE, KEY_PREV_PAGE


def find_pedal_device():
    """Returns the first /dev/input device whose name contains
    PEDAL_DEVICE_NAME_HINT, or None if nothing matches (pedal not
    paired, or AirTurn Manager renamed it to something unexpected)."""
    for path in list_devices():
        dev = InputDevice(path)
        if PEDAL_DEVICE_NAME_HINT.lower() in dev.name.lower():
            return dev
    return None


def _matches(keycode, target: str) -> bool:
    # evdev's keycode is sometimes a list when multiple ecodes alias to
    # the same value — normalize to a list either way before checking.
    codes = keycode if isinstance(keycode, list) else [keycode]
    return target in codes


def listen(on_next, on_prev):
    """Blocking loop: calls on_next()/on_prev() for each pedal tap.
    Meant to run in its own thread — the caller owns the display, so
    these callbacks just update state and trigger a redraw."""
    dev = find_pedal_device()
    if dev is None:
        raise RuntimeError(
            f"No input device matching '{PEDAL_DEVICE_NAME_HINT}' found. "
            "Is the pedal paired and connected? Run `python pedal_input.py "
            "--probe` (or `sudo evtest`) to list available input devices."
        )

    print(f"[pedal] listening on: {dev.name} ({dev.path})")
    for event in dev.read_loop():
        if event.type != ecodes.EV_KEY:
            continue
        key_event = categorize(event)
        if key_event.keystate != key_event.key_down:
            continue
        if _matches(key_event.keycode, KEY_NEXT_PAGE):
            on_next()
        elif _matches(key_event.keycode, KEY_PREV_PAGE):
            on_prev()


def _probe():
    """List all input devices, then print raw key names as they're
    pressed — for figuring out which device is the pedal and what key
    codes it actually sends."""
    print("Available input devices:")
    for path in list_devices():
        dev = InputDevice(path)
        print(f"  {dev.path}: {dev.name}")

    dev = find_pedal_device()
    if dev is None:
        print(f"\nNo device matched '{PEDAL_DEVICE_NAME_HINT}' — pass a different "
              "hint via PEDAL_DEVICE_NAME_HINT, or check pairing.")
        return

    print(f"\nListening on {dev.name} ({dev.path}) — tap each pedal, Ctrl+C to stop.")
    for event in dev.read_loop():
        if event.type != ecodes.EV_KEY:
            continue
        key_event = categorize(event)
        if key_event.keystate == key_event.key_down:
            print(f"  key down: {key_event.keycode}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true", help="List input devices and print raw key names")
    args = parser.parse_args()
    if args.probe:
        _probe()
    else:
        parser.print_help()
