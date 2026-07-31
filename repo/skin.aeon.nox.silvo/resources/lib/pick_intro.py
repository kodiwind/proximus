# -*- coding: utf-8 -*-
"""
Manual trigger for Aeon Nox: SiLVO's "Random (Cloud)" startup intro.

Invoked directly by the skin via:
    RunScript(special://skin/resources/lib/pick_intro.py)

This runs when the user switches the startup-intro mode to "Random
(Cloud)" in Settings > Interface (see 16x9/Includes_Select.xml). It
primes Skin.String(StartupIntro) with a first pick right away, instead
of making the user wait for the background service's next scheduled
run (service.py, ~15s after the *next* Kodi start) before anything is
queued up to play.
"""
import xbmc

import randomintro

if __name__ == "__main__":
    try:
        randomintro.refresh(reason="manual")
    except Exception as exc:  # noqa: BLE001 - must never crash the skin's settings menu
        xbmc.log(
            "[skin.aeon.nox.silvo] RandomCloudIntro: manual pick failed: {0}".format(exc),
            xbmc.LOGERROR,
        )
