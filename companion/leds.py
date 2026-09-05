"""
NeoPixel mini button PCBs (SK6812 RGBW) behind the three tactile switches.
"""
import logging
import config

log = logging.getLogger("companion.leds")

IDX_PREV, IDX_SELECT, IDX_NEXT = 0, 1, 2

# (R, G, B, W)
_IDLE = (0, 0, 0, 20)          # warm white glow
_PRESSED = (0, 40, 0, 0)       # green flash
_NOW_PLAYING = (0, 0, 40, 10)  # blue-white pulse


def init_strip():
    from rpi_ws281x import PixelStrip, ws

    strip_type = getattr(ws, config.NEOPIXEL_STRIP_TYPE)
    strip = PixelStrip(
        config.NEOPIXEL_COUNT,
        config.NEOPIXEL_PIN,
        800000,
        10,
        False,
        config.NEOPIXEL_BRIGHTNESS,
        0,
        strip_type,
    )
    strip.begin()
    return strip


def _set(strip, idx, rgbw):
    # Pack 32-bit color: (W << 24) | (R << 16) | (G << 8) | B
    color = (rgbw[3] << 24) | (rgbw[0] << 16) | (rgbw[1] << 8) | rgbw[2]
    strip.setPixelColor(idx, color)
    strip.show()


def idle_all(strip):
    for i in range(config.NEOPIXEL_COUNT):
        _set(strip, i, _IDLE)


def flash_press(strip, idx):
    _set(strip, idx, _PRESSED)


def set_now_playing_indicator(strip, is_synced):
    _set(strip, IDX_SELECT, _NOW_PLAYING if is_synced else _IDLE)
