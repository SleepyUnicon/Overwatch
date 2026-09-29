"""Third panel: the call you are in, and whether you can be heard.

WHAT THIS IS FOR

The one mistake a physical display can prevent that a screen cannot is
believing you are muted when you are not. Every meeting application puts its
mute state inside the window you are not looking at -- behind the slides, or
the shared terminal, or the other monitor. A lamp on the desk that says LIVE
is a different kind of object from an icon in a tab.

So the mic row reads the real state of the system microphone every refresh,
and `Live` is toned as a warning. Not because being live is wrong, but because
it is the state you can be wrong about at somebody else's expense.

WHAT IT DELIBERATELY DOES NOT DO

There is no Leave tile and no camera tile. Both would mean synthesising Zoho
Meeting's own keyboard shortcut, which I do not know, into a browser tab --
and a Leave button that drops the wrong window, or nothing at all, is worse
than no button. The fourth tile is left empty rather than filled with a guess.
"""
import sys

from pc import meeting, mic
from V2.panel import Panel, Row

# Tiles are built in ONE place and dispatched by what they say, not by a
# hard-coded index. The first version numbered them 0/1/2 and dropped the mic
# tile when the microphone could not be read -- which shifted Show down into
# Sound's slot, so the Show button silenced the speakers. A panel whose tile
# list is conditional cannot also have constant indices.
#
# Short labels: at three tiles a button is 88 px, about eleven characters of
# montserrat_14. "Unmute" and "Sound" fit; "Unsilence" would not.
MIC = "mic"
SOUND = "Sound"
SHOW = "Show"

# A row VALUE is eighteen characters. "your package manager" is twenty, and
# arrived on the glass as "your package manag" -- the same truncation bug
# window_panel.py already carried a comment about and then repeated.
# test_every_hint_fits_a_row keeps both honest.
_WHERE_TO_FIX = {
    "install wmctrl to see calls": "package manager",
    "install pactl for mute control": "package manager",
    "could not list applications": "Privacy settings",
}


def _fit(s, n):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n - 1] + "…"


def _mic_row():
    """The real state, or an honest blank. Never a guess."""
    state, err = mic.muted()
    if err:
        return Row("Mic", _fit(err, 18), tone="dim"), None
    # Muted is `ok` and live is `warn` on purpose. Being live is the ordinary
    # state of a person in a meeting -- but it is the one you can be wrong
    # about in a way that costs somebody else something, so it is the one that
    # gets the amber.
    if state:
        return Row("Mic", "Muted", tone="ok"), True
    return Row("Mic", "LIVE", tone="warn"), False


def _sound_row():
    state, err = mic.out_muted()
    if err:
        return Row("Sound", _fit(err, 18), tone="dim"), None
    if state:
        return Row("Sound", "Muted", tone="warn"), True
    return Row("Sound", "On", tone="dim"), False


def _plan():
    """(rows, [(label, action)]) -- the single source of what is on the panel.

    build() draws it and on_tap() indexes it, so the two cannot disagree.
    """
    call, err = meeting.detect()

    rows = []
    tiles = []

    if err:
        # Could not look, which is not the same as no call -- and is something
        # a person can fix, so it goes on the glass rather than only the log.
        rows.append(Row("Call", _fit(err, 18), tone="warn"))
        hint = _WHERE_TO_FIX.get(err)
        if hint:
            rows.append(Row("Fix in", hint, tone="dim"))
    elif call:
        rows.append(Row("Call", _fit(call["service"], 18), tone="ok"))
    else:
        rows.append(Row("Call", "None", tone="dim"))

    mic_row, is_muted = _mic_row()
    rows.append(mic_row)
    sound_row, _out_muted = _sound_row()
    rows.append(sound_row)

    if call and call.get("where"):
        rows.append(Row("In", _fit(call["where"], 18), tone="dim"))

    # The mic tile says what it will DO, not what the state is -- the row
    # above already says the state, and a button labelled with the thing you
    # are trying to get away from reads backwards.
    if is_muted is not None:
        tiles.append(("Unmute" if is_muted else "Mute", MIC))
    # else: no tile at all. A button that cannot report what it did is the
    # exact thing this panel exists to avoid.
    tiles.append((SOUND, SOUND))
    if call:
        tiles.append((SHOW, SHOW))

    return rows[:5], tiles


def build():
    rows, tiles = _plan()
    return Panel("Meeting", rows, tiles=[label for label, _a in tiles])


def on_tap(tile):
    _rows, tiles = _plan()
    if not 0 <= tile < len(tiles):
        return
    action = tiles[tile][1]

    if action == MIC:
        state, err = mic.toggle()
        if err:
            print("[meeting] mic: %s" % err, file=sys.stderr)
        else:
            print("[meeting] mic now %s" % ("muted" if state else "live"),
                  file=sys.stderr)
    elif action == SOUND:
        _state, err = mic.toggle_out()
        if err:
            print("[meeting] sound: %s" % err, file=sys.stderr)
    elif action == SHOW:
        call, err = meeting.detect()
        if err or not call:
            print("[meeting] nothing to show", file=sys.stderr)
            return
        ok, err = meeting.show(call)
        if not ok:
            print("[meeting] show: %s" % (err or "did not raise"),
                  file=sys.stderr)
