# -*- coding: utf-8 -*-
"""
Random Cloud Intro - core logic for Aeon Nox: SiLVO.

Aeon Nox already has a built-in "startup intro" feature: whatever path
is stored in Skin.String(StartupIntro) gets played once, full-screen,
the next time Kodi boots (see 16x9/custom_1101_Startup.xml), and Kodi
then continues its normal startup flow automatically.

This module adds a *random remote* source for that feature. Instead of
a single fixed file, a filename is chosen at random from a manifest.txt
hosted alongside the intro videos in cloud storage, and the resulting
URL is streamed directly (no local download/caching), per Steve's
choice for this feature.

Because Kodi's Startup window reads Skin.String(StartupIntro)
synchronously right at boot -- before any Python service has a
realistic chance to finish a network call -- this module does NOT try
to pick an intro live at boot. Instead, a background service
(../../service.py) calls refresh() a short while *after* each Kodi
start, which prepares the pick for the *next* boot. Whatever was
already stored from the previous session is what plays on the current
boot, so there is always something ready and no startup delay.

Only acts when "Random (Cloud)" is the active startup-intro mode
(tracked by the ENABLED_SETTING skin bool, set from the skin's
Settings > Interface menu). If the user has chosen Off, the bundled
default, or a manually browsed file instead, refresh() is a no-op and
leaves their choice untouched.
"""
import random

try:
    # Python 3 (Kodi Omega and above)
    import urllib.request as urllib_request
    import urllib.error as urllib_error
except ImportError:  # pragma: no cover - defensive only
    import urllib2 as urllib_request  # type: ignore
    urllib_error = urllib_request

import xbmc
import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")

# Remote source. manifest.txt is a plain text file, one intro filename
# per line, living alongside the videos themselves.
BASE_URL = "https://filedn.com/l0jm1ttNAy54e9NylPPsPVk/Intros/random_intros/"
MANIFEST_URL = BASE_URL + "manifest.txt"

# Bundled fallback used when the remote manifest can't be reached.
FALLBACK_INTRO = "special://skin/extras/intro.mp4"
FALLBACK_LABEL = "intro.mp4"

# Keep short - this must never be allowed to hang Kodi.
TIMEOUT_SECONDS = 8

# Skin setting (Skin.SetBool / Skin.HasSetting) that marks "Random
# (Cloud)" as the active startup-intro mode. Set/unset from
# 16x9/Includes_Select.xml (SelectStartupIntro).
ENABLED_SETTING = "RandomCloudIntro.Enabled"

# Existing skin string the built-in startup-intro player reads from.
STARTUP_INTRO_SETTING = "StartupIntro"

# Friendly filename-only string, used purely for display in
# SkinSettings.xml (see Variables.xml: StartupIntroLabelVar).
STARTUP_INTRO_FILE_SETTING = "StartupIntroFile"


def log(message, level=xbmc.LOGINFO):
    xbmc.log("[{0}] RandomCloudIntro: {1}".format(ADDON_ID, message), level)


def is_enabled():
    """True if 'Random (Cloud)' is the currently selected startup-intro mode."""
    return xbmc.getCondVisibility("Skin.HasSetting({0})".format(ENABLED_SETTING))


def get_current_intro():
    """The intro URL currently queued to play on the next boot, if any."""
    return xbmc.getInfoLabel("Skin.String({0})".format(STARTUP_INTRO_SETTING))


def set_startup_intro(url, label=None):
    xbmc.executebuiltin("Skin.SetString({0},{1})".format(STARTUP_INTRO_SETTING, url))
    if label is not None:
        xbmc.executebuiltin("Skin.SetString({0},{1})".format(STARTUP_INTRO_FILE_SETTING, label))


def fetch_manifest():
    """Return the list of filenames listed in manifest.txt, or None on failure."""
    try:
        request = urllib_request.Request(
            MANIFEST_URL, headers={"User-Agent": "Kodi-skin.aeon.nox.silvo"}
        )
        response = urllib_request.urlopen(request, timeout=TIMEOUT_SECONDS)
        try:
            raw = response.read().decode("utf-8", "ignore")
        finally:
            response.close()
    except Exception as exc:  # noqa: BLE001 - any network/parsing failure is a soft failure
        log("Could not reach manifest at {0}: {1}".format(MANIFEST_URL, exc), xbmc.LOGWARNING)
        return None

    files = [line.strip() for line in raw.splitlines() if line.strip() and not line.startswith("#")]
    if not files:
        log("Manifest fetched but contained no usable entries.", xbmc.LOGWARNING)
        return None
    return files


def pick_next_intro():
    """
    Pick a random intro filename from the manifest, trying not to repeat
    whatever is currently queued. Returns (url, filename) or (None, None)
    if the manifest could not be read.
    """
    files = fetch_manifest()
    if not files:
        return None, None

    current = get_current_intro()
    if current and len(files) > 1:
        candidates = [name for name in files if (BASE_URL + name) != current]
        if candidates:
            files = candidates

    choice = random.choice(files)
    return BASE_URL + choice, choice


def refresh(reason="scheduled"):
    """
    Pick a fresh random intro for the *next* boot and store it in
    Skin.String(StartupIntro). Falls back to the skin's bundled
    extras/intro.mp4 if the remote manifest can't be reached, so an
    intro still plays instead of nothing.

    No-op if "Random (Cloud)" is not the currently selected
    startup-intro mode.
    """
    if not is_enabled():
        log("Random (Cloud) is not the active startup-intro mode; nothing to do ({0}).".format(reason))
        return

    url, filename = pick_next_intro()
    if url:
        set_startup_intro(url, label=filename)
        log("Queued next intro for the next boot ({0}): {1}".format(reason, filename))
    else:
        set_startup_intro(FALLBACK_INTRO, label=FALLBACK_LABEL)
        log(
            "Manifest unreachable, queued bundled fallback intro instead ({0}).".format(reason),
            xbmc.LOGWARNING,
        )
