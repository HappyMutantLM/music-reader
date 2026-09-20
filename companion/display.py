"""
Renders the two screens (list / detail) as PIL images and pushes them to
the Waveshare 4.2" panel.

Not hardware-confirmed yet — unlike pi_client/display_driver.py's IT8951
calls (run and confirmed on the physical 9.7" panel), this hasn't been
tested against the real 4.2" HAT. In particular:

  - Refresh speed: this uses a full refresh (epd.display) on every screen
    change, ~2 seconds on this panel. Some Waveshare epd4in2 driver
    versions expose a partial-refresh call (displayPartial /
    display_Partial, naming varies by version) that's much faster for
    text-only updates — pi_client took a similar path (DU partial refresh
    with periodic full GC16 passes, see its README's "Partial refresh"
    note), but I didn't want to guess at an API that might not match this
    driver's actual version and silently break on first run. Worth
    revisiting once this runs on real hardware.

Assumes Waveshare's official Python library is installed and importable
as `waveshare_epd.epd4in2` — see companion/README.md for install steps
(there's no official pip package).
"""

import logging

from PIL import Image, ImageDraw, ImageFont

import config
import state as state_mod

log = logging.getLogger("companion.display")

_font_title = ImageFont.truetype(config.FONT_PATH_BOLD, 16)
_font_body = ImageFont.truetype(config.FONT_PATH, 13)
_font_small = ImageFont.truetype(config.FONT_PATH, 12)
_font_blurb = ImageFont.truetype(config.FONT_PATH, 13)


def init_epd():
    from waveshare_epd import epd4in2  # deferred import — only needed on the Pi

    epd = epd4in2.EPD()
    epd.init()
    epd.Clear()
    return epd


def push(epd, image):
    epd.display(epd.getbuffer(image))


def sleep(epd):
    epd.sleep()


def render(app_state):
    if app_state.view == state_mod.VIEW_DETAIL and app_state.current_item:
        return _render_detail(app_state)
    return _render_list(app_state)


def _blank_canvas():
    img = Image.new("1", (config.EPD_WIDTH, config.EPD_HEIGHT), 255)
    return img, ImageDraw.Draw(img)


def _render_list(app_state):
    img, draw = _blank_canvas()
    w, h = config.EPD_WIDTH, config.EPD_HEIGHT

    draw.text((12, 8), app_state.program.get("name", "Program"), font=_font_title, fill=0)
    draw.line((12, 30, w - 12, 30), fill=0)

    items = app_state.items
    row_h = (h - 60) // max(len(items), 1) if items else h - 60
    row_h = min(row_h, 46)
    y = 38

    for i, item in enumerate(items):
        is_cursor = i == app_state.cursor_index
        is_playing = item.get("id") == app_state.now_playing_score_id

        if is_cursor:
            draw.rectangle((8, y - 2, w - 8, y + row_h - 6), outline=0, width=2)

        label = f"{item.get('order', i + 1)}. {item.get('composer') or ''}"
        draw.text((16, y), label, font=_font_body, fill=0)
        draw.text((16, y + 16), item.get("title") or "", font=_font_small, fill=0)

        if is_playing:
            badge = "now playing"
            bw = draw.textlength(badge, font=_font_small)
            draw.text((w - 16 - bw, y + 4), badge, font=_font_small, fill=0)

        y += row_h
        if y > h - 30:
            break  # more items than fit one screen — pagination is a v2 problem

    draw.line((12, h - 26, w - 12, h - 26), fill=0)
    draw.text((16, h - 20), "< prev", font=_font_small, fill=0)
    draw.text((w // 2 - 20, h - 20), "select", font=_font_small, fill=0)
    draw.text((w - 60, h - 20), "next >", font=_font_small, fill=0)

    return img


def _render_detail(app_state):
    img, draw = _blank_canvas()
    w, h = config.EPD_WIDTH, config.EPD_HEIGHT
    item = app_state.current_item

    pos = f"{app_state.cursor_index + 1} of {len(app_state.items)}"
    draw.text((12, 8), pos, font=_font_small, fill=0)

    draw.text((12, 26), item.get("composer") or "", font=_font_title, fill=0)
    draw.text((12, 48), item.get("title") or "", font=_font_body, fill=0)

    instrument = item.get("instrument")
    if instrument:
        draw.text((12, 66), instrument, font=_font_small, fill=0)

    draw.line((12, 88, w - 12, 88), fill=0)
    _draw_wrapped(draw, item.get("blurb") or "", (12, 96), w - 24, _font_blurb)

    is_playing = item.get("id") == app_state.now_playing_score_id
    footer_label = "now playing" if is_playing else "piece detail"

    draw.line((12, h - 26, w - 12, h - 26), fill=0)
    draw.text((16, h - 20), "< prev", font=_font_small, fill=0)
    fw = draw.textlength(footer_label, font=_font_small)
    draw.text((w / 2 - fw / 2, h - 20), footer_label, font=_font_small, fill=0)
    draw.text((w - 60, h - 20), "next >", font=_font_small, fill=0)

    return img


def _draw_wrapped(draw, text, xy, max_width, font, line_height=17):
    x, y = xy
    words = text.split()
    line = ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            line = trial
        else:
            draw.text((x, y), line, font=font, fill=0)
            y += line_height
            line = word
    if line:
        draw.text((x, y), line, font=font, fill=0)
