"""Fourth panel: the tools of whatever application is in front.

WHY IT FOLLOWS THE FRONTMOST APP RATHER THAN THE LAUNCHER

The obvious shape is "tapping the Illustrator tile opens Illustrator's tools".
This does something slightly different and strictly more useful: it watches what
is in FRONT. Same result when you launch from the board, and it also works when
you cmd-tab, when you come back from a meeting, and when the app was already
open before Overwatch was. It is also one panel slot instead of one per
application, which matters -- a slot is 288 bytes of a board with 25 KB spare.

Six tiles, in two rows of three, which is the widest the screen allows with
labels people can read. See PANEL_TILE_COLS in V2/firmware/ui_panel.c for the
arithmetic, and pc/apptools.py for why the shipped defaults are tool selections
and nothing that writes to a document.
"""
import sys

from pc import actions, apptools, macperm, windows
from V2.panel import Panel, Row

_WHERE_TO_FIX = {
    "Accessibility off": "Privacy settings",
    "not on this OS": "macOS and X11",
}


def _fit(s, n):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n - 1] + "…"


def _document(title, app):
    """The document name out of a window title.

    Adobe appends the zoom and colour space -- "Staff IDs MAR26 PRINT.pdf* @
    83.49 % (CMYK/Preview)" -- which is 26 characters of nothing on a row that
    holds 18. Cutting at " @ " leaves the part somebody named.
    """
    t = " ".join((title or "").split())
    if not t or t == app:
        return ""
    return t.split(" @ ")[0].strip()


def _plan():
    """(title, rows, tools) -- built once so build() and on_tap() agree.

    The same rule meeting_panel learned the hard way: a panel whose tile list
    depends on what is in front cannot also have constant tile indices.
    """
    fields, err = windows.current()
    if err:
        rows = [Row("Not yet", _fit(err, 18), tone="warn")]
        hint = _WHERE_TO_FIX.get(err)
        if hint:
            rows.append(Row("Fix in", hint, tone="dim"))
        return "Tools", rows, []
    if not fields:
        return "Tools", [Row("Nothing", "in front", tone="dim")], []

    app = fields.get("app") or fields.get("title") or ""
    tools = apptools.for_app(app)
    if not tools:
        # Not an error -- most applications have no tile set, and saying so
        # plainly beats an empty page that reads as a fault.
        return "Tools", [
            Row("App", _fit(app, 18)),
            Row("Tools", "none set", tone="dim"),
            Row("Add in", "tools.json", tone="dim"),
        ], []

    # The title carries the application, so a row repeating it would spend one
    # of the three on nothing. What the rows are for is WHICH DOCUMENT -- the
    # same reason the window panel shows a title: knowing the tiles are aimed
    # at the right thing before tapping one.
    rows = []
    doc = _document(fields.get("title"), app)
    if doc:
        rows.append(Row("Doc", _fit(doc, 18), tone="dim"))
    else:
        rows.append(Row("Ready", "%d tools" % len(tools), tone="dim"))
    return _fit(app, 20), rows, tools


def build():
    title, rows, tools = _plan()
    return Panel(title, rows, tiles=[t["label"] for t in tools])


def on_tap(tile):
    _title, _rows, tools = _plan()
    if not 0 <= tile < len(tools):
        return
    tool = tools[tile]
    ok, why = actions.send_keys(tool["keys"])
    if ok:
        return
    # A tile that does nothing and says nothing is the worst outcome here,
    # because the app it was aimed at looks like the thing that is broken.
    granted, state = macperm.ax_check()
    if not granted:
        print("[tools] %s: %s" % (tool["label"], macperm.ax_explain(state)),
              file=sys.stderr)
        return
    print("[tools] %s (%s): %s" % (tool["label"], tool["keys"],
                                   why or "did not send"), file=sys.stderr)
