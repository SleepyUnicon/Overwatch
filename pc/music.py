"""The transport widget's half: read whatever is playing, relay three commands.

Player-agnostic by asking each known player, in order, whether it is running
and then talking to the first one that is. Spotify and Apple Music both expose
the same four verbs and the same four facts over AppleScript, so the only
thing that differs between them is the application name and one unit.

What this does NOT reach is a browser tab. Controlling that needs the system
media keys, which are NX events rather than key codes and cannot be sent from
AppleScript - it takes a compiled helper. Out of scope for a device that
installs with one command.

macOS only today. Read through one osascript call and nothing else: no API,
no token, no network, which keeps this widget inside the promise README.md
makes about the rest of the product.

Standard library only (CLAUDE.md).
"""
import subprocess
import sys

from pc import macperm

from pc import protocol

# Mirrors TEXT_MAX in firmware/src/ui_music.c. 320 px of montserrat_16 is
# about 34 characters and the title is inset 16 px each side; 28 is what sits
# inside the panel rather than touching both edges.
TEXT_MAX = 28

# One call, not five. osascript costs about 36 ms to spawn on an M-series Mac
# (measured 2026-09-22, ten calls averaged), and that is spawn cost, not work:
# asking for five fields separately is five spawns and 180 ms of a poll that
# runs every two seconds. Everything this page draws comes back from this one
# script, newline-delimited.
#
# `application "Spotify" is running` is the guard, and it is load-bearing.
# A bare `tell application "Spotify" to ...` LAUNCHES Spotify when it is not
# running -- so a board plugged in at the start of the day would start playing
# music nobody asked for. The `is running` test does not.
# Asked in order; the first that is RUNNING wins. `is running` is the whole
# trick: a bare `tell application "X"` LAUNCHES X, so a board plugged in at
# breakfast would start a music player nobody asked for.
PLAYERS = ("Spotify", "Music")

_READ_TMPL = '''
if application "%s" is running then
  tell application "%s"
    set s to player state as text
    try
      set n to name of current track
      set a to artist of current track
      set d to duration of current track
      set p to player position
    on error
      return "idle"
    end try
  end tell
  return s & linefeed & n & linefeed & a & linefeed & p & linefeed & d
else
  return "closed"
end if
'''

_VERB = {
    "play": "playpause",
    "next": "next track",
    "prev": "previous track",
}

# macOS refuses an Apple event with this when the user has not granted (or has
# revoked) Automation permission. It is worth its own message because the cure
# is a trip to System Settings, and because the daemon is a LOGIN AGENT: the
# prompt appears once, unattended, and a missed click looks identical to a
# broken widget forever after.
# Shared with the launcher, which fails the same way for the same reason.
_TCC_DENIED = macperm.TCC_DENIED

TIMEOUT_S = 5


def _osa(script):
    """Run one AppleScript. Returns (stdout, err_or_None)."""
    if sys.platform != "darwin":
        return None, "Spotify control needs a Mac"
    try:
        p = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None, "Could not reach the player"
    if p.returncode != 0:
        # stderr is not relayed verbatim. It can carry the script, and the
        # script names the user's player state; the board gets a sentence this
        # file chose. Same reflex as CLAUDE.md's rule about serial contents.
        if _TCC_DENIED in (p.stderr or ""):
            return None, "Allow Overwatch to control music in Settings"
        return None, "The player did not answer"
    return (p.stdout or "").strip(), None


def _fit(s):
    return s[:TEXT_MAX].strip()


def _duration_seconds(raw):
    """Spotify's `duration` is MILLISECONDS; `player position` is seconds.

    Two units in one script, which is the same trap docs/multi-provider.md
    records for the desktop cache (ms) sitting beside Codex (s). Handled the
    way that document says to handle it -- range-checked here, at the parser,
    because this is the only place the unit is known. No real track is 10000
    seconds long and none is 200 milliseconds, so the two ranges do not
    overlap and the check cannot pick wrong.
    """
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return -1
    if v <= 0:
        return -1
    return int(v / 1000) if v > 10000 else int(v)


class MusicWidget:
    """Polls whichever player is running and answers the board's three buttons.

    `osa` is injected so no test ever talks to a real player - or trips the
    macOS Automation prompt on whoever is running the suite.
    """

    def __init__(self, osa=None, players=PLAYERS):
        self._osa = osa or _osa
        self._players = tuple(players)
        # Which player answered last. Tried FIRST next time, so a machine
        # running two of them does not flip between them between polls, and
        # a command lands on the one the panel is currently showing.
        self._last = None

    def _order(self):
        if self._last and self._last in self._players:
            return (self._last,) + tuple(p for p in self._players
                                         if p != self._last)
        return self._players

    # --- inbound -----------------------------------------------------
    def handles(self, msg):
        return msg.get("t") == "music"

    def on_command(self, msg):
        """Run one of three verbs on the player that is actually playing.

        Returns None: the next poll is the reply. The board does not repaint
        optimistically (ui_music.c on_cmd), so there is nothing here for an
        ack to correct.
        """
        verb = _VERB.get(msg.get("cmd"))
        if verb is None:
            return None
        for name in self._order():
            out, err = self._osa('if application "%s" is running then '
                                 'tell application "%s" to %s' % (name, name, verb))
            if err is None:
                self._last = name
                return None
        return None

    # --- outbound ----------------------------------------------------
    def poll(self):
        """One `track` message from the first player that is running."""
        last_err = None
        for name in self._order():
            out, err = self._osa(_READ_TMPL % (name, name))
            if err is not None:
                last_err = err
                continue
            if out == "closed":
                continue            # not this one; try the next
            self._last = name
            if out == "idle":
                return self._unavailable("%s has nothing queued" % name)
            parts = (out or "").split("\n")
            if len(parts) < 5:
                return self._unavailable("The player did not answer")
            state, nm, artist, pos, dur = parts[0], parts[1], parts[2], parts[3], parts[4]
            try:
                pos_s = int(float(pos))
            except (TypeError, ValueError):
                pos_s = -1
            return {"t": "track", "v": protocol.VERSION,
                    "a": _fit(artist), "n": _fit(nm),
                    "st": 1 if state.strip() == "playing" else 0,
                    "pos": pos_s, "dur": _duration_seconds(dur)}
        if last_err is not None:
            return self._unavailable(last_err)
        return self._unavailable("No music player running")

    def _unavailable(self, why):
        # The board keeps 47 characters of it (ui_music.h), so the sentence is
        # trimmed here rather than clipped there.
        return {"t": "track", "v": protocol.VERSION, "why": why[:47]}
