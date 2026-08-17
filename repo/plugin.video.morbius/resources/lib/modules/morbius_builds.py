# -*- coding: utf-8 -*-
"""
Parser/loader for the "Morbius" main-menu build lists.

The Morbius main-menu entry points at a remote, hand-authored text source
(e.g. main1_movies4k.txt) that lists either:
  - <dir>...</dir> blocks: sub-folders, each pointing at another URL (another
    build list) or a <tmdb>list/ID</tmdb> reference, or
  - <item>...</item> blocks: individual playable movie entries.

These sources are NOT well-formed XML - closing tags are frequently missing
their leading "<" (e.g. "Road House/title>" instead of "</title>"), and
titles/links are sometimes duplicated or nested (<link><sublink>...). All
parsing here is therefore done with tolerant regexes rather than a strict
XML/HTML parser, on purpose.

Scope note (Tier 1): only the <dir> / <item> text format is supported.
Links ending in .xml, and <tmdb> list references, are recognised but shown
as "not supported yet" rather than parsed, since their formats are not part
of this pass. Leaf movie items are added with their source <link> used
as-is (no real-debrid/1fichier/etc. resolution) - Kodi will attempt to open
the link directly, which may or may not be directly playable depending on
the link type.
"""
import re
import requests
from caches.main_cache import main_cache
from modules.kodi_utils import logger

REQUEST_TIMEOUT = 15
CACHE_EXPIRATION_HOURS = 6
CACHE_KEY_PREFIX = 'MORBIUS_BUILD_'

_TAG_RE_CACHE = {}


def _tag_pattern(name):
	pattern = _TAG_RE_CACHE.get(name)
	if pattern is None:
		# Tolerant: closing tag's leading "<" is optional (source data omits it often).
		pattern = re.compile(r'<%s>(.*?)<?/%s\s*>' % (name, name), re.S | re.I)
		_TAG_RE_CACHE[name] = pattern
	return pattern


def _tag(block, name):
	match = _tag_pattern(name).search(block)
	return match.group(1).strip() if match else ''


def _blocks(text, name):
	# Tolerant: closing tag may be missing its trailing ">" entirely.
	pattern = re.compile(r'<%s>(.*?)</%s\s*>?' % (name, name), re.S | re.I)
	return pattern.findall(text)


def fetch_url(url):
	response = requests.get(url, timeout=REQUEST_TIMEOUT)
	response.raise_for_status()
	if not response.encoding: response.encoding = 'utf-8'
	return response.text


def get_cached(url, force=False):
	cache_key = '%s%s' % (CACHE_KEY_PREFIX, url)
	if not force:
		cached = main_cache.get(cache_key)
		if cached is not None: return cached
	text = fetch_url(url)
	main_cache.set(cache_key, text, expiration=CACHE_EXPIRATION_HOURS)
	return text


def classify(text):
	"""Return 'items', 'folders', or 'empty' depending on which tags the text contains.
	If both are present, items win (a movie list is the more specific/leaf case)."""
	if re.search(r'<item>', text, re.I): return 'items'
	if re.search(r'<dir>', text, re.I): return 'folders'
	return 'empty'


def parse_folders(text):
	folders = []
	for block in _blocks(text, 'dir'):
		title = _tag(block, 'title')
		if not title: continue
		folders.append({
			'title': title,
			'link': _tag(block, 'link'),
			'tmdb': _tag(block, 'tmdb'),
			'thumbnail': _tag(block, 'thumbnail'),
			'fanart': _tag(block, 'fanart')})
	return folders


_PLACEHOLDER_SUBLINKS = ('search', 'searchsd')


def parse_items(text):
	items = []
	for block in _blocks(text, 'item'):
		title = _tag(block, 'title')
		if not title: continue
		link_block = _tag(block, 'link')
		sublinks = re.findall(r'<sublink>(.*?)<?/sublink\s*>', link_block, re.S | re.I)
		if sublinks:
			# Nested <link><sublink>...</sublink>...</link> format (e.g. New Releases).
			# Placeholders like "search"/"searchsd" aren't URLs - they're markers for a
			# live-search fallback that isn't implemented here. Blank entries are also
			# skipped so the first *usable* sublink is picked, not just the first one.
			usable = [s.strip() for s in sublinks if s.strip() and s.strip().lower() not in _PLACEHOLDER_SUBLINKS]
			link = usable[0] if usable else ''
		else:
			# Plain <link>URL</link> format (e.g. Intros) - use as-is.
			link = link_block.strip()
		if not link: continue
		items.append({
			'title': title,
			'link': link,
			'imdb': _tag(block, 'imdb'),
			'summary': _tag(block, 'summary'),
			'thumbnail': _tag(block, 'thumbnail'),
			'fanart': _tag(block, 'fanart')})
	return items


def is_unsupported_link(link):
	"""Links to formats this pass doesn't parse (currently just .xml sources)."""
	return link.lower().split('?')[0].endswith('.xml')


def is_alldebrid_link(link):
	"""AllDebrid share-page links (e.g. https://alldebrid.com/f/<id>) aren't direct
	streams - they need to go through AllDebrid's unrestrict API first, same as the
	addon's existing Saved Links / Cloud sections do."""
	return 'alldebrid.com' in link.lower()


def log_error(function_name, url, error):
	logger('morbius_builds.%s' % function_name, 'FAILED url=%s err=%s' % (url, error))
