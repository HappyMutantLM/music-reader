# Companion e-ink display

A second, small e-ink device (Pi Zero 2 W + Waveshare 4.2" + PiSugar S +
3 buttons + NeoPixel button lights) passed around during a performance so
guests can browse the evening's program and read a short note on
whatever's playing, in place of a printed program. Talks to the same
FastAPI backend as `pi_client/`, via `routers/companion.py`.

**Nothing here has been run on real hardware yet** — unlike `pi_client/`,
which has hardware-confirmed notes throughout its own README from actual
runs on the Pi 4B + IT8951 panel. Treat this as a first pass to test on
the actual companion build, not a verified one.

## Setup

```
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`--system-site-packages` matters here too, same reasoning as
`pi_client/README.md` — lets the venv see apt-installed GPIO/SPI libs
that aren't pip-installable on Trixie.

Waveshare's e-paper library isn't on PyPI:
```
git clone https://github.com/waveshareteam/e-Paper.git
cp -r e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd .venv/lib/python*/site-packages/
```

Enable SPI first: `sudo raspi-config` → Interface Options → SPI → enable, then reboot.

## Configure

Everything lives in `config.py`, overridable via env vars:

| Env var | Default | Notes |
|---|---|---|
| `MUSIC_SERVER_URL` | `http://memoryalpha:8000` | Same NAS backend as `pi_client` |
| `COMPANION_SETLIST_ID` | `1` | Which evening's program to load — or pass `--setlist-id` |
| `COMPANION_POLL_SECONDS` | `8` | How often to check for the live now-playing badge |
| `COMPANION_CACHE_PATH` | `~/.companion_program_cache.json` | Local fallback if the NAS drops off Wi-Fi mid-evening |
| `COMPANION_PIN_PREV` / `_SELECT` / `_NEXT` | `5` / `6` / `12` | BCM pins for the three nav buttons |
| `COMPANION_LED_BRIGHTNESS` | `60` | NeoPixel brightness, 0-255 — kept dim on purpose |

## Run

```
sudo python3 main.py --setlist-id 3
```

`sudo` is needed for the NeoPixels' PWM/DMA access on GPIO18. Once it
runs cleanly, install as a service:
```
sudo cp companion.service /etc/systemd/system/
sudo systemctl enable --now companion
```

## Known gaps / next steps

- **Partial refresh: not implemented.** Every screen change does a full
  refresh (`epd.display()`), ~2 seconds on this panel. `pi_client` solved
  the equivalent problem with `draw_partial(DisplayModes.DU)` plus a
  periodic full `GC16` pass — worth doing the same here once this driver
  version's actual partial-refresh API (naming varies) is confirmed
  against real hardware.
- **NeoPixel RGBW color calls: unverified.** `leds.py` sets color via
  `setPixelColorRGB` and leaves the white channel unused — `rpi_ws281x`'s
  API for the white channel varies by version/fork, so check the
  installed version's actual signature before relying on it.
- **PiSugar's own power button isn't wired into this code at all** —
  that's handled entirely by PiSugar's onboard hardware/daemon, separate
  from this firmware.
- **No pagination** for a program with enough pieces that they don't fit
  one screen (see the `# more items than fit` comment in `display.py`).
- **No sleep/wake on inactivity** — the panel stays live the whole time
  the process runs.
- **`POST /now-playing` (routers/companion.py) isn't triggered by
  anything yet.** It exists for whatever ends up marking a setlist
  advance on the performer's side — not built.
