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
