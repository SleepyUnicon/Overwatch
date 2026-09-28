"""Build panels for the board, and route the taps that come back.

This is the daemon half of V2/firmware/ui_panel.c. Between them they are the
whole point of V2: after this, a new page on the device is a Python object and
a function, with no firmware build, no release and no OTA. See V2/README.md.

A feature written against this looks like:

    def shop():
        return Panel("Shop today", [
            Row("Orders", "14", tone="ok"),
            Row("Revenue", "KSh 48,200"),
            Row("Last", "3 min ago", tone="dim"),
        ], tiles=["Refresh"])

and a tap on tile 0 arrives as on_tap(panel=0, tile=0).

Standard library only, like the rest of pc/ (CLAUDE.md).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pc import protocol                                          # noqa: E402

# Mirrors V2/firmware/ui_panel.h. The board clamps to these too -- it has to,
# since it cannot trust a line it did not compose -- but truncating HERE means
# the text that arrives is the text somebody chose the end of, rather than
# whatever fell inside the limit.
PANEL_MAX = 2
ROWS_MAX = 5
TILES_MAX = 3

TITLE_MAX = 20
LABEL_MAX = 14
VALUE_MAX = 18
TILE_MAX = 12

TONES = ("dim", "ok", "warn", "bad")

# Under protocol.MAX_LINE_BYTES (512) with room to spare. The board drops an
# over-long line WHOLE, so a panel that grew by one character would not arrive
# clipped -- it would not arrive at all, and nothing on the glass would say so.
# Refusing here, where there is a traceback, beats a page that silently stops
# updating.
LINE_BUDGET = 480


def _cut(s, n):
    return ("" if s is None else str(s))[:n]


class Row:
    """One label-and-value line.

    `tone` says what the value MEANS -- ok, warn, bad, dim -- not what colour
    to paint it. The board resolves it through ui_theme(), which is why a
    panel reads correctly in both themes without this side knowing which one
    is on. A daemon that picked colours would be wrong half the time and have
    no way to find out.
    """

    __slots__ = ("label", "value", "tone")

    def __init__(self, label, value, tone=None):
        if tone is not None and tone not in TONES:
            raise ValueError("tone must be one of %s, not %r" % (TONES, tone))
        self.label = _cut(label, LABEL_MAX)
        self.value = _cut(value, VALUE_MAX)
        self.tone = tone


class Panel:
    """A page: a title, some rows, and up to three tiles you can press."""

    __slots__ = ("title", "rows", "tiles")

    def __init__(self, title, rows=(), tiles=()):
        self.title = _cut(title, TITLE_MAX)
        self.rows = list(rows)[:ROWS_MAX]
        self.tiles = [_cut(t, TILE_MAX) for t in tiles][:TILES_MAX]

    def message(self, slot):
        """The wire form, as flat keys.

        Flat because msg_parse.c reads flat keys and nothing else -- no
        arrays, no nesting. It is also the shape whose size can be reasoned
        about at a glance, which matters against a 512-byte line.
        """
        if not 0 <= slot < PANEL_MAX:
            raise ValueError("panel slot %r outside 0..%d" % (slot, PANEL_MAX - 1))
        # "v" like every other message on this link. proto.c does not read it
        # on the way in, but a message that is shaped differently from its
        # siblings is one somebody has to think about twice.
        msg = {"t": "panel", "v": protocol.VERSION, "p": slot,
               "title": self.title, "n": len(self.rows),
               "tn": len(self.tiles)}
        for i, row in enumerate(self.rows):
            msg["l%d" % i] = row.label
            msg["v%d" % i] = row.value
            if row.tone:
                msg["c%d" % i] = row.tone
        for i, tile in enumerate(self.tiles):
            msg["b%d" % i] = tile
        return msg


def too_long(msg):
    """How many bytes over LINE_BUDGET this message is, or 0.

    Separate from sending so a caller can measure a panel while writing it,
    rather than finding out on the desk.
    """
    over = len(protocol.encode(msg)) - LINE_BUDGET
    return over if over > 0 else 0


class Panels:
    """The daemon's panel set: what to show, and what a tap means.

    A source is a callable returning a Panel, or None to leave the slot as it
    is. Called on a schedule by the owner -- nothing here starts a thread or a
    timer, because pc/bridge.py already owns the one loop this daemon has.
    """

    def __init__(self):
        self._sources = []
        self._taps = []
        self._last = {}

    def add(self, build, on_tap=None):
        """Register a panel. Returns its slot number.

        Slots are handed out in order and never reused: ui_panel.c counts
        panels contiguously from zero, so a gap would put a blank page between
        two real ones with no way to tell it from a panel with nothing to say.
        """
        if len(self._sources) >= PANEL_MAX:
            raise ValueError(
                "the board holds %d panels; see PANEL_MAX in "
                "V2/firmware/ui_panel.h" % PANEL_MAX)
        self._sources.append(build)
        self._taps.append(on_tap)
        return len(self._sources) - 1

    def messages(self):
        """The messages to send now: one per panel whose content CHANGED.

        Unchanged panels are skipped. The link carries a usage frame every few
        seconds already, and a panel that repaints identical text is spend
        against the same budget for no visible difference.
        """
        out = []
        for slot, build in enumerate(self._sources):
            try:
                panel = build()
            except Exception as e:                  # a panel must not take the
                # daemon down: it is a decoration on a device whose job is the
                # dials. Say so in the panel itself, where it can be seen.
                panel = Panel("Panel %d" % slot,
                              [Row("Error", type(e).__name__, tone="bad")])
            if panel is None:
                continue
            msg = panel.message(slot)
            over = too_long(msg)
            if over:
                msg = Panel(panel.title,
                            [Row("Too long", "by %d bytes" % over, tone="bad")]
                            ).message(slot)
            if self._last.get(slot) == msg:
                continue
            self._last[slot] = msg
            out.append(msg)
        return out

    def handles(self, msg):
        return msg.get("t") == "panel_tap"

    def on_tap(self, msg):
        """Run the handler for a tap. Returns True if one was found.

        The board sends two numbers and nothing else, so this is the only
        place that knows what a tile does -- the same split pc/widgets.py uses
        for the launcher, and for the same reason: a message from the panel
        cannot name an action this side has not already agreed to.
        """
        slot, tile = msg.get("p"), msg.get("i")
        if not isinstance(slot, int) or not isinstance(tile, int):
            return False
        if not 0 <= slot < len(self._taps):
            return False
        handler = self._taps[slot]
        if handler is None:
            return False
        handler(tile)
        return True
