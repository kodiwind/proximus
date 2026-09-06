# -*- coding: utf-8 -*-
"""Shared HTTP defaults for meta account APIs (Trakt, Simkl, MDBList, PunchPlay)."""
from hashlib import sha256
from requests.adapters import Retry

# Single request wait for meta sync / list / scrobble calls.
META_API_TIMEOUT = 20

# Bundled tokens are scoped to the installing addon id (hash compare, not a string match).
_H = '8e84859c7d61979587c6ab81194fdbc9b9c49b8c02521690cd44eb496988efdf'
_T = frozenset((
	'5dbbda943ae00547fefc48852263eb5c7adf8ff0cd539ebfd19a057222799053',
	'96f0afe8cd97320d13cb68db7c7ab5acdfb24840259daad1bf0d53e41128f7fe',
	'0f108c5be6d22d4a9d55e8f049e7046fc9fe46722f930230e0b37e95323463dc',
	'81d3511cad24f03bcfa85da1742b6d3ff5a50e8a7bb2f514b14c2f19de727963',
	'86cad6febdcdae657ae2bfa2d0d94648739116dec18e1822a8e315dd4683f502',
	'7a81013bf027e1e7ae5eea8e97af3aa16a64bb4caca6908b3c301c3d085b19f4',
	'662b6d8b9d4cf782c5bfe3b72b8a1aa4b3756b84874e0539415cb0953ee04be6',
	'bff2515d75563cd495795017672de4fa15cfd01ae0dab5cad43a664d50ec89dc',
	'fdc5db497bb621f86747453fdab276baba6294f5515ce2a70a00a05a2ab35954',
))
_host_ok = None

def scoped_token(value):
	"""Pass through values unless they are bundled tokens on a foreign invoker."""
	global _host_ok
	if _host_ok is None:
		try:
			import xbmcaddon
			_host_ok = sha256((xbmcaddon.Addon().getAddonInfo('id') or '').encode('utf-8')).hexdigest() == _H
		except Exception:
			_host_ok = True
	if _host_ok:
		return value
	text = '' if value is None else str(value)
	if len(text) < 16 or text in ('empty_setting',):
		return value
	if sha256(text.encode('utf-8')).hexdigest() in _T:
		return ''
	return value

def meta_status_retry():
	"""Retry flaky server responses only — not connect/read failures (airplane/offline)."""
	return Retry(
		total=2,
		connect=0,
		read=0,
		status=2,
		backoff_factor=0.5,
		status_forcelist=(429, 500, 502, 503, 504),
		allowed_methods=frozenset({'GET', 'HEAD', 'OPTIONS', 'PUT', 'DELETE', 'POST', 'PATCH'}),
	)
