"""
	Fenomscrapers Module
"""

from sys import argv
from urllib.parse import parse_qsl
from morbiusscrapers import providers
from morbiusscrapers.modules import control

params = dict(parse_qsl(argv[2].replace('?', '')))
action = params.get('action')
name = params.get('name')

if action is None:
	control.openSettings('0.0', 'script.module.morbiusscrapers')

if action == "morbiusscrapersSettings":
	control.openSettings('0.0', 'script.module.morbiusscrapers')

elif action == 'ShowChangelog':
	from morbiusscrapers.modules import changelog
	changelog.get()

elif action == 'ShowHelp':
	from morbiusscrapers.modules import help
	help.get(name)

elif action == "Defaults":
	from morbiusscrapers import sources
	try:
		provider_defaults = control.getProviderDefaults()
		sourceList = []
		sourceList = sources(ret_all=True)
		for name, source in sourceList:
			source_setting = 'provider.' + name
			default_setting = provider_defaults.get(source_setting) or 'false'
			control.setSetting(source_setting, default_setting)
		control.notification(message='Success')
	except: control.notification(message='Error')

elif action == "toggleAll":
	sourceList = []
	sourceList = providers.all_providers
	for i in sourceList:
		source_setting = 'provider.' + i
		control.setSetting(source_setting, params['setting'])

elif action == "toggleAllHosters":
	sourceList = []
	sourceList = providers.hoster_providers
	for i in sourceList:
		source_setting = 'provider.' + i
		control.setSetting(source_setting, params['setting'])

elif action == "toggleAllTorrent":
	sourceList = []
	sourceList = providers.torrent_providers
	for i in sourceList:
		source_setting = 'provider.' + i
		control.setSetting(source_setting, params['setting'])

elif action == "toggleAllPackTorrent":
	from morbiusscrapers import sources
	sourceList = []
	sourceList = sources(ret_all=True)
	for name, source in sourceList:
		setting = 'true' if source.pack_capable else 'false'
		source_setting = 'provider.' + name
		control.setSetting(source_setting, setting)

elif action == 'cleanSettings':
	control.clean_settings()

elif action == 'undesirablesSelect':
	from morbiusscrapers.modules.undesirables import undesirablesSelect
	undesirablesSelect()

elif action == 'undesirablesInput':
	from morbiusscrapers.modules.undesirables import undesirablesInput
	undesirablesInput()

elif action == 'undesirablesUserRemove':
	from morbiusscrapers.modules.undesirables import undesirablesUserRemove
	undesirablesUserRemove()

elif action == 'undesirablesUserRemoveAll':
	from morbiusscrapers.modules.undesirables import undesirablesUserRemoveAll
	undesirablesUserRemoveAll()

elif action == 'tools_clearLogFile':
	from morbiusscrapers.modules import log_utils
	cleared = log_utils.clear_logFile()
	if cleared == 'canceled': pass
	elif cleared: control.notification(message='morbiusscrapers Log File Successfully Cleared')
	else: control.notification(message='Error clearing morbiusscrapers Log File, see kodi.log for more info')

elif action == 'tools_viewLogFile':
	from morbiusscrapers.modules import log_utils
	log_utils.view_LogFile(name)

elif action == 'tools_uploadLogFile':
	from morbiusscrapers.modules import log_utils
	log_utils.upload_LogFile()

elif action == 'healthCheck':
	from morbiusscrapers.modules.health import morbiusscrapers
	morbiusscrapers()