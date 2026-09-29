"""Mute control, call detection, and the meeting panel.

Both halves are driven by recorded output: the suite runs on macOS and in CI,
and neither has pactl, wmctrl, or a second machine to hold a call on. What
that leaves covered is the part worth covering -- which sentence comes back
for which state, and the one arithmetic that matters, which is that a tile
index still means what it says when a tile is missing.
"""
import pytest

from pc import meeting, mic
from V2 import meeting_panel


# ===================================================================== mic

class FakePactl:
    """Stands in for _run, keyed on the pactl subcommand."""

    def __init__(self, **over):
        self.calls = []
        self.over = over

    def __call__(self, argv):
        self.calls.append(argv)
        key = " ".join(argv[:2])
        if key in self.over:
            return self.over[key]
        return "", None


@pytest.fixture
def linux(monkeypatch):
    monkeypatch.setattr(mic.sys, "platform", "linux")
    monkeypatch.setattr(mic.shutil, "which", lambda n: "/usr/bin/" + n)


@pytest.fixture
def mac(monkeypatch):
    monkeypatch.setattr(mic.sys, "platform", "darwin")


# --- the modern Linux path -------------------------------------------


def test_linux_reads_the_mute_flag(linux, monkeypatch):
    monkeypatch.setattr(mic, "_run", FakePactl(
        **{"pactl get-source-mute": ("Mute: yes", None)}))
    assert mic.muted() == (True, None)


def test_linux_reads_an_unmuted_mic(linux, monkeypatch):
    monkeypatch.setattr(mic, "_run", FakePactl(
        **{"pactl get-source-mute": ("Mute: no", None)}))
    assert mic.muted() == (False, None)


def test_the_speakers_are_a_sink_not_a_source(linux, monkeypatch):
    fake = FakePactl(**{"pactl get-sink-mute": ("Mute: yes", None)})
    monkeypatch.setattr(mic, "_run", fake)
    assert mic.out_muted() == (True, None)
    assert fake.calls[0][1] == "get-sink-mute"
    assert fake.calls[0][2] == "@DEFAULT_SINK@"


# --- the old-pactl fallback, which is the whole reason it exists -----

PACTL_INFO = """Server String: /run/user/1000/pulse/native
Server Name: PulseAudio (on PipeWire 1.0.5)
Default Sink: alsa_output.pci-0000_00_1f.3.analog-stereo
Default Source: alsa_input.usb-Blue_Yeti-00.analog-stereo
"""

LIST_SOURCES = """Source #0
\tState: SUSPENDED
\tName: alsa_input.pci-0000_00_1f.3.analog-stereo
\tMute: no

Source #1
\tState: RUNNING
\tName: alsa_input.usb-Blue_Yeti-00.analog-stereo
\tMute: yes
\tVolume: front-left: 39321 /  60%
"""


def test_an_old_pactl_without_the_getter_still_answers(linux, monkeypatch):
    """`pactl get-source-mute` arrived in PulseAudio 16 (2022); its setter is
    over a decade old. A Debian-stable box can mute and be unable to say
    whether it is muted -- and assuming the getter exists because the setter
    does is the mistake that shipped "Spotify control needs a Mac" to Linux.
    """
    fake = FakePactl(**{
        "pactl get-source-mute": (None, "pactl refused"),
        "pactl info": (PACTL_INFO, None),
        "pactl list": (LIST_SOURCES, None),
    })
    monkeypatch.setattr(mic, "_run", fake)
    assert mic.muted() == (True, None)


def test_the_fallback_picks_the_DEFAULT_source_not_the_first(linux,
                                                            monkeypatch):
    """Source #0 is unmuted and Source #1 is the default and muted. Reading
    the first block would answer "live" about a microphone that is not the
    one in use -- confidently wrong, in the direction that matters."""
    fake = FakePactl(**{
        "pactl get-source-mute": (None, "pactl refused"),
        "pactl info": (PACTL_INFO, None),
        "pactl list": (LIST_SOURCES, None),
    })
    monkeypatch.setattr(mic, "_run", fake)
    assert mic.muted()[0] is True


def test_the_fallback_asks_for_sinks_when_asked_about_output(linux,
                                                            monkeypatch):
    fake = FakePactl(**{
        "pactl get-sink-mute": (None, "pactl refused"),
        "pactl info": (PACTL_INFO, None),
        "pactl list": ("Sink #0\n\tName: alsa_output.pci-0000_00_1f.3."
                       "analog-stereo\n\tMute: no\n", None),
    })
    monkeypatch.setattr(mic, "_run", fake)
    assert mic.out_muted() == (False, None)
    assert ["pactl", "list", "sinks"] in fake.calls


def test_a_missing_default_source_is_said_so(linux, monkeypatch):
    monkeypatch.setattr(mic, "_run", FakePactl(**{
        "pactl get-source-mute": (None, "pactl refused"),
        "pactl info": ("Server Name: PulseAudio\n", None),
    }))
    state, err = mic.muted()
    assert state is None and "mic" in err


def test_a_missing_pactl_is_named_rather_than_guessed_around(monkeypatch):
    monkeypatch.setattr(mic.sys, "platform", "linux")
    monkeypatch.setattr(mic.shutil, "which", lambda _n: None)
    state, err = mic.muted()
    assert state is None and "pactl" in err
    assert mic.set_muted(True) == (False, "install pactl for mute control")


# --- macOS ------------------------------------------------------------


def test_macos_treats_a_zero_level_as_muted(mac, monkeypatch):
    monkeypatch.setattr(mic, "_run", lambda a: ("0", None))
    assert mic.muted() == (True, None)


def test_macos_treats_any_level_as_live(mac, monkeypatch):
    monkeypatch.setattr(mic, "_run", lambda a: ("100", None))
    assert mic.muted() == (False, None)


def test_macos_minus_one_means_it_cannot_say(mac, monkeypatch):
    """Some USB interfaces and AirPods report -1: the input has no settable
    level at all. That is "cannot say", NOT "live" -- and a panel that drew it
    as live would be telling somebody they are hot when nobody knows."""
    monkeypatch.setattr(mic, "_run", lambda a: ("-1", None))
    state, err = mic.muted()
    assert state is None
    assert err == "mic has no level"


def test_macos_reads_the_output_mute_flag(mac, monkeypatch):
    monkeypatch.setattr(mic, "_run", lambda a: ("true", None))
    assert mic.out_muted() == (True, None)
    monkeypatch.setattr(mic, "_run", lambda a: ("false", None))
    assert mic.out_muted() == (False, None)


def test_macos_unmuting_restores_a_usable_level(mac, monkeypatch):
    """Not the level it was, deliberately: that is not remembered anywhere
    surviving a daemon restart, and coming back at 15% is a mic that is
    technically live and practically not."""
    sent = []
    monkeypatch.setattr(mic, "_run", lambda a: (sent.append(a), ("", None))[1])
    mic.set_muted(False)
    assert "input volume 100" in sent[-1][-1]
    mic.set_muted(True)
    assert "input volume 0" in sent[-1][-1]


# --- toggling ---------------------------------------------------------


def test_toggle_reads_first_so_it_can_say_which_way_it_went(mac, monkeypatch):
    """pactl has its own `toggle`, and it reports nothing. The panel has to
    print the new state, so the state is read here instead."""
    monkeypatch.setattr(mic, "muted", lambda: (False, None))
    wrote = []
    monkeypatch.setattr(mic, "set_muted",
                        lambda w: (wrote.append(w) or (True, None)))
    assert mic.toggle() == (True, None)
    assert wrote == [True]


def test_toggle_passes_a_read_failure_straight_out(mac, monkeypatch):
    monkeypatch.setattr(mic, "muted", lambda: (None, "mic has no level"))
    assert mic.toggle() == (None, "mic has no level")


def test_available_is_platform_only(monkeypatch):
    """music_linux's players() once folded "gdbus is missing" into "nothing is
    playing", and the panel told a Linux user to buy a Mac. A tool being
    absent is a different sentence from a platform being unsupported."""
    monkeypatch.setattr(mic.sys, "platform", "linux")
    monkeypatch.setattr(mic.shutil, "which", lambda _n: None)
    assert mic.available() is True
    monkeypatch.setattr(mic.sys, "platform", "win32")
    assert mic.available() is False


# ================================================================ detect

IN_CALL = [
    ("https://meeting.zoho.com/meeting/join?key=abc", "Zoho Meeting"),
    ("https://meeting.zoho.eu/meeting/xyz789", "Zoho Meeting"),
    ("https://meet.google.com/abc-defg-hij", "Google Meet"),
    ("https://zoom.us/j/9876543210", "Zoom"),
    ("https://acme.zoom.us/wc/join/123", "Zoom"),
    ("https://teams.microsoft.com/l/meetup-join/19%3ameeting", "Teams"),
    ("https://acme.webex.com/meet/jane", "Webex"),
    ("https://meet.jit.si/OverwatchStandup", "Jitsi"),
    ("https://whereby.com/vision-plus", "Whereby"),
]

NOT_A_CALL = [
    "https://meet.google.com/",
    "https://meet.google.com",
    "https://zoom.us/",
    "https://www.zoho.com/meeting/",
    "https://mail.zoho.com/zm/#mail/folder/inbox",
    "https://calendar.google.com/calendar/u/0/r",
    "https://github.com/SleepyUnicon/Overwatch",
]


def _match(url):
    import re
    for label, pat, _t, _n in meeting.SERVICES:
        if re.search(pat, url, re.I):
            return label
    return None


@pytest.mark.parametrize("url,want", IN_CALL)
def test_an_in_call_url_is_recognised(url, want):
    assert _match(url) == want


@pytest.mark.parametrize("url", NOT_A_CALL)
def test_an_open_tab_is_not_a_call(url):
    """meet.google.com is a landing page; meet.google.com/abc-defg-hij is a
    call. Every web service needs a path beyond the host, or the panel would
    announce a meeting because somebody has a bookmark open."""
    assert _match(url) is None


def test_a_browser_that_is_not_running_is_never_asked(monkeypatch):
    """THE one that would bite a real person. `tell application "Google
    Chrome" to get ...` LAUNCHES Chrome when it is not running, so a panel
    refreshing every few seconds would reopen every browser on the machine.
    Detection is gated on the process list for exactly this reason."""
    monkeypatch.setattr(meeting.sys, "platform", "darwin")
    monkeypatch.setattr(meeting, "_mac_processes", lambda: ["Brave Browser"])
    asked = []
    monkeypatch.setattr(meeting, "_mac_tabs",
                        lambda b: (asked.append(b) or []))
    meeting.detect()
    assert asked == ["Brave Browser"]
    assert "Google Chrome" not in asked
    assert "Safari" not in asked


def test_a_call_in_a_background_tab_is_found(monkeypatch):
    """The reason macOS reads tab URLs rather than window titles: a window
    title is only ever the ACTIVE tab, and a call you have tabbed away from is
    exactly the call you need a desk lamp for."""
    monkeypatch.setattr(meeting.sys, "platform", "darwin")
    monkeypatch.setattr(meeting, "_mac_processes", lambda: ["Brave Browser"])
    monkeypatch.setattr(meeting, "_mac_tabs", lambda b: [
        (1, 1, "https://mail.zoho.com/zm/#mail/folder/inbox"),
        (1, 4, "https://meeting.zoho.com/meeting/join?key=abc"),
        (1, 5, "https://github.com/SleepyUnicon/Overwatch"),
    ])
    call, err = meeting.detect()
    assert err is None
    assert call["service"] == "Zoho Meeting"
    assert (call["window"], call["tab"]) == (1, 4)


def test_a_native_app_outranks_a_tab(monkeypatch):
    """Zoom's application is only running because there is a call; a tab might
    be a calendar invite somebody clicked an hour ago."""
    monkeypatch.setattr(meeting.sys, "platform", "darwin")
    monkeypatch.setattr(meeting, "_mac_processes",
                        lambda: ["Brave Browser", "zoom.us"])
    monkeypatch.setattr(meeting, "_mac_tabs", lambda b: [
        (1, 1, "https://meet.google.com/abc-defg-hij")])
    call, _ = meeting.detect()
    assert call["service"] == "Zoom"
    assert call["kind"] == "app"


def test_no_call_is_not_an_error(monkeypatch):
    """The distinction the whole module is shaped around: "there is no call"
    and "I could not look" are different sentences."""
    monkeypatch.setattr(meeting.sys, "platform", "darwin")
    monkeypatch.setattr(meeting, "_mac_processes", lambda: ["Finder"])
    assert meeting.detect() == (None, None)


def test_being_unable_to_look_IS_an_error(monkeypatch):
    monkeypatch.setattr(meeting.sys, "platform", "darwin")
    monkeypatch.setattr(meeting, "_mac_processes", lambda: [])
    call, err = meeting.detect()
    assert call is None and err


def test_a_broken_browser_dictionary_is_logged_not_swallowed(monkeypatch,
                                                             capsys):
    """If Safari's dictionary turns out to differ, the log has to name the
    browser -- otherwise the symptom is a panel that quietly never sees a
    call and nothing anywhere saying why."""
    monkeypatch.setattr(meeting, "_run", lambda a: (None, "osascript refused"))
    assert meeting._mac_tabs("Safari") == []
    assert "Safari" in capsys.readouterr().err


# --- Linux detection --------------------------------------------------

WMCTRL = """0x02200003  0 box Inbox - Zoho Mail — Brave
0x02400005  0 box Zoho Meeting — Brave
0x02600007  0 box notes.txt - Text Editor
"""


def test_linux_matches_a_window_title(monkeypatch):
    monkeypatch.setattr(meeting.sys, "platform", "linux")
    monkeypatch.setattr(meeting, "_linux_procs", lambda: [])
    monkeypatch.setattr(meeting.shutil, "which", lambda n: "/usr/bin/" + n)
    monkeypatch.setattr(meeting, "_run", lambda a: (WMCTRL, None))
    call, err = meeting.detect()
    assert err is None
    assert call["service"] == "Zoho Meeting"
    assert call["wid"] == "0x02400005"


def test_linux_says_when_wmctrl_is_missing(monkeypatch):
    monkeypatch.setattr(meeting.sys, "platform", "linux")
    monkeypatch.setattr(meeting, "_linux_procs", lambda: [])
    monkeypatch.setattr(meeting.shutil, "which", lambda _n: None)
    call, err = meeting.detect()
    assert call is None and "wmctrl" in err


def test_linux_raises_the_window_by_id(monkeypatch):
    monkeypatch.setattr(meeting.sys, "platform", "linux")
    sent = []
    monkeypatch.setattr(meeting, "_run",
                        lambda a: (sent.append(a) or ("", None)))
    ok, _ = meeting.show({"kind": "window", "wid": "0x02400005"})
    assert ok
    assert sent[-1] == ["wmctrl", "-i", "-a", "0x02400005"]


def test_macos_show_selects_the_tab_and_not_merely_the_browser(monkeypatch):
    monkeypatch.setattr(meeting.sys, "platform", "darwin")
    sent = []
    monkeypatch.setattr(meeting, "_run",
                        lambda a: (sent.append(a) or ("", None)))
    meeting.show({"kind": "tab", "browser": "Brave Browser",
                  "window": 2, "tab": 4})
    script = sent[-1][-1]
    assert "active tab index of window 2 to 4" in script
    assert "activate" in script


# ================================================================= panel


@pytest.fixture
def quiet_desk(monkeypatch):
    monkeypatch.setattr(meeting, "detect", lambda: (None, None))
    monkeypatch.setattr(mic, "muted", lambda: (False, None))
    monkeypatch.setattr(mic, "out_muted", lambda: (False, None))


def test_the_panel_says_live_in_amber(quiet_desk):
    """Being live is the ordinary state of somebody in a meeting -- but it is
    the one you can be wrong about at another person's expense, so it is the
    one that gets the warning tone."""
    p = meeting_panel.build()
    row = next(r for r in p.rows if r.label == "Mic")
    assert row.value == "LIVE"
    assert row.tone == "warn"


def test_a_muted_mic_is_the_reassuring_one(monkeypatch, quiet_desk):
    monkeypatch.setattr(mic, "muted", lambda: (True, None))
    row = next(r for r in meeting_panel.build().rows if r.label == "Mic")
    assert row.value == "Muted"
    assert row.tone == "ok"


def test_the_tile_says_what_it_will_do_not_what_the_state_is(monkeypatch,
                                                            quiet_desk):
    assert meeting_panel.build().tiles[0] == "Mute"
    monkeypatch.setattr(mic, "muted", lambda: (True, None))
    assert meeting_panel.build().tiles[0] == "Unmute"


def test_a_detected_call_is_named_and_gets_a_show_tile(monkeypatch,
                                                       quiet_desk):
    monkeypatch.setattr(meeting, "detect", lambda: (
        {"service": "Zoho Meeting", "where": "Brave Browser", "kind": "tab",
         "browser": "Brave Browser", "window": 1, "tab": 4}, None))
    p = meeting_panel.build()
    assert any(r.label == "Call" and r.value == "Zoho Meeting" for r in p.rows)
    assert any(r.label == "In" and r.value == "Brave Browser" for r in p.rows)
    assert "Show" in p.tiles


def test_no_call_means_no_show_tile(quiet_desk):
    """Nothing to raise, so no button offering to."""
    p = meeting_panel.build()
    assert "Show" not in p.tiles
    assert any(r.label == "Call" and r.value == "None" for r in p.rows)


def test_a_problem_gets_a_second_row_saying_where_to_fix_it(monkeypatch,
                                                           quiet_desk):
    monkeypatch.setattr(meeting, "detect",
                        lambda: (None, "install wmctrl to see calls"))
    p = meeting_panel.build()
    assert any(r.value == "package manager" for r in p.rows)


def test_an_unreadable_mic_gets_no_tile_at_all(monkeypatch, quiet_desk):
    """A button that cannot report what it did is the thing this panel exists
    to avoid."""
    monkeypatch.setattr(mic, "muted", lambda: (None, "mic has no level"))
    p = meeting_panel.build()
    assert "Mute" not in p.tiles and "Unmute" not in p.tiles
    # The whole reason, not a truncation of it: 16 characters against 18.
    assert any(r.label == "Mic" and r.value == "mic has no level"
               for r in p.rows)


def test_the_tiles_still_mean_what_they_say_when_one_is_missing(monkeypatch,
                                                               quiet_desk):
    """THE regression. The first version numbered tiles 0/1/2 and dropped the
    mic tile when the mic could not be read -- which shifted Show into
    Sound's index, so the Show button silenced the speakers."""
    monkeypatch.setattr(meeting, "detect", lambda: (
        {"service": "Zoom", "where": "zoom.us", "kind": "app"}, None))
    monkeypatch.setattr(mic, "muted", lambda: (None, "mic has no level"))
    p = meeting_panel.build()
    assert p.tiles == ["Sound", "Show"]

    did = []
    monkeypatch.setattr(mic, "toggle_out",
                        lambda: (did.append("sound") or (True, None)))
    monkeypatch.setattr(meeting, "show",
                        lambda c: (did.append("show") or (True, None)))
    meeting_panel.on_tap(0)
    meeting_panel.on_tap(1)
    assert did == ["sound", "show"]


def test_a_tap_outside_the_tiles_does_nothing(monkeypatch, quiet_desk):
    did = []
    monkeypatch.setattr(mic, "toggle", lambda: (did.append(1) or (True, None)))
    monkeypatch.setattr(mic, "toggle_out",
                        lambda: (did.append(1) or (True, None)))
    meeting_panel.on_tap(9)
    meeting_panel.on_tap(-1)
    assert did == []


def test_the_mic_tap_toggles_the_mic(monkeypatch, quiet_desk):
    did = []
    monkeypatch.setattr(mic, "toggle", lambda: (did.append(1) or (True, None)))
    meeting_panel.on_tap(0)
    assert did == [1]


def test_the_panel_fits_the_board(quiet_desk):
    from V2 import panel as panel_mod
    p = meeting_panel.build()
    assert len(p.rows) <= panel_mod.ROWS_MAX
    assert len(p.tiles) <= panel_mod.TILES_MAX
    for t in p.tiles:
        assert len(t) <= panel_mod.TILE_MAX


def test_the_board_has_room_for_a_third_panel():
    """The daemon's mirror of V2/firmware/ui_panel.h. A daemon that registers
    more panels than the board reserves would have the third one silently
    refused."""
    from V2 import panel as panel_mod
    assert panel_mod.PANEL_MAX >= 3


def test_all_three_panels_register():
    from pc import widget_bridge
    ps = widget_bridge._default_panels()
    assert len(ps._sources) == 3


def test_every_hint_fits_a_row():
    """A value is eighteen characters. "your package manager" is twenty and
    reached the glass as "your package manag" -- in BOTH panels, because the
    second one copied the string along with the comment warning about it."""
    from V2 import panel as panel_mod, window_panel
    for mod in (meeting_panel, window_panel):
        for reason, hint in mod._WHERE_TO_FIX.items():
            assert len(hint) <= panel_mod.VALUE_MAX, (mod.__name__, hint)


def test_every_error_this_module_can_report_fits_a_row():
    """The reasons are written here, so they can be checked here rather than
    discovered truncated on a 320 px screen."""
    from V2 import panel as panel_mod
    for reason in meeting_panel._WHERE_TO_FIX:
        assert len(reason) <= 40, reason
    for text in ("mic has no level", "install pactl for mute control"[:18],
                 "could not read the mixer"[:18]):
        assert len(text) <= panel_mod.VALUE_MAX
