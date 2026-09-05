import os

# ─── backend ──────────────────────────────────────────────────────────────

# Same NAS FastAPI server as pi_client — see pi_client/config.py's comment
# on memoryalpha:8000 being the known host in docker-compose's ALLOWED_ORIGINS.
SERVER_URL = os.getenv("MUSIC_SERVER_URL", "http://memoryalpha:8000")
REQUEST_TIMEOUT = 5  # seconds — shorter than pi_client's 10s; a stale badge
                      # is fine to wait out, a hung poll loop is not

SETLIST_ID = int(os.getenv("COMPANION_SETLIST_ID", "1"))  # which evening's program to load
NOW_PLAYING_POLL_SECONDS = int(os.getenv("COMPANION_POLL_SECONDS", "8"))

# Survives a Wi-Fi drop mid-evening — the companion falls back to whatever
# was last fetched successfully rather than showing a blank screen.
CACHE_PATH = os.getenv(
    "COMPANION_CACHE_PATH", os.path.expanduser("~/.companion_program_cache.json")
)

# ─── buttons (BCM numbering) ─────────────────────────────────────────────

PIN_BUTTON_PREV = int(os.getenv("COMPANION_PIN_PREV", "5"))
PIN_BUTTON_SELECT = int(os.getenv("COMPANION_PIN_SELECT", "6"))
PIN_BUTTON_NEXT = int(os.getenv("COMPANION_PIN_NEXT", "12"))
BUTTON_BOUNCE_SECONDS = 0.05

# ─── NeoPixel button lights (SK6812 RGBW mini button PCBs) ───────────────

NEOPIXEL_PIN = 18         # BCM18 — PWM/DMA-capable, doesn't collide with the
                           # e-paper HAT's SPI pins (see companion/README.md)
NEOPIXEL_COUNT = 3        # prev, select, next — same order as the pins above
NEOPIXEL_BRIGHTNESS = int(os.getenv("COMPANION_LED_BRIGHTNESS", "60"))  # 0-255
NEOPIXEL_STRIP_TYPE = "SK6812_STRIP_RGBW"

# ─── display ──────────────────────────────────────────────────────────────

# Waveshare 4.2" panel, 400x300 — unrelated to pi_client's IT8951 9.7"
# panel and PANEL_WIDTH/PANEL_HEIGHT there; this is a separate, smaller
# display with its own driver library (see README.md).
EPD_WIDTH = 400
EPD_HEIGHT = 300
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_PATH_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
