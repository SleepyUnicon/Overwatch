"""The system microphone: is it live, and make it not be.

WHY THE SYSTEM MIC AND NOT THE MEETING'S MUTE BUTTON

Zoho Meeting runs in a browser tab, and so does Google Meet, and so does half
of Teams. Driving their mute buttons means synthesising the application's own
keyboard shortcut into the right window -- and I do not know Zoho Meeting's
shortcut. Guessing one is how this project spent a day telling a Linux user
that music control needed a Mac.

The system microphone has none of that problem. It is the same control for
every meeting application there has ever been, it needs no shortcut and no
window focus, and -- the part that matters most for a panel -- IT CAN BE READ
BACK. A tile that toggles something unreadable can only ever show what it
believes it did. This shows what is true.

THE TRADE-OFF, STATED: the meeting's own interface will still show you as
unmuted, because as far as it knows you are. Nobody hears you, and the other
participants see an open microphone icon. If that matters more than certainty,
bind the application's own shortcut to a Launchpad `keys` tile instead.

Standard library only (CLAUDE.md), one subprocess per question.
"""
import re
import shutil
import subprocess
import sys

TIMEOUT_S = 4

# Eighteen characters, because that is what a row holds. The first
# version said "mute control is macOS and Linux only" (36) and a
# Windows user would have read "mute control is m\u2026" on three rows at
# once. The long form belongs in a log, not on a 320 px screen.
_NOT_HERE = "not on this OS"

# pactl speaks to PulseAudio and to PipeWire's pipewire-pulse layer, which
# between them is every desktop Linux worth naming.
_SOURCE = "@DEFAULT_SOURCE@"


def _run(argv):
    """(stdout, err_or_None). Never raises."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True,
                           timeout=TIMEOUT_S)
    except FileNotFoundError:
        return None, "install %s for mic control" % argv[0]
    except (OSError, subprocess.SubprocessError):
        return None, "%s did not run" % argv[0]
    if p.returncode != 0:
        return None, "%s refused" % argv[0]
    return (p.stdout or "").strip(), None


def _linux():
    return sys.platform.startswith("linux")


# ---------------------------------------------------------------- Linux

# The microphone is a "source" and the speakers are a "sink"; every pactl verb
# below comes in both flavours and is otherwise identical, so the kind is a
# parameter rather than a second copy of the code.
_DEFAULT = {"source": "@DEFAULT_SOURCE@", "sink": "@DEFAULT_SINK@"}


def _yes_no(text):
    """True/False from a "Mute: yes" line, or None."""
    m = re.search(r"mute:\s*(yes|no)", (text or "").lower())
    if not m:
        return None
    return m.group(1) == "yes"


def _linux_muted_longhand(kind):
    """Read the mute flag out of `pactl list sources` / `list sinks`.

    NOT the tidy way, and deliberately here anyway. `pactl get-source-mute`
    arrived in PulseAudio 16 (2022) -- while `set-source-mute` has existed for
    over a decade -- so a Debian-stable or Mint machine can perfectly well
    mute and be unable to answer whether it is muted. Assuming the getter
    exists because the setter does is the same mistake that shipped
    "Spotify control needs a Mac" to a Linux desktop.

    `pactl info` names the default device; `pactl list` carries a Mute: line
    per device. Both are as old as pactl itself.
    """
    info, err = _run(["pactl", "info"])
    if err:
        return None, err
    want = None
    m = re.search(r"^Default %s:\s*(\S+)" % kind.capitalize(), info or "",
                  re.M)
    if m:
        want = m.group(1)
    if not want:
        return None, "no default %s" % ("mic" if kind == "source" else "output")

    out, err = _run(["pactl", "list", kind + "s"])
    if err:
        return None, err
    # Blocks are separated by a blank line, each opening with "Source #N".
    for block in re.split(r"\n\s*\n", out or ""):
        if re.search(r"^\s*Name:\s*%s\s*$" % re.escape(want), block, re.M):
            state = _yes_no(block)
            if state is None:
                return None, "could not read the mixer"
            return state, None
    return None, "no default %s" % ("mic" if kind == "source" else "output")


def _linux_muted(kind):
    if not shutil.which("pactl"):
        return None, "install pactl for mute control"
    out, err = _run(["pactl", "get-%s-mute" % kind, _DEFAULT[kind]])
    if err is None:
        state = _yes_no(out)
        if state is not None:
            return state, None
    # Either the subcommand is too new for this pactl, or it answered
    # something unexpected. Ask the old way before giving up.
    return _linux_muted_longhand(kind)


def _linux_set(kind, want):
    if not shutil.which("pactl"):
        return False, "install pactl for mute control"
    _, err = _run(["pactl", "set-%s-mute" % kind, _DEFAULT[kind],
                   "1" if want else "0"])
    return (err is None), err


# ---------------------------------------------------------------- macOS

def _osa(script):
    out, err = _run(["osascript", "-e", script])
    if err:
        # osascript is always present on a Mac, so a non-zero exit here is a
        # refusal or a broken script, not a missing tool.
        return None, "could not reach the mixer"
    return out, None


def _mac_mic_muted():
    out, err = _osa("input volume of (get volume settings)")
    if err:
        return None, err
    m = re.search(r"-?\d+", out or "")
    if not m:
        return None, "could not read the mic"
    level = int(m.group(0))
    # macOS exposes no mute FLAG for input, only a level -- and reports -1
    # when the default input has no settable volume at all, which some USB
    # interfaces and AirPods do. -1 is "cannot say", not "live".
    if level < 0:
        return None, "mic has no level"
    return level == 0, None


def _mac_out_muted():
    out, err = _osa("output muted of (get volume settings)")
    if err:
        return None, err
    low = (out or "").strip().lower()
    if low in ("true", "false"):
        return low == "true", None
    return None, "could not read the output"


# ----------------------------------------------------------------- api

def available():
    """Whether this platform has a mute control at all.

    Platform only, and that is the point: `players()` in music_linux once
    folded "gdbus is missing" into "nothing is playing" and the panel told a
    Linux user to go and buy a Mac. A tool being absent is a different
    sentence from a feature being unsupported, and each deserves its own.
    """
    return _linux() or sys.platform == "darwin"


def muted():
    """Is the microphone muted. (is_muted, err); None when unanswerable."""
    if _linux():
        return _linux_muted("source")
    if sys.platform == "darwin":
        return _mac_mic_muted()
    return None, _NOT_HERE


def set_muted(want):
    """Mute or unmute the microphone. (ok, err).

    macOS restores to 100 rather than to whatever the level was, deliberately:
    that level is not remembered anywhere that survives a daemon restart, and
    coming back at 15% is a microphone that is technically live and practically
    not -- the worst of the two states to be in on a call.
    """
    if _linux():
        return _linux_set("source", want)
    if sys.platform == "darwin":
        _, err = _osa("set volume input volume %d" % (0 if want else 100))
        return (err is None), err
    return False, _NOT_HERE


def out_muted():
    """Is the OUTPUT muted -- can you hear the meeting. (is_muted, err)."""
    if _linux():
        return _linux_muted("sink")
    if sys.platform == "darwin":
        return _mac_out_muted()
    return None, _NOT_HERE


def set_out_muted(want):
    """Silence or restore the speakers. (ok, err)."""
    if _linux():
        return _linux_set("sink", want)
    if sys.platform == "darwin":
        _, err = _osa("set volume output muted %s"
                      % ("true" if want else "false"))
        return (err is None), err
    return False, _NOT_HERE


def _flip(read, write):
    state, err = read()
    if err:
        return None, err
    ok, err = write(not state)
    if not ok:
        return None, err
    return (not state), None


def toggle():
    """Flip the microphone. (muted, err).

    Reads first rather than sending pactl's own `toggle`, because the panel has
    to say afterwards which way it went and `toggle` reports nothing.
    """
    return _flip(muted, set_muted)


def toggle_out():
    """Flip the speakers. (muted, err)."""
    return _flip(out_muted, set_out_muted)
