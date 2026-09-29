"""What a Launchpad tile does when it is not an app.

The board sends a slot number and nothing else -- it has always been the
daemon that decides what a number means, which is what stops a message from
the panel naming anything this side has not already agreed to. This widens
that decision from "which app" to "which app, keystroke, or command", and
leaves the board completely unchanged: it already draws an icon or a label
and already sends an index.

Two action types, and they are not equally reliable:

  run   an argv LIST, executed directly. Works everywhere.
  keys  a keystroke synthesised into whatever is frontmost. Works on macOS
        and on X11. Under Wayland it deliberately does not -- see send_keys.

Standard library only (CLAUDE.md).
"""
import os
import shutil
import subprocess
import sys

TIMEOUT_S = 5

# Modifier names as a person writes them, per platform. "cmd" is the one
# people type whichever machine they are on, so it is accepted everywhere and
# means Super on Linux.
_MODS_MAC = {"cmd": "command down", "command": "command down",
             "ctrl": "control down", "control": "control down",
             "alt": "option down", "option": "option down",
             "opt": "option down", "shift": "shift down",
             "super": "command down", "win": "command down"}

_MODS_X11 = {"cmd": "super", "command": "super", "super": "super",
             "win": "super", "ctrl": "ctrl", "control": "ctrl",
             "alt": "alt", "option": "alt", "opt": "alt", "shift": "shift"}

# Keys that are not a character. macOS needs a numeric key code for these --
# `keystroke` only takes text -- where xdotool takes the name.
_KEYCODE_MAC = {
    "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51,
    "escape": 53, "esc": 53, "left": 123, "right": 124, "down": 125,
    "up": 126, "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
}

_KEYNAME_X11 = {
    "return": "Return", "enter": "Return", "tab": "Tab", "space": "space",
    "delete": "BackSpace", "escape": "Escape", "esc": "Escape",
    "left": "Left", "right": "Right", "up": "Up", "down": "Down",
    "home": "Home", "end": "End", "pageup": "Prior", "pagedown": "Next",
}


def _linux():
    return sys.platform.startswith("linux")


def wayland():
    """Is this a Wayland session?

    Asked because it decides whether `keys` can work at all, and the answer
    has to be given to the user rather than discovered as a tile that does
    nothing.
    """
    if not _linux():
        return False
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        return True
    # A login service does not always inherit XDG_SESSION_TYPE, so the
    # display socket is the second opinion.
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def _parse(spec):
    """"cmd+shift+4" -> (["cmd", "shift"], "4"). (None, None) if unusable."""
    if not isinstance(spec, str) or not spec.strip():
        return None, None
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    if not parts:
        return None, None
    return parts[:-1], parts[-1]


def _keys_macos(mods, key):
    known = _MODS_MAC
    using = [known[m] for m in mods if m in known]
    if len(using) != len(mods):
        return False, "unknown modifier in %s" % "+".join(mods)
    suffix = (" using {%s}" % ", ".join(using)) if using else ""

    if key in _KEYCODE_MAC:
        script = "key code %d%s" % (_KEYCODE_MAC[key], suffix)
    elif len(key) == 1:
        # Quoted, and the only character that needs escaping inside an
        # AppleScript string is the quote itself.
        script = 'keystroke "%s"%s' % (key.replace('"', '\\"'), suffix)
    else:
        return False, "unknown key %r" % key

    try:
        p = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to %s' % script],
            capture_output=True, text=True, timeout=TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return False, "could not reach System Events"
    if p.returncode != 0:
        # -1719 and -1743 are the Automation refusals. The daemon is a login
        # agent, so the prompt was raised at install time or not at all.
        if "-1743" in (p.stderr or "") or "-1719" in (p.stderr or ""):
            return False, ("Allow Overwatch to control your computer in"
                           " System Settings > Privacy > Accessibility")
        return False, "the keystroke was refused"
    return True, None


def _keys_x11(mods, key):
    if not shutil.which("xdotool"):
        return False, "install xdotool for keystroke tiles"
    known = _MODS_X11
    parts = [known[m] for m in mods if m in known]
    if len(parts) != len(mods):
        return False, "unknown modifier in %s" % "+".join(mods)
    parts.append(_KEYNAME_X11.get(key, key))
    try:
        p = subprocess.run(["xdotool", "key", "+".join(parts)],
                           capture_output=True, text=True, timeout=TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return False, "xdotool did not run"
    return (p.returncode == 0), (None if p.returncode == 0
                                 else "the keystroke was refused")


def send_keys(spec):
    """Synthesise a keystroke into whatever is frontmost. (ok, why)."""
    mods, key = _parse(spec)
    if key is None:
        return False, "not a keystroke: %r" % (spec,)
    if sys.platform == "darwin":
        return _keys_macos(mods, key)
    if _linux():
        if wayland():
            # Not a gap to fill later. Wayland's design is that no client may
            # synthesise input into another, and the tools that manage it
            # (ydotool) want a root daemon and a uinput device. A launcher
            # that quietly asks for that is not what anybody agreed to
            # install, so this says so and the `run` type stays available.
            return False, ("Wayland does not allow synthetic keystrokes --"
                           " use a run: tile instead")
        return _keys_x11(mods, key)
    return False, "keystroke tiles are macOS and X11 only"


def run_command(argv):
    """Run argv. (ok, why).

    A LIST, always, and never shell=True. The entries come from a file the
    customer owns, and the difference between a list and a string is the
    difference between running `x` and running the second half of
    `x; rm -rf ~`. pc/widgets._argv_for says the same thing about app names.

    Detached and not waited on: a tile that starts a long-running thing must
    not hold the daemon's only loop, and the started thing must outlive a
    service restart.
    """
    if not isinstance(argv, (list, tuple)) or not argv:
        return False, "not a command"
    if not all(isinstance(a, str) for a in argv):
        return False, "every argument has to be a string"
    kw = {}
    if not sys.platform.startswith("win"):
        kw["start_new_session"] = True
    try:
        subprocess.Popen(list(argv), stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, **kw)
    except (OSError, subprocess.SubprocessError) as e:
        return False, "%s: %s" % (argv[0], type(e).__name__)
    return True, None


def perform(entry):
    """Do whatever this slot says. (ok, why)."""
    if not isinstance(entry, dict):
        return False, "not an action"
    if "keys" in entry:
        return send_keys(entry.get("keys"))
    if "run" in entry:
        return run_command(entry.get("run"))
    return False, "an action needs keys: or run:"
