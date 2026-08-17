# -*- coding: utf-8 -*-
import sqlite3, os
sdb = os.path.expandvars(r'%APPDATA%\Kodi\userdata\addon_data\plugin.video.morbius\databases\simkl.db')
con = sqlite3.connect(sdb)
print('=== all progress ===')
for r in con.execute('SELECT db_type, media_id, season, episode, resume_point, last_played, resume_id, title FROM progress').fetchall():
    print(r)
print('=== tango-ish watched/progress ===')
for r in con.execute("SELECT 'watched', db_type, media_id, season, episode, last_played, title FROM watched WHERE lower(title) LIKE '%tango%' OR lower(title) LIKE '%cash%'"):
    print(r)
for r in con.execute("SELECT 'progress', db_type, media_id, season, episode, resume_point, last_played, title FROM progress WHERE lower(title) LIKE '%tango%' OR lower(title) LIKE '%cash%'"):
    print(r)
# settings
settings = os.path.expandvars(r'%APPDATA%\Kodi\userdata\addon_data\plugin.video.morbius\databases\settings.db')
c2 = sqlite3.connect(settings)
for sid in ('watched_indicators', 'watched_indicators_name', 'simkl.user'):
    print(sid, c2.execute('SELECT setting_value FROM settings WHERE setting_id=?', (sid,)).fetchone())
