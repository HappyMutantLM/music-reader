"""
Reads PageFlip Dragonfly pedal presses. Like the AirTurn pedal used
earlier in this project, the Dragonfly pairs as a standard Bluetooth HID
keyboard, so once paired it shows up as a /dev/input/event* device like
any other keyboard — evdev just needs to find that device and listen for
key-down events.

Run this file directly to see what the pedal actually sends:
    python pedal_input.py --probe
"""
import argparse
import time

from evdev import InputDevice, categorize, ecodes, list_devices

from config import PEDAL_DEVICE_NAME_HINT, KEY_NEXT_PAGE, KEY_PREV_PAGE

# Time threshold to prevent rapid double-turns from accidental bounce
# or events queued while the IT8951 SPI bus was busy drawing.
DEBOUNCE_SECONDS = 0.5


def find_pedal_device():
    for path in list_devices():
        dev = InputDevice(path)
        if PEDAL_DEVICE_NAME_HINT.lower() in dev.name.lower():
            return dev
    return None


def _matches(keycode, target: str) -> bool:
    codes = keycode if isinstance(keycode, list) else [keycode]
    return target in codes


def listen(on_next, on_prev):
    """Resilient event loop with auto-reconnect and input debounce."""
    last_tap_time = 0.0

    while True:
        dev = find_pedal_device()
        if dev is None:
            print(f"[pedal] device '{PEDAL_DEVICE_NAME_HINT}' not found; retrying in 2s...")
            time.sleep(2)
            continue

        print(f"[pedal] listening on: {dev.name} ({dev.path})")
        try:
            for event in dev.read_loop():
                if event.type != ecodes.EV_KEY:
                    continue
                key_event = categorize(event)
                if key_event.keystate != key_event.key_down:
                    continue

                now = time.time()
                if now - last_tap_time < DEBOUNCE_SECONDS:
                    continue

                if _matches(key_event.keycode, KEY_NEXT_PAGE):
                    last_tap_time = now
                    on_next()
                elif _matches(key_event.keycode, KEY_PREV_PAGE):
                    last_tap_time = now
                    on_prev()

        except (OSError, IOError) as exc:
            print(f"[pedal] disconnected ({exc}). Reconnecting...")
            time.sleep(2)


def _probe():
    print("Available input devices:")
    for path in list_devices():
        dev = InputDevice(path)
        print(f"  {dev.path}: {dev.name}")

    dev = find_pedal_device()
    if dev is None:
        print(f"\nNo device matched '{PEDAL_DEVICE_NAME_HINT}' — check pairing.")
        return

    print(f"\nListening on {dev.name} ({dev.path}) — tap each pedal, Ctrl+C to stop.")
    try:
        for event in dev.read_loop():
            if event.type != ecodes.EV_KEY:
                continue
            key_event = categorize(event)
            if key_event.keystate == key_event.key_down:
                print(f"  key down: {key_event.keycode}")
    except (OSError, IOError):
        print("\nPedal disconnected.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true", help="List input devices and print raw key names")
    args = parser.parse_args()
    if args.probe:
        _probe()
    else:
        parser.print_help()
