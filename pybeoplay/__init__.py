"""

BeoPlay JSON interface for Bang & Olufsen Speakers, TVs and other NL devices
Reference: https://documenter.getpostman.com/view/1053298/T1LTe4Lt#intro
Reference: https://raw.githubusercontent.com/PolyPv/BeoRemote/master/BeoRemote.txt
Lifted a lot of code from marton borzak's ha-beoplay

https://widdowquinn.github.io/coding/update-pypi-package/

"""

import requests
import aiohttp
import asyncio
from aiohttp import ClientResponse
import json
import logging
from typing import Optional
from .const import *


LOG = logging.getLogger(__name__)


class BeoPlay(object):
    def __init__(self, host, session: Optional[aiohttp.ClientSession] = None):
        """Initializes a BeoPlay connection to the speaker / TV
        Host: the IP address of the speaker
        Session (optional): a asyncio client session to be used for async
        communication with the speaker (if not provided, only blocking calls 
        using Requests will work)
        """
        # network information
        self._host = host
        self._host_notifications = BASE_URL.format(
            self._host, BEOPLAY_URL_NOTIFICATIONS
        )
        self._connfail = 0
        self._clientsession = session
        # The following are only going ot be valid after a call to getDeviceInfo
        # device information
        self._name = None
        self._serialNumber = None
        self._typeNumber = None
        self._itemNumber = None
        self._typeName = None
        self._softwareVersion = None
        self._hardwareVersion = None
        # The following are only going ot be valid after a call to getMediaInfo, getStandby
        # Or, they are updated by the Notifications task. The actual field updated by
        # Notifications varies by device. Some devices for example provide notifications when
        # Sound mode changes (e.g., Stage), others (e.g., BeoVision Avant 55) don't.
        # State and Media information
        self.on = None
        self.min_volume = None
        self.max_volume = None
        self.volume = None
        self.muted = None
        self.state = None
        self.media_url = None
        self.media_track = None
        self.media_artist = None
        self.media_album = None
        self.media_genre = None
        self.media_country = None
        self.media_languages = None
        self.primary_experience = None
        # The following are only going ot be valid after a call to getSources
        # Sources
        self.source = None
        self.source_id = None
        self.sources = []
        self.sourcesID = []
        self.sourcesBorrowed = []
        self.listeners = []
        # Extra attributes for tracking primary experience
        self.role = None
        self.primary_jid = None
        # The following are only going ot be valid after a call to getSoundModes
        # Sound modes
        self._soundMode = None
        self._soundModes = {}
        # The following are only going ot be valid after a call to getStandPosition
        # Stand control
        self._standPosition = None
        self._standPositions = {}

    @property
    def host(self):
        """Return the device host."""
        return self._host
    
    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def serialNumber(self):
        """Return the device serial number."""
        return self._serialNumber

    @property
    def itemNumber(self):
        """Return the device serial number."""
        return self._itemNumber

    @property
    def typeNumber(self):
        """Return the device type model number."""
        return self._typeNumber

    @property
    def typeName(self):
        """Return the device type name."""
        return self._typeName

    @property
    def softwareVersion(self):
        """Return the device serial number."""
        return self._softwareVersion

    @property
    def hardwareVersion(self):
        """Return the device serial number."""
        return self._hardwareVersion

    @property
    def remote_commands(self):
        """Get the list of available remote commands"""
        return BEOPLAY_REMOTE_COMMANDS

    @property
    def digits(self):
        """Get the list of available digits"""
        return BEOPLAY_DIGITS
    
    @property
    def soundMode(self):
        """Get the current sound modes"""
        return self._soundMode
    
    @property
    def soundModes(self):
        """Get the list of available sound modes"""
        return list(self._soundModes.keys())
    
    @property
    def soundModesID(self):
        """Get the list of available sound mode IDs"""
        return list(self._soundModes.values())

    @property
    def standPosition(self):
        """Get the current stand position"""
        return self._standPosition
    
    @property
    def standPositions(self):
        """Get the list of available stand positions"""
        return self._standPositions
    
    ###############################################################
    # ASYNC BASED NETWORK CALLS
    ###############################################################

    async def async_getReq(self, path):
        """Non blocking GET call to the speaker, with a given path."""
        if self._clientsession is None:
            LOG.error("Attempt asyncio with no ClientSession")
            return
        try:
            async with self._clientsession.get(
                BASE_URL.format(self._host, path)
            ) as resp:
                LOG.debug("Request Status: %s", str(resp.status))
                if resp.status != 200:
                    return None
                json = await resp.json()
                LOG.debug("Request Json: %s", json)
                return json
        except (asyncio.TimeoutError, aiohttp.ClientError) as _e:
            LOG.info("Client error %s on %s" , repr(_e), self._name)
            raise

    async def async_postReq(self, type, path, jsondata: dict = {}):
        """Non blocking POST/PUT/DELETE call to the speaker.

        ``type``: ``"PUT"`` | ``"POST"`` | ``"DELETE"``
        ``path``: the URL path relative to the speaker base
        ``jsondata``: JSON body (Python dict/list) — ignored for DELETE

        Returns ``True`` when the device responds with any 2xx status
        (200 OK, 201 Created, 202 Accepted, 204 No Content — all of
        which B&O uses for different endpoints; PlayPointer for example
        returns 204 on success). Returns ``False`` and logs the body
        on non-2xx so callers can react.
        """
        if self._clientsession is None:
            LOG.error("Attempt asyncio with no ClientSession")
            return
        try:
            if type == "PUT":
                async with self._clientsession.put(
                    BASE_URL.format(self._host, path), json=jsondata, timeout=aiohttp.ClientTimeout(total=TIMEOUT)
                ) as resp:
                    if not (200 <= resp.status < 300):
                        body = await resp.text()
                        LOG.warning("PUT %s status=%s body=%s", path, resp.status, body[:200])
                        return False
                    LOG.debug("Status: %s", resp.status)
            elif type == "POST":
                async with self._clientsession.post(
                    BASE_URL.format(self._host, path), json=jsondata, timeout=aiohttp.ClientTimeout(total=TIMEOUT)
                ) as resp:
                    if not (200 <= resp.status < 300):
                        body = await resp.text()
                        LOG.warning("POST %s status=%s body=%s", path, resp.status, body[:200])
                        return False
                    LOG.debug("Status: %s", resp.status)
            elif type == "DELETE":
                async with self._clientsession.delete(
                    BASE_URL.format(self._host, path), timeout=aiohttp.ClientTimeout(total=TIMEOUT)
                ) as resp:
                    if not (200 <= resp.status < 300):
                        body = await resp.text()
                        LOG.warning("DELETE %s status=%s body=%s", path, resp.status, body[:200])
                        return False
                    LOG.debug("Status: %s", resp.status)
            else:
                return False
        except (asyncio.TimeoutError, aiohttp.ClientError) as _e:
            LOG.info("Client error %s on %s" , repr(_e), self._name)
            raise
        return True

    async def async_notificationsTask(self, callback=None) -> bool:
        """
        Async notifications taks that can be used to keep track of the speaker actions.
        B&O speakers disconnect after 5 minutes of inactivity, so restart the task if this exits.
        This function automatically updates the internal state of the BeoPlay object.

        callback: a function to be called to use the notification (E.g. to update a UI...)
        """
        if self._clientsession is None:
            LOG.error("Attempt asyncio with no ClientSession")
            return False
        try:
            async with self._clientsession.get(self._host_notifications) as response:
                data = None
                if response.status == 200:
                    while True:
                        data = await response.content.readline()
                        if data and len(data) > 0:
                            data = (
                                data.decode("utf-8").replace("\r", "").replace("\n", "")
                            )
                            if len(data) > 0:
                                LOG.info("Update status: %s %s", self._name, data)
                                data_json = json.loads(data)
                                self._processNotification(data_json)
                                if callback is not None:
                                    callback(data_json["notification"])
                        else:
                            break
                else:
                    LOG.error(
                        "Error %s on %s.",
                        response.status,
                        self._host_notifications,
                    )
                    return False

        except (asyncio.TimeoutError, aiohttp.ClientError) as _e:
            LOG.info("Client error %s on %s" , repr(_e), self._name)
            raise

        return True

    ###############################################################
    # GET ATTRIBUTES FROM THE SPEAKER - NON-BLOCKING CALLS
    ###############################################################

    async def async_get_source(self):
        """Returns the current source friendlyName, or None if not retrieved.

        Also populates self.source_id (the source id, e.g. 'spotify:...@...') and the
        grouping state (primary_jid, listeners, role) from the same ActiveSources payload,
        so consumers get the id and multiroom role without waiting for a notification."""
        self.source = None
        self.source_id = None
        r = await self.async_getReq(BEOPLAY_URL_ACTIVE_SOURCES)
        if r:
            primary = r.get("primaryExperience") or {}
            source = primary.get("source") or {}
            self.source = source.get("friendlyName")
            self.source_id = source.get("id")
            if primary:
                self._update_grouping_from_primary_experience(primary)
            else:
                self._clear_grouping_state()
        return self.source

    # edited to only include in Use sources
    async def async_get_sources(self):
        """Returns a list of available sources, or None if not retrieved."""
        r = await self.async_getReq(BEOPLAY_URL_GET_SOURCES)
        if r:
            # clear previously stored sources
            self.sources = []
            self.sourcesID = []
            self.sourcesBorrowed = []
            for elements in r:
                i = 0
                while i < len(r[elements]):
                    if r[elements][i][1]["inUse"] == True:
                        self.sourcesBorrowed.append(r[elements][i][1]["borrowed"])
                        self.sources.append(r[elements][i][1]["friendlyName"])
                        self.sourcesID.append(r[elements][i][0])
                    i += 1
            return self.sources
        return

    async def async_get_standby(self) -> bool:
        """Returns True of the device is on, False if off or unavailable."""
        r = await self.async_getReq(BEOPLAY_URL_STANDBY)
        if r:
            if r["standby"]["powerState"] == "on":
                self.on = True
            else:
                self.on = False
            return self.on
        return False
    
    async def async_get_sound_mode(self):
        """Returns the current sound mode, or None if not retrieved."""
        self._soundMode = None
        await self.async_get_sound_modes()
        return self._soundMode

    async def async_get_sound_modes(self):
        """Returns a dictionary of available sound modes, or None if not retrieved."""
        r = await self.async_getReq(BEOPLAY_URL_GET_SOUND_MODE)
        if r:
            r = r.get("mode", {"list": []})
            l = r.get("list", [])
            a = r.get("active", None)
            for element in l:
                self._soundModes[element["friendlyName"]] = element["id"]
                if a and a == element["id"]:
                    self._soundMode = element["friendlyName"]
            return self._soundModes
        return
    
    async def async_get_stand_position(self):
        """Returns the stand position, or None if not retrieved."""
        self._standPosition = None
        r = await self.async_getReq(BEOPLAY_URL_STAND_ACTIVE)
        if r and "active" in r:
            if r["active"] is not None:
                self._standPosition = r["active"]
            return self._standPosition
        return

    async def async_get_stand_positions(self):
        """Returns a list of available stand positions, or None if not retrieved."""
        # clear previous stand positions
        self._standPositions = {}
        r = await self.async_getReq(BEOPLAY_URL_STAND)
        if r and "stand" in r:
            if r["stand"] is not None:
                for elements in r["stand"]["list"]:
                    self._standPositions[elements["friendlyName"]] = elements["id"]
                return self._standPositions
        return

    async def async_get_device_info(self):
        """Returns a tuple serialNumber, name, typeNumber, itemNumber"""
        r = await self.async_getReq("BeoDevice")
        if r:
            self._serialNumber = r["beoDevice"]["productId"]["serialNumber"]
            self._name = r["beoDevice"]["productFriendlyName"]["productFriendlyName"]
            self._typeNumber = r["beoDevice"]["productId"]["typeNumber"]
            self._itemNumber = r["beoDevice"]["productId"]["itemNumber"]
            self._softwareVersion = r["beoDevice"]["software"]["version"]
            self._hardwareVersion = r["beoDevice"]["hardware"]["version"]
            self._typeName = r["beoDevice"]["productId"]["productType"]
            return self._serialNumber, self._name, self._typeNumber, self._itemNumber
        return

    ###############################################################
    # COMMANDS - Non Blocking
    ###############################################################

    async def async_get_volume(self):
        """Fetch current speaker volume and range. Sets self.volume (0-1).

        The Speaker/Level resource also carries the device volume range, so capture
        min_volume/max_volume here too — they would otherwise stay None until the first
        VOLUME notification, leaving consumers unable to scale (devices differ, e.g. 0..50
        vs 0..90)."""
        r = await self.async_getReq(BEOPLAY_URL_SET_VOLUME)
        if r and "level" in r:
            self.volume = r["level"] / 100
            if isinstance(r.get("range"), dict):
                if "minimum" in r["range"]:
                    self.min_volume = r["range"]["minimum"] / 100
                if "maximum" in r["range"]:
                    self.max_volume = r["range"]["maximum"] / 100
        return self.volume

    async def async_set_volume(self, volume):
        # store the quantized level we actually send (int(volume*100)/100) rather than the
        # raw input, so a read-back of self.volume matches what the device received
        level = int(volume * 100)
        self.volume = level / 100
        await self.async_postReq("PUT", BEOPLAY_URL_SET_VOLUME, {"level": level})

    async def async_set_mute(self, mute):
        if mute:
            await self.async_postReq("PUT", BEOPLAY_URL_MUTE, {"muted": True})
        else:
            await self.async_postReq("PUT", BEOPLAY_URL_MUTE, {"muted": False})

    async def async_play(self):
        await self.async_postReq("POST", BEOPLAY_URL_PLAY, {})

    async def async_pause(self):
        await self.async_postReq("POST", BEOPLAY_URL_PAUSE, {})

    async def async_stop(self):
        await self.async_postReq("POST", BEOPLAY_URL_STOP, {})

    async def async_stepup(self):
        await self.async_postReq("POST", BEOPLAY_URL_STEPUP, {})

    async def async_stepdown(self):
        await self.async_postReq("POST", BEOPLAY_URL_STEPDOWN, {})

    async def async_forward(self):
        await self.async_postReq("POST", BEOPLAY_URL_FORWARD, {})

    async def async_backward(self):
        await self.async_postReq("POST", BEOPLAY_URL_BACKWARD, {})

    async def async_shuffle(self):
        await self.async_postReq("POST", BEOPLAY_URL_SHUFFLE, {})

    async def async_repeat(self):
        await self.async_postReq("POST", BEOPLAY_URL_REPEAT, {})

    async def async_standby(self):
        await self.async_postReq(
            "PUT", BEOPLAY_URL_STANDBY, {"standby": {"powerState": "standby"}}
        )
        self.on = False

    async def async_turn_on(self):
        """Turn on the device. There is no such thing as an "on" command on B&O 
        equipment, so just select the first source, if it exists."""
        if len(self.sources)>0:
            await self.async_set_source(self.sources[0])
            self.on = True

    async def async_set_source(self, source):
        i = 0
        while i < len(self.sources):
            if self.sources[i] == source:
                chosenSource = self.sourcesID[i]
                await self.async_postReq(
                    "POST",
                    BEOPLAY_URL_ACTIVE_SOURCES,
                    {"primaryExperience": {"source": {"id": chosenSource}}},
                )
            i += 1

    async def async_set_sound_mode(self, soundMode):
        # get sound modes if not already done
        if not self._soundModes:
            await self.async_get_sound_modes()
        
        if soundMode not in self._soundModes:
            raise ValueError("Sound mode not available")
        
        soundModeId = self._soundModes[soundMode]
        
        await self.async_postReq("PUT", BEOPLAY_URL_SET_SOUND_MODE, {"active": soundModeId})
            

    async def async_set_stand_position(self, standPosition):
        if not self._standPositions:
            await self.async_get_stand_positions()
        
        if standPosition not in self._standPositions:
            raise ValueError("Stand position not available")

        standPositionID = self._standPositions.get(standPosition, None)

        await self.async_postReq("PUT", BEOPLAY_URL_STAND_ACTIVE, {"active": standPositionID})

    async def async_join_experience(self):
        """Join whatever experience is currently active on the local network.

        POSTs to /BeoZone/Zone/Device/OneWayJoin. The speaker picks up the
        single playing experience automatically — no source-id needed —
        but you don't get to choose which master to follow when several
        speakers are playing different things at once. Use
        ``async_borrow_source()`` for the targeted "A → B" join instead.
        """
        await self.async_postReq("POST", BEOPLAY_URL_JOIN_EXPERIENCE)

    async def async_leave_experience(self):
        """Leave any current borrowed experience.

        DELETEs /BeoZone/Zone/ActiveSources/primaryExperience. After this
        the speaker returns to its idle state (no primary source set).
        Mirrors the leave-multiroom action exposed by the official Beo
        app's room-grouping UI.
        """
        await self.async_postReq("DELETE", BEOPLAY_URL_LEAVE_EXPERIENCE)

    async def async_get_active_sources(self):
        """Fetch the speaker's current /BeoZone/Zone/ActiveSources.

        Useful for reading ``primaryExperience.source.id`` (needed by
        ``async_borrow_source`` when joining another speaker) and
        ``primaryExperience.source.product.jid`` (master ownership —
        same value pushed onto ``self.primary_jid`` from notifications,
        but a GET is more reliable when notifications have not arrived
        yet, e.g. immediately after the speaker powers on).

        Returns the parsed JSON or ``None`` on error.
        """
        return await self.async_getReq(BEOPLAY_URL_ACTIVE_SOURCES)

    async def async_borrow_source(self, source_id: str):
        """Start playing a specific source on this speaker.

        POSTs ``{"primaryExperience": {"source": {"id": <source_id>}}}``
        to /BeoZone/Zone/ActiveSources. When ``source_id`` is the active
        source-id reported by another speaker on the network, the effect
        is that this speaker joins that speaker's experience — the
        canonical "join A → B" multiroom mechanism used by the official
        Beo app.

        Unlike ``async_join_experience`` (OneWayJoin, which picks the
        single active experience automatically), this lets the caller
        target a specific master when several speakers are playing
        different things at once.

        Typical flow to join this speaker (B) to another speaker (A)::

            active = await beo_a.async_get_active_sources()
            source_id = active["primaryExperience"]["source"]["id"]
            await beo_b.async_borrow_source(source_id)

        ``source_id`` can also be used to start a known external source
        directly (radio, line-in) by passing its source-id from
        ``async_get_sources()``.
        """
        payload = {"primaryExperience": {"source": {"id": source_id}}}
        return await self.async_postReq("POST", BEOPLAY_URL_ACTIVE_SOURCES, payload)

    async def async_clear_queue(self):
        """Delete all items from the play queue."""
        await self.async_postReq("DELETE", BEOPLAY_URL_PLAYQUEUE)

    async def async_get_play_queue(self, offset: int = -1000):
        """Fetch the current play queue.

        B&O paginates this endpoint: the default response only returns a
        handful of items around playNowId (5 on the firmware verified
        against — Beosound CA17). Pass a negative ``offset`` to start
        that many items before the currently playing item; the response
        will then include everything from there to the end of the queue.
        ``-1000`` is a safe upper bound for "give me everything" — B&O
        caps queue length well below that.

        Returns the parsed JSON response or ``None`` on error. Shape::

            {"playQueue": {
                "playNowId":   "plid-5413",     # str on current firmware
                "total":       int,
                "offset":      int,
                "startOffset": int,             # negative = items before current
                "count":       int,
                "repeat":      "off" | "track" | "all",
                "random":      "off" | "on",
                "playQueueItem": [
                    {"id": "plid-5413",
                     "behaviour": "planned",
                     "track": {...},
                     "_links": {
                         "/relation/delete": {"href": "./plid-5413"},
                         "/relation/insert": {"href": "./?id=plid-5413"},
                         "/relation/move":   {"href": "./plid-5413?id={movebeforeid}",
                                              "templated": true}
                     }},
                    ...
                ]
            }}

        Each item exposes HATEOAS ``_links`` pointing at the matching
        ``async_delete_queue_item`` / ``async_move_queue_item`` /
        ``async_insert_queue_item`` operations below.
        """
        return await self.async_getReq(f"{BEOPLAY_URL_PLAYQUEUE}?offset={offset}")

    async def async_delete_queue_item(self, item_id):
        """Remove a single item from the play queue by its B&O id.

        ``item_id`` is the queue-item id as reported by B&O — a string
        like ``"plid-5413"`` on current firmware, an int on older ones.
        It corresponds to the ``id`` field of a ``playQueueItem`` and is
        the same value used in that item's ``_links/delete`` href.
        """
        return await self.async_postReq("DELETE", f"{BEOPLAY_URL_PLAYQUEUE}/{item_id}")

    async def async_move_queue_item(self, item_id, before_id=None):
        """Move an item to a new position in the play queue.

        Without ``before_id`` the item is moved to the end of the queue.
        With ``before_id`` it is moved to immediately before that item.
        Both ids must already exist in the queue (use
        ``async_insert_queue_item`` to add a new item at a specific
        position).

        Mirrors the HATEOAS template
        ``./{item_id}?id={movebeforeid}`` exposed by each playQueueItem.
        """
        path = f"{BEOPLAY_URL_PLAYQUEUE}/{item_id}"
        if before_id is not None:
            path = f"{path}?id={before_id}"
        return await self.async_postReq("PUT", path)

    async def async_set_play_pointer(self, item_id):
        """Jump playback to a specific item already in the play queue.

        POSTs ``{"playPointer": {"playQueueItemId": <item_id>}}`` to
        ``/BeoZone/Zone/PlayQueue/PlayPointer``. The speaker starts
        playing the named item immediately and updates its internal
        playNowId to match. Use this for "jump to this row in the queue
        UI" — much cheaper than clearing and re-pushing the queue.

        ``item_id`` is the same opaque queue-item id used everywhere
        else (``"plid-5413"`` on current firmware, int on legacy).

        B&O returns 204 No Content on success. PUT against the same
        endpoint returns 400 — this method intentionally uses POST.
        """
        path = f"{BEOPLAY_URL_PLAYQUEUE}/PlayPointer"
        payload = {"playPointer": {"playQueueItemId": item_id}}
        return await self.async_postReq("POST", path, payload)

    async def async_insert_queue_item(self, queueItem: dict, after_id=None):
        """Insert a queue item at a specific position.

        ``queueItem`` follows the same envelope as
        ``async_play_queue_item`` — i.e. a dict of shape
        ``{"playQueueItem": {"behaviour": ..., "track": {...}}}``.

        Without ``after_id`` the item is appended to the end of the
        queue (same as ``async_play_queue_item(instantplay=False, ...)``).

        With ``after_id`` the item is inserted immediately after the
        existing queue item with that id — useful for implementing
        "play next" against the currently playing item's id.

        Mirrors the HATEOAS template ``./?id={after_id}`` exposed by
        each playQueueItem.
        """
        if after_id is None:
            return await self.async_postReq("POST", BEOPLAY_URL_PLAYQUEUE, queueItem)
        return await self.async_postReq(
            "POST", f"{BEOPLAY_URL_PLAYQUEUE}?id={after_id}", queueItem,
        )

    async def async_play_queue_item(self, instantplay: bool, queueItem: dict):
        """Play a queue item, from Deezer, TuneIn or DLNA.
        TuneIn Dict structure:
            "playQueueItem": {
               "behaviour": "planned",
                "station": {
                    "tuneIn": {
                    "stationId": "s45455"
                    },
                    "image" : []
                }
            }

        Deezer:
            "playQueueItem": {
                "behaviour": "impulsive",
                "track": {
                    "deezer": {
                        "id": 997764
                    },
                    "image" : []
                }
            }

        DLNA:
            "playQueueItem": {
                "behaviour": "impulsive",
                "track": {
                    "dlna": {
                        "url": "http://192.168.100.124:50599/disk/NON-DLNA-OP01-FLAGS01700000/O0$1$8I96439051.m4a"
                    }
                }
            }

        """
        if instantplay:
            await self.async_postReq(
                "POST", BEOPLAY_URL_PLAYQUEUE + BEOPLAY_URL_PLAYQUEUE_INSTANT, queueItem
            )
        else:
            await self.async_postReq("POST", BEOPLAY_URL_PLAYQUEUE, queueItem)

    async def async_remote_command(self, command : str, toBeReleased :bool = False):
        """
        Send a remote command to the device. Command needs to be one of:  

        Cursor/Select, Cursor/Up, Cursor/Down, Cursor/Left, Cursor/Right, Cursor/Exit, Cursor/Back, Cursor/PageUp, Cursor/PageDown, Cursor/Clear, 
        Stream/Play, Stream/Stop, Stream/Pause, Stream/Wind, Stream/Rewind, Stream/Forward, Stream/Backward, 
        List/StepUp, List/StepDown, List/PreviousElement, List/Shuffle, List/Repeat, 
        Menu/Root, Menu/Option, Menu/Setup, Menu/Contents, Menu/Favorites, Menu/ElectronicProgramGuide, Menu/VideoOnDemand, Menu/Text, Menu/HbbTV,Menu/HomeControl, 
        Device/Information, Device/Eject, Device/TogglePower, Device/Languages, Device/Subtitles, Device/OneWayJoin, Device/Mots, 
        Record/Record, 
        Generic/Blue, Generic/Red, Generic/Green, Generic/Yellow.
        
        toBeReleased: true if this is a button press that is held. Needs to be completed by calling async_remote_release.

        """
        if (command not in BEOPLAY_REMOTE_COMMANDS):
            return
        await self.async_postReq("POST", BEOPLAY_REMOTE_PREFIX + command, {"toBeReleased": toBeReleased})

    async def async_remote_release(self, command : str):
        if (command not in BEOPLAY_REMOTE_COMMANDS):
            return
        await self.async_postReq("POST", BEOPLAY_REMOTE_PREFIX + command + BEOPLAY_URL_RELEASE, {})

    async def async_digits(self, digit : str):
        """
        Send a digit keypress to the device. Digits are 0-9.

        Note: the device expects an integer body ({"digits": 3}); a string
        ({"digits": "3"}) is rejected with 400 on current firmware (verified
        on Beosound Stage). This method casts with int() accordingly.
        """
        if (digit not in BEOPLAY_DIGITS):
            return
        await self.async_postReq("POST", BEOPLAY_DIGITS_URL, {BEOPLAY_DIGITS_KEY: int(digit)})

    ###############################################################
    # ADDITIONAL ENDPOINTS - Non Blocking
    # Mapped live from Beosound Stage + CA17 (2026-06). Write payloads
    # verified against real devices; see docs/api-kartlegging.md.
    ###############################################################

    async def async_ping(self) -> bool:
        """Cheap liveness probe. GET /Ping returns 200 with an empty body
        on a reachable device — lighter than fetching /BeoDevice just to
        check whether the speaker is online. Returns True on 200."""
        if self._clientsession is None:
            LOG.error("Attempt asyncio with no ClientSession")
            return False
        try:
            async with self._clientsession.get(
                BASE_URL.format(self._host, BEOPLAY_URL_PING),
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as resp:
                return resp.status == 200
        except (asyncio.TimeoutError, aiohttp.ClientError) as _e:
            LOG.info("Client error %s on %s", repr(_e), self._name)
            return False

    async def async_all_standby(self):
        """Put the entire Beolink setup into standby (powerState 'allStandby').

        Unlike async_standby() which only affects this device, this powers
        down every networked B&O product at once — the classic "turn
        everything off" behaviour. Use with care."""
        await self.async_postReq(
            "PUT", BEOPLAY_URL_STANDBY, {"standby": {"powerState": "allStandby"}}
        )
        self.on = False

    async def async_reboot(self):
        """Reboot this device (powerState 'reboot'). Takes ~1-2 minutes to
        come back. Valid per the standby endpoint's _capabilities enum."""
        await self.async_postReq(
            "PUT", BEOPLAY_URL_STANDBY, {"standby": {"powerState": "reboot"}}
        )
        self.on = False

    async def async_get_default_volume(self):
        """Return the startup (default) volume level (0-100), or None.

        GET /BeoZone/Zone/Sound/Volume/Speaker/DefaultLevel -> {"defaultLevel": n}.
        Note this is the correct path; the older .../Speaker/Default 404s on
        current firmware."""
        r = await self.async_getReq(BEOPLAY_URL_DEFAULT_VOLUME)
        if r and "defaultLevel" in r:
            return r["defaultLevel"]
        return None

    async def async_set_default_volume(self, level: int):
        """Set the startup (default) volume level (0-100).

        PUT {"defaultLevel": <int>} to .../Speaker/DefaultLevel."""
        return await self.async_postReq(
            "PUT", BEOPLAY_URL_DEFAULT_VOLUME, {"defaultLevel": int(level)}
        )

    async def async_get_sound_adjustment(self):
        """Return the bass/treble/loudness adjustment, or None.

        GET /BeoZone/Zone/Sound/Adjustment ->
            {"adjustment": {"bass": -10..10, "treble": -10..10, "loudness": bool, ...}}
        The nested _capabilities.range gives the valid bass/treble range."""
        r = await self.async_getReq(BEOPLAY_URL_SOUND_ADJUSTMENT)
        if r and "adjustment" in r:
            return r["adjustment"]
        return None

    async def async_set_sound_adjustment(self, bass: int = None, treble: int = None,
                                         loudness: bool = None):
        """Set bass, treble and/or loudness. Partial updates are accepted —
        only pass the fields you want to change.

        PUT {"adjustment": {"bass": n, "treble": n, "loudness": bool}}."""
        adj = {}
        if bass is not None:
            adj["bass"] = int(bass)
        if treble is not None:
            adj["treble"] = int(treble)
        if loudness is not None:
            adj["loudness"] = bool(loudness)
        if not adj:
            return False
        return await self.async_postReq(
            "PUT", BEOPLAY_URL_SOUND_ADJUSTMENT, {"adjustment": adj}
        )

    async def async_reset_sound_adjustment(self):
        """Reset bass/treble/loudness to defaults (PUT .../Adjustment/reset)."""
        return await self.async_postReq(
            "PUT", BEOPLAY_URL_SOUND_ADJUSTMENT + "/reset"
        )

    async def async_get_sound_explore(self):
        """Return the Sound Explore DSP settings (Beosound Stage), or None.

        On devices that support it (feature SOUND_EXPLORE — e.g. Stage),
        GET /BeoZone/Zone/Sound/Explore ->
            {"explore": {"toneTouch": {...}, "contentProcessing": "off|low|high",
                         "upmix": bool, "virtualize": bool, "lfeTuning": bool, ...}}
        Devices without it (e.g. CA17) return their ToneTouch instead and a
        GET here 404s; Stage's ToneTouch endpoint conversely 501s and points
        here."""
        r = await self.async_getReq(BEOPLAY_URL_SOUND_EXPLORE)
        if r and "explore" in r:
            return r["explore"]
        return None

    async def async_set_sound_explore(self, content_processing: str = None,
                                      upmix: bool = None, virtualize: bool = None,
                                      lfe_tuning: bool = None):
        """Set Sound Explore DSP options (Beosound Stage). Partial updates OK.

        content_processing: 'off' | 'low' | 'high'
        upmix / virtualize / lfe_tuning: bool

        PUT {"explore": {...}}."""
        exp = {}
        if content_processing is not None:
            exp["contentProcessing"] = content_processing
        if upmix is not None:
            exp["upmix"] = bool(upmix)
        if virtualize is not None:
            exp["virtualize"] = bool(virtualize)
        if lfe_tuning is not None:
            exp["lfeTuning"] = bool(lfe_tuning)
        if not exp:
            return False
        return await self.async_postReq(
            "PUT", BEOPLAY_URL_SOUND_EXPLORE, {"explore": exp}
        )

    async def async_get_buffer_setup(self):
        """Return the net-radio buffer time in seconds (feature
        BUFFER_SETUP_NETRADIO), or None.

        GET /BeoZone/Zone/Sound/BufferSetup -> {"netRadio": {"bufferTime": n, ...}}.
        _capabilities.range lists the discrete valid steps (e.g. 0, 2-3,
        5-20/5, 30-60/15)."""
        r = await self.async_getReq(BEOPLAY_URL_BUFFER_SETUP)
        if r and "netRadio" in r:
            return r["netRadio"].get("bufferTime")
        return None

    async def async_set_buffer_setup(self, seconds: int):
        """Set the net-radio buffer time (seconds). Value must match one of
        the discrete steps the device reports in its capabilities."""
        return await self.async_postReq(
            "PUT", BEOPLAY_URL_BUFFER_SETUP, {"netRadio": {"bufferTime": int(seconds)}}
        )

    async def async_get_sleep_timer(self):
        """Return the sleep-timer duration in minutes (0 = inactive), or None.

        GET /BeoDevice/powerManagement/sleepTimer ->
            {"sleepTimer": {"duration": 0..60, ...}}."""
        r = await self.async_getReq(BEOPLAY_URL_SLEEP_TIMER)
        if r and "sleepTimer" in r:
            return r["sleepTimer"].get("duration")
        return None

    async def async_set_sleep_timer(self, minutes: int):
        """Arm the sleep timer (0-60 minutes). After the duration elapses the
        device goes to standby.

        PUT {"sleepTimer": {"duration": <int>}}."""
        return await self.async_postReq(
            "PUT", BEOPLAY_URL_SLEEP_TIMER, {"sleepTimer": {"duration": int(minutes)}}
        )

    async def async_cancel_sleep_timer(self):
        """Cancel a running sleep timer (DELETE .../sleepTimer; duration -> 0)."""
        return await self.async_postReq("DELETE", BEOPLAY_URL_SLEEP_TIMER)

    async def async_get_snapshots(self):
        """Return the list of device-side snapshot buttons, or None.

        GET /BeoZone/Zone/Snapshot ->
            {"snapshot": {"list": [{"id": "button-...", "elements": [...],
                                    "sourceId": "...", ...}, ...]}}
        Each button stores a scene (source, and on some devices soundMode).
        Stage exposes its physical button-tv / button-music here in addition
        to button-mybutton-1..4."""
        r = await self.async_getReq(BEOPLAY_URL_SNAPSHOT)
        if r and "snapshot" in r:
            return r["snapshot"].get("list", [])
        return None

    async def async_activate_snapshot(self, snapshot_id: str):
        """Recall a stored snapshot/scene (PUT .../Snapshot/Activate/<id>)."""
        return await self.async_postReq(
            "PUT", f"{BEOPLAY_URL_SNAPSHOT}/Activate/{snapshot_id}"
        )

    async def async_persist_snapshot(self, snapshot_id: str):
        """Store the current state onto a snapshot button
        (PUT .../Snapshot/Persist/<id>)."""
        return await self.async_postReq(
            "PUT", f"{BEOPLAY_URL_SNAPSHOT}/Persist/{snapshot_id}"
        )

    async def async_reset_snapshot(self, snapshot_id: str):
        """Clear a snapshot button (PUT .../Snapshot/Reset/<id>)."""
        return await self.async_postReq(
            "PUT", f"{BEOPLAY_URL_SNAPSHOT}/Reset/{snapshot_id}"
        )

    async def async_get_home_timers(self):
        """Return the device-side alarm/timer list, or None.

        GET /BeoHome/trigger/timerList -> {"timerList": {"timer": [...]}}.
        Present on speakers (Stage, CA17), absent on the BeoLink Converter.
        Creating timers (POST) is not implemented here: the 'active' field
        takes an undocumented enum that still needs to be captured from a
        timer created via the official Beo app."""
        r = await self.async_getReq(BEOPLAY_URL_HOME_TIMERS)
        if r and "timerList" in r:
            return r["timerList"].get("timer", [])
        return None


    ###############################################################
    # REQUESTS (BLOCKING) NETWORK CALLS
    ###############################################################

    def _getReq(self, path):
        try:
            if self._connfail:
                LOG.debug("Connfail: %i", self._connfail)
                self._connfail -= 1
                return False
            r = requests.get(BASE_URL.format(self._host, path), timeout=TIMEOUT)
            if r.status_code != 200:
                return None
            return json.loads(r.text)
        except requests.exceptions.RequestException as err:
            LOG.debug("Exception: %s", str(err))
            self._connfail = CONNFAILCOUNT
            return None

    def _postReq(self, type, path, data: dict = {}):
        try:
            r = None
            if self._connfail:
                LOG.debug("Connfail: %i", self._connfail)
                self._connfail -= 1
                return False
            if type == "PUT":
                r = requests.put(
                    BASE_URL.format(self._host, path),
                    json=data,
                    timeout=TIMEOUT,
                )
            elif type == "POST":
                if data is None or data == "":
                    r = requests.post(
                        BASE_URL.format(self._host, path), timeout=TIMEOUT
                    )
                else:
                    r = requests.post(
                        BASE_URL.format(self._host, path),
                        json=data,
                        timeout=TIMEOUT,
                    )
            elif type == "DELETE":
                r = requests.delete(BASE_URL.format(self._host, path), timeout=TIMEOUT)
            if r:
                LOG.debug("Response: %s", r.content)
                if r.status_code == 200:
                    return True
            return False
        except requests.exceptions.RequestException as err:
            LOG.debug("Exception: %s", str(err))
            self._connfail = CONNFAILCOUNT
            return False

    ###############################################################
    # GET ATTRIBUTES FROM THE SPEAKER - BLOCKING CALLS
    ###############################################################

    # edited to only include in Use sources
    def getSources(self):
        r = self._getReq(BEOPLAY_URL_GET_SOURCES)
        if r:
            for elements in r:
                i = 0
                while i < len(r[elements]):
                    if r[elements][i][1]["inUse"] == True:
                        self.sourcesBorrowed.append(r[elements][i][1]["borrowed"])
                        self.sources.append(r[elements][i][1]["friendlyName"])
                        self.sourcesID.append(r[elements][i][0])
                    i += 1

    def getSource(self):
        self.source = None
        r = self._getReq(BEOPLAY_URL_ACTIVE_SOURCES)
        if r:
            self.source = r["primaryExperience"]["source"]["friendlyName"] if "friendlyName" in r["primaryExperience"]["source"] else None
            self.listeners = [listener["jid"] for listener in r["primaryExperience"]["listenerList"]["listener"]] if "listenerList" in r["primaryExperience"] else []
        return self.source

    def getStandby(self):
        r = self._getReq(BEOPLAY_URL_STANDBY)
        if r:
            if r["standby"]["powerState"] == "on":
                self.on = True
            else:
                self.on = False

    def getSoundMode(self):
        """ Get sound mode. Return the current active sound mode or None if not retreived."""
        self._soundMode = None
        self.getSoundModes()
        return self._soundMode

    def getSoundModes(self):
        """ Get sound modes. You need to call this before reading soundMode or soundModes."""
        r = self._getReq(BEOPLAY_URL_GET_SOUND_MODE)
        if r:
            r = r.get("mode", {"list": []})
            l = r.get("list", [])
            a = r.get("active", None)
            for element in l:
                self._soundModes[element["friendlyName"]] = element["id"]
                if a and a == element["id"]:
                    self._soundMode = element["friendlyName"]
            return self._soundModes
        return None

    def getStandPosition(self):
        self._standPosition = None
        r = self._getReq(BEOPLAY_URL_STAND_ACTIVE)
        if r and "active" in r:
            if r["active"] is not None:
                self._standPosition = r["active"] 
            return self._standPosition
        return None

    def getStandPositions(self):
        self._standPositions = {}
        r = self._getReq(BEOPLAY_URL_STAND)
        if r and "stand" in r:
            if r["stand"] is not None:
                for elements in r["stand"]["list"]:
                    self._standPositions[elements["friendlyName"]] = elements["id"]
                return self._standPositions
        return

    def getDeviceInfo(self):
        r = self._getReq("BeoDevice")
        if r:
            self._serialNumber = r["beoDevice"]["productId"]["serialNumber"]
            self._name = r["beoDevice"]["productFriendlyName"]["productFriendlyName"]
            self._typeNumber = r["beoDevice"]["productId"]["typeNumber"]
            self._itemNumber = r["beoDevice"]["productId"]["itemNumber"]
            self._softwareVersion = r["beoDevice"]["software"]["version"]
            self._hardwareVersion = r["beoDevice"]["hardware"]["version"]
            self._typeName = r["beoDevice"]["productId"]["productType"]
    ###############################################################
    # COMMANDS - Blocking
    ###############################################################

    def setVolume(self, volume):
        self.volume = volume
        volume = int(volume * 100)
        self._postReq("PUT", BEOPLAY_URL_SET_VOLUME, {"level": volume})

    def setMute(self, mute):
        if mute:
            self._postReq("PUT", BEOPLAY_URL_MUTE, {"muted": True})
        else:
            self._postReq("PUT", BEOPLAY_URL_MUTE, {"muted": False})

    def Play(self):
        self._postReq("POST", BEOPLAY_URL_PLAY, {})

    def Pause(self):
        self._postReq("POST", BEOPLAY_URL_PAUSE, {})

    def Stop(self):
        self._postReq("POST", BEOPLAY_URL_STOP, {})

    def StepUp(self):
        self._postReq("POST", BEOPLAY_URL_STEPUP, {})

    def StepDown(self):
        self._postReq("POST", BEOPLAY_URL_STEPDOWN, {})

    def Forward(self):
        self._postReq("POST", BEOPLAY_URL_FORWARD, {})

    def Backward(self):
        self._postReq("POST", BEOPLAY_URL_BACKWARD, {})

    def Repeat(self):
        self._postReq("POST", BEOPLAY_URL_REPEAT, {})

    def Shuffle(self):
        self._postReq("POST", BEOPLAY_URL_SHUFFLE, {})

    def Standby(self):
        self._postReq(
            "PUT", BEOPLAY_URL_STANDBY, {"standby": {"powerState": "standby"}}
        )
        self.on = False

    def turnOn(self):
        """Turn on the device. There is no such thing as an "on" command on B&O 
        equipment, so just select the first source, if it exists."""
        if len(self.sources)>0:
            self.setSource(self.sources[0])
            self.on = True

    def setSource(self, source):
        i = 0
        while i < len(self.sources):
            if self.sources[i] == source:
                chosenSource = self.sourcesID[i]
                self._postReq(
                    "POST",
                    BEOPLAY_URL_ACTIVE_SOURCES,
                    {"primaryExperience": {"source": {"id": chosenSource}}},
                )
            i += 1

    def setSoundMode(self, soundMode):
        """Get sound modes if not already done."""
        if not self._soundModes:
            self.getSoundModes()
        
        if soundMode not in self._soundModes:
            raise ValueError("Sound mode not available")
        
        soundModeId = self._soundModes[soundMode]
        
        self._postReq("PUT", BEOPLAY_URL_SET_SOUND_MODE, {"active": soundModeId})

    def setStandPosition(self, standPosition):
        """Get sound modes if not already done."""
        if not self._standPositions:
            self.getStandPositions()
        
        if standPosition not in self._standPositions:
            raise ValueError("Stand position not available")

        standPositionID = self._standPositions.get(standPosition)

        self._postReq("PUT", BEOPLAY_URL_STAND_ACTIVE, {"active": standPositionID})

    def joinExperience(self):
        self._postReq("POST", BEOPLAY_URL_JOIN_EXPERIENCE, {})

    def leaveExperience(self):
        self._postReq("DELETE", BEOPLAY_URL_LEAVE_EXPERIENCE, {})

    def playQueueItem(self, instantplay: bool, queueItem: dict):
        if instantplay:
            self._postReq(
                "POST", BEOPLAY_URL_PLAYQUEUE + BEOPLAY_URL_PLAYQUEUE_INSTANT, queueItem
            )
        else:
            self._postReq("POST", BEOPLAY_URL_PLAYQUEUE, queueItem)

    ###############################################################
    # PARSE NOTIFICATIONS MESSAGES
    ###############################################################

    def _processVolume(self, data):
        if (
            data["notification"]["type"] == "VOLUME"
            and data["notification"]["data"] is not None
        ):
            self.volume = int(data["notification"]["data"]["speaker"]["level"]) / 100
            self.min_volume = (
                int(data["notification"]["data"]["speaker"]["range"]["minimum"]) / 100
            )
            self.max_volume = (
                int(data["notification"]["data"]["speaker"]["range"]["maximum"]) / 100
            )
            self.muted = data["notification"]["data"]["speaker"]["muted"]

    @property
    def my_jid(self) -> Optional[str]:
        """This speaker's own JID, built from productId fields.

        Returns None until ``async_get_device_info()`` has populated
        ``_typeNumber``, ``_itemNumber`` and ``_serialNumber``. The JID
        format is the canonical
        ``{typeNumber}.{itemNumber}.{serialNumber}@products.bang-olufsen.com``
        — same value B&O reports as ``product.jid`` on its own
        ActiveSources responses, so callers can compare against
        ``self.primary_jid`` to detect role.
        """
        if not (self._typeNumber and self._itemNumber and self._serialNumber):
            return None
        return f"{self._typeNumber}.{self._itemNumber}.{self._serialNumber}@products.bang-olufsen.com"

    def _clear_grouping_state(self) -> None:
        """Drop grouping/role data — call when this speaker can no longer
        be part of a multiroom session (standby, source cleared, etc.)."""
        self.role = None
        self.primary_jid = None
        self.listeners = []

    def _recompute_role(self) -> None:
        """Derive ``self.role`` from ``self.primary_jid``, ``self.listeners``
        and ``self.my_jid``.

        Heuristic only — consumers that need authoritative multiroom-join
        state should derive it themselves from ``primary_jid`` + ``listeners``
        plus their own knowledge (e.g. whether the user explicitly /joined
        this speaker). This property returns ``None`` rather than guessing
        when ``my_jid`` isn't available yet (device info not fetched).
        """
        my = self.my_jid
        if my is None:
            self.role = None
            return
        if self.primary_jid == my:
            self.role = "primary"
        elif my in self.listeners:
            self.role = "listener"
        else:
            self.role = None

    def _update_grouping_from_primary_experience(self, primary_experience: dict) -> None:
        """Extract primary_jid + listeners from a primaryExperience block and recompute
        role. Shared between the SOURCE/SOURCE_EXPERIENCE_CHANGED notifications and the
        ActiveSources GET."""
        source = primary_experience.get("source") or {}
        product = source.get("product") or {}
        self.primary_jid = product.get("jid")
        # listeners live under listenerList.listener as [{"jid": ...}, ...]; normalize to
        # a flat list of jid strings so consumers never see the raw dict shape
        listeners = (primary_experience.get("listenerList") or {}).get("listener") or []
        self.listeners = [
            listener["jid"]
            for listener in listeners
            if isinstance(listener, dict) and "jid" in listener
        ]
        self._recompute_role()

    def _processSource(self, data):
        if (
            data["notification"]["type"] == "SOURCE"
            and data["notification"]["data"] is not None
        ):
            if not data["notification"]["data"]:
                self.source = None
                self.source_id = None
                self.state = None
                self.on = False
                self._clear_grouping_state()
            else:
                primary = data["notification"]["data"]["primaryExperience"]
                self.source = primary["source"]["friendlyName"]
                self.source_id = primary["source"].get("id")
                self.state = primary["state"]
                self.on = True
                self._update_grouping_from_primary_experience(primary)
            self.media_url = None
            self.media_track = None
            self.media_artist = None
            self.media_album = None
            self.media_genre = None
            self.media_country = None
            self.media_languages = None

#    def _processPrimaryExperience(self, data):
#        if data["notification"]["type"] == "SOURCE":
#            self.primary_experience = data["primary"]

    def _processSourceExperienceChanged(self, data):
        if data["notification"]["type"] != "SOURCE_EXPERIENCE_CHANGED":
            return
        payload = data["notification"]["data"]
        # B&O sends ``data: null`` to signal the experience was torn down
        # entirely, and ``data: {}`` for a transient empty update. Treat
        # both as "no grouping" so we don't keep stale primary_jid/listeners.
        if not payload:
            self._clear_grouping_state()
        else:
            primary = payload.get("primaryExperience") or {}
            self._update_grouping_from_primary_experience(primary)
        LOG.debug(
            "[%s] SOURCE_EXPERIENCE_CHANGED: role=%s, primary_jid=%s, listeners=%s",
            getattr(self, "_name", "?"),
            self.role,
            self.primary_jid,
            self.listeners,
        )

    def _processState(self, data):
        """Progress information provides info about the current state of play.
        It is only reliable if the device is on."""
        if not (
            data["notification"]["type"] == "PROGRESS_INFORMATION"
            and data["notification"]["data"] is not None
        ):
            return
        self.state = data["notification"]["data"].get("state")
        # Stop / standby implies any multiroom session this speaker was
        # part of is over — clear so consumers don't see stale role.
        if self.state in ("stop", "stopped", "off", "standby"):
            self.on = False
            self._clear_grouping_state()
            LOG.debug(
                "[%s] STATE %s → cleared grouping",
                getattr(self, "_name", "?"), self.state,
            )

    def _processMusicInfo(self, data):
        if data["notification"]["type"] == "NOW_PLAYING_STORED_MUSIC":
            if data["notification"]["data"]["trackImage"]:
                self.media_url = data["notification"]["data"]["trackImage"][0]["url"]
            else:
                self.media_url = None
            self.media_artist = data["notification"]["data"]["artist"]
            self.media_album = data["notification"]["data"]["album"]
            self.media_track = data["notification"]["data"]["name"]
            self.media_genre = data["notification"]["data"]["genre"]
            self.media_country = None
            self.media_languages = None

        elif data["notification"]["type"] == "NOW_PLAYING_STORED_VIDEO":     
            self.media_url = None
            self.media_artist = None
            self.media_album = None
            self.media_track = data["notification"]["data"]["name"]
            self.media_genre = None
            self.media_country = None
            self.media_languages = None

        elif data["notification"]["type"] == "NOW_PLAYING_NET_RADIO":
            self.media_url = None
            self.media_artist = None
            self.media_album = None
            self.media_genre = None
            self.media_country = None
            self.media_languages = None
            if (
                "image" in data["notification"]["data"]
                and data["notification"]["data"]["image"]
            ):
                self.media_url = data["notification"]["data"]["image"][0]["url"]
                self.media_url = self.media_url.replace(
                    ".:8080/", ":8080/"
                )  # some B&O devices provide a hostname with trailing '.' which doesn't resolve
            if "name" in data["notification"]["data"]:
                self.media_artist = data["notification"]["data"]["name"]
            if "liveDescription" in data["notification"]["data"]:
                self.media_track = data["notification"]["data"]["liveDescription"]
            if "genre" in data["notification"]["data"]:
                self.media_genre = data["notification"]["data"]["genre"]
            if "country" in data["notification"]["data"]:
                self.media_country = data["notification"]["data"]["country"]
            if "languages" in data["notification"]["data"]["languages"]:
                self.media_languages = data["notification"]["data"]["languages"]

        elif data["notification"]["type"] == "NOW_PLAYING_LEGACY":
            self.media_url = None
            self.media_artist = None
            self.media_album = None
            self.media_genre = None
            self.media_country = None
            self.media_languages = None
            self.media_track = str(data["notification"]["data"]["trackNumber"])
            if data["notification"]["kind"] == "playing":
                self.on = True
            else:
                self.on = False
            self.state = data["notification"]["kind"]

        elif data["notification"]["type"] == "NOW_PLAYING_ENDED":
            self.media_url = None
            self.media_artist = None
            self.media_album = None
            self.media_genre = None
            self.media_country = None
            self.media_languages = None
            self.media_track = None

        elif data["notification"]["type"] == "NUMBER_AND_NAME":
            self.media_url = None
            self.media_artist = None
            self.media_album = None
            self.media_genre = None
            self.media_country = None
            self.media_languages = None
            self.media_track = (
                str(data["notification"]["data"]["number"])
                + ". "
                + data["notification"]["data"]["name"]
            )

    def _processSoundMode(self, data):
        if data["notification"]["type"] == "SOUND_ACTIVE_MODE_CHANGED":
            self._soundMode = data["notification"]["data"]["friendlyName"]


    def _processNotification(self, data):
        """Cumulative process all the potential notification information."""
        try:
            # get volume
            self._processVolume(data)
            # get source
            self._processSource(data)
            # get source experience
            self._processSourceExperienceChanged(data)
            # get state
            self._processState(data)
            # get currently playing music info
            self._processMusicInfo(data)
            # get sound mode
            self._processSoundMode(data)
        except KeyError:
            LOG.debug("Malformed notification: %s", str(data))
