"""Per-application tool tiles: what the app in front can be told to do.

WHY THIS IS SAFE WHERE THE MEETING PANEL'S MUTE WAS NOT

pc/mic.py drives the SYSTEM microphone rather than the meeting's own button,
because Zoho Meeting's shortcut is unknowable and guessing it would have been
the third time this project shipped a confident wrong answer. That reasoning
does not transfer here, and the difference is worth being explicit about:

  - Illustrator's tool shortcuts are published, single keys, and stable across
    versions. `v` has selected the Selection tool for twenty years.
  - They are IDEMPOTENT. Pressing `v` twice is pressing it once. Pressing the
    wrong one selects the wrong tool and the next tap fixes it.
  - They are visible. The tool palette in the app changes, so a wrong mapping
    announces itself immediately rather than corrupting something quietly.

None of that is true of a mute button, and none of it is true of `cmd+z`,
`delete`, or anything that writes. So the SHIPPED defaults are tool selections
ONLY. Anything that changes a document is something the owner adds themselves,
to their own file, having decided they want it.

That rule is enforced, not merely stated: see _REFUSED and clean_tool().

The mapping lives in ~/.overwatch/tools.json and the defaults below are used
for any application the file does not mention.
"""
import json
import os
import sys

# Six, because the board draws six tiles in two rows of three. More would be
# 41 px a tile, which is five characters of montserrat_14 -- "Select" does not
# fit. See PANEL_TILE_COLS in V2/firmware/ui_panel.c.
MAX_TOOLS = 6

# Never shipped as a default, and refused from a config file that asks for one
# by name, because a tile is one tap from a document with unsaved work in it.
#
# This is not a security boundary -- the file is the owner's and `run` tiles in
# apps.json can already do anything a program can. It is a guard against the
# specific accident this feature invites: copying a shortcut out of a forum
# post into a panel that is then tapped by somebody reaching past a keyboard.
_REFUSED = frozenset({
    "delete", "forwarddelete", "backspace",
    # Save is not destructive, but "cmd+s" next to "cmd+shift+s" on a 90 px
    # button, on a document somebody has not decided to keep, is an accident
    # waiting to be reported as a bug in Overwatch.
    "cmd+s", "cmd+shift+s", "cmd+w", "cmd+q", "cmd+z", "cmd+shift+z",
    "ctrl+s", "ctrl+shift+s", "ctrl+w", "ctrl+q", "ctrl+z", "ctrl+shift+z",
})

# Tool selections only. Every one of these is a single key that changes which
# tool is active and nothing else.
#
# Adobe's own documented defaults. They are listed here rather than detected
# because there is nothing to detect -- no application publishes its keymap --
# and a person who has remapped theirs edits tools.json, which is the same
# answer as for a meeting service's shortcut.
DEFAULTS = {
    "Adobe Illustrator": [
        ("Select", "v"), ("Direct", "a"), ("Pen", "p"),
        ("Type", "t"), ("Shape", "m"), ("Zoom", "z"),
    ],
    "Adobe Photoshop": [
        ("Move", "v"), ("Marquee", "m"), ("Lasso", "l"),
        ("Brush", "b"), ("Eraser", "e"), ("Type", "t"),
    ],
    "Adobe InDesign": [
        ("Select", "v"), ("Direct", "a"), ("Pen", "p"),
        ("Type", "t"), ("Frame", "f"), ("Zoom", "z"),
    ],
}


def path(home=None):
    """~/.overwatch/tools.json, resolved per call and never at import."""
    base = home or os.path.join(os.path.expanduser("~"), ".overwatch")
    return os.path.join(base, "tools.json")


def clean_tool(entry):
    """One {label, keys} pair, or None. Never raises.

    A dropped tile is better than a refused config: somebody with a typo in one
    of six entries should lose that tile, not the panel.
    """
    if isinstance(entry, (list, tuple)) and len(entry) == 2:
        label, keys = entry
    elif isinstance(entry, dict):
        label, keys = entry.get("label"), entry.get("keys")
    else:
        return None
    if not isinstance(label, str) or not isinstance(keys, str):
        return None
    label, keys = label.strip(), keys.strip().lower()
    if not label or not keys:
        return None
    if keys in _REFUSED:
        print("[tools] refusing %r for %r: see _REFUSED in pc/apptools.py"
              % (keys, label), file=sys.stderr)
        return None
    return {"label": label, "keys": keys}


def _clean_set(tools):
    out = []
    for t in tools or ():
        c = clean_tool(t)
        if c is not None:
            out.append(c)
        if len(out) == MAX_TOOLS:
            break
    return out


def load(home=None):
    """{app name: [{label, keys}]}. The defaults, with the file laid over.

    An app named in the file REPLACES its default set rather than adding to it
    -- otherwise there is no way to remove a tile you do not want, and the
    sixth slot is spoken for.
    """
    sets = {k: _clean_set(v) for k, v in DEFAULTS.items()}
    try:
        with open(path(home), encoding="utf-8") as fh:
            got = json.load(fh)
    except (OSError, ValueError):
        return sets
    if not isinstance(got, dict):
        return sets
    for app, tools in got.items():
        if not isinstance(app, str) or not app.strip():
            continue
        sets[app.strip()] = _clean_set(tools)
    return sets


def _norm(name):
    return " ".join((name or "").split()).lower()


def for_app(app, home=None):
    """The tiles for this application, or [].

    Matched loosely on purpose: the frontmost process is "Adobe Illustrator"
    on one machine and "Adobe Illustrator 2026" on another, and nobody should
    have to discover that to get their tiles.
    """
    want = _norm(app)
    if not want:
        return []
    sets = load(home)
    for key, tools in sets.items():
        k = _norm(key)
        if k == want:
            return tools
    for key, tools in sets.items():
        k = _norm(key)
        if k and (k in want or want in k):
            return tools
    return []
