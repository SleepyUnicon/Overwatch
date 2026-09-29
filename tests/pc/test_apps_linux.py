"""The launcher on Linux: desktop entries instead of .app bundles.

Driven by real .desktop files written into a temporary directory, because that
is what the parser actually meets -- an ini file with a spec's worth of
optional keys, several of which mean "do not show this to anybody".
"""
import os
import sys

import pytest

from pc import apps_linux, widgets

FIREFOX = """[Desktop Entry]
Version=1.0
Type=Application
Name=Firefox
GenericName=Web Browser
Exec=/usr/lib/firefox/firefox %u
Icon=firefox
Categories=Network;WebBrowser;
"""

CODE = """[Desktop Entry]
Type=Application
Name=Visual Studio Code
Exec=/usr/share/code/code --unity-launch %F
Icon=vscode
"""

# NoDisplay is "this exists but is not for people" -- MIME handlers, settings
# panels, half of what a desktop ships with.
HIDDEN_MIME = """[Desktop Entry]
Type=Application
Name=Some MIME Handler
Exec=/usr/bin/handler %f
NoDisplay=true
"""

DELETED = """[Desktop Entry]
Type=Application
Name=Removed Thing
Exec=/usr/bin/gone
Hidden=true
"""

# A terminal app launched from a login service has no terminal to appear in.
TERMINAL = """[Desktop Entry]
Type=Application
Name=Htop
Exec=htop
Terminal=true
"""

NOT_AN_APP = """[Desktop Entry]
Type=Link
Name=A Bookmark
URL=https://example.com
"""

NO_EXEC = """[Desktop Entry]
Type=Application
Name=Broken Entry
"""


@pytest.fixture
def apps(tmp_path, monkeypatch):
    """A fake applications directory, and apps_linux pointed at it."""
    d = tmp_path / "applications"
    d.mkdir()

    def write(stem, body):
        (d / (stem + ".desktop")).write_text(body, encoding="utf-8")

    write("firefox", FIREFOX)
    write("code", CODE)
    write("handler", HIDDEN_MIME)
    write("gone", DELETED)
    write("htop", TERMINAL)
    write("bookmark", NOT_AN_APP)
    write("broken", NO_EXEC)
    monkeypatch.setattr(apps_linux, "APP_DIRS", (str(d),))
    return d


def test_the_picker_offers_real_applications(apps):
    """This is the bug: on Linux the list was empty, so nothing could be
    chosen at all."""
    assert apps_linux.names() == ["Firefox", "Visual Studio Code"]


def test_entries_nobody_should_see_are_left_out(apps):
    got = apps_linux.names()
    for unwanted in ("Some MIME Handler", "Removed Thing", "Htop",
                     "A Bookmark", "Broken Entry"):
        assert unwanted not in got, unwanted


def test_the_command_comes_from_the_entry(apps):
    assert apps_linux.argv_for("Firefox") == ["/usr/lib/firefox/firefox"]


def test_field_codes_are_dropped(apps):
    """%u and %F are placeholders for documents the board never hands over.
    Left in, they arrive as literal arguments and some applications open a
    file named "%U"."""
    for argv in (apps_linux.argv_for("Firefox"),
                 apps_linux.argv_for("Visual Studio Code")):
        assert not any("%" in a for a in argv), argv


def test_arguments_that_are_not_field_codes_survive(apps):
    assert "--unity-launch" in apps_linux.argv_for("Visual Studio Code")


def test_a_name_is_matched_whatever_its_case(apps):
    """The config may have been typed by hand."""
    assert apps_linux.argv_for("firefox") == apps_linux.argv_for("Firefox")


def test_an_app_that_is_not_installed_has_no_command(apps):
    assert apps_linux.argv_for("Ableton Live") is None
    assert apps_linux.argv_for("") is None
    assert apps_linux.argv_for(None) is None


def test_the_users_own_copy_wins(tmp_path, monkeypatch):
    """~/.local/share/applications comes first in the spec's order, and that
    is what makes a customised launcher work."""
    mine, system = tmp_path / "mine", tmp_path / "system"
    mine.mkdir()
    system.mkdir()
    (mine / "firefox.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Firefox\n"
        "Exec=/opt/firefox-nightly/firefox\n", encoding="utf-8")
    (system / "firefox.desktop").write_text(FIREFOX, encoding="utf-8")
    monkeypatch.setattr(apps_linux, "APP_DIRS", (str(mine), str(system)))
    assert apps_linux.argv_for("Firefox") == ["/opt/firefox-nightly/firefox"]


def test_a_directory_that_is_not_there_is_not_an_error(monkeypatch):
    monkeypatch.setattr(apps_linux, "APP_DIRS", ("/no/such/place",))
    assert apps_linux.names() == []


def test_a_file_that_will_not_parse_costs_only_itself(apps):
    """One badly encoded file installed by one package must not empty the
    picker."""
    (apps / "junk.desktop").write_bytes(b"\xff\xfe not an ini at all")
    assert "Firefox" in apps_linux.names()


# --- the launcher side ------------------------------------------------


def test_widgets_asks_the_desktop_entries_on_linux(apps, monkeypatch):
    """It used to return [name] -- running the display name as if it were an
    executable, which works for "firefox" by accident and almost nothing
    else."""
    monkeypatch.setattr(widgets.sys, "platform", "linux")
    assert widgets._argv_for("Firefox") == ["/usr/lib/firefox/firefox"]
    assert widgets._argv_for("Visual Studio Code")[0].endswith("/code")


def test_a_mac_is_untouched(monkeypatch):
    monkeypatch.setattr(widgets.sys, "platform", "darwin")
    assert widgets._argv_for("Safari") == ["open", "-a", "Safari"]


def test_a_missing_app_says_so_rather_than_failing_quietly(apps, monkeypatch,
                                                           capsys):
    monkeypatch.setattr(widgets.sys, "platform", "linux")
    lx = widgets.Launcher(apps=["Ableton Live"])
    assert lx._spawn("Ableton Live") is False
    assert "no such application" in capsys.readouterr().err


def test_a_linux_launch_does_not_wait_for_the_app_to_exit(apps, monkeypatch):
    """The fault this would otherwise have: `open -a` returns in
    milliseconds, but a desktop entry's Exec IS the application. Waiting on it
    means waiting until the user quits Firefox, so the tap would report a
    failure for an app that started perfectly well.
    """
    monkeypatch.setattr(widgets.sys, "platform", "linux")
    started = []

    class FakePopen:
        def __init__(self, argv, **kw):
            started.append((argv, kw))

    monkeypatch.setattr(widgets.subprocess, "Popen", FakePopen)

    def no_waiting(*a, **kw):
        raise AssertionError("subprocess.call would block on a GUI app")

    monkeypatch.setattr(widgets.subprocess, "call", no_waiting)

    assert widgets.Launcher(apps=["Firefox"])._spawn("Firefox") is True
    assert started and started[0][0] == ["/usr/lib/firefox/firefox"]
    assert started[0][1].get("start_new_session") is True, \
        "the app must outlive a daemon restart"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX spawn semantics")
def test_a_command_that_does_not_exist_is_reported(apps, monkeypatch, capsys):
    monkeypatch.setattr(widgets.sys, "platform", "linux")
    (apps / "ghost.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Ghost\n"
        "Exec=%s\n" % os.path.join(str(apps), "definitely-not-here"),
        encoding="utf-8")
    assert widgets.Launcher(apps=["Ghost"])._spawn("Ghost") is False
    assert "launch failed" in capsys.readouterr().err
