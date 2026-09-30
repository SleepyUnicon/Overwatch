"""Read and move the frontmost window.

The launcher can already send a keystroke, so a person could bind their own
window-snapping shortcut to a tile and be done. What this adds is the part a
keypad cannot do: the panel SHOWS which window it is about to move, and which
screen that window is on, before you touch anything.

Two backends, and they are not equally comfortable. X11 has tools built for
exactly this -- wmctrl states a geometry and xdotool answers questions --
where macOS has System Events, which can do it but needs Accessibility
permission and a good deal more arithmetic.

Standard library only (CLAUDE.md), one subprocess per question.
"""
import re
import shutil
import subprocess
import sys
import time

from pc import macperm

TIMEOUT_S = 5

# Eighteen characters, because that is what a panel row holds. The long form
# ("window control is macOS and X11 only", 36) arrived on the glass as
# "window control is\u2026" -- cutting away the half that says what to do.
_NOT_HERE = "not on this OS"

# Where a window can be put. Six, matching the six tiles a panel now holds and
# -- not by coincidence -- the halves and fill that macOS's own green-button
# menu offers. At three tiles to a row each button is 90 px, about eleven
# characters, so every label here fits.
PLACES = ("left", "right", "top", "bottom", "full", "next")


def _linux():
    return sys.platform.startswith("linux")


def _run(argv):
    """(stdout, err_or_None). Never raises."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True,
                           timeout=TIMEOUT_S)
    except FileNotFoundError:
        return None, "%s is not installed" % argv[0]
    except (OSError, subprocess.SubprocessError):
        return None, "%s did not run" % argv[0]
    if p.returncode != 0:
        return None, "%s refused" % argv[0]
    return (p.stdout or "").strip(), None


# ------------------------------------------------------------------ X11

def _x11_tools():
    for tool in ("xdotool", "wmctrl"):
        if not shutil.which(tool):
            return "install %s for window control" % tool
    return None


def _x11_screens():
    """[(x, y, w, h)] for each connected output, left to right.

    From xrandr, because a window has to be moved to a screen's coordinates
    and only the X server knows where the screens are. Sorted by x so "next"
    means the one to the right, which is what a person means.
    """
    out, err = _run(["xrandr", "--query"])
    if err or not out:
        return []
    found = []
    for line in out.splitlines():
        if " connected" not in line:
            continue
        m = re.search(r"(\d+)x(\d+)\+(\d+)\+(\d+)", line)
        if m:
            w, h, x, y = (int(g) for g in m.groups())
            found.append((x, y, w, h))
    return sorted(found)


def _x11_current():
    out, err = _run(["xdotool", "getactivewindow"])
    if err or not out:
        return None, err or "no active window"
    wid = out.split()[0]

    name, _ = _run(["xdotool", "getwindowname", wid])
    # WM_CLASS is the APPLICATION; getwindowname is the document. macOS
    # reports the process and the window title separately and the panel shows
    # both, so X11 should give it the same two things rather than one string
    # that has to be truncated to fit.
    klass, _ = _run(["xprop", "-id", wid, "WM_CLASS"])
    app = ""
    if klass and '"' in klass:
        parts = [q for q in klass.split('"') if q.strip(", ")]
        if parts:
            app = parts[-1]
    geom, _ = _run(["xdotool", "getwindowgeometry", "--shell", wid])
    pos = {}
    for line in (geom or "").splitlines():
        k, _, v = line.partition("=")
        if v.strip().lstrip("-").isdigit():
            pos[k.strip()] = int(v)

    screens = _x11_screens()
    on = 0
    cx = pos.get("X", 0) + pos.get("WIDTH", 0) // 2
    for i, (x, _y, w, _h) in enumerate(screens):
        if x <= cx < x + w:
            on = i
            break
    return {"wid": wid, "title": name or "", "app": app,
            "screen": on, "screens": len(screens) or 1,
            "x": pos.get("X", 0), "y": pos.get("Y", 0),
            "w": pos.get("WIDTH", 0), "h": pos.get("HEIGHT", 0)}, None


def _x11_place(where):
    missing = _x11_tools()
    if missing:
        return False, missing
    cur, err = _x11_current()
    if cur is None:
        return False, err

    screens = _x11_screens() or [(0, 0, 1920, 1080)]
    i = cur["screen"]
    if where == "next":
        i = (i + 1) % len(screens)
        where = "full"
    x, y, w, h = screens[min(i, len(screens) - 1)]

    box = _box((x, y, w, h), where)

    # Unmaximise first. wmctrl -e is ignored outright on a maximised window,
    # which reads as a tile that does nothing on exactly the windows somebody
    # is most likely to be trying to move.
    _run(["wmctrl", "-i", "-r", cur["wid"], "-b",
          "remove,maximized_vert,maximized_horz"])
    _, err = _run(["wmctrl", "-i", "-r", cur["wid"], "-e",
                   "0,%d,%d,%d,%d" % box])
    return (err is None), err


# ---------------------------------------------------------------- macOS

# Accessibility, not Automation. System Events can already be ASKED what is
# frontmost with the grant `install` requests; reading a window's geometry is a
# separate permission, and macOS refuses until it is given.
#
# WHICH CODES MEAN "DENIED", AND WHICH DO NOT.
#
# This list used to contain -1719 and -1728, and both were wrong:
#
#   -25211  kAXErrorAPIDisabled     Accessibility really is off.
#   -1743   errAEEventNotPermitted  Automation is off. A DIFFERENT permission
#                                   with a different cure, so not here.
#   -1719   errAEIllegalIndex       There is no window at that index.
#   -1728   errAENoSuchObject       There is no such object.
#
# The last two fire when the frontmost application simply HAS NO WINDOW -- a
# Finder with everything closed, an agent with only a menu bar item. Treating
# them as a permission failure means the panel says "Accessibility off" on a
# machine where Accessibility is perfectly fine, and sends the owner to a
# settings pane to switch on something that is already on. Which is exactly
# what happened here, twice, including once after they had removed and re-added
# the entry on my advice.
#
# The text is matched as well as the code, because AppleScript's wording is the
# thing that is actually stable across macOS versions: "not allowed assistive
# access".
_AX_DENIED = ("-25211",)
_AX_DENIED_TEXT = ("assistive access", "not authorized to send apple events")

# Not a permission problem: there is nothing in front with a window.
_NO_WINDOW = ("-1719", "-1728")


def _ax_denied(stderr):
    """Is this stderr a PERMISSION refusal, as opposed to an empty desktop?"""
    text = (stderr or "").lower()
    if any(c in text for c in _AX_DENIED):
        return True
    return any(t in text for t in _AX_DENIED_TEXT)

# How often to repeat a refusal that is not going to change on its own.
#
# The panel rebuilds every few seconds, so the same sentence was written to the
# log on every pass: 1,058 copies of "System Events has no assistive access" in
# one file, which is not disclosure, it is a haystack. Five minutes is the
# interval claude_usage_bridge.py already uses for the same shape of problem
# (ERR_REPEAT_S) -- often enough that somebody tailing the log after granting
# the permission sees it stop, rare enough to read.
_DENIED_REPEAT_S = 300.0
_denied_said_at = [0.0]


def _say_denied():
    now = time.monotonic()
    if _denied_said_at[0] and now - _denied_said_at[0] < _DENIED_REPEAT_S:
        return
    first = not _denied_said_at[0]
    _denied_said_at[0] = now
    print("[windows] %sSystem Events has no assistive access. Allow Overwatch"
          " under System Settings > Privacy & Security > Accessibility."
          % ("" if first else "still: "), file=sys.stderr)


def clear_denied_notice():
    """Forget that we have complained, so the next refusal is reported.

    Called when the grant comes back, so a LATER loss is not swallowed by the
    five-minute window from the previous one.
    """
    _denied_said_at[0] = 0.0

# NO `on error` HERE, and that is the point.
#
# The first version wrapped the geometry in a try and returned zeros when it
# failed -- so a machine that had simply never been granted Accessibility
# reported a window 0x0 in size and the panel drew it as though that were the
# answer. The refusal is -1719, it is completely actionable, and swallowing it
# turned "click Allow in Settings" into "the tiles do nothing".
_FRONT = '''
tell application "System Events"
  set p to first application process whose frontmost is true
  set w to front window of p
  set {wx, wy} to position of w
  set {ww, wh} to size of w
  return (name of p) & "\\n" & (name of w) & "\\n" & wx & "\\n" & wy ¬
    & "\\n" & ww & "\\n" & wh
end tell
'''

# Asked separately, because it needs no Accessibility grant at all: it is how
# the panel can still name what is in front on a machine that has not given
# one, instead of showing nothing.
_FRONT_APP = ('tell application "System Events" to get name of '
              'first application process whose frontmost is true')

_PLACE = '''
tell application "Finder" to set b to bounds of window of desktop
tell application "System Events"
  set p to first application process whose frontmost is true
  set w to front window of p
  set position of w to {%d, %d}
  set size of w to {%d, %d}
end tell
'''


def _osa(script):
    try:
        p = subprocess.run(["osascript", "-e", script], capture_output=True,
                           text=True, timeout=TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None, "could not reach System Events"
    if p.returncode != 0:
        if _ax_denied(p.stderr):
            _say_denied()
            return None, "Accessibility off"
        if any(c in (p.stderr or "") for c in _NO_WINDOW):
            return None, "nothing in front"
        # The raw code, trimmed, because every time this has gone wrong the
        # answer was in an error nobody was printing. Not the whole stderr:
        # the script names what the owner has open.
        code = re.search(r"\(-?\d{3,5}\)", p.stderr or "")
        print("[windows] System Events refused: %s"
              % (code.group(0) if code else "no code"), file=sys.stderr)
        return None, "the window did not move"
    return (p.stdout or "").strip(), None


# Per-display frames, via AppKit rather than Finder.
#
# THIS IS WHAT THE OLD REFUSAL WAS FOR. `bounds of window of desktop` returns
# ONE rectangle spanning every monitor -- measured on a three-display desk as
# (-1920, 0, 4920, 1920) -- so "left half" of it lands across two screens.
# Rather than be confidently wrong, _mac_place declined outright on any machine
# with more than one display, which is most desks that would want this.
#
# AppleScript can load AppKit, and NSScreen knows each display separately. Its
# visibleFrame already excludes the menu bar and the Dock, which is exactly the
# area a window should be snapped into.
#
# COORDINATES, which is where this would have gone wrong. NSScreen is Cocoa:
# origin at the BOTTOM-left of the main display, y upwards. Accessibility --
# what actually moves the window -- is top-left, y downwards. So
#
#     ax_y = main_full_height - (cocoa_y + cocoa_height)
#
# Checked against a real window rather than derived and hoped for: the main
# display is 1080 tall with a 1050-tall visibleFrame at cocoa y=0, giving
# ax_y = 30 -- and a maximised window on it reported y=30.
_SCREENS = r'''
use framework "AppKit"
use scripting additions
set m to item 1 of (current application's NSScreen's screens())
set mh to (item 2 of item 2 of (m's frame())) as integer
set out to ""
repeat with s in (current application's NSScreen's screens())
  set f to s's visibleFrame()
  set x to (item 1 of item 1 of f) as integer
  set y to (item 2 of item 1 of f) as integer
  set w to (item 1 of item 2 of f) as integer
  set h to (item 2 of item 2 of f) as integer
  set out to out & x & "," & (mh - (y + h)) & "," & w & "," & h & linefeed
end repeat
return out
'''


def _mac_screens():
    """[(x, y, w, h)] per display in ACCESSIBILITY coordinates, left to right.

    Sorted by x so "next" means the one to the right, which is what somebody
    looking at their desk means. Empty when AppKit cannot be reached, and the
    caller refuses rather than guessing.
    """
    out, err = _osa(_SCREENS)
    if err or not out:
        return []
    found = []
    for line in out.splitlines():
        parts = [q.strip() for q in line.split(",")]
        if len(parts) != 4:
            continue
        try:
            x, y, w, h = (int(q) for q in parts)
        except ValueError:
            continue
        if w > 0 and h > 0:
            found.append((x, y, w, h))
    return sorted(found)


def _box(screen, where):
    """The rectangle for `where` within `screen`.

    Shared by both platforms: a half is a half, and the arithmetic was already
    written twice.
    """
    x, y, w, h = screen
    if where == "left":
        return (x, y, w // 2, h)
    if where == "right":
        return (x + w // 2, y, w // 2, h)
    if where == "top":
        return (x, y, w, h // 2)
    if where == "bottom":
        return (x, y + h // 2, w, h // 2)
    return (x, y, w, h)


def _record_ax(granted):
    """Write down what THIS process can see.

    The daemon is the only process whose answer matters, and it is the only
    one that cannot be asked from a terminal: macOS attributes a TCC grant to
    the RESPONSIBLE process, so the same binary run from a shell inherits the
    shell's grant and reports "granted" while the launchd copy is refused.
    Measured on 2026-09-30 -- `overwatch status` said granted, the daemon was
    logging the refusal at the same moment, and both were the same executable
    at the same path.

    So `status` no longer probes. It reads what the daemon put here.
    """
    if sys.platform != "darwin":
        return
    try:
        macperm.ax_note(granted)
    except Exception:
        # Never let bookkeeping take down a panel build.
        pass


def _mac_current():
    out, err = _osa(_FRONT)
    if err:
        # A permission refusal is the user's to fix and says so. Anything
        # else means this process has no ordinary window -- a full-screen
        # app, a palette -- and the app's name is still worth showing.
        if "Accessibility" in err:
            _record_ax(False)
            return None, err
        name, nerr = _osa(_FRONT_APP)
        if nerr or not name:
            return None, err
        return {"wid": "", "app": name, "title": "",
                "screen": 0, "screens": 1,
                "x": 0, "y": 0, "w": 0, "h": 0}, None
    lines = (out or "").splitlines()
    if len(lines) < 6:
        return None, "no window in front"
    try:
        x, y, w, h = (int(v) for v in lines[2:6])
    except ValueError:
        return None, "no window in front"
    # Reading a window's geometry is the thing Accessibility gates, so getting
    # it back is proof of the grant rather than an assumption about it.
    _record_ax(True)
    clear_denied_notice()
    # Which display, now that there is a way to know. It was hardcoded to
    # "screen 0 of 1" because Finder only ever reported one rectangle; the
    # panel therefore never showed the Screen row on a Mac, on exactly the
    # desks where it matters most.
    screens = _mac_screens()
    at = 0
    cx, cy = x + w // 2, y + h // 2
    for i, (sx, sy, sw, sh) in enumerate(screens):
        if sx <= cx < sx + sw and sy <= cy < sy + sh:
            at = i
            break
    return {"wid": "", "app": lines[0], "title": lines[1],
            "screen": at, "screens": len(screens) or 1,
            "x": x, "y": y, "w": w, "h": h}, None


def _mac_place(where):
    screens = _mac_screens()
    if not screens:
        # No AppKit, no frames, no honest answer. Finder's single rectangle is
        # still available and still spans every display, so falling back to it
        # would be the confidently-wrong behaviour this replaced.
        return False, "could not read screens"

    cur, err = _mac_current()
    if cur is None:
        return False, err or "nothing in front"

    # The display the window is MOSTLY on, by its centre. Using whichever
    # screen happens to be first would move somebody's window to another
    # monitor for asking it to fill the one it is already on.
    cx = cur.get("x", 0) + cur.get("w", 0) // 2
    cy = cur.get("y", 0) + cur.get("h", 0) // 2
    at = 0
    for i, (x, y, w, h) in enumerate(screens):
        if x <= cx < x + w and y <= cy < y + h:
            at = i
            break

    if where == "next":
        if len(screens) < 2:
            return False, "only one display"
        at = (at + 1) % len(screens)
        where = "full"

    _, err = _osa(_PLACE % _box(screens[at], where))
    return (err is None), err


# ----------------------------------------------------------------- api

def current():
    """What is in front. (fields, err). fields is None when nothing is."""
    if _linux():
        missing = _x11_tools()
        if missing:
            return None, missing
        return _x11_current()
    if sys.platform == "darwin":
        return _mac_current()
    return None, _NOT_HERE


def place(where):
    """Move the frontmost window. (ok, err)."""
    if where not in PLACES:
        return False, "nowhere called %r" % (where,)
    if _linux():
        return _x11_place(where)
    if sys.platform == "darwin":
        return _mac_place(where)
    return False, _NOT_HERE
