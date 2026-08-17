"""
	Fenomscrapers Module
"""

from morbiusscrapers.modules.control import addonPath, addonVersion, joinPath
from morbiusscrapers.modules.textviewer import TextViewerXML


def get(file):
	morbiusscrapers_path = addonPath()
	morbiusscrapers_version = addonVersion()
	helpFile = joinPath(morbiusscrapers_path, 'resources', 'help', file + '.txt')
	r = open(helpFile, 'r', encoding='utf-8', errors='ignore')
	text = r.read()
	r.close()
	heading = '[B]morbiusscrapers -  v%s - %s[/B]' % (morbiusscrapers_version, file)
	windows = TextViewerXML('textviewer.xml', morbiusscrapers_path, heading=heading, text=text)
	windows.run()
	del windows
