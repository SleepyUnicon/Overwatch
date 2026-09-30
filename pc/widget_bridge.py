"""Bridge + widgets, as a SUBCLASS.

Not an edit to pc/bridge.py, and that is the whole point: the author ships
releases on his own cadence and a fork that patches his files turns every one
of them into a merge conflict. Everything here is additive -- unknown types
still fall through to his on_message, which ignores them exactly as before.
"""
import sys

import time

from pc import protocol
from pc.bridge import Bridge
from pc.music import MusicWidget
from pc.widgets import Launcher

# V2 panels: pages whose content is described here rather than written in
# C. Imported lazily-ish -- at module scope, but the bridge works without
# any panel registered, so a broken import here cannot take the dials down.
from V2 import host_panel
from V2 import meeting_panel
from V2 import tool_panel
from V2 import window_panel
from V2.panel import Panels

# How often the player is read while it is running.
#
# Two seconds is chosen against the local tick, not against how fast a track
# changes: ui_music.c advances the position itself between readings, so this
# only has to catch a track CHANGE before the bar drifts visibly. Each poll is
# one osascript spawn at about 36 ms.
MUSIC_POLL_S = 2.0

# And how often while it is closed. A machine with Spotify shut is the common
# case for most of the day, and paying a spawn every two seconds to be told
# "still closed" is the sort of idle cost that gets a login agent noticed.
MUSIC_IDLE_POLL_S = 15.0

# How often a panel is rebuilt. Each one costs a few process spawns, and every
# reading on the first panel -- uptime, disk, memory -- moves far too slowly
# for anybody to catch it being ten seconds stale.
PANEL_POLL_S = 10.0


def _default_panels():
    """The panels this daemon ships with.

    A function rather than a constant so a test can pass its own set and never
    spawn `pmset` -- and so the list of what is on the device is one readable
    place rather than scattered through __init__.
    """
    ps = Panels()
    ps.add(host_panel.build, on_tap=host_panel.on_tap)
    ps.add(window_panel.build, on_tap=window_panel.on_tap)
    ps.add(meeting_panel.build, on_tap=meeting_panel.on_tap)
    ps.add(tool_panel.build, on_tap=tool_panel.on_tap)
    return ps


class WidgetBridge(Bridge):
    def __init__(self, *a, launcher=None, music=None, panels=None,
                 clock=time.monotonic, **kw):
        super().__init__(*a, **kw)
        self._launcher = launcher or Launcher()
        self._music = music or MusicWidget()
        self._clock = clock
        self._next_track = 0.0
        self._last_track = None
        self._panels = panels if panels is not None else _default_panels()
        self._next_panel = 0.0

    def _send_checked(self, msg):
        """Every production writer uses encode_checked, never plain encode.

        CLAUDE.md is blunt about why: the board DROPS an over-long line whole,
        with no error on either side, so the panel stops updating while this
        log keeps reporting success. The guard shipped with no production
        caller once already; it is not going to be two.
        """
        raw, why = protocol.encode_checked(msg)
        if raw is None:
            print("[widgets] not sent: %s" % why, file=sys.stderr)
            return False
        self._write(msg)
        return True

    def greet(self):
        """The board has connected. Tell it what its buttons say.

        On every connection, not just the first: the daemon restarts for its
        own updates and the board has no memory of the table across a reboot.
        Same reasoning as proto_send_pref riding along with every hello.
        """
        super().greet()
        self._send_checked(self._launcher.apps_message())
        # Panels too, and for the same reason: the board keeps no memory of
        # them across a reboot, and until one arrives the page is not in the
        # navigation at all.
        self._push_panels(force=True)

    def poll_if_changed(self):
        """His fast tick, plus the player.

        Overridden rather than bolted onto the main loop because this is
        already the method that runs often and only while the board is
        provably alive (claude_usage_bridge.py:1224) -- a poll that writes
        into a port nobody is listening on is the part worth not doing.
        """
        super().poll_if_changed()
        # A save from the web config lands as a new mtime; push the new tile
        # names down before anybody taps a slot that has moved.
        if self._launcher.reload_if_changed():
            print("[widgets] launcher table reloaded", file=sys.stderr)
            self._send_checked(self._launcher.apps_message())
        self._poll_music()
        self._poll_panels()

    def _poll_panels(self):
        now = self._clock()
        if now < self._next_panel:
            return
        self._next_panel = now + PANEL_POLL_S
        self._push_panels()

    def _push_panels(self, force=False):
        if force:
            self._panels.forget()
        for msg in self._panels.messages():
            self._send_checked(msg)

    def _poll_music(self):
        now = self._clock()
        if now < self._next_track:
            return
        msg = self._music.poll()
        if msg is None:
            self._next_track = now + MUSIC_IDLE_POLL_S
            return
        # Back off while there is nothing to watch. `why` is the unavailable
        # shape; a closed player is not going to open between two ticks.
        self._next_track = now + (MUSIC_IDLE_POLL_S if "why" in msg
                                  else MUSIC_POLL_S)
        # Quiet when nothing moved. The board holds the last reading and ticks
        # the position itself, so resending an identical line spends the line
        # budget to tell it what it already knows -- the same reasoning as his
        # poll_if_changed being separate from poll_once.
        if msg == self._last_track:
            return
        self._last_track = msg
        self._send_checked(msg)

    def on_message(self, msg):
        if self._music.handles(msg):
            self._music.on_command(msg)
            # Ask again promptly: the player has just been told to do
            # something and the next scheduled poll could be two seconds out,
            # which is long enough for a button to feel dead.
            self._next_track = 0.0
            return
        if self._panels.handles(msg):
            self._panels.on_tap(msg)
            # Whatever the tile did may have changed what the panel says, and
            # the next scheduled rebuild could be ten seconds out -- which is
            # long enough for a button to feel dead.
            self._next_panel = 0.0
            return
        if self._launcher.handles(msg):
            reply = self._launcher.on_launch(msg)
            if reply is not None:
                self._send_checked(reply)
            return
        return super().on_message(msg)
