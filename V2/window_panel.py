"""Second panel: the window in front, and four places to put it.

The launcher can already send a keystroke, so somebody could bind their own
snapping shortcut to a tile. What this adds is the half a keypad cannot: it
SHOWS which window is about to move, and which screen it is on, before
anything happens. Moving the wrong window is the failure mode of every blind
shortcut, and a 320 px screen is exactly the right size to prevent it.

Four tiles because there are four useful places and PANEL_TILES is four.
"""
import sys

from pc import windows
from V2.panel import Panel, Row

TILES = ("Left", "Right", "Full", "Next")

# A short reason fits the row; where to go about it does not fit beside it.
_WHERE_TO_FIX = {
    "Accessibility off": "Device Control",
    "install xdotool for window control": "package manager",
    "install wmctrl for window control": "package manager",
}


def _fit(s, n):
    """Cut to fit, with an ellipsis so a cut reads as one."""
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n - 1] + "…"


def build():
    fields, err = windows.current()
    if err:
        # The permission and the missing-tool cases both land here, and both
        # are things a person can fix -- so they go on the panel rather than
        # only into a log nobody is reading.
        #
        # In two rows, because a value is eighteen characters and "Allow
        # Overwatch under System Settings > Privacy & Security >
        # Accessibility" is not. The short reason names the problem; the
        # second row says where to go. The full sentence is in the log.
        # "Snapping", not "Not yet". The tools panel is blocked by the same
        # permission and drew the same two rows, so the two pages were
        # identical apart from a 20-character title -- and the owner swiped
        # past one reporting there was no fourth page at all. A row that names
        # what is lost tells them apart and is more use besides.
        rows = [Row("Snapping", _fit(err, 18), tone="warn")]
        hint = _WHERE_TO_FIX.get(err)
        if hint:
            rows.append(Row("Fix in", hint, tone="dim"))
        return Panel("Window", rows)
    if fields is None:
        return Panel("Window", [Row("Nothing", "in front", tone="dim")])

    rows = []
    # The app on macOS, the title on X11: System Events names the process and
    # xdotool names the window, and each is the more useful of the two on its
    # own platform.
    who = fields.get("app") or fields.get("title")
    if who:
        rows.append(Row("Window", _fit(who, 18)))
    if fields.get("app") and fields.get("title"):
        rows.append(Row("Title", _fit(fields["title"], 18), tone="dim"))

    if fields.get("w") and fields.get("h"):
        rows.append(Row("Size", "%d x %d" % (fields["w"], fields["h"]),
                        tone="dim"))
    if fields.get("screens", 1) > 1:
        rows.append(Row("Screen", "%d of %d" % (fields.get("screen", 0) + 1,
                                                fields["screens"])))
    if not rows:
        rows.append(Row("Window", "in front"))

    return Panel("Window", rows, tiles=list(TILES))


def on_tap(tile):
    if not 0 <= tile < len(TILES):
        return
    where = windows.PLACES[tile]
    ok, err = windows.place(where)
    if not ok:
        print("[panel] %s: %s" % (where, err or "did not move"),
              file=sys.stderr)
