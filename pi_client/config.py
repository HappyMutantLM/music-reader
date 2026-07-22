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

# AirTurn pedals pair as a generic Bluetooth HID keyboard. Key codes below
# match AirTurn's factory default mapping (left pedal = Left arrow, right
# pedal = Right arrow). If AirTurn Manager was used to remap the pedal,
# update these two to match whatever it actually sends — run
# `python pedal_input.py --probe` to see raw key names.
PEDAL_DEVICE_NAME_HINT = os.getenv("PEDAL_DEVICE_NAME_HINT", "AirTurn")
KEY_NEXT_PAGE = os.getenv("PEDAL_KEY_NEXT", "KEY_RIGHT")
KEY_PREV_PAGE = os.getenv("PEDAL_KEY_PREV", "KEY_LEFT")

# ─── state persistence ──────────────────────────────────────────────────────

# Last (score_id, page_number), so a reboot/power cycle resumes on the same
# page instead of booting to a blank screen every time.
STATE_FILE = os.getenv("READER_STATE_FILE", os.path.expanduser("~/.music_reader_state.json"))
