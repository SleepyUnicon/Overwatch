"""The transport widget's daemon half.

Every test injects `osa`, so nothing here talks to a real player or trips the
macOS Automation prompt on whoever runs the suite.
"""
from pc import protocol, music


def _w(out=None, err=None, log=None):
    def osa(script):
        if log is not None:
            log.append(script)
        return out, err
    return music.MusicWidget(osa=osa)


def _playing(name="Midnight Train", artist="Sauti Sol", pos="93", dur="241000",
             state="playing"):
    return "\n".join([state, name, artist, pos, dur])


# --- reading the player -------------------------------------------------

def test_a_playing_track_becomes_a_track_message():
    msg = _w(out=_playing()).poll()
    assert msg["n"] == "Midnight Train" and msg["a"] == "Sauti Sol"
    assert msg["st"] == 1 and msg["pos"] == 93 and msg["dur"] == 241


def test_paused_is_reported_as_paused_not_absent():
    assert _w(out=_playing(state="paused")).poll()["st"] == 0


def test_duration_in_milliseconds_is_converted():
    """Spotify's duration is ms while player position is seconds."""
    assert _w(out=_playing(dur="241000")).poll()["dur"] == 241


def test_duration_already_in_seconds_is_left_alone():
    """The range check cannot pick wrong: the two ranges do not overlap."""
    assert _w(out=_playing(dur="241")).poll()["dur"] == 241


def test_a_zero_or_junk_duration_is_unknown_not_zero():
    assert _w(out=_playing(dur="0")).poll()["dur"] == -1
    assert _w(out=_playing(dur="")).poll()["dur"] == -1


def test_long_names_are_cut_to_what_the_panel_draws():
    msg = _w(out=_playing(name="A" * 80, artist="B" * 80)).poll()
    assert len(msg["n"]) <= music.TEXT_MAX
    assert len(msg["a"]) <= music.TEXT_MAX


# --- the three ways it can be unavailable --------------------------------

def test_a_player_with_nothing_queued_says_so():
    assert "nothing queued" in _w(out="idle").poll()["why"]





def test_a_denied_automation_prompt_names_the_cure():
    """-1743 is a trip to System Settings, not a broken widget."""
    msg = _w(err="Allow Overwatch to control music in Settings").poll()
    assert "Settings" in msg["why"]


def test_a_short_reply_is_refused_rather_than_half_parsed():
    assert "why" in _w(out="playing\nonly two").poll()


def test_the_reason_fits_what_the_board_keeps():
    msg = _w(err="x" * 200).poll()
    assert len(msg["why"]) <= 47


# --- the rule the whole widget rests on ----------------------------------

def test_no_read_script_ever_launches_a_player():
    """A bare `tell application "X"` STARTS X. A board plugged in at
    breakfast must not begin playing music - for ANY player it knows."""
    for name in music.PLAYERS:
        assert 'application "%s" is running' % name in music._READ_TMPL % (name, name)


def test_it_falls_through_to_the_next_player():
    """Spotify shut, Music playing: the panel shows Music."""
    def osa(script):
        if "Spotify" in script:
            return ("closed", None)
        return ("playing\nKuliko Jana\nSauti Sol\n41\n254", None)
    msg = music.MusicWidget(osa=osa).poll()
    assert msg["n"] == "Kuliko Jana" and msg["dur"] == 254


def test_with_nothing_running_it_says_so():
    assert music.MusicWidget(osa=lambda s: ("closed", None)).poll()["why"] \
        == "No music player running"


def test_the_answering_player_is_tried_first_next_time():
    """Otherwise a machine with two players flips between them between polls,
    and a command lands on the one the panel is not showing."""
    seen = []
    def osa(script):
        seen.append(script)
        return ("closed", None) if "Spotify" in script else ("idle", None)
    w = music.MusicWidget(osa=osa)
    w.poll(); seen.clear(); w.poll()
    assert "Music" in seen[0]


def test_unavailable_carries_no_track_fields():
    """So the board cannot draw a stale name beside a fresh error."""
    msg = _w(out="closed").poll()
    assert "n" not in msg and "a" not in msg and "st" not in msg


# --- commands ------------------------------------------------------------

def test_each_button_runs_its_own_verb():
    for cmd, verb in [("play", "playpause"), ("next", "next track"),
                      ("prev", "previous track")]:
        log = []
        _w(out="", log=log).on_command({"t": "music", "cmd": cmd})
        assert log and verb in log[0], cmd


def test_an_unknown_verb_runs_nothing():
    log = []
    _w(out="", log=log).on_command({"t": "music", "cmd": "selfdestruct"})
    _w(out="", log=log).on_command({"t": "music"})
    assert log == []


def test_a_command_is_answered_by_the_next_poll_not_an_ack():
    assert _w(out="").on_command({"t": "music", "cmd": "play"}) is None


# --- the wire ------------------------------------------------------------

def test_the_widest_track_message_fits_the_board_line_limit():
    msg = _w(out=_playing(name="A" * 80, artist="B" * 80)).poll()
    raw, err = protocol.encode_checked(msg)
    assert raw is not None, err
    assert len(raw) <= protocol.MAX_LINE_BYTES


def test_a_board_line_round_trips_into_a_command():
    line = '{"t":"music","v":2,"cmd":"next"}'
    msg = protocol.decode(line)
    w = _w(out="")
    assert w.handles(msg) and msg["cmd"] == "next"
