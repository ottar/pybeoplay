#
# BeoPlay JSON interface for Bang & Olufsen Speakers, TVs and other NL devices
# Reference: https://documenter.getpostman.com/view/1053298/T1LTe4Lt#intro
# Reference: https://raw.githubusercontent.com/PolyPv/BeoRemote/master/BeoRemote.txt
# Lifted a lot of code from marton borzak's ha-beoplay
#
#

# Connection constants
BASE_URL = 'http://{0}:8080/{1}'
TIMEOUT = 5.0
CONNFAILCOUNT = 5

# BeoPlay constants
BEOPLAY_URL_NOTIFICATIONS = 'BeoNotify/Notifications'

BEOPLAY_URL_SET_VOLUME = 'BeoZone/Zone/Sound/Volume/Speaker/Level'
BEOPLAY_URL_MUTE = 'BeoZone/Zone/Sound/Volume/Speaker/Muted'
BEOPLAY_URL_PLAY = 'BeoZone/Zone/Stream/Play'
BEOPLAY_URL_RELEASE = '/Release'
BEOPLAY_URL_PAUSE = 'BeoZone/Zone/Stream/Pause'
BEOPLAY_URL_STOP = 'BeoZone/Zone/Stream/Stop'
BEOPLAY_URL_FORWARD = 'BeoZone/Zone/Stream/Forward'
BEOPLAY_URL_BACKWARD = 'BeoZone/Zone/Stream/Backward'
BEOPLAY_URL_STEPUP = 'BeoZone/Zone/List/StepUp'
BEOPLAY_URL_STEPDOWN = 'BeoZone/Zone/List/StepDown'
BEOPLAY_URL_SHUFFLE = 'BeoZone/Zone/List/Shuffle'
BEOPLAY_URL_REPEAT = 'BeoZone/Zone/List/Repeat'
BEOPLAY_URL_STANDBY = 'BeoDevice/powerManagement/standby'

BEOPLAY_URL_GET_SOURCES = 'BeoZone/Zone/Sources'
BEOPLAY_URL_ACTIVE_SOURCES = 'BeoZone/Zone/ActiveSources'

BEOPLAY_URL_STAND_ACTIVE = 'BeoZone/Zone/Stand/Active'
BEOPLAY_URL_STAND = 'BeoZone/Zone/Stand'
BEOPLAY_URL_GET_SOUND_MODE = 'BeoZone/Zone/Sound/Mode'
BEOPLAY_URL_SET_SOUND_MODE = 'BeoZone/Zone/Sound/Mode/Active'

# Additional endpoints mapped from live devices (Beosound Stage + CA17), 2026-06.
# See the consuming project's docs/api-kartlegging.md for the full survey.
BEOPLAY_URL_SOUND_ADJUSTMENT = 'BeoZone/Zone/Sound/Adjustment'        # bass/treble/loudness
BEOPLAY_URL_SOUND_EXPLORE = 'BeoZone/Zone/Sound/Explore'             # Stage DSP (upmix/virtualize/lfeTuning/contentProcessing)
BEOPLAY_URL_DEFAULT_VOLUME = 'BeoZone/Zone/Sound/Volume/Speaker/DefaultLevel'  # startup volume
BEOPLAY_URL_BUFFER_SETUP = 'BeoZone/Zone/Sound/BufferSetup'          # net-radio buffering (seconds)
BEOPLAY_URL_SLEEP_TIMER = 'BeoDevice/powerManagement/sleepTimer'     # GET/PUT/DELETE, minutes
BEOPLAY_URL_SNAPSHOT = 'BeoZone/Zone/Snapshot'                       # device-side scene buttons
BEOPLAY_URL_HOME_TIMERS = 'BeoHome/trigger/timerList'               # device-side alarms/timers
BEOPLAY_URL_PING = 'Ping'                                            # cheap liveness check (200, empty body)

# Valid powerState values for BeoDevice/powerManagement/standby (from _capabilities).
# 'allStandby' powers down the whole Beolink setup; 'reboot' restarts the device.
BEOPLAY_POWER_STATES = ['on', 'standby', 'allStandby', 'reboot']

BEOPLAY_URL_JOIN_EXPERIENCE = 'BeoZone/Zone/Device/OneWayJoin'
BEOPLAY_URL_LEAVE_EXPERIENCE = 'BeoZone/Zone/ActiveSources/primaryExperience'
BEOPLAY_URL_PLAYQUEUE = 'BeoZone/Zone/PlayQueue'
BEOPLAY_URL_PLAYQUEUE_INSTANT = '?instantplay'


BEOPLAY_REMOTE_COMMANDS = ['Cursor/Select', 'Cursor/Up', 'Cursor/Down', 'Cursor/Left', 'Cursor/Right', 'Cursor/Exit', 'Cursor/Back', 'Cursor/PageUp', 'Cursor/PageDown', 'Cursor/Clear', 'Stream/Play', 'Stream/Stop', 'Stream/Pause', 'Stream/Wind', 'Stream/Rewind', 'Stream/Forward', 'Stream/Backward', 'List/StepUp', 'List/StepDown', 'List/PreviousElement', 'List/Shuffle', 'List/Repeat', 'Menu/Root', 'Menu/Option', 'Menu/Setup', 'Menu/Contents', 'Menu/Favorites', 'Menu/ElectronicProgramGuide', 'Menu/VideoOnDemand', 'Menu/Text', 'Menu/HbbTV,Menu/HomeControl', 'Device/Information', 'Device/Eject', 'Device/TogglePower', 'Device/Languages', 'Device/Subtitles', 'Device/OneWayJoin', 'Device/Mots', 'Record/Record', 'Generic/Blue', 'Generic/Red', 'Generic/Green', 'Generic/Yellow']
BEOPLAY_REMOTE_PREFIX = 'BeoZone/Zone/'

BEOPLAY_DIGITS = [ '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
BEOPLAY_DIGITS_URL = 'BeoZone/Zone/Digits'
BEOPLAY_DIGITS_KEY = 'digits'
# NOTE: the Digits endpoint expects an INTEGER value, not a string
# (verified on Stage: {"digits": "3"} -> 400, {"digits": 3} -> 200).
# async_digits() already casts with int(); keep that if you call the API directly.
