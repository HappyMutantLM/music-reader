# Pi e-ink display client

Runs on the Pi (4B now, CM4 for the final build) and drives the
Waveshare 9.7" IT8951 panel: fetches rendered pages from the FastAPI
backend and turns pages via the PageFlip Dragonfly pedal.

## Setup

```
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install git+https://github.com/GregDMeyer/IT8951.git
```

`--system-site-packages` matters on Raspberry Pi OS 13 (Trixie) — it lets
the venv see the apt-installed `RPi.GPIO`/`rpi-lgpio` shim and SPI libs,
which aren't pip-installable there.

## Configure

Everything lives in `config.py`, overridable via env vars:

| Env var | Default | Notes |
|---|---|---|
| `MUSIC_SERVER_URL` | `http://memoryalpha:8000` | FastAPI backend on the NAS |
| `PANEL_VCOM` | `-1.87` | **Printed on the panel's ribbon cable** — never guess this |
| `PANEL_SPI_HZ` | `24000000` | SPI clock speed |
| `PANEL_ROTATE` | `CW` | Compensates for the enclosure mounting the panel in portrait (90° from its native 1200x825 landscape orientation). One of `CW`/`CCW`/`flip`/empty. **Hardware-confirmed correct** on Leila's enclosure — leave as `CW` unless the panel is remounted differently. |
| `PANEL_BW_THRESHOLD` | `200` | Grayscale pixels this light or lighter become pure white before every draw (rest become pure black) — keeps anti-aliased text/lines from washing out under DU/GC16. Lower toward `0` if text looks too bold; raise toward `255` if thin lines are still dropping out. |
| `PANEL_FULL_REFRESH_EVERY` | `10` | Page turns between full GC16 refreshes (partial DU turns in between) |
| `PEDAL_DEVICE_NAME_HINT` | `PageFlip` | Substring match against `/dev/input` device names. Matches "PageFlip Dragonfly" (V5+ pedals, USB-C port). Pedals marked V4 or earlier broadcast as "Quad Pedal" instead — check the version label on the underside of the pedal and set this to `Quad Pedal` if so. |
| `PEDAL_KEY_NEXT` / `PEDAL_KEY_PREV` | `KEY_DOWN` / `KEY_UP` | **Hardware-confirmed** — left pedal pages back, right pedal pages forward |
| `READER_STATE_FILE` | `~/.music_reader_state.json` | Last (score_id, page_number) |

Find the pedal's actual device name and key codes with:

```
python pedal_input.py --probe
```

## Run

```
python reader.py --score-id 12
```

Subsequent runs resume the last score/page automatically — omit
`--score-id` once state exists.

## Known gaps / next steps

- **Panel rotation: fixed and hardware-confirmed.** The enclosure mounts
  the panel in portrait, but `display_driver.py` was telling the IT8951
  driver `rotate=None` (copied from `eink_test.py`, which was only ever
  tested with the bare panel on a desk). That made pages render sideways
  and only partially fill the panel — the landscape-fitted image occupied
  just part of the rotated framebuffer. Fixed by passing `PANEL_ROTATE`
  (default `CW`) through to `AutoEPDDisplay`, and pointing
  `PANEL_WIDTH`/`PANEL_HEIGHT` (here and on the backend) at the resulting
  portrait shape (825x1200) so pages render to fill the actual usable
  area instead of a landscape box. Confirmed on hardware: `CW` is the
  correct direction for this enclosure.
- **Faint/broken-up text: two stacked bugs, now fixed and confirmed.**
  (1) The very first page of a session was going through the fast DU
  (1bpp, black/white-only) refresh path instead of a proper grayscale
  GC16 draw — `clear()` in `display_driver.py`'s `__init__` only blanks
  the panel, it never draws real content, so seeding the "turns since
  full refresh" counter at 0 was wrong. Now seeded at `FULL_REFRESH_EVERY`
  so the first page always forces a full GC16 draw. (2) Nothing was
  thresholding the backend's anti-aliased grayscale renders to pure
  black/white before display, so thin/anti-aliased strokes could wash
  out under DU (and even under GC16, once printed to actual e-ink
  pigment). Fixed via `PANEL_BW_THRESHOLD` above, applied to every page
  before it's pasted onto the panel canvas. Confirmed on hardware: pages
  now display crisp and complete.
- **Pedal key codes: hardware-confirmed.** The project switched from an
  AirTurn pedal to a PageFlip Dragonfly. Per the Dragonfly's manual, its
  *primary* (larger) pedals never send Left/Right Arrow in any of its
  five preset modes — only Stop/Play, Up/Down Arrow, or Space/Enter.
  Left/Right Arrow is exclusively a *secondary* (small, top) pedal
  function on that device. `PEDAL_KEY_NEXT`/`PEDAL_KEY_PREV` default to
  `KEY_DOWN`/`KEY_UP`, and on Leila's unit that maps left pedal = page
  back, right pedal = page forward, exactly as wanted. If the pedal is
  ever re-paired or reprogrammed via the PageFlip app to a different
  mode, re-check with `python pedal_input.py --probe`.
- **Pedal device-name hint depends on hardware version.** `PEDAL_DEVICE_NAME_HINT`
  defaults to `PageFlip`, matching a V5+ Dragonfly's Bluetooth name
  ("PageFlip Dragonfly"). A pre-V5 pedal broadcasts as "Quad Pedal"
  instead and won't be found with this hint — check the version label on
  the pedal's underside.
- **No on-panel score picker.** Score is chosen via `--score-id` or by
  editing the state file directly. A future "browse the library"
  screen would remove this.
- **`display_driver.py`'s IT8951 calls mirror `eink_test.py`** (the
  script that was actually run and confirmed working on the Pi 4B +
  Waveshare 9.7" HAT) — same `AutoEPDDisplay(vcom=..., rotate=None,
  spi_hz=...)` call and `.clear()` (not `.epd.clear()`). Canvas size
  comes from the driver's own reported `display.width/height`, not a
  hardcoded constant, so this should carry over cleanly to the 13.3"
  panels later.
- **Partial refresh: done and hardware-confirmed.** Page turns now use
  `draw_partial(DisplayModes.DU)` (fast, black/white-only) instead of a
  full `GC16` redraw every time; every `PANEL_FULL_REFRESH_EVERY` turns
  (default 10) a full `GC16` pass runs instead to clear the ghosting DU
  leaves behind. This was written against the driver's actual
  `AutoDisplay.draw_partial`/`draw_full` source (it tracks `prev_frame`
  and diffs automatically — no manual dirty-rect code needed here), and
  has now been run through a real score on the physical panel with the
  pedal driving page turns. If ghosting becomes visible before the Nth
  turn, lower `PANEL_FULL_REFRESH_EVERY`; if the periodic flicker is more
  distracting than faint ghosting, raise it.
- **Retry/backoff: done.** `api_client.py` now retries connection-level
  failures (NAS asleep, Wi-Fi drop) 3x with 0.5s/1s backoff before
  raising `ApiError`. Non-200 HTTP responses (bad score id, etc.) are
  not retried — a retry won't fix those. Still surfaces as an on-panel
  error message via `show_message()` rather than crashing the client.
