"""Per-application tool tiles, and the rule about what they may send.

The meeting panel drives the SYSTEM microphone because Zoho Meeting's shortcut
is unknowable. That reasoning does not carry here and the difference is the
point: Illustrator's tool keys are published, single, stable, idempotent and
visible -- press the wrong one and the palette changes, press another and it is
undone. None of that is true of anything that writes to a document, which is
why the shipped defaults are tool selections only and why _REFUSED exists.
"""
import json

import pytest

from pc import apptools, windows
from V2 import panel as pm, tool_panel


# --- what a config may say --------------------------------------------


def test_a_pair_and_a_dict_both_work():
    assert apptools.clean_tool(("Pen", "p")) == {"label": "Pen", "keys": "p"}
    assert apptools.clean_tool({"label": "Pen", "keys": "p"})["keys"] == "p"


def test_rubbish_is_dropped_rather_than_raised_on():
    """One typo in six entries should cost that tile, not the panel."""
    for bad in (None, 7, [], ["only"], {"label": "x"}, {"keys": "v"},
                {"label": "  ", "keys": "v"}, {"label": "x", "keys": ""},
                {"label": 1, "keys": "v"}):
        assert apptools.clean_tool(bad) is None


def test_a_destructive_shortcut_is_refused(capsys):
    """THE rule. A tile is one tap from a document with unsaved work, and the
    tap may come from somebody reaching past a keyboard."""
    for keys in ("delete", "cmd+z", "cmd+w", "cmd+q", "ctrl+s"):
        assert apptools.clean_tool({"label": "X", "keys": keys}) is None
    assert "refusing" in capsys.readouterr().err


def test_the_refusal_is_case_insensitive():
    assert apptools.clean_tool({"label": "X", "keys": "CMD+Z"}) is None


def test_every_shipped_default_survives_its_own_validator():
    """A default that the validator refuses would be a tile that silently is
    not there, in the set most people never edit."""
    for app, tools in apptools.DEFAULTS.items():
        cleaned = [apptools.clean_tool(t) for t in tools]
        assert all(c is not None for c in cleaned), app
        assert len(cleaned) <= apptools.MAX_TOOLS, app


def test_every_shipped_default_is_a_bare_key_not_a_command():
    """Tool selections only. A modifier in a default means someone has added
    something that does more than change which tool is active."""
    for app, tools in apptools.DEFAULTS.items():
        for label, keys in tools:
            assert "+" not in keys, (app, label, keys)
            assert len(keys) == 1, (app, label, keys)


def test_six_is_the_ceiling():
    """The board draws six. A seventh would be accepted here and never
    appear, which is worse than being told."""
    many = [("T%d" % i, chr(ord("a") + i)) for i in range(10)]
    assert len(apptools._clean_set(many)) == apptools.MAX_TOOLS


# --- the file ---------------------------------------------------------


def test_defaults_apply_when_there_is_no_file(tmp_path):
    got = apptools.for_app("Adobe Illustrator", str(tmp_path))
    assert [t["label"] for t in got][:2] == ["Select", "Direct"]


def test_a_named_app_replaces_its_defaults_rather_than_adding(tmp_path):
    """Otherwise there is no way to remove a tile you do not want, and the
    sixth slot is already spoken for."""
    (tmp_path / "tools.json").write_text(json.dumps({
        "Adobe Illustrator": [{"label": "Mine", "keys": "q"}]}),
        encoding="utf-8")
    got = apptools.for_app("Adobe Illustrator", str(tmp_path))
    assert [t["label"] for t in got] == ["Mine"]


def test_another_app_keeps_its_defaults(tmp_path):
    (tmp_path / "tools.json").write_text(json.dumps({
        "Adobe Illustrator": [{"label": "Mine", "keys": "q"}]}),
        encoding="utf-8")
    assert apptools.for_app("Adobe Photoshop", str(tmp_path))


def test_a_broken_file_falls_back_rather_than_failing(tmp_path):
    (tmp_path / "tools.json").write_text("{not json", encoding="utf-8")
    assert apptools.for_app("Adobe Illustrator", str(tmp_path))


def test_a_versioned_application_name_still_matches(tmp_path):
    """The frontmost process is "Adobe Illustrator" on one machine and
    "Adobe Illustrator 2026" on another. Nobody should have to discover
    that."""
    assert apptools.for_app("Adobe Illustrator 2026", str(tmp_path))


def test_an_unknown_app_gets_nothing(tmp_path):
    assert apptools.for_app("Finder", str(tmp_path)) == []
    assert apptools.for_app("", str(tmp_path)) == []


def test_the_path_is_resolved_per_call(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert str(tmp_path) in apptools.path()


# --- the panel --------------------------------------------------------


@pytest.fixture
def in_illustrator(monkeypatch):
    monkeypatch.setattr(windows, "current", lambda: ({
        "app": "Adobe Illustrator",
        "title": "Staff IDs MAR26 PRINT.pdf* @ 83.49 % (CMYK/Preview)",
        "screen": 0, "screens": 1, "x": 0, "y": 30, "w": 1920, "h": 1050,
        "wid": ""}, None))


def test_the_panel_is_titled_after_the_app(in_illustrator):
    assert tool_panel.build().title == "Adobe Illustrator"


def test_it_offers_six_tiles(in_illustrator):
    assert tool_panel.build().tiles == ["Select", "Direct", "Pen", "Type",
                                        "Shape", "Zoom"]


def test_the_document_loses_adobes_zoom_suffix(in_illustrator):
    """"@ 83.49 % (CMYK/Preview)" is 26 characters of nothing on a row that
    holds eighteen."""
    doc = next(r for r in tool_panel.build().rows if r.label == "Doc")
    assert doc.value.startswith("Staff IDs MAR26")
    assert "83.49" not in doc.value


def test_six_tiles_leave_room_for_their_rows(in_illustrator):
    """The board wraps six tiles to a second row and paints over where rows 4
    and 5 would be. panel.Panel refuses to build one; this is the check that
    the real panel stays inside that."""
    p = tool_panel.build()
    assert len(p.tiles) == 6
    assert len(p.rows) <= pm.ROWS_WITH_MANY_TILES


def test_the_panel_fits_one_line(in_illustrator):
    assert pm.too_long(tool_panel.build().message(3)) == 0


def test_an_app_with_no_tools_says_so_and_offers_nothing(monkeypatch):
    monkeypatch.setattr(windows, "current",
                        lambda: ({"app": "Finder", "title": ""}, None))
    p = tool_panel.build()
    assert p.tiles == []
    assert any(r.value == "none set" for r in p.rows)
    assert any("tools.json" in r.value for r in p.rows)


def test_a_permission_problem_says_where_to_fix_it(monkeypatch):
    monkeypatch.setattr(windows, "current",
                        lambda: (None, "Accessibility off"))
    p = tool_panel.build()
    assert p.tiles == []
    assert any(r.value == "Device Control" for r in p.rows)


# --- taps -------------------------------------------------------------


def test_a_tap_sends_that_tool_s_key(in_illustrator, monkeypatch):
    sent = []
    monkeypatch.setattr(tool_panel.actions, "send_keys",
                        lambda k: (sent.append(k) or (True, None)))
    for i in range(6):
        tool_panel.on_tap(i)
    assert sent == ["v", "a", "p", "t", "m", "z"]


def test_a_tap_outside_the_tiles_sends_nothing(in_illustrator, monkeypatch):
    sent = []
    monkeypatch.setattr(tool_panel.actions, "send_keys",
                        lambda k: (sent.append(k) or (True, None)))
    tool_panel.on_tap(9)
    tool_panel.on_tap(-1)
    assert sent == []


def test_tapping_an_app_with_no_tools_sends_nothing(monkeypatch):
    monkeypatch.setattr(windows, "current",
                        lambda: ({"app": "Finder", "title": ""}, None))
    sent = []
    monkeypatch.setattr(tool_panel.actions, "send_keys",
                        lambda k: (sent.append(k) or (True, None)))
    tool_panel.on_tap(0)
    assert sent == []


def test_a_failed_send_blames_the_permission_not_the_app(in_illustrator,
                                                         monkeypatch, capsys):
    """A tile that does nothing and says nothing leaves the application
    looking like the broken thing."""
    monkeypatch.setattr(tool_panel.actions, "send_keys",
                        lambda k: (False, "Accessibility"))
    monkeypatch.setattr(tool_panel.macperm, "ax_check",
                        lambda: (False, "denied"))
    tool_panel.on_tap(0)
    assert "Accessibility" in capsys.readouterr().err


def test_all_four_panels_register():
    from pc import widget_bridge
    assert len(widget_bridge._default_panels()._sources) == 4


def test_two_panels_blocked_by_one_permission_do_not_look_alike(monkeypatch):
    """Window and Tools are both gated on Accessibility, and both used to draw
    "Not yet / Accessibility off" over "Fix in / Privacy settings" -- identical
    apart from a title. The owner swiped through all four pages and reported
    that the fourth did not exist, which is exactly what two identical pages
    look like.
    """
    from V2 import window_panel
    monkeypatch.setattr(windows, "current", lambda: (None, "Accessibility off"))
    w = window_panel.build()
    t = tool_panel.build()
    assert [r.label for r in w.rows] != [r.label for r in t.rows]
    # And each says what IS lost, rather than only why.
    assert any("Snap" in r.label for r in w.rows)
    assert any("Tool" in r.label for r in t.rows)
