"""V2 panels: the message the board has to be able to read.

The firmware half is V2/firmware/ui_panel.c. What binds the two is a 512-byte
line and a parser that reads flat keys only, so most of what is worth testing
here is arithmetic about size and shape rather than behaviour.
"""
import pytest

from pc import protocol
from V2 import panel as P


def _line(msg):
    return protocol.encode(msg)


def test_a_panel_is_flat_keys_only():
    """msg_parse.c has no arrays and no nesting. A list here would arrive as
    a string the board cannot index, and it would look fine on this side."""
    msg = P.Panel("Shop", [P.Row("Orders", "14")], tiles=["Refresh"]).message(0)
    assert all(not isinstance(v, (list, dict)) for v in msg.values())


def test_the_keys_are_the_ones_the_firmware_reads():
    msg = P.Panel("Shop", [P.Row("Orders", "14", tone="ok")],
                  tiles=["Refresh"]).message(0)
    assert msg["t"] == "panel"
    assert msg["p"] == 0
    assert msg["n"] == 1 and msg["tn"] == 1
    assert msg["l0"] == "Orders" and msg["v0"] == "14" and msg["c0"] == "ok"
    assert msg["b0"] == "Refresh"


def test_a_plain_row_sends_no_tone():
    """Absent, not "plain". Every key costs bytes against the line, and the
    board already treats a missing tone as ordinary ink."""
    msg = P.Panel("x", [P.Row("a", "b")]).message(0)
    assert "c0" not in msg


def test_the_worst_case_panel_fits_the_line():
    """The number the whole vocabulary was chosen around.

    proto.c drops an over-long line WHOLE, so a panel one byte too big does
    not arrive clipped -- it does not arrive, and nothing on the glass says
    so. Five rows and three tiles at maximum field widths has to clear it
    with room left.
    """
    worst = P.Panel("T" * P.TITLE_MAX,
                    [P.Row("L" * P.LABEL_MAX, "V" * P.VALUE_MAX, tone="warn")
                     for _ in range(P.ROWS_MAX)],
                    tiles=["B" * P.TILE_MAX] * P.TILES_MAX)
    msg = worst.message(P.PANEL_MAX - 1)
    assert P.too_long(msg) == 0
    assert len(_line(msg)) <= P.LINE_BUDGET < protocol.MAX_LINE_BYTES


def test_fields_are_cut_on_this_side():
    """The board clamps too -- it must, it cannot trust a line it did not
    compose -- but cutting here means the text that arrives ends where
    somebody decided it should."""
    row = P.Row("a" * 99, "b" * 99)
    assert len(row.label) == P.LABEL_MAX
    assert len(row.value) == P.VALUE_MAX
    p = P.Panel("t" * 99, [P.Row("x", "y")] * 99, tiles=["z"] * 99)
    assert len(p.title) == P.TITLE_MAX
    assert len(p.tiles) == P.TILES_MAX
    # Three, not five: ninety-nine tiles is more than four, so they wrap to a
    # second row on the board and paint over where rows 4 and 5 would be.
    assert len(p.rows) == P.ROWS_WITH_MANY_TILES

    # With a tile row that does not wrap, all five rows survive.
    q = P.Panel("t", [P.Row("x", "y")] * 99, tiles=["z"] * P.TILES_ONE_ROW)
    assert len(q.rows) == P.ROWS_MAX


def test_an_unknown_tone_is_refused_here():
    """The board maps an unknown tone to plain ink rather than dropping the
    row, which is right for a board meeting a newer daemon -- and exactly
    wrong as a way to discover a typo on this side."""
    with pytest.raises(ValueError):
        P.Row("a", "b", tone="urgent")


def test_a_slot_outside_the_board_is_refused():
    with pytest.raises(ValueError):
        P.Panel("x").message(P.PANEL_MAX)


def test_slots_are_handed_out_in_order_and_run_out():
    ps = P.Panels()
    assert [ps.add(lambda: None) for _ in range(P.PANEL_MAX)] == \
        list(range(P.PANEL_MAX))
    with pytest.raises(ValueError):
        ps.add(lambda: None)


def test_an_unchanged_panel_is_not_resent():
    """The link already carries a usage frame every few seconds. Repainting
    identical text is spend against the same budget for no difference."""
    ps = P.Panels()
    ps.add(lambda: P.Panel("Shop", [P.Row("Orders", "14")]))
    assert len(ps.messages()) == 1
    assert ps.messages() == []


def test_a_changed_panel_is_resent():
    n = {"v": 14}
    ps = P.Panels()
    ps.add(lambda: P.Panel("Shop", [P.Row("Orders", str(n["v"]))]))
    assert len(ps.messages()) == 1
    n["v"] = 15
    assert len(ps.messages()) == 1


def test_a_panel_that_raises_says_so_instead_of_taking_the_daemon_down():
    """A panel is decoration on a device whose job is the dials. It does not
    get to stop them -- and the failure belongs where it can be seen."""
    ps = P.Panels()
    ps.add(lambda: 1 / 0)
    msgs = ps.messages()
    assert len(msgs) == 1
    assert msgs[0]["v0"] == "ZeroDivisionError"
    assert msgs[0]["c0"] == "bad"


def test_an_over_long_panel_is_replaced_rather_than_sent():
    """Sending it would mean the board dropped the line and the page silently
    stopped updating. Saying so on the page is worse-looking and better."""
    ps = P.Panels()
    ps.add(lambda: P.Panel("x", [P.Row("l", "v")] * 0, tiles=[]))
    # A panel whose fields are legal individually but whose total is not:
    # build it past the budget by hand.
    big = P.Panel("T" * P.TITLE_MAX,
                  [P.Row("L" * P.LABEL_MAX, "V" * P.VALUE_MAX, tone="warn")
                   for _ in range(P.ROWS_MAX)],
                  tiles=["B" * P.TILE_MAX] * P.TILES_MAX)
    big.rows = big.rows * 4                 # past what message() would allow
    msg = big.message(0)
    assert P.too_long(msg) > 0


def test_a_tap_routes_by_number_to_the_right_panel():
    seen = []
    ps = P.Panels()
    ps.add(lambda: P.Panel("a"), on_tap=lambda i: seen.append(("a", i)))
    ps.add(lambda: P.Panel("b"), on_tap=lambda i: seen.append(("b", i)))
    assert ps.on_tap({"t": "panel_tap", "p": 1, "i": 2})
    assert seen == [("b", 2)]


def test_a_tap_for_a_panel_with_no_handler_is_not_an_error():
    ps = P.Panels()
    ps.add(lambda: P.Panel("a"))
    assert ps.on_tap({"t": "panel_tap", "p": 0, "i": 0}) is False


def test_a_malformed_tap_is_refused():
    """The board composes these, but a line is 512 bytes of anything and this
    runs in the daemon's only loop."""
    ps = P.Panels()
    ps.add(lambda: P.Panel("a"), on_tap=lambda i: None)
    for bad in ({"t": "panel_tap"},
                {"t": "panel_tap", "p": "0", "i": 0},
                {"t": "panel_tap", "p": 0, "i": None},
                {"t": "panel_tap", "p": -1, "i": 0},
                {"t": "panel_tap", "p": 99, "i": 0}):
        assert ps.on_tap(bad) is False


def test_it_only_claims_its_own_messages():
    ps = P.Panels()
    assert ps.handles({"t": "panel_tap"})
    assert not ps.handles({"t": "launch"})


def test_the_limits_match_the_firmware_header():
    """Two files, one set of numbers. They are apart because one is C and one
    is Python, not because they are allowed to differ -- the board clamps to
    its own and a daemon that sent six rows would have the sixth vanish with
    no error anywhere."""
    import os
    import re

    hdr = os.path.join(os.path.dirname(__file__), "..", "..",
                       "V2", "firmware", "ui_panel.h")
    src = open(hdr).read()

    def define(name):
        m = re.search(r"#define\s+%s\s+(\d+)" % name, src)
        assert m, "%s not found in ui_panel.h" % name
        return int(m.group(1))

    assert P.PANEL_MAX == define("PANEL_MAX")
    assert P.ROWS_MAX == define("PANEL_ROWS")
    assert P.TILES_MAX == define("PANEL_TILES")
    assert P.TITLE_MAX == define("PANEL_TITLE_MAX")
    assert P.LABEL_MAX == define("PANEL_LABEL_MAX")
    assert P.VALUE_MAX == define("PANEL_VALUE_MAX")
    assert P.TILE_MAX == define("PANEL_TILE_MAX")
