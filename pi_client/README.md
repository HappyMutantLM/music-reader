# Pi e-ink display client

Runs on the Pi (4B now, CM4 for the final build) and drives the
Waveshare 9.7" IT8951 panel: fetches rendered pages from the FastAPI
backend and turns pages via the AirTurn pedal.

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
| `PANEL_FULL_REFRESH_EVERY` | `10` | Page turns between full GC16 refreshes (partial DU turns in between) |
| `PEDAL_DEVICE_NAME_HINT` | `AirTurn` | Substring match against `/dev/input` device names |
| `PEDAL_KEY_NEXT` / `PEDAL_KEY_PREV` | `KEY_RIGHT` / `KEY_LEFT` | AirTurn factory defaults — update if AirTurn Manager remapped the pedal |
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
- **Partial refresh: done, not yet hardware-tested.** Page turns now use
  `draw_partial(DisplayModes.DU)` (fast, black/white-only) instead of a
  full `GC16` redraw every time; every `PANEL_FULL_REFRESH_EVERY` turns
  (default 10) a full `GC16` pass runs instead to clear the ghosting DU
  leaves behind. This was written against the driver's actual
  `AutoDisplay.draw_partial`/`draw_full` source (it tracks `prev_frame`
  and diffs automatically — no manual dirty-rect code needed here), but
  hasn't been run on the physical panel yet. **Before trusting it at a
  gig:** run through a real score, check DU turns are legible and fast,
  and watch a few full-refresh cycles for correctness. If ghosting is
  still visible before the Nth turn, lower `PANEL_FULL_REFRESH_EVERY`;
  if the periodic flicker is more distracting than faint ghosting,
  raise it.
- **Retry/backoff: done.** `api_client.py` now retries connection-level
  failures (NAS asleep, Wi-Fi drop) 3x with 0.5s/1s backoff before
  raising `ApiError`. Non-200 HTTP responses (bad score id, etc.) are
  not retried — a retry won't fix those. Still surfaces as an on-panel
  error message via `show_message()` rather than crashing the client.
