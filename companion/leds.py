"""
NeoPixel mini button PCBs (SK6812 RGBW) behind the three tactile switches.
Kept deliberately simple and dim — these are status lights on a handheld
object passed between guests at a hausmusik, not a keyboard RGB show.

Not hardware-confirmed. Requires root (PWM/DMA access to GPIO18) — run
main.py with sudo, or grant the capability via setcap, per rpi_ws281x's
own notes. The RGBW call signature below (setPixelColorRGB, no white
channel) is a conservative choice — rpi_ws281x's API for the white
channel varies a bit by version/fork, and I didn't want to guess at one
that might not match what's actually installed. Worth revisiting once
this runs on the real strip.
"""

import logging

import config

log = logging.getLogger("companion.leds")

# Indices into the strip, matching button order in config.py
IDX_PREV, IDX_SELECT, IDX_NEXT = 0, 1, 2

_IDLE = (0, 0, 0, 20)          # dim warm-white glow, "device is alive"
_PRESSED = (0, 40, 0, 0)       # brief green flash on a press
_NOW_PLAYING = (0, 0, 40, 10)  # soft blue pulse on select when synced live


def init_strip():
    from rpi_ws281x import PixelStrip, ws

    strip_type = getattr(ws, config.NEOPIXEL_STRIP_TYPE)
    strip = PixelStrip(
        config.NEOPIXEL_COUNT,
        config.NEOPIXEL_PIN,
        800000,   # signal frequency, standard for WS281x/SK6812
        10,       # DMA channel
        False,    # invert signal
        config.NEOPIXEL_BRIGHTNESS,
        0,        # PWM channel
        strip_type,
    )
    strip.begin()
    return strip


def _set(strip, idx, rgbw):
    strip.setPixelColorRGB(idx, rgbw[0], rgbw[1], rgbw[2])
    # If your installed rpi_ws281x supports RGBW directly, prefer
    # strip.setPixelColor(idx, Color(r, g, b, w)) instead — see module note.
    strip.show()


def idle_all(strip):
    for i in range(config.NEOPIXEL_COUNT):
        _set(strip, i, _IDLE)


def flash_press(strip, idx):
    _set(strip, idx, _PRESSED)
    # Caller (main.py) restores idle/now-playing state on the next render
    # tick rather than blocking here with a sleep — this runs on the
    # button's own callback thread.


def set_now_playing_indicator(strip, is_synced):
    _set(strip, IDX_SELECT, _NOW_PLAYING if is_synced else _IDLE)
