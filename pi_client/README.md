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
- **Full refresh (GC16) on every page turn.** Slower and more visible
  flicker than a partial refresh. Partial refresh is a separate,
  not-yet-done task — swap the `draw_full` call in
  `display_driver.py::show_page` once that's tested.
- **`display_driver.py`'s IT8951 calls mirror `eink_test.py`** (the
  script that was actually run and confirmed working on the Pi 4B +
  Waveshare 9.7" HAT) — same `AutoEPDDisplay(vcom=..., rotate=None,
  spi_hz=...)` call, `.clear()` (not `.epd.clear()`), and
  `draw_full(constants.DisplayModes.GC16)`. Canvas size comes from the
  driver's own reported `display.width/height`, not a hardcoded
  constant, so this should carry over cleanly to the 13.3" panels later.
- Network hiccups (NAS asleep, Wi-Fi drop) surface as an on-panel error
  message via `show_message()` rather than crashing the client, but
  there's no automatic retry/backoff yet.
