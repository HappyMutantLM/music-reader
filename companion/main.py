"""
Entry point for the companion e-ink display. Ties together: initial
program fetch, the e-paper display, the three buttons, the NeoPixel
indicators, and a background thread that polls for the "now playing"
badge.

    python main.py                    # loads config.SETLIST_ID
    python main.py --setlist-id 3     # overrides it for this run

Threading model, kept deliberately simple:
  - Button presses (gpiozero callbacks) only ever mutate AppState and
    flash an LED. They never touch the display directly.
  - One background thread polls now-playing and mutates AppState.
  - The main loop is the only thing that ever calls display.push() — so
    there's never a risk of two threads fighting over the e-paper driver.

Not hardware-confirmed — see display.py and leds.py for the specific
unknowns (partial refresh, RGBW call signature).
"""

import argparse
import logging
import threading
import time

import api_client
import config
import display
import leds
from state import AppState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("companion.main")


def now_playing_poll_loop(app_state, stop_event):
    while not stop_event.is_set():
        score_id = api_client.get_now_playing()
        if score_id is not None:
            app_state.set_now_playing(score_id)
        stop_event.wait(config.NOW_PLAYING_POLL_SECONDS)


def make_button_handlers(app_state, strip):
    def on_prev():
        app_state.move_cursor(-1)
        leds.flash_press(strip, leds.IDX_PREV)

    def on_next():
        app_state.move_cursor(1)
        leds.flash_press(strip, leds.IDX_NEXT)

    def on_select():
        app_state.select()
        leds.flash_press(strip, leds.IDX_SELECT)

    return on_prev, on_select, on_next


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setlist-id", type=int, default=None,
                         help="Override config.SETLIST_ID for this run")
    args = parser.parse_args()
    if args.setlist_id is not None:
        config.SETLIST_ID = args.setlist_id

    log.info("Fetching program for setlist %s...", config.SETLIST_ID)
    program = api_client.fetch_program()
    app_state = AppState(program)

    log.info("Initializing e-paper display...")
    epd = display.init_epd()

    log.info("Initializing NeoPixels...")
    strip = leds.init_strip()
    leds.idle_all(strip)

    log.info("Initializing buttons...")
    from gpiozero import Button

    on_prev, on_select, on_next = make_button_handlers(app_state, strip)
    btn_prev = Button(config.PIN_BUTTON_PREV, pull_up=True, bounce_time=config.BUTTON_BOUNCE_SECONDS)
    btn_select = Button(config.PIN_BUTTON_SELECT, pull_up=True, bounce_time=config.BUTTON_BOUNCE_SECONDS)
    btn_next = Button(config.PIN_BUTTON_NEXT, pull_up=True, bounce_time=config.BUTTON_BOUNCE_SECONDS)
    btn_prev.when_pressed = on_prev
    btn_select.when_pressed = on_select
    btn_next.when_pressed = on_next

    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=now_playing_poll_loop, args=(app_state, stop_event), daemon=True
    )
    poll_thread.start()

    display.push(epd, display.render(app_state))  # initial draw

    try:
        while True:
            if app_state.take_dirty():
                leds.set_now_playing_indicator(
                    strip,
                    app_state.current_item is not None
                    and app_state.current_item.get("id") == app_state.now_playing_score_id,
                )
                display.push(epd, display.render(app_state))
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        display.sleep(epd)


if __name__ == "__main__":
    main()
