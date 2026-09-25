"""The launcher widget's half of the link: slot numbers in, apps launched.

The board sends `{"t":"launch","slot":N}` and nothing else -- no app name, no
path. The table below is the only thing that turns N into a program, and it
lives here rather than on the board for two reasons: the customer can change it
without a reflash, and a message from the panel cannot name a program this side
has not already agreed to run.

Standard library only, like the rest of pc/ (CLAUDE.md). Nothing here adds a
megabyte to anybody's download.
"""
import json
import os
import subprocess
import sys

from pc import macperm

from pc import protocol

# Mirrors LABEL_MAX in firmware/src/ui_launcher.c. The grid draws 96 px in
# montserrat_14 and a longer name is not clipped by LVGL, it is centred and
# spills over both edges of the button.
LABEL_MAX = 14

# Six, because the firmware draws three columns by two rows and a seventh slot
# has nowhere to go. Kept as a name so the two sides fail loudly if they drift.
SLOTS = 6

# Windows: every child the daemon starts must be told not to open a console.
# Same reason as pc/ota.py -- the daemon runs hidden, so a console-subsystem
# child gets a black window of its own on the customer's desktop.
NO_WINDOW = {"creationflags": 0x08000000} if sys.platform == "win32" else {}

# How long to wait for the launcher command itself. `open -a` returns as soon
# as it has handed off to LaunchServices, so this is not the app's startup
# time -- it is the ceiling on a launcher that has wedged. The board is waiting
# on an answer and the protocol thread must not be the thing that blocks.
LAUNCH_TIMEOUT_S = 10

DEFAULT_APPS = {
    "darwin": ["Claude", "Adobe Illustrator 2026", "Adobe Photoshop 2026",
               "Spotify", "Brave Browser", "PCSX2-v2.6.3"],
    "linux": ["claude", "inkscape", "gimp", "spotify", "brave-browser", "pcsx2"],
    "win32": ["claude", "illustrator", "photoshop", "spotify", "brave", "pcsx2"],
}

# The icon keys firmware/src/icons_gen.h was generated with. The board owns
# what it can draw; this side only has to name it.
#
# A key the board does not have is not an error - ui_launcher.c falls back to
# drawing the string as text - which is what lets somebody point a slot at an
# app nobody shipped an icon for and still get a usable button.
ICON_KEYS = ("claude", "illustrator", "photoshop", "spotify", "brave", "pcsx2")


def icon_for(app):
    """The icon key for an app name, or None.

    Substring, deliberately: the launcher table holds what `open -a` needs,
    and that is "Adobe Photoshop 2026" or "PCSX2-v2.6.3" - names that carry a
    version the icon does not. Matching on containment means a customer who
    upgrades Photoshop keeps their icon without editing anything.
    """
    low = (app or "").lower()
    for k in ICON_KEYS:
        if k in low:
            return k
    return None


def _config_path():
    """~/.overwatch/apps.json -- resolved HERE, never at module scope.

    CLAUDE.md records why: a constant computed with expanduser("~") at import
    is evaluated before conftest.py can redirect HOME, so it points at the real
    home no matter what the fixture does. A test that wrote one would edit the
    developer's own file.
    """
    return os.path.join(os.path.expanduser("~"), ".overwatch", "apps.json")


def _short(name):
    """A button label the panel can actually draw.

    Truncated on this side rather than the board's, because the board would
    have to carry the rule and the bytes both. "Visual Studio Code" is 18 and
    becomes "Visual Studio"; the launch still uses the full name.
    """
    return name[:LABEL_MAX].strip()


def load_apps():
    """The six slots, from ~/.overwatch/apps.json when it exists.

    A malformed or unreadable file falls back to the defaults rather than
    raising. The daemon is a login agent: a customer who hand-edits this file
    and drops a comma should get the stock grid back, not a service that no
    longer starts.
    """
    apps = list(DEFAULT_APPS.get(sys.platform, DEFAULT_APPS["linux"]))
    try:
        with open(_config_path(), "r", encoding="utf-8") as fh:
            got = json.load(fh)
    except (OSError, ValueError):
        return apps[:SLOTS]
    if isinstance(got, list):
        for i, name in enumerate(got[:SLOTS]):
            if isinstance(name, str):
                apps[i] = name
    return apps[:SLOTS]


# Is this app frontmost right now? Asked of System Events, which is the only
# thing that knows - an app has no AppleScript verb for "are you in front".
#
# Returns "front", "back", "notrunning", or None when the question could not
# be asked at all. None matters: System Events needs its own Automation grant,
# and a machine that has not given it must still LAUNCH things. So a failure
# here falls through to `open -a`, which raises or launches either way, and
# the only thing lost is hiding.
_STATE = '''
tell application "System Events"
  if not (exists process "%(n)s") then return "notrunning"
  if frontmost of process "%(n)s" then return "front"
  return "back"
end tell
'''

_HIDE = '''
tell application "System Events" to set visible of process "%(n)s" to false
'''


def _osa(script):
    """Run one AppleScript. Returns (stdout, ok, state).

    `state` is None when it worked, else 'denied' or 'failed' -- see
    pc/macperm.py. It used to return (stdout, ok), which made a revoked
    Automation grant indistinguishable from a script that simply found
    nothing, and the launcher reported both as "could not read window state".
    That is the one failure here whose cure is a trip to System Settings, so
    it is the one that has to be nameable.
    """
    if sys.platform != "darwin":
        return "", False, "failed"
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True,
                           text=True, timeout=LAUNCH_TIMEOUT_S, **NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return "", False, "failed"
    state = macperm.classify(r.returncode, r.stderr)
    return (r.stdout or "").strip(), state is None, state


def _argv_for(name):
    """The command that launches `name`, as a LIST.

    Never a shell string and never shell=True. The name reaches here from a
    file the customer owns, and the difference between a list and a string is
    the difference between launching an app called `x; rm -rf ~` and running
    the second half of it.
    """
    if not name:
        return None
    if sys.platform == "darwin":
        return ["open", "-a", name]
    if sys.platform == "win32":
        # `start` is a cmd builtin, so it needs cmd -- but the name is still a
        # separate argv entry, not interpolated into the command string.
        return ["cmd", "/c", "start", "", name]
    return [name]


class Launcher:
    """Turns `launch` messages into processes, and answers every one.

    `run` is injected so the tests never start a real program.
    """

    def __init__(self, apps=None, run=None):
        self._fixed = apps is not None      # a test's table; never reloaded
        self._apps = list(apps) if apps is not None else load_apps()
        self._run = run or self._spawn
        self._mtime = self._config_mtime()

    @staticmethod
    def _config_mtime():
        try:
            return os.path.getmtime(_config_path())
        except OSError:
            return 0.0

    def reload_if_changed(self):
        """Re-read the table when apps.json has been written since last time.

        The web config writes that file; without this the daemon would hold
        the table it loaded at startup and a save would appear to do nothing
        until someone restarted the service - which is exactly the kind of
        silent no-op that makes a config screen feel broken.

        Compares mtime rather than polling the contents: the file is small,
        but this runs on the fast tick and a stat is cheaper than a parse.
        """
        if self._fixed:
            return False
        m = self._config_mtime()
        if m == self._mtime:
            return False
        self._mtime = m
        self._apps = load_apps()
        return True

    # --- outbound ----------------------------------------------------
    def apps_message(self):
        """What each button shows: an ICON KEY where one exists, the app's
        short name where one does not.

        Flat keys s0..s5 rather than an array, because msg_parse.c reads flat
        JSON only and a flat line is one whose byte cost can be read off at a
        glance against the 512-byte budget. Icon keys are also SHORTER than
        the names they replace, so this message got cheaper, not dearer.
        """
        msg = {"t": "apps", "v": protocol.VERSION}
        for i, name in enumerate(self._apps[:SLOTS]):
            if not name:
                continue
            msg["s%d" % i] = icon_for(name) or _short(name)
        return msg

    # --- inbound -----------------------------------------------------
    def handles(self, msg):
        return msg.get("t") == "launch"

    def on_launch(self, msg):
        """Run the slot and return the `launched` reply, or None to stay quiet.

        Always an answer when the slot is real. A tap that produced nothing --
        because the app is gone, or the launcher failed -- must not look
        identical to one that worked: the board lights the button on tap and
        only this tells it which colour to settle into.
        """
        slot = msg.get("slot")
        if not isinstance(slot, int) or isinstance(slot, bool):
            return None
        if not 0 <= slot < SLOTS:
            return None
        name = self._apps[slot] if slot < len(self._apps) else ""
        if not name:
            # An unassigned slot. The board already refuses to send these, so
            # arriving here means the two sides disagree about the table --
            # answer false rather than silently doing nothing.
            return {"t": "launched", "v": protocol.VERSION,
                    "slot": slot, "ok": False}
        return {"t": "launched", "v": protocol.VERSION,
                "slot": slot, "ok": bool(self._run(name))}

    def _spawn(self, name):
        """Toggle the app: hide it if it is in front, otherwise bring it up.

        Three states, and `open -a` already handles two of them - it launches
        an app that is not running and raises one that is. The only thing it
        cannot do is put a frontmost app away, so that is the one case that
        needs System Events, and it is the one case that degrades: without
        that permission the tap still raises, it just never hides.

        A tap that hides counts as success. The board lights the tile green
        either way, because both outcomes are the tap doing what was asked.
        """
        if sys.platform == "darwin":
            where, ok, why = _osa(_STATE % {"n": name})
            if ok and where == "front":
                _, hid, hwhy = _osa(_HIDE % {"n": name})
                if hid:
                    print("[widgets] %s: hidden" % name, file=sys.stderr)
                    return True
                print("[widgets] %s: %s" % (name, macperm.explain(hwhy)),
                      file=sys.stderr)
            elif not ok:
                # Still falls through to `open -a`, which raises and launches
                # without any Automation grant at all. Only hiding is lost.
                print("[widgets] %s: %s Raising instead."
                      % (name, macperm.explain(why)), file=sys.stderr)

        argv = _argv_for(name)
        if not argv:
            return False
        try:
            rc = subprocess.call(argv, timeout=LAUNCH_TIMEOUT_S,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE, **NO_WINDOW)
        except (OSError, subprocess.SubprocessError) as e:
            print("[widgets] %s: launch failed (%s)" % (name, type(e).__name__),
                  file=sys.stderr)
            return False
        # Say what happened. A tile that lights and does nothing is the single
        # hardest thing to diagnose from the other side of a serial cable.
        print("[widgets] %s: %s" % (name, "raised/launched" if rc == 0
                                    else "open -a exited %d" % rc),
              file=sys.stderr)
        return rc == 0
