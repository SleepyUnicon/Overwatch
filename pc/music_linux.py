"""The transport widget's Linux half: MPRIS over D-Bus.

pc/music.py talks to macOS through one AppleScript call. This is the same idea
against the standard Linux players actually implement -- org.mpris.MediaPlayer2
-- reached with `gdbus`, which ships with glib and is therefore on any machine
that has a desktop session. No new dependency, the same promise README.md makes
about the rest of the product.

What this reaches that the Mac cannot: a BROWSER TAB. The macOS side records
that controlling one needs NX events and a compiled helper, so it gave up on
them. Firefox and Chrome both publish MPRIS, so on Linux a YouTube tab is just
another player.

Standard library only (CLAUDE.md), and one subprocess per poll.
"""
import re
import subprocess
import sys

TIMEOUT_S = 5

# Everything the page draws, in ONE call.
#
# The same reasoning pc/music.py gives for its single osascript: asking for
# PlaybackStatus, Metadata and Position separately is three process spawns on a
# poll that runs every two seconds. GetAll returns the lot.
_IFACE = "org.mpris.MediaPlayer2.Player"
_PATH = "/org/mpris/MediaPlayer2"

_VERB = {
    "play": "PlayPause",
    "next": "Next",
    "prev": "Previous",
}

# A bus name from ListNames is external input, and it is about to become a
# subprocess argument. It cannot be anything but this.
_NAME_OK = re.compile(r"^org\.mpris\.MediaPlayer2\.[A-Za-z0-9._-]+$")


def available():
    """Is there a gdbus to talk through?"""
    if not sys.platform.startswith("linux"):
        return False
    try:
        p = subprocess.run(["gdbus", "--version"], capture_output=True,
                           timeout=TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return False
    return p.returncode == 0


def _gdbus(*args):
    """Run one gdbus call. Returns (stdout, err_or_None)."""
    try:
        p = subprocess.run(("gdbus",) + args, capture_output=True, text=True,
                           timeout=TIMEOUT_S)
    except FileNotFoundError:
        return None, "Install gdbus (glib) for media control"
    except (OSError, subprocess.SubprocessError):
        return None, "Could not reach the player"
    if p.returncode != 0:
        # stderr is not relayed verbatim -- it can carry the user's session
        # details, and the board gets a sentence this file chose. Same reflex
        # as pc/music.py and CLAUDE.md's rule about serial contents.
        return None, "The player did not answer"
    return (p.stdout or "").strip(), None


def players():
    """Every MPRIS name on the session bus, in the order the bus gives them."""
    out, err = _gdbus("call", "--session", "--dest", "org.freedesktop.DBus",
                      "--object-path", "/org/freedesktop/DBus",
                      "--method", "org.freedesktop.DBus.ListNames")
    if err is not None or not out:
        return []
    found = re.findall(r"org\.mpris\.MediaPlayer2\.[A-Za-z0-9._-]+", out)
    # Deduplicated, order kept: a player can appear twice when it owns both a
    # well-known name and an instance-suffixed one.
    seen, keep = set(), []
    for name in found:
        if name not in seen and _NAME_OK.match(name):
            seen.add(name)
            keep.append(name)
    return keep


# ------------------------------------------------------------ GVariant bits
#
# gdbus prints GVariant TEXT, not JSON:
#
#   (<{'PlaybackStatus': <'Playing'>, 'Position': <int64 12345678>,
#      'Metadata': <{'xesam:title': <'Song'>,
#                    'xesam:artist': <['A', 'B']>,
#                    'mpris:length': <int64 245000000>}>}>,)
#
# A full parser is not worth writing for four fields. These pull out what is
# needed and answer None when the shape is not what was expected, which is the
# behaviour that matters: a player with an odd metadata dict should cost its
# title, never the whole page.


def _quoted(blob, key):
    """The value of `'key': <'...'>`, with backslash escapes undone."""
    m = re.search(r"'%s'\s*:\s*<'((?:[^'\\]|\\.)*)'>" % re.escape(key), blob)
    if not m:
        return None
    return re.sub(r"\\(.)", r"\1", m.group(1))


def _first_of_list(blob, key):
    """The first string of `'key': <['a', 'b']>`.

    xesam:artist is an ARRAY. Several players put one name in it, some put the
    whole billing; the panel has 28 characters, so the first is what fits and
    what a person would have said anyway.
    """
    m = re.search(r"'%s'\s*:\s*<\[(.*?)\]>" % re.escape(key), blob, re.S)
    if not m:
        return None
    first = re.search(r"'((?:[^'\\]|\\.)*)'", m.group(1))
    if not first:
        return None
    return re.sub(r"\\(.)", r"\1", first.group(1))


def _number(blob, key):
    """The value of `'key': <int64 123>`, or `<uint64 123>`, or a bare number."""
    m = re.search(r"'%s'\s*:\s*<(?:[a-z0-9]+\s+)?(-?\d+)" % re.escape(key),
                  blob)
    return int(m.group(1)) if m else None


def _read_one(name):
    """(fields, err). fields is None when this player said nothing useful."""
    out, err = _gdbus("call", "--session", "--dest", name,
                      "--object-path", _PATH,
                      "--method", "org.freedesktop.DBus.Properties.GetAll",
                      _IFACE)
    if err is not None:
        return None, err
    if not out:
        return None, None

    status = _quoted(out, "PlaybackStatus") or ""
    title = _quoted(out, "xesam:title")
    artist = _first_of_list(out, "xesam:artist")
    if artist is None:
        # Some players publish a plain string rather than the array the spec
        # asks for. Take it rather than showing a track with no name on it.
        artist = _quoted(out, "xesam:artist")

    if title is None and not status:
        # Nothing recognisable came back. Say what arrived, once, where a
        # person can read it -- a page that says "could not read the player"
        # and nothing else costs a round trip to find out why.
        print("[music] unrecognised MPRIS reply from %s: %s"
              % (name, out[:200]), file=sys.stderr)
        return None, None

    length_us = _number(out, "mpris:length")
    pos_us = _number(out, "Position")
    return {
        "player": name,
        "state": status.lower(),
        "name": title or "",
        "artist": artist or "",
        # Microseconds on the wire, seconds on the panel.
        "pos_s": int(pos_us // 1000000) if pos_us is not None else -1,
        "dur_s": int(length_us // 1000000) if length_us else 0,
    }, None


def read(prefer=None):
    """The first player worth showing.

    A PLAYING one wins over a paused one, because a desk with Spotify paused
    and a video actually running should show the video. Failing that, `prefer`
    -- the one last talked to -- so the page does not flicker between two
    paused players as the bus reorders them.
    """
    names = players()
    if not names:
        return None, None

    best = None
    for name in names:
        fields, err = _read_one(name)
        if fields is None:
            continue
        if fields["state"] == "playing":
            return fields, None
        if best is None or (prefer and name == prefer):
            best = fields
    return best, None


def command(verb, prefer=None):
    """Run one of the three verbs. Returns err_or_None.

    On the player that is PLAYING where there is one -- the same choice read()
    makes, and for the same reason: the transport on the panel should act on
    whatever it is currently showing.
    """
    method = _VERB.get(verb)
    if method is None:
        return None
    fields, _ = read(prefer)
    target = fields["player"] if fields else None
    if target is None:
        names = players()
        target = names[0] if names else None
    if target is None:
        return "No music player running"
    _, err = _gdbus("call", "--session", "--dest", target,
                    "--object-path", _PATH,
                    "--method", "%s.%s" % (_IFACE, method))
    return err


def _main():
    """`python3 -m pc.music_linux` -- what this machine's players look like.

    A way to check MPRIS without a board, a daemon or a panel in the loop. If
    the transport misbehaves, this says whether the fault is here or further
    up, and its output is the thing worth pasting into a bug report.
    """
    if not sys.platform.startswith("linux"):
        print("not Linux; this backend is not used here")
        return 0
    if not available():
        print("no gdbus on PATH -- media control needs glib installed")
        return 1
    names = players()
    print("players on the bus: %d" % len(names))
    for name in names:
        print("  %s" % name)
    if not names:
        print("\nNothing publishes MPRIS. Start a player and try again --")
        print("Firefox and Chrome count, a tab playing audio is enough.")
        return 1
    fields, err = read()
    if err:
        print("\nerror: %s" % err)
        return 1
    if fields is None:
        print("\nplayers are present but none answered with anything usable")
        return 1
    print("\nchosen: %s" % fields["player"])
    for k in ("state", "name", "artist", "pos_s", "dur_s"):
        print("  %-8s %s" % (k, fields[k]))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
