# -*- coding: utf-8 -*-
"""
Background service for Aeon Nox: SiLVO (xbmc.service entry point).

Handles the "Random (Cloud)" startup-intro mode. Deliberately waits a
short while after Kodi has started before doing any network work, for
two reasons:

  1. It avoids competing with Kodi's own startup/GUI initialisation
     for CPU and network at the busiest possible moment.
  2. The skin's Startup window (16x9/custom_1101_Startup.xml) reads
     Skin.String(StartupIntro) synchronously right at boot, long
     before this service could realistically finish a network call
     anyway. So there is nothing to gain by racing it - this service
     instead prepares the pick for the *next* boot.

Whatever was already stored in Skin.String(StartupIntro) from the
previous run of this service is what plays on the current boot.
"""
import os
import sys

import xbmc
import xbmcaddon

_ADDON_PATH = xbmcaddon.Addon().getAddonInfo("path")
_LIB_PATH = os.path.join(_ADDON_PATH, "resources", "lib")
if _LIB_PATH not in sys.path:
    sys.path.insert(0, _LIB_PATH)

import randomintro  # noqa: E402  (import after sys.path setup, by design)

STARTUP_DELAY_SECONDS = 15


if __name__ == "__main__":
    monitor = xbmc.Monitor()

    # waitForAbort returns True only if Kodi is shutting down during the
    # wait - in that case, skip the work entirely.
    if not monitor.waitForAbort(STARTUP_DELAY_SECONDS):
        try:
            randomintro.refresh(reason="startup")
        except Exception as exc:  # noqa: BLE001 - a service must never crash/hang Kodi
            xbmc.log(
                "[skin.aeon.nox.silvo] RandomCloudIntro: service failed: {0}".format(exc),
                xbmc.LOGERROR,
            )
