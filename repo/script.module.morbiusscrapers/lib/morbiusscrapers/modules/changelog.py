"""
	Fenomscrapers Module
"""

from morbiusscrapers.modules.control import addonPath, addonVersion, joinPath
from morbiusscrapers.modules.textviewer import TextViewerXML


def get():
	morbiusscrapers_path = addonPath()
	morbiusscrapers_version = addonVersion()
	changelogfile = joinPath(morbiusscrapers_path, 'changelog.txt')
	r = open(changelogfile, 'r', encoding='utf-8', errors='ignore')
	text = r.read()
	r.close()
	heading = '[B]morbiusscrapers -  v%s - ChangeLog[/B]' % morbiusscrapers_version
	windows = TextViewerXML('textviewer.xml', morbiusscrapers_path, heading=heading, text=text)
	windows.run()
	del windows
