import os

# ─── backend ──────────────────────────────────────────────────────────────

# NAS FastAPI server. docker-compose's ALLOWED_ORIGINS lists memoryalpha:8000
# as a known host for this backend — default to that.
SERVER_URL = os.getenv("MUSIC_SERVER_URL", "http://memoryalpha:8000")
REQUEST_TIMEOUT = 10  # seconds

# ─── display panel ──────────────────────────────────────────────────────────

# Waveshare 9.7" IT8951 HAT. Matches routers/pages.py's PANEL_WIDTH/
# PANEL_HEIGHT defaults on the backend — the two should stay in sync so
# rendered pages arrive already sized close to the panel's native res.
PANEL_WIDTH = 1200
PANEL_HEIGHT = 825

# Printed on the panel's ribbon cable. Do not guess this value — using the
# wrong VCOM produces poor contrast/ghosting and can affect panel
# longevity. Leila's panel: -1.87V.
VCOM = float(os.getenv("PANEL_VCOM", "-1.87"))
SPI_HZ = int(os.getenv("PANEL_SPI_HZ", "24000000"))

# Page turns use a fast DU (1bpp, black/white only) partial refresh rather
# than a full GC16 redraw — noticeably quicker with far less flicker, which
# matters more for a page-turn-under-your-foot instrument than photo-grade
# grayscale. DU updates only touch pixels that changed since the last
# refresh, but leave faint ghosting behind (an IT8951 characteristic, not a
# bug), so every FULL_REFRESH_EVERY-th turn does a full GC16 pass instead to
# clear it. Lower this if ghosting is visible before that point on your
# panel; raise it if the periodic flicker is more distracting than the
# ghosting.
FULL_REFRESH_EVERY = int(os.getenv("PANEL_FULL_REFRESH_EVERY", "10"))

# ─── pedal ──────────────────────────────────────────────────────────────────

# PageFlip Dragonfly Bluetooth/USB quad pedal — replaces the AirTurn pedal
# used earlier in the project. Like the AirTurn, it pairs as a generic
# Bluetooth HID keyboard, so the same evdev-based approach in
# pedal_input.py still works unchanged; only the device-name hint and key
# codes below needed to change.
#
# Device name: V5+ Dragonflies (the ones with a USB-C port on the back)
# broadcast as "PageFlip Dragonfly", which this hint matches. Pedals
# marked V4 or earlier (micro-USB port) broadcast as "Quad Pedal" instead
# — this hint would NOT match one of those. Check the version printed on
# the label on the underside of the pedal before assuming pairing works
# out of the box; set this to "Quad Pedal" if it's a <V5 unit.
PEDAL_DEVICE_NAME_HINT = os.getenv("PEDAL_DEVICE_NAME_HINT", "PageFlip")

# Key codes for the two *primary* (larger) pedals — the ones actually
# meant to be tapped with a foot mid-performance. Per the Dragonfly's own
# manual, the primary pedals never send Left/Right Arrow in any of its
# five preset modes (only Stop/Play, Up/Down Arrow, or Space/Enter) —
# Left/Right Arrow is exclusively a *secondary* (small, top) pedal
# function there. The pedal's factory-default mode immediately after
# first pairing is the middle preset ("left/right and up/down arrow
# keys"), which sends Up/Down Arrow from the primary pedals.
#
# KEY_DOWN/KEY_UP below is a best guess (Up = previous, Down = next),
# chosen to mirror the left=prev/right=next handedness the old AirTurn
# KEY_LEFT/KEY_RIGHT mapping used — the Dragonfly manual doesn't document
# which physical primary pedal (left vs. right) sends Up vs. Down.
# NOT hardware-confirmed. Run `python pedal_input.py --probe` and tap
# each primary pedal before trusting this at a performance; swap the two
# values below if the mapping turns out reversed, or if the pedal's been
# reprogrammed via the PageFlip app to a different mode.
KEY_NEXT_PAGE = os.getenv("PEDAL_KEY_NEXT", "KEY_DOWN")
KEY_PREV_PAGE = os.getenv("PEDAL_KEY_PREV", "KEY_UP")

# ─── state persistence ──────────────────────────────────────────────────────

# Last (score_id, page_number), so a reboot/power cycle resumes on the same
# page instead of booting to a blank screen every time.
STATE_FILE = os.getenv("READER_STATE_FILE", os.path.expanduser("~/.music_reader_state.json"))
