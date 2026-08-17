# -*- coding: utf-8 -*-
"""
MDBList (mdblist.com) My Lists browsing.

Modeled directly on indexers/tmdb_lists.py's get_tmdb_lists()/build_tmdb_list()
pair (per explicit guidance: MDBList's own lists are simple named lists, same
shape as TMDb's own account lists, unlike Trakt/Simkl's OAuth-personal-lists-
vs-status-buckets model) — but pared down to browsing only. No create/rename/
delete/add-to-list management UI is offered here; that would duplicate a
sizeable chunk of tmdb_lists.py's list-management surface for a feature this
pass wasn't scoped to cover on the MDBList side.
"""
import sys
from threading import Thread
from apis.mdblist_api import mdblist_user_lists, mdblist_list_items, mdblist_catalog
from indexers.movies import Movies
from indexers.tvshows import TVShows
from modules.utils import paginate_list
from modules.settings import paginate, page_limit, widget_hide_next_page
from modules import kodi_utils
# logger = kodi_utils.logger

def get_mdblist_lists(params):
	def _process():
		# mdblist.com/movies/ and /shows/ - the site's own general catalog, as
		# two fixed entries ahead of the user's own named lists, matching how
		# they're presented as their own top-level pages on the actual site.
		for catalog_media_type, catalog_label in (('movie', 'MDB Movies'), ('show', 'MDB Shows')):
			try:
				url = build_url({'mode': 'mdblist.list.build_mdblist_catalog', 'media_type': catalog_media_type, 'list_name': catalog_label})
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(catalog_label)
				listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': background, 'banner': background})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(' ')
				yield (url, listitem, True)
			except: pass
		for item in data:
			try:
				list_name, list_id, item_count = item.get('name', ''), item['id'], item.get('items', 0)
				url_params = {'mode': 'mdblist.list.build_mdblist_list', 'list_id': list_id, 'list_name': list_name, 'name': list_name}
				url = build_url(url_params)
				display = '%s [I](x%02d)[/I]' % (list_name, item_count)
				cm = [('[B]Clear Contents Cache[/B]', 'RunPlugin(%s)' % build_url({'mode': 'mdblist.cache_delete_list_mdblist', 'list_id': list_id})),
				('[B]Clear All Lists Cache[/B]', 'RunPlugin(%s)' % build_url({'mode': 'mdblist.cache_delete_all_mdblist'})),
				('[B]Add to Shortcut Folder[/B]', 'RunPlugin(%s)' % build_url({'mode': 'menu_editor.shortcut_folder_add_known', 'url': url}))]
				listitem = kodi_utils.make_listitem()
				listitem.setLabel(display)
				listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': background, 'banner': background})
				info_tag = listitem.getVideoInfoTag(True)
				info_tag.setPlot(' ')
				listitem.addContextMenuItems(cm)
				yield (url, listitem, True)
			except: pass
	handle, icon, background = int(sys.argv[1]), kodi_utils.get_icon('lists'), kodi_utils.get_addon_fanart()
	build_url = kodi_utils.build_url
	try:
		data = mdblist_user_lists() or []
		kodi_utils.add_items(handle, list(_process()))
	except: pass
	kodi_utils.set_content(handle, 'files')
	kodi_utils.set_category(handle, params.get('category_name', 'MDBList Lists'))
	kodi_utils.end_directory(handle)
	kodi_utils.set_view_mode('view.main')

def build_mdblist_catalog(params):
	# mdblist.com/movies/ or /shows/ - same worker-thread handoff shape as
	# build_mdblist_list() below, sourcing from the /catalog/{movie,show}
	# endpoint instead of a specific list_id. Only ONE media type is ever
	# populated here (the catalog endpoint itself is movie-only or show-only,
	# unlike a personal list which can mix both) - Movies/TVShows still both
	# get threaded for symmetry with build_mdblist_list, the unused one just
	# gets an empty list and resolves instantly.
	def _process(function, _list, _type):
		if not _list['list']: return
		item_list_extend(function(_list).worker())
	handle, is_external = int(sys.argv[1]), kodi_utils.external()
	hide_next_page = is_external and widget_hide_next_page()
	media_type = params.get('media_type', 'movie')
	list_name = params.get('list_name', 'MDB Movies' if media_type == 'movie' else 'MDB Shows')
	content = 'movies' if media_type == 'movie' else 'tvshows'
	try:
		threads, item_list = [], []
		item_list_extend = item_list.extend
		page_no, paginate_start = int(params.get('new_page', '1')), int(params.get('paginate_start', '0'))
		if page_no == 1 and not is_external: kodi_utils.set_property('morbius.exit_params', kodi_utils.folder_path())
		result = mdblist_catalog(media_type) or []
		if paginate(is_external):
			limit = page_limit(is_external)
			result, total_pages = paginate_list(result, page_no, limit, paginate_start)
			if is_external: paginate_start = limit
		else: total_pages = 1
		ordered = [dict(i, **{'order': c}) for c, i in enumerate(result)]
		movie_list = {'list': [(i['order'], i['id']) for i in ordered], 'custom_order': 'true'} if media_type == 'movie' else {'list': [], 'custom_order': 'true'}
		tvshow_list = {'list': [(i['order'], i['id']) for i in ordered], 'custom_order': 'true'} if media_type != 'movie' else {'list': [], 'custom_order': 'true'}
		for item in ((Movies, movie_list, 'movies'), (TVShows, tvshow_list, 'tvshows')):
			threaded_object = Thread(target=_process, args=item)
			threaded_object.start()
			threads.append(threaded_object)
		[i.join() for i in threads]
		item_list.sort(key=lambda k: k[1])
		kodi_utils.add_items(handle, [i[0] for i in item_list])
		if total_pages > page_no and not hide_next_page:
			new_page = str(page_no + 1)
			new_params = {'mode': 'mdblist.list.build_mdblist_catalog', 'media_type': media_type, 'list_name': list_name, 'paginate_start': paginate_start, 'new_page': new_page}
			kodi_utils.add_dir(handle, new_params, 'Next Page (%s) >>' % new_page, 'nextpage', kodi_utils.get_icon('nextpage_landscape'))
	except: pass
	kodi_utils.set_content(handle, content)
	kodi_utils.set_category(handle, list_name)
	kodi_utils.end_directory(handle, cacheToDisc=False if is_external else True)
	if not is_external:
		if params.get('refreshed') == 'true': kodi_utils.sleep(1000)
		kodi_utils.set_view_mode('view.%s' % content, content, is_external)

def build_mdblist_list(params):
	def _process(function, _list, _type):
		if not _list['list']: return
		item_list_extend(function(_list).worker())
	handle, is_external, content = int(sys.argv[1]), kodi_utils.external(), 'movies'
	hide_next_page = is_external and widget_hide_next_page()
	list_name = params.get('list_name', 'MDBList')
	try:
		threads, item_list = [], []
		item_list_extend = item_list.extend
		list_id = params.get('list_id')
		page_no, paginate_start = int(params.get('new_page', '1')), int(params.get('paginate_start', '0'))
		if page_no == 1 and not is_external: kodi_utils.set_property('morbius.exit_params', kodi_utils.folder_path())
		result = mdblist_list_items(list_id) or []
		if paginate(is_external):
			limit = page_limit(is_external)
			result, total_pages = paginate_list(result, page_no, limit, paginate_start)
			if is_external: paginate_start = limit
		else: total_pages = 1
		all_movies = [dict(i, **{'order': c}) for c, i in enumerate(result) if i['media_type'] == 'movie']
		all_tvshows = [dict(i, **{'order': c}) for c, i in enumerate(result) if i['media_type'] == 'tv']
		movie_list = {'list': [(i['order'], i['id']) for i in all_movies], 'custom_order': 'true'}
		tvshow_list = {'list': [(i['order'], i['id']) for i in all_tvshows], 'custom_order': 'true'}
		content = max([('movies', len(all_movies)), ('tvshows', len(all_tvshows))], key=lambda k: k[1])[0]
		for item in ((Movies, movie_list, 'movies'), (TVShows, tvshow_list, 'tvshows')):
			threaded_object = Thread(target=_process, args=item)
			threaded_object.start()
			threads.append(threaded_object)
		[i.join() for i in threads]
		item_list.sort(key=lambda k: k[1])
		kodi_utils.add_items(handle, [i[0] for i in item_list])
		if total_pages > page_no and not hide_next_page:
			new_page = str(page_no + 1)
			new_params = {'mode': 'mdblist.list.build_mdblist_list', 'list_id': list_id, 'list_name': list_name, 'paginate_start': paginate_start, 'new_page': new_page}
			kodi_utils.add_dir(handle, new_params, 'Next Page (%s) >>' % new_page, 'nextpage', kodi_utils.get_icon('nextpage_landscape'))
	except: pass
	kodi_utils.set_content(handle, content)
	kodi_utils.set_category(handle, list_name)
	kodi_utils.end_directory(handle, cacheToDisc=False if is_external else True)
	if not is_external:
		if params.get('refreshed') == 'true': kodi_utils.sleep(1000)
		kodi_utils.set_view_mode('view.%s' % content, content, is_external)
