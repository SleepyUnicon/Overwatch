"""The launcher widget's daemon half.

Fixture-free on purpose: every test here builds its own Launcher with an
injected `run`, so nothing in this file can start a program on the machine
running it.
"""
import json
import os
import tempfile

from pc import protocol, widgets


def _lx(apps, run=None):
    return widgets.Launcher(apps=apps, run=run or (lambda name: True))


# --- the wire ---------------------------------------------------------

def test_apps_message_fits_the_board_line_limit():
    """Six of the longest label the firmware will draw, against the cliff."""
    lx = _lx(["X" * widgets.LABEL_MAX] * widgets.SLOTS)
    raw, err = protocol.encode_checked(lx.apps_message())
    assert raw is not None, err
    assert len(raw) <= protocol.MAX_LINE_BYTES


def test_empty_slots_are_omitted_not_sent_empty():
    """Unknown values are omitted, not sent as sentinels -- the budget rule."""
    msg = _lx(["Safari", "", "Figma", "", "", ""]).apps_message()
    assert msg["s0"] == "Safari" and msg["s2"] == "Figma"
    assert "s1" not in msg and "s3" not in msg


# --- icons ---------------------------------------------------------------

def test_a_versioned_app_name_still_finds_its_icon():
    """The launcher table holds what `open -a` needs, and that carries a
    version the icon does not."""
    assert widgets.icon_for("Adobe Photoshop 2026") == "photoshop"
    assert widgets.icon_for("PCSX2-v2.6.3") == "pcsx2"
    assert widgets.icon_for("Brave Browser") == "brave"


def test_an_app_with_no_icon_gets_none_not_a_guess():
    assert widgets.icon_for("Ableton Live") is None
    assert widgets.icon_for("") is None
    assert widgets.icon_for(None) is None


def test_the_board_is_sent_icon_keys_not_display_names():
    msg = _lx(["Adobe Photoshop 2026", "Spotify"]).apps_message()
    assert msg["s0"] == "photoshop" and msg["s1"] == "spotify"


def test_an_app_without_an_icon_falls_back_to_its_name():
    """ui_launcher.c draws an unknown key as text, so this must stay a
    sensible label rather than becoming empty."""
    msg = _lx(["Ableton Live"]).apps_message()
    assert msg["s0"] == "Ableton Live"[:widgets.LABEL_MAX].strip()


def test_every_key_this_side_names_exists_on_the_board():
    """Pins the two halves together. The daemon naming an icon the firmware
    was not generated with is a tile that silently falls back to text, which
    looks like a rendering bug and is a table mismatch."""
    import os, re
    hdr = os.path.join(os.path.dirname(__file__), "..", "..",
                       "firmware", "src", "icons_gen.h")
    if not os.path.isfile(hdr):
        return                      # header is generated; skip if not built
    on_board = set(re.findall(r'\{\s*"([a-z0-9]+)",\s*&icon_', open(hdr).read()))
    assert set(widgets.ICON_KEYS) <= on_board, set(widgets.ICON_KEYS) - on_board


def test_long_names_are_cut_to_what_the_panel_draws():
    msg = _lx(["Visual Studio Code"]).apps_message()
    assert msg["s0"] == "Visual Studio"
    assert len(msg["s0"]) <= widgets.LABEL_MAX


def test_a_real_board_line_round_trips_into_a_launch():
    """Byte-for-byte what proto.c's snprintf emits."""
    line = '{"t":"launch","v":2,"slot":3}'
    msg = protocol.decode(line)
    lx = _lx(["a", "b", "c", "Terminal", "e", "f"])
    assert lx.handles(msg)
    assert lx.on_launch(msg) == {"t": "launched", "v": protocol.VERSION,
                                 "slot": 3, "ok": True}


# --- answering honestly ------------------------------------------------

def test_a_failed_launch_answers_false_rather_than_going_quiet():
    lx = _lx(["Safari"] * widgets.SLOTS, run=lambda name: False)
    assert lx.on_launch({"t": "launch", "slot": 0})["ok"] is False


def test_an_unassigned_slot_answers_false():
    lx = _lx([""] * widgets.SLOTS)
    assert lx.on_launch({"t": "launch", "slot": 2})["ok"] is False


def test_a_slot_off_the_end_is_refused_outright():
    lx = _lx(["Safari"] * widgets.SLOTS)
    assert lx.on_launch({"t": "launch", "slot": 99}) is None
    assert lx.on_launch({"t": "launch", "slot": -1}) is None
    assert lx.on_launch({"t": "launch", "slot": "0"}) is None
    assert lx.on_launch({"t": "launch"}) is None


def test_a_boolean_slot_is_not_an_index():
    """True == 1 in Python, so a bool would launch slot 1 if it reached the
    subscript. It is refused at the type check instead."""
    lx = _lx(["a", "SHOULD NOT RUN", "c", "d", "e", "f"],
             run=lambda name: (_ for _ in ()).throw(AssertionError(name)))
    assert lx.on_launch({"t": "launch", "slot": True}) is None


def test_nothing_runs_for_a_refused_slot():
    fired = []
    lx = _lx(["Safari"] * widgets.SLOTS, run=lambda n: fired.append(n) or True)
    lx.on_launch({"t": "launch", "slot": 99})
    assert fired == []


# --- the command --------------------------------------------------------

def test_the_command_is_a_list_never_a_shell_string():
    """A name off a customer-owned file must not become shell syntax."""
    argv = widgets._argv_for("x; rm -rf ~")
    assert isinstance(argv, list)
    assert "x; rm -rf ~" in argv          # carried whole, as one argument
    assert not any(";" in a for a in argv if a != "x; rm -rf ~")


def test_an_empty_name_produces_no_command_at_all():
    assert widgets._argv_for("") is None


# --- the config file ----------------------------------------------------

def test_a_malformed_config_falls_back_instead_of_raising():
    """A login agent must start even when the customer drops a comma."""
    home = tempfile.mkdtemp()
    old = os.environ.get("HOME")
    os.environ["HOME"] = home
    try:
        os.makedirs(os.path.join(home, ".overwatch"), exist_ok=True)
        with open(widgets._config_path(), "w") as fh:
            fh.write("{ not json,,,")
        assert len(widgets.load_apps()) == widgets.SLOTS
    finally:
        if old is not None:
            os.environ["HOME"] = old


def test_the_config_path_follows_a_redirected_home():
    """Pins the CLAUDE.md sandbox hole: resolved in the function, not at
    import, so a test can never write the developer's own apps.json."""
    home = tempfile.mkdtemp()
    old = os.environ.get("HOME")
    os.environ["HOME"] = home
    try:
        assert widgets._config_path().startswith(home)
    finally:
        if old is not None:
            os.environ["HOME"] = old


def test_a_config_file_overrides_the_defaults():
    home = tempfile.mkdtemp()
    old = os.environ.get("HOME")
    os.environ["HOME"] = home
    try:
        os.makedirs(os.path.join(home, ".overwatch"), exist_ok=True)
        with open(widgets._config_path(), "w") as fh:
            json.dump(["Ableton"], fh)
        assert widgets.load_apps()[0] == "Ableton"
    finally:
        if old is not None:
            os.environ["HOME"] = old
