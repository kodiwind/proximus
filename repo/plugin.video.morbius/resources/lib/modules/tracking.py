# -*- coding: utf-8 -*-
"""
Active watched-status dispatcher for Morbius.

Source of truth: settings.watched_indicators()
  0 -> built-in (local watched_db only; callers short-circuit before here)
  1 -> Trakt    (apis.trakt_api + trakt_db)
  2 -> Simkl    (apis.simkl_api + simkl_db)
  3 -> MDBList  (apis.mdblist_api + mdblist_db)

XOR: only one provider owns mark-watched / scrobble / progress / calendar sync.
Trakt, Simkl, and MDBList accounts may still be authorized for browsing personal
lists; list browsing does not go through this module.
"""
from modules import settings


def provider():
	"""Return 'builtin' | 'trakt' | 'simkl' | 'mdblist' from watched_indicators XOR."""
	return {0: 'builtin', 1: 'trakt', 2: 'simkl', 3: 'mdblist'}.get(settings.watched_indicators(), 'builtin')

def is_external():
	return provider() in ('trakt', 'simkl', 'mdblist')

#=========================== READ / SYNC ===========================#
def sync_activities(force_update=False):
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_sync_activities
		return trakt_sync_activities(force_update)
	if p == 'simkl':
		from apis.simkl_api import simkl_sync_activities
		return simkl_sync_activities(force_update)
	if p == 'mdblist':
		from apis.mdblist_api import mdblist_sync_activities
		return mdblist_sync_activities(force_update)
	return 'no account'

def indicators_movies():
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_indicators_movies
		return trakt_indicators_movies()
	if p == 'simkl':
		from apis.simkl_api import simkl_indicators_movies
		return simkl_indicators_movies()
	if p == 'mdblist':
		from apis.mdblist_api import mdblist_indicators_movies
		return mdblist_indicators_movies()

def indicators_tv():
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_indicators_tv
		return trakt_indicators_tv()
	if p == 'simkl':
		from apis.simkl_api import simkl_indicators_tv
		return simkl_indicators_tv()
	if p == 'mdblist':
		from apis.mdblist_api import mdblist_indicators_tv
		return mdblist_indicators_tv()

def playback_progress():
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_playback_progress
		return trakt_playback_progress()
	if p == 'simkl':
		from apis.simkl_api import simkl_playback_progress
		return simkl_playback_progress()
	if p == 'mdblist':
		from apis.mdblist_api import mdblist_playback_progress
		return mdblist_playback_progress()
	return []

#=========================== WRITE ===========================#
def mark_watched(action, media, media_id, tvdb_id=0, season=None, episode=None, key='tmdb'):
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_watched_status_mark
		return trakt_watched_status_mark(action, media, media_id, tvdb_id, season, episode, key)
	if p == 'simkl':
		from apis.simkl_api import simkl_mark_watched
		return simkl_mark_watched(action, media, media_id, tvdb_id, season, episode, key)
	if p == 'mdblist':
		from apis.mdblist_api import mdblist_watched_status_mark
		return mdblist_watched_status_mark(action, media, media_id, tvdb_id, season, episode, key)
	return True

def scrobble(action, media, media_id, percent, season=None, episode=None, resume_id=None, refresh_tracker=False, title=''):
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_progress
		return trakt_progress(action, media, media_id, percent, season, episode, resume_id, refresh_tracker)
	if p == 'simkl':
		from apis.simkl_api import simkl_progress
		return simkl_progress(action, media, media_id, percent, season, episode, resume_id, refresh_tracker, title=title)
	if p == 'mdblist':
		from apis.mdblist_api import mdblist_progress
		return mdblist_progress(action, media, media_id, percent, season, episode, resume_id, refresh_tracker, title=title)

# alias kept for readability at older call sites
progress = scrobble

def official_status(media_type):
	# True == Morbius should perform its own scrobble/mark; False == an external scrobbler owns it.
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_official_status
		return trakt_official_status(media_type)
	if p == 'simkl':
		from apis.simkl_api import simkl_official_status
		return simkl_official_status(media_type)
	return True

def clear_watchlist_data(list_type, media_type):
	p = provider()
	if p == 'trakt':
		from caches.trakt_cache import clear_trakt_collection_watchlist_data
		return clear_trakt_collection_watchlist_data(list_type, media_type)
	if p == 'simkl':
		from caches.simkl_cache import clear_simkl_status_data
		return clear_simkl_status_data()

def get_hidden_items(list_type):
	if provider() == 'trakt':
		from apis.trakt_api import trakt_get_hidden_items
		return trakt_get_hidden_items(list_type)
	return None

def get_my_calendar(recently_aired, current_date, calendar_provider=None):
	"""
	calendar_provider: optional override ('simkl'|'trakt') for menus that force a provider
	even when it is not the active XOR tracker (e.g. Simkl Calendar under My Content).
	"""
	p = calendar_provider or provider()
	if p == 'simkl':
		from apis.simkl_api import simkl_get_my_calendar
		return simkl_get_my_calendar(recently_aired, current_date)
	from apis.trakt_api import trakt_get_my_calendar
	return trakt_get_my_calendar(recently_aired, current_date)

def watchlist_shows():
	p = provider()
	if p == 'trakt':
		from apis.trakt_api import trakt_watchlist
		return trakt_watchlist('watchlist', 'tvshow')
	if p == 'simkl':
		from apis.simkl_api import simkl_status_list
		return simkl_status_list('plantowatch', 'tvshow')
	return []
