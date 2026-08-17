# -*- coding: utf-8 -*-
"""
MDBList (mdblist.com) account pairing + watched-status provider + My Lists.

Mirrors the shape of trakt_api.py / simkl_api.py (all auth + API logic lives
in this one file, no separate auth module — matches this codebase's existing
convention), but MDBList's own auth is dramatically simpler than either:
it's a bring-your-own personal API key sent as a `?apikey=` query parameter
on every request (confirmed live against api.mdblist.com's own OpenAPI
schema, 2026: `securitySchemes.apiKey: {type: apiKey, in: query, name: apikey}`).
There is no client_id/secret/device-code/PIN flow at all.

SECURITY: the user's own MDBList API key lives ONLY in Kodi's Settings
storage (morbius.mdblist.api_key, via get_setting/set_setting), read fresh on
every call — never hardcoded here or anywhere else in this codebase. Default
value is empty string; morbius.mdblist.user defaults to 'empty_setting' (the
same sentinel convention trakt.user/simkl.user already use to mean
"not paired").

Endpoints used below were confirmed live against api.mdblist.com's OpenAPI
schema (GET https://api.mdblist.com/schema/) and, for the sync/scrobble
shapes, against the already-shipped plugin.video.starfleet MDBList
integration (resources/lib/mdblist_sync.py / mdblist_auth.py):
  - GET  /user                       - verify a key, returns {username, ...}
  - GET  /lists/user                 - the caller's own lists:
        [{id, name, slug, items, likes, ranked}, ...]
  - GET  /lists/{listid}/items       - a list's contents, cursor-paginated:
        {movies: [{id, title, imdb_id, ids:{imdb,tmdb,tvdb}, mediatype,
                   release_year, ...}], shows: [...same shape...],
         seasons: [...], episodes: [...], pagination: {...}}
  - GET  /sync/last_activities       - {watched_at, episode_watched_at, ...}
        used purely as a cheap "did anything change" watermark.
  - GET  /sync/watched?mediatype=... - full watched snapshot (movies/shows).
  - POST /sync/watched               - add watched entries.
  - POST /sync/watched/remove        - remove watched entries.
  - POST /scrobble/start|pause|stop|clear - playback progress.

KNOWN SIMPLIFICATION (documented, not a silent gap): Trakt/Simkl each carry
a bespoke delta-merge/removals-reconciliation cache (trakt_cache.py /
simkl_cache.py) that incrementally patches a local mirror. MDBList's own
sync endpoints DO support incremental pulls (`/sync/watched?since=...`), but
replicating that whole merge engine here was judged out of scope for this
pass. Instead, mdblist_sync_activities() does a straightforward "did the
watermark move -> pull a fresh full watched snapshot -> replace the local
rows" sync. This is correct and live, just less network-efficient than
Trakt/Simkl's incremental engine for very large libraries. There is also no
background MDBListMonitor service (unlike TraktMonitor/SimklMonitor in
service.py) - sync runs on pairing and opportunistically; add one later if
periodic background resync turns out to matter in practice.
"""
import time
import requests
from threading import Thread
from caches.base_cache import connect_database
from caches.lists_cache import lists_cache, lists_cache_object
from caches.settings_cache import get_setting, set_setting
from modules import kodi_utils, settings

sleep, notification, logger = kodi_utils.sleep, kodi_utils.notification, kodi_utils.logger
confirm_dialog, kodi_refresh = kodi_utils.confirm_dialog, kodi_utils.kodi_refresh
empty_setting_check = (None, 'empty_setting', '')
MDBLIST_ENDPOINT = 'https://api.mdblist.com%s'
timeout = 15
# Confirmed live 2026-08-15 against the account's own GET /user response
# ({"rate_limit":1000,"rate_limit_reset":<midnight-UTC epoch>,...}) - this is
# a 1000/day budget with no visible per-second limit at all, not something
# that needs sub-second self-throttling for a one-off interactive fetch (a
# few requests opening a screen, then long idle gaps). The original 0.3s
# floor was stacking real, felt delay on top of MDBList's own already-
# nontrivial ~300ms round-trip time (confirmed live) every single request,
# which is what was actually making list/catalog population noticeably
# slower than Trakt's equivalent (a single request, no gate at all on
# Trakt's own side). Lowered to a much smaller floor that still guards
# against a genuine request-storm bug without meaningfully throttling
# normal browsing.
MIN_REQUEST_GAP = 0.05
_last_request = [0.0]

def _rate_gate():
	wait = MIN_REQUEST_GAP - (time.time() - _last_request[0])
	if wait > 0: sleep(int(wait * 1000))
	_last_request[0] = time.time()

def _api_key():
	return get_setting('morbius.mdblist.api_key', '')

def no_client_key():
	notification('Please Enter a Valid MDBList API Key')
	return None

def call_mdblist(path, params=None, data=None, method=None):
	api_key = _api_key()
	if api_key in empty_setting_check: return no_client_key()
	call_params = dict(params or {}); call_params['apikey'] = api_key
	headers = {'Content-Type': 'application/json'}
	def send_query():
		_rate_gate()
		try:
			if method == 'post' or data is not None:
				return requests.post(MDBLIST_ENDPOINT % path, params=call_params, json=data, headers=headers, timeout=timeout)
			return requests.get(MDBLIST_ENDPOINT % path, params=call_params, headers=headers, timeout=timeout)
		except Exception as e:
			logger('MDBList Error', str(e))
			return None
	backoffs = (1, 2, 4)
	attempt = 0
	while True:
		response = send_query()
		if response is None: return None
		status_code = response.status_code
		if status_code == 403:
			try: err = (response.json() or {}).get('error', '')
			except: err = ''
			logger('MDBList Auth Error', '%s -> %s' % (path, err or 'invalid API key'))
			return None
		if status_code == 429 or 500 <= status_code < 600:
			if attempt < len(backoffs):
				sleep(backoffs[attempt] * 1000)
				attempt += 1
				continue
			return None
		if status_code == 204: return {'result': 'OK'}
		try: response.encoding = 'utf-8'
		except: pass
		try: return response.json()
		except: return None

#=========================== Pairing ===========================#
def mdblist_get_user():
	return call_mdblist('/user')

def mdblist_authenticate(dummy=''):
	current = get_setting('morbius.mdblist.api_key', '')
	default_value = '' if current in empty_setting_check else current
	new_key = kodi_utils.kodi_dialog().input('Enter Your MDBList API Key (from mdblist.com/preferences)', defaultt=default_value)
	if not new_key: return False
	new_key = new_key.strip()
	set_setting('mdblist.api_key', new_key)
	user = mdblist_get_user()
	if not isinstance(user, dict) or not user.get('username'):
		set_setting('mdblist.api_key', '')
		notification('MDBList: Invalid API Key', 3000)
		return False
	set_setting('mdblist.user', str(user.get('username')))
	kodi_utils.set_property('morbius.mdblist.user', get_setting('mdblist.user') or get_setting('morbius.mdblist.user'))
	notification('MDBList Account Authorized', 3000)
	# XOR: offer to make MDBList the active watched-status provider (value 3).
	if settings.watched_indicators() != 3:
		if (not settings.trakt_user_active() and not settings.simkl_user_active()) or confirm_dialog(
				heading='Active Tracker', text='Make MDBList your active watched-status provider now?[CR]Choose No to keep your current provider.'):
			set_setting('watched_indicators', '3')
	sleep(500)
	Thread(target=mdblist_sync_activities, kwargs={'force_update': True}).start()
	kodi_refresh()
	return True

def mdblist_revoke_authentication(dummy=''):
	set_setting('mdblist.user', 'empty_setting')
	set_setting('mdblist.api_key', '')
	if settings.watched_indicators() == 3:
		if settings.trakt_user_active() and confirm_dialog(heading='Active Tracker', text='Switch watched-status provider to Trakt?[CR]Choose No to use built-in tracking.'):
			set_setting('watched_indicators', '1')
		elif settings.simkl_user_active() and confirm_dialog(heading='Active Tracker', text='Switch watched-status provider to Simkl?[CR]Choose No to use built-in tracking.'):
			set_setting('watched_indicators', '2')
		else: set_setting('watched_indicators', '0')
	kodi_utils.set_property('morbius.mdblist.user', 'empty_setting')
	clear_all_mdblist_cache_data(silent=True, refresh=False)
	notification('MDBList Account Authorization Reset', 3000)
	kodi_refresh()

#=========================== My Lists ===========================#
def _ids_object(item):
	ids = item.get('ids') or {}
	tmdb_id = ids.get('tmdb') or item.get('id')
	imdb_id = ids.get('imdb') or item.get('imdb_id')
	return tmdb_id, imdb_id

def mdblist_user_lists():
	def _process(_dummy):
		result = call_mdblist('/lists/user', params={'sort': 'name'})
		return result if isinstance(result, list) else []
	return lists_cache_object(_process, 'mdblist_user_lists', 'dummy')

def _fetch_list_items(list_id):
	# Combine movies + shows into one flat list, matching tmdb_lists.py's own
	# get_tmdb_list() shape: {'id': tmdb_id, 'media_type': 'movie'/'tv', 'title':..., 'release_date':...}.
	# Page cap confirmed live 2026-08-15 as the real reason MDBList list-populating
	# was noticeably slower than Trakt's equivalent: Trakt's own list-items call
	# (trakt_api.py's get_trakt_list_contents) is a SINGLE request regardless of
	# list size (extended=full, no pagination at all on Trakt's side) - MDBList's
	# API is cursor-paginated instead, and cursor pagination can't be parallelized
	# (each page's cursor only exists after the previous page's response), so this
	# was previously paying up to 20 sequential round-trips before the screen
	# populated even once. Lowered to a cap that still covers any realistic
	# personal list size while cutting the worst case by 4x.
	items, cursor, pages = [], None, 0
	while pages < 5:
		params = {'limit': 200}
		if cursor: params['cursor'] = cursor
		data = call_mdblist('/lists/%s/items' % list_id, params=params)
		if not isinstance(data, dict): break
		for bucket, media_type in (('movies', 'movie'), ('shows', 'tv')):
			for entry in data.get(bucket) or []:
				try:
					tmdb_id, imdb_id = _ids_object(entry)
					if not tmdb_id: continue
					items.append({'id': tmdb_id, 'imdb_id': imdb_id, 'media_type': media_type, 'title': entry.get('title', ''),
									'release_date': '%s-01-01' % entry['release_year'] if entry.get('release_year') else None})
				except: continue
		pagination = data.get('pagination') or {}
		cursor = pagination.get('next_cursor')
		pages += 1
		if not cursor: break
	return items

def mdblist_list_items(list_id):
	string = 'mdblist_list_items_%s' % list_id
	return lists_cache_object(_fetch_list_items, string, list_id)

def _fetch_catalog(media_type):
	# mdblist.com/movies/ and /shows/ - the site's own general catalog browse,
	# confirmed live against api.mdblist.com's OpenAPI schema: GET /catalog/movie
	# and /catalog/show, cursor-paginated, {'movies'|'shows': [...], 'pagination': {...}}.
	# 'score' (MDBList's own aggregate score) is used as the default sort - the
	# schema documents no single "default" sort, so this is a judgment call
	# matching the general intent of a catalog/discovery browse.
	# Capped at a SINGLE request (100 items) - confirmed live this is what it
	# actually takes to match Trakt's felt speed: Trakt's own list-items call
	# is always exactly one request no matter the list size, and MDBList's per-
	# request latency alone (~300ms, confirmed live) already roughly matches
	# Trakt's whole round-trip - so 2+ sequential MDBList calls can never
	# really tie Trakt's one-call time, only 1 can. 100 items is still several
	# Kodi-facing pages' worth via the existing local pagination; a user who
	# pages deep enough to exhaust it just doesn't get a further page link
	# past that point (cache lives here same as before - reopening the same
	# catalog within the TTL is instant either way).
	path = '/catalog/movie' if media_type == 'movie' else '/catalog/show'
	bucket = 'movies' if media_type == 'movie' else 'shows'
	out, cursor, pages = [], None, 1
	while pages > 0:
		params = {'sort': 'score', 'sort_order': 'desc', 'limit': 100}
		if cursor: params['cursor'] = cursor
		data = call_mdblist(path, params=params)
		if not isinstance(data, dict): break
		for entry in data.get(bucket) or []:
			try:
				tmdb_id, imdb_id = _ids_object(entry)
				if not tmdb_id: continue
				out.append({'id': tmdb_id, 'imdb_id': imdb_id, 'media_type': 'movie' if media_type == 'movie' else 'tv',
							'title': entry.get('title', ''),
							'release_date': '%s-01-01' % entry['release_year'] if entry.get('release_year') else None})
			except: continue
		pagination = data.get('pagination') or {}
		cursor = pagination.get('next_cursor')
		pages -= 1
		if not cursor: break
	return out

def mdblist_catalog(media_type):
	return lists_cache_object(_fetch_catalog, 'mdblist_catalog_%s' % media_type, media_type)

def cache_delete_list_mdblist(params):
	lists_cache.delete('mdblist_list_items_%s' % params['list_id'])
	notification('Success')
	kodi_refresh()

def cache_delete_all_mdblist(params=None):
	lists_cache.delete_like('mdblist_%')
	notification('Success')
	kodi_refresh()

#=========================== Watched Status Provider (XOR value 3) ===========================#
def mdblist_user_active():
	return settings.mdblist_user_active()

def _iso_now():
	return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

def _payload_ids(media_id, key='tmdb', extra_ids=None):
	ids = {key: str(media_id)}
	if extra_ids:
		for k, v in extra_ids.items():
			if v not in (None, '', 'None', 0, '0'): ids[k] = v
	return ids

def _watched_row(db_type, media_id, season, episode, title):
	last_played = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
	return (db_type, str(media_id), season or '', episode or '', last_played, title or '')

def mdblist_watched_status_mark(action, media, media_id, tvdb_id=0, season=None, episode=None, key='tmdb'):
	if not mdblist_user_active(): return True
	ids = _payload_ids(media_id, key)
	endpoint = '/sync/watched' if action == 'mark_as_watched' else '/sync/watched/remove'
	watched_at = _iso_now()
	if media == 'movies':
		entry = {'ids': ids}
		if action == 'mark_as_watched': entry['watched_at'] = watched_at
		data = {'movies': [entry]}
	elif media == 'episode':
		ep = {'number': int(episode)}
		if action == 'mark_as_watched': ep['watched_at'] = watched_at
		data = {'shows': [{'ids': ids, 'seasons': [{'number': int(season), 'episodes': [ep]}]}]}
	elif media == 'shows':
		data = {'shows': [{'ids': ids}]}
	else:  # season
		data = {'shows': [{'ids': ids, 'seasons': [{'number': int(season)}]}]}
	result = call_mdblist(endpoint, data=data, method='post')
	return result is not None

def _scrobble_body(media, media_id, percent, season=None, episode=None, key='tmdb'):
	ids = _payload_ids(media_id, key)
	body = {'progress': float(percent)}
	if media not in ('movie', 'movies'):
		body['show'] = {'ids': ids, 'season': int(season), 'episode': int(episode)}
	else:
		body['movie'] = {'ids': ids}
	return body

def mdblist_progress(action, media, media_id, percent, season=None, episode=None, resume_id=None, refresh_tracker=False, title=''):
	if not mdblist_user_active(): return
	if action == 'clear_progress':
		try: call_mdblist('/scrobble/clear', data=_scrobble_body(media, media_id, 0, season, episode), method='post')
		except Exception as e: logger('MDBList Error', str(e))
		return
	try: call_mdblist('/scrobble/pause', data=_scrobble_body(media, media_id, percent, season, episode), method='post')
	except Exception as e: logger('MDBList Error', str(e))
	if refresh_tracker:
		try: mdblist_sync_activities(bypass_throttle=True)
		except: pass

SYNC_STAMP_KEY = 'mdblist_last_activities_check'
SYNC_THROTTLE_SECONDS = 900

def _sync_throttled():
	try:
		dbcon = connect_database('mdblist_db')
		row = dbcon.execute('SELECT data FROM mdblist_data WHERE id = ?', (SYNC_STAMP_KEY,)).fetchone()
		return row and (time.time() - float(row[0])) < SYNC_THROTTLE_SECONDS
	except: return False

def _watermark_get():
	try:
		dbcon = connect_database('mdblist_db')
		row = dbcon.execute('SELECT data FROM mdblist_data WHERE id = ?', ('mdblist_watermark',)).fetchone()
		return row[0] if row else ''
	except: return ''

def _watermark_set(value):
	try:
		dbcon = connect_database('mdblist_db')
		dbcon.execute('INSERT OR REPLACE INTO mdblist_data VALUES (?, ?)', ('mdblist_watermark', value))
	except: pass

def _pull_watched(mediatype):
	# Full snapshot pull (see module docstring re: the incremental-sync simplification).
	out, cursor, pages = [], None, 20
	while pages > 0:
		params = {'mediatype': mediatype, 'limit': 200}
		if cursor: params['cursor'] = cursor
		data = call_mdblist('/sync/watched', params=params)
		if not isinstance(data, dict): break
		bucket = 'movies' if mediatype == 'movie' else 'shows'
		out.extend(data.get(bucket) or [])
		cursor = (data.get('pagination') or {}).get('next_cursor')
		pages -= 1
		if not cursor: break
	return out

def mdblist_indicators_movies(act=None):
	items = _pull_watched('movie')
	rows = []
	for item in items:
		try:
			movie = item.get('movie') or {}
			tmdb_id = (movie.get('ids') or {}).get('tmdb')
			if not tmdb_id: continue
			rows.append(_watched_row('movie', tmdb_id, '', '', movie.get('title', '')))
		except: continue
	dbcon = connect_database('mdblist_db')
	dbcon.execute('DELETE FROM watched WHERE db_type = ?', ('movie',))
	if rows: dbcon.executemany('INSERT OR REPLACE INTO watched VALUES (?, ?, ?, ?, ?, ?)', rows)

def mdblist_indicators_tv(act=None):
	items = _pull_watched('show')
	rows = []
	for item in items:
		try:
			show = item.get('show') or {}
			tmdb_id = (show.get('ids') or {}).get('tmdb')
			if not tmdb_id: continue
			for season in item.get('seasons') or []:
				for ep in season.get('episodes') or []:
					rows.append(_watched_row('episode', tmdb_id, season.get('number'), ep.get('number'), show.get('title', '')))
		except: continue
	dbcon = connect_database('mdblist_db')
	dbcon.execute('DELETE FROM watched WHERE db_type = ?', ('episode',))
	if rows: dbcon.executemany('INSERT OR REPLACE INTO watched VALUES (?, ?, ?, ?, ?, ?)', rows)

def mdblist_playback_progress():
	result = call_mdblist('/sync/playback')
	if isinstance(result, list): return result
	return []

def mdblist_sync_activities(force_update=False, bypass_throttle=False):
	if not mdblist_user_active(): return 'no account'
	if not force_update and not bypass_throttle and _sync_throttled(): return 'not needed'
	try:
		dbcon = connect_database('mdblist_db')
		dbcon.execute('INSERT OR REPLACE INTO mdblist_data VALUES (?, ?)', (SYNC_STAMP_KEY, str(time.time())))
	except: pass
	latest = call_mdblist('/sync/last_activities')
	if not isinstance(latest, dict): return 'failed'
	watermark = '%s|%s' % (latest.get('watched_at', ''), latest.get('episode_watched_at', ''))
	if not force_update and watermark == _watermark_get(): return 'not needed'
	try:
		mdblist_indicators_movies()
		mdblist_indicators_tv()
	except Exception as e:
		logger('MDBList Sync Error', str(e))
		return 'failed'
	_watermark_set(watermark)
	return 'success'

#=========================== Cache ===========================#
def clear_all_mdblist_cache_data(silent=False, refresh=True):
	try:
		start = silent or confirm_dialog()
		if not start: return False
		dbcon = connect_database('mdblist_db')
		for table in ('mdblist_data', 'progress', 'watched', 'watched_status'): dbcon.execute('DELETE FROM %s' % table)
		dbcon.execute('VACUUM')
		lists_cache.delete_like('mdblist_%')
		if refresh: Thread(target=mdblist_sync_activities, kwargs={'force_update': True}).start()
		return True
	except: return False
