"""
Wrapper around GregDMeyer's IT8951 python driver
(https://github.com/GregDMeyer/IT8951). The AutoEPDDisplay(...) call,
.clear(), .frame_buf.paste(...), and .draw_full(constants.DisplayModes.GC16)
sequence below mirrors eink_test.py exactly — the bare-bones script that
was actually run on the Pi 4B + Waveshare 9.7" HAT and confirmed working.
Don't drift from that call shape without re-testing on hardware.

The IT8951 import is deferred into __init__ rather than done at module
load, so this file can still be imported (e.g. for tests) on a machine
with no SPI hardware and no IT8951 package installed.
"""
import io

from PIL import Image, ImageDraw

from config import PANEL_WIDTH, PANEL_HEIGHT, VCOM, SPI_HZ


class EinkDisplay:
    def __init__(self):
        from IT8951 import constants
        from IT8951.display import AutoEPDDisplay

        self._constants = constants
        # rotate=None + these two args match eink_test.py's working call.
        self.display = AutoEPDDisplay(vcom=VCOM, rotate=None, spi_hz=SPI_HZ)
        self.display.clear()  # NOT display.epd.clear() — matches eink_test.py

        # Trust the driver's own reported resolution (also printed by
        # eink_test.py) over the PANEL_WIDTH/PANEL_HEIGHT constants in
        # config.py — those are just the backend's render-target hint,
        # and would silently drift once the planned 13.3" dual-panel
        # upgrade happens.
        self.width = self.display.width
        self.height = self.display.height
        if (self.width, self.height) != (PANEL_WIDTH, PANEL_HEIGHT):
            print(
                f"[display] driver reports {self.width}x{self.height}, "
                f"differs from config PANEL_WIDTH/PANEL_HEIGHT "
                f"({PANEL_WIDTH}x{PANEL_HEIGHT}) — the backend renders "
                "pages for the config size, so a mismatched panel may not "
                "fill the screen correctly until config.py is updated."
            )

    def show_page(self, png_bytes: bytes):
        """Full-refresh redraw of a page image.

        Every page turn does a full GC16 refresh for now — slower and
        more visible flicker than a partial refresh, but ghost-free and
        simple. Partial refresh is a separate not-yet-done task (see
        project notes); swap the draw_full call below for the driver's
        partial-refresh path once that's been tested.
        """
        img = Image.open(io.BytesIO(png_bytes)).convert("L")

        # Center the (already panel-scaled) page on the full panel
        # canvas rather than assume the backend's render exactly fills
        # width x height — routers/pages.py fits by whichever dimension
        # is binding, so one axis is usually smaller.
        canvas = Image.new("L", (self.width, self.height), 0xFF)
        x = (self.width - img.width) // 2
        y = (self.height - img.height) // 2
        canvas.paste(img, (x, y))

        self.display.frame_buf.paste(canvas, (0, 0))
        self.display.draw_full(self._constants.DisplayModes.GC16)

    def show_message(self, text: str):
        """Full-screen plain-text message for errors/status (backend
        unreachable, no score loaded, page fetch failed) — not sheet
        music, just enough feedback that the panel isn't a blank
        mystery when something's wrong."""
        canvas = Image.new("L", (self.width, self.height), 0xFF)
        draw = ImageDraw.Draw(canvas)
        draw.multiline_text((40, self.height // 2 - 20), text, fill=0)
        self.display.frame_buf.paste(canvas, (0, 0))
        self.display.draw_full(self._constants.DisplayModes.GC16)
