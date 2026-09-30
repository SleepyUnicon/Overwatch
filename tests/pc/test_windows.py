"""Reading and moving the frontmost window.

The X11 half is driven by recorded xdotool and xrandr output: the suite runs
on macOS and in CI and neither has a display server. That covers the
arithmetic, which is the part worth covering -- half of one screen out of
three is a sum, and getting it wrong puts somebody's window somewhere they
did not ask for.
"""
import pytest

from pc import windows
from V2 import window_panel


XRANDR = """Screen 0: minimum 320 x 200, current 4920 x 2188, maximum 16384 x 16384
eDP-1 connected primary 1920x1080+0+1108 (normal left inverted right) 344mm x 194mm
   1920x1080     60.01*+
HDMI-1 connected 1920x1080+1920+0 (normal left inverted right) 527mm x 296mm
DP-2 connected 1080x1920+3840+0 (normal left inverted right) 527mm x 296mm
DP-3 disconnected (normal left inverted right)
"""

GEOM = """WINDOW=44040201
X=1950
Y=40
WIDTH=1200
HEIGHT=800
SCREEN=0
"""


class FakeX11:
    """Stands in for _run, keyed on the tool and its first argument."""

    def __init__(self, **over):
        self.calls = []
        self.over = over

    def __call__(self, argv):
        self.calls.append(argv)
        key = argv[0] if len(argv) == 1 else "%s %s" % (argv[0], argv[1])
        if key in self.over:
            return self.over[key]
        if argv[0] == "xrandr":
            return XRANDR, None
        if argv[0] == "xdotool":
            if argv[1] == "getactivewindow":
                return "44040201", None
            if argv[1] == "getwindowname":
                return "notes.txt - Text Editor", None
            if argv[1] == "getwindowgeometry":
                return GEOM, None
        if argv[0] == "xprop":
            return 'WM_CLASS(STRING) = "gedit", "Gedit"', None
        if argv[0] == "wmctrl":
            return "", None
        return "", None


@pytest.fixture
def x11(monkeypatch):
    fake = FakeX11()
    monkeypatch.setattr(windows.sys, "platform", "linux")
    monkeypatch.setattr(windows.shutil, "which", lambda n: "/usr/bin/" + n)
    monkeypatch.setattr(windows, "_run", fake)
    return fake


# --- reading the screens ---------------------------------------------


def test_screens_are_read_left_to_right(x11):
    """Order matters: "next" means the one to the right, which is what a
    person means when they look at their desk."""
    assert windows._x11_screens() == [
        (0, 1108, 1920, 1080),      # eDP-1, the laptop, sitting low
        (1920, 0, 1920, 1080),      # HDMI-1
        (3840, 0, 1080, 1920),      # DP-2, portrait
    ]


def test_a_disconnected_output_is_not_a_screen(x11):
    assert len(windows._x11_screens()) == 3


# --- reading the window -----------------------------------------------


def test_the_active_window_is_described(x11):
    fields, err = windows.current()
    assert err is None
    assert fields["title"] == "notes.txt - Text Editor"
    assert (fields["w"], fields["h"]) == (1200, 800)
    assert fields["screens"] == 3


def test_the_window_is_placed_on_the_screen_it_is_on(x11):
    """X=1950 is on HDMI-1, not the laptop. Snapping has to happen on the
    screen the window is already on -- moving it to another monitor because
    that one happens to be first is the worst possible answer."""
    fields, _ = windows.current()
    assert fields["screen"] == 1


# --- the arithmetic ---------------------------------------------------


def _wmctrl_geometry(fake):
    for argv in fake.calls:
        if argv[0] == "wmctrl" and "-e" in argv:
            return argv[argv.index("-e") + 1]
    return None


def test_left_is_half_of_the_screen_the_window_is_on(x11):
    ok, err = windows.place("left")
    assert ok and err is None
    # HDMI-1 is 1920 wide at x=1920, so its left half starts there.
    assert _wmctrl_geometry(x11) == "0,1920,0,960,1080"


def test_right_is_the_other_half(x11):
    windows.place("right")
    assert _wmctrl_geometry(x11) == "0,2880,0,960,1080"


def test_full_is_the_whole_of_that_screen_only(x11):
    windows.place("full")
    assert _wmctrl_geometry(x11) == "0,1920,0,1920,1080"


def test_next_moves_to_the_following_screen_and_fills_it(x11):
    windows.place("next")
    # From HDMI-1 to DP-2, the portrait one at x=3840.
    assert _wmctrl_geometry(x11) == "0,3840,0,1080,1920"


def test_next_wraps_round(x11, monkeypatch):
    geom = GEOM.replace("X=1950", "X=3900")        # already on the last
    monkeypatch.setattr(windows, "_run", FakeX11(
        **{"xdotool getwindowgeometry": (geom, None)}))
    windows.place("next")
    assert _wmctrl_geometry(windows._run) == "0,0,1108,1920,1080"


def test_a_maximised_window_is_unmaximised_first(x11):
    """wmctrl -e is ignored outright on a maximised window, which reads as a
    tile that does nothing on exactly the windows somebody most wants to
    move."""
    windows.place("left")
    assert any(argv[0] == "wmctrl" and "remove,maximized_vert,maximized_horz"
               in argv for argv in x11.calls)


def test_nowhere_called_that(x11):
    assert windows.place("sideways") == (False, "nowhere called 'sideways'")


# --- the tools have to be there ---------------------------------------


def test_a_missing_tool_is_named(monkeypatch):
    monkeypatch.setattr(windows.sys, "platform", "linux")
    monkeypatch.setattr(windows.shutil, "which",
                        lambda n: None if n == "wmctrl" else "/usr/bin/" + n)
    _, err = windows.current()
    assert "wmctrl" in err


# --- macOS: correct or refuse -----------------------------------------


def test_macos_refuses_to_snap_across_several_displays(monkeypatch):
    """Finder reports ONE rectangle spanning every monitor -- 0,0,4920,2188
    on a three-screen desk -- and AppleScript offers no per-display bounds.
    Half of that rectangle lands across two screens, so this refuses rather
    than being confidently wrong."""
    monkeypatch.setattr(windows.sys, "platform", "darwin")
    monkeypatch.setattr(windows, "_mac_displays", lambda: 3)
    ok, err = windows.place("left")
    assert not ok
    assert "3 displays" in err


def test_macos_snaps_happily_on_one_display(monkeypatch):
    monkeypatch.setattr(windows.sys, "platform", "darwin")
    monkeypatch.setattr(windows, "_mac_displays", lambda: 1)
    monkeypatch.setattr(windows, "_mac_screen", lambda: (0, 0, 1800, 1100))
    sent = []
    monkeypatch.setattr(windows, "_osa",
                        lambda s: (sent.append(s) or ("", None)))
    ok, err = windows.place("right")
    assert ok and err is None
    assert "900" in sent[-1]


def test_the_accessibility_refusal_is_short_enough_for_a_row(monkeypatch):
    """A row value is eighteen characters. "Allow Overwatch under System
    Settings > Privacy & Security > Accessibility" is not, and the first
    version of this was truncated to "Allow Overwatch u..." on the glass."""
    monkeypatch.setattr(windows.sys, "platform", "darwin")
    monkeypatch.setattr(windows, "_osa",
                        lambda s: (None, "Accessibility off"))
    _, err = windows.current()
    assert err == "Accessibility off"
    assert len(err) <= 18


# --- the panel --------------------------------------------------------


def test_the_panel_names_the_window_and_offers_four_places(x11):
    p = window_panel.build()
    assert p.tiles == ["Left", "Right", "Full", "Next"]
    # The application, from WM_CLASS -- not the whole document title, which
    # is 23 characters against a row's 18 and would arrive truncated.
    assert any(r.label == "Window" and r.value == "Gedit" for r in p.rows)
    assert any(r.label == "Title" for r in p.rows)
    assert any(r.label == "Screen" and r.value == "2 of 3" for r in p.rows)


def test_a_problem_gets_a_second_row_saying_where_to_fix_it(monkeypatch):
    monkeypatch.setattr(windows, "current",
                        lambda: (None, "Accessibility off"))
    p = window_panel.build()
    assert [r.value for r in p.rows] == ["Accessibility off",
                                         "Device Control"]
    assert p.tiles == [], "no point offering tiles that cannot work"


def test_a_tap_maps_to_the_place_the_tile_shows(monkeypatch):
    asked = []
    monkeypatch.setattr(windows, "place",
                        lambda w: (asked.append(w) or (True, None)))
    for i, want in enumerate(windows.PLACES):
        window_panel.on_tap(i)
    assert asked == list(windows.PLACES)


def test_a_tap_outside_the_tiles_does_nothing(monkeypatch):
    asked = []
    monkeypatch.setattr(windows, "place",
                        lambda w: (asked.append(w) or (True, None)))
    window_panel.on_tap(9)
    window_panel.on_tap(-1)
    assert asked == []
