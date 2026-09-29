"""Media control on Linux, through MPRIS.

Everything here is driven by recorded `gdbus` output rather than a session
bus: the suite runs on macOS and in CI, and neither has an MPRIS player. What
that buys is coverage of the PARSING, which is the part most likely to be
wrong -- gdbus prints GVariant text, not JSON, and players disagree about the
details within it.

What it does not buy is proof that the command lines are right. That needs a
real desktop.
"""
from pc import music, music_linux

# What `gdbus call ... ListNames` really returns: one GVariant tuple holding
# an array, with the unique ":1.n" names mixed in among the well-known ones.
LIST = ("(['org.freedesktop.DBus', ':1.7', 'org.mpris.MediaPlayer2.spotify',"
        " ':1.42', 'org.mpris.MediaPlayer2.firefox.instance_1_23',"
        " 'org.gnome.Shell'],)")

# A GetAll reply. mpris:length is uint64 here and int64 elsewhere -- both are
# in the wild, which is why the number pattern does not insist on one.
PLAYING = ("({'CanQuit': <true>, 'PlaybackStatus': <'Playing'>,"
           " 'Position': <int64 65000000>,"
           " 'Metadata': <{'mpris:trackid':"
           " <objectpath '/org/mpris/MediaPlayer2/Track/1'>,"
           " 'mpris:length': <uint64 245000000>,"
           " 'xesam:title': <'Make Them Know'>,"
           " 'xesam:artist': <['Drake', 'Another']>,"
           " 'xesam:album': <'Some Album'>}>, 'CanGoNext': <true>},)")

PAUSED = ("({'PlaybackStatus': <'Paused'>, 'Position': <int64 3000000>,"
          " 'Metadata': <{'mpris:length': <int64 180000000>,"
          " 'xesam:title': <'Quiet One'>,"
          " 'xesam:artist': <['Someone']>}>},)")

STOPPED = "({'PlaybackStatus': <'Stopped'>, 'Metadata': <{}>},)"


class FakeGdbus:
    """Stands in for the subprocess, keyed on the --dest argument."""

    def __init__(self, names=LIST, replies=None, fail=()):
        self.names = names
        self.replies = replies or {}
        self.fail = set(fail)
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        dest = args[args.index("--dest") + 1]
        if dest in self.fail:
            return None, "The player did not answer"
        if dest == "org.freedesktop.DBus":
            return self.names, None
        if "--method" in args:
            method = args[args.index("--method") + 1]
            if method.endswith(("PlayPause", "Next", "Previous")):
                return "()", None
        return self.replies.get(dest, STOPPED), None


def _patch(monkeypatch, fake):
    monkeypatch.setattr(music_linux, "_gdbus", fake)


# --- the GVariant extractors ------------------------------------------


def test_a_quoted_string_is_read():
    assert music_linux._quoted(PLAYING, "PlaybackStatus") == "Playing"
    assert music_linux._quoted(PLAYING, "xesam:title") == "Make Them Know"


def test_an_apostrophe_in_a_title_survives():
    """Escaped by gdbus, and a great many tracks have one."""
    blob = r"({'xesam:title': <'Don\'t Stop'>},)"
    assert music_linux._quoted(blob, "xesam:title") == "Don't Stop"


def test_the_first_artist_of_the_array_is_taken():
    """xesam:artist is an ARRAY. The panel has 28 characters; the first name
    is what fits and what a person would have said."""
    assert music_linux._first_of_list(PLAYING, "xesam:artist") == "Drake"


def test_a_number_is_read_whatever_its_type_tag():
    assert music_linux._number(PLAYING, "mpris:length") == 245000000
    assert music_linux._number(PLAYING, "Position") == 65000000
    assert music_linux._number(PAUSED, "mpris:length") == 180000000


def test_a_missing_key_is_none_rather_than_an_error():
    """A player with an odd metadata dict should cost its title, never the
    whole page."""
    assert music_linux._quoted(STOPPED, "xesam:title") is None
    assert music_linux._first_of_list(STOPPED, "xesam:artist") is None
    assert music_linux._number(STOPPED, "mpris:length") is None


# --- discovery --------------------------------------------------------


def test_only_mpris_names_are_players(monkeypatch):
    _patch(monkeypatch, FakeGdbus())
    names, err = music_linux.players()
    assert err is None
    assert names == [
        "org.mpris.MediaPlayer2.spotify",
        "org.mpris.MediaPlayer2.firefox.instance_1_23",
    ]


def test_a_bus_with_no_player_is_empty(monkeypatch):
    _patch(monkeypatch, FakeGdbus(names="(['org.freedesktop.DBus'],)"))
    assert music_linux.players() == ([], None)


# --- choosing between players ----------------------------------------


def test_a_playing_player_beats_a_paused_one(monkeypatch):
    """A desk with Spotify paused and a video running should show the video.

    Order on the bus is not meaningful, so the paused one is listed first here
    deliberately.
    """
    _patch(monkeypatch, FakeGdbus(replies={
        "org.mpris.MediaPlayer2.spotify": PAUSED,
        "org.mpris.MediaPlayer2.firefox.instance_1_23": PLAYING,
    }))
    fields, err = music_linux.read()
    assert err is None
    assert fields["player"].endswith("firefox.instance_1_23")
    assert fields["state"] == "playing"


def test_with_nothing_playing_the_remembered_player_is_kept(monkeypatch):
    """Or the page flickers between two paused players as the bus reorders
    them."""
    _patch(monkeypatch, FakeGdbus(replies={
        "org.mpris.MediaPlayer2.spotify": PAUSED,
        "org.mpris.MediaPlayer2.firefox.instance_1_23": PAUSED,
    }))
    fields, _ = music_linux.read(prefer="org.mpris.MediaPlayer2.spotify")
    assert fields["player"] == "org.mpris.MediaPlayer2.spotify"


def test_a_player_that_will_not_answer_is_skipped(monkeypatch):
    _patch(monkeypatch, FakeGdbus(
        replies={"org.mpris.MediaPlayer2.firefox.instance_1_23": PLAYING},
        fail={"org.mpris.MediaPlayer2.spotify"}))
    fields, _ = music_linux.read()
    assert fields is not None and fields["state"] == "playing"


def test_microseconds_become_seconds(monkeypatch):
    """MPRIS is microseconds; the panel draws seconds. A factor of a million
    is the kind of mistake that looks like a stuck progress bar."""
    _patch(monkeypatch, FakeGdbus(
        replies={"org.mpris.MediaPlayer2.spotify": PLAYING}))
    fields, _ = music_linux.read()
    assert fields["pos_s"] == 65
    assert fields["dur_s"] == 245


# --- commands ---------------------------------------------------------


def test_a_verb_goes_to_the_player_that_is_playing(monkeypatch):
    fake = FakeGdbus(replies={
        "org.mpris.MediaPlayer2.spotify": PAUSED,
        "org.mpris.MediaPlayer2.firefox.instance_1_23": PLAYING,
    })
    _patch(monkeypatch, fake)
    assert music_linux.command("play") is None
    sent = [c for c in fake.calls if "--method" in c
            and c[c.index("--method") + 1].endswith("PlayPause")]
    assert len(sent) == 1
    assert sent[0][sent[0].index("--dest") + 1].endswith("firefox.instance_1_23")


def test_the_three_verbs_map_to_mpris_methods(monkeypatch):
    for verb, method in (("play", "PlayPause"), ("next", "Next"),
                         ("prev", "Previous")):
        fake = FakeGdbus(replies={
            "org.mpris.MediaPlayer2.spotify": PLAYING})
        _patch(monkeypatch, fake)
        music_linux.command(verb)
        assert any(c[c.index("--method") + 1].endswith(method)
                   for c in fake.calls if "--method" in c), verb


def test_an_unknown_verb_does_nothing(monkeypatch):
    fake = FakeGdbus()
    _patch(monkeypatch, fake)
    assert music_linux.command("eject") is None
    assert not any("--method" in c
                   and c[c.index("--method") + 1].endswith(
                       ("PlayPause", "Next", "Previous"))
                   for c in fake.calls)


def test_a_verb_with_no_player_says_so(monkeypatch):
    _patch(monkeypatch, FakeGdbus(names="(['org.freedesktop.DBus'],)"))
    assert music_linux.command("play") == "No music player running"


# --- the widget, which the board actually talks to --------------------


def test_the_board_gets_the_same_message_shape_as_on_a_mac(monkeypatch):
    """ui_music.c and the protocol have nothing macOS-specific in them, and
    this is what keeps it that way."""
    _patch(monkeypatch, FakeGdbus(
        replies={"org.mpris.MediaPlayer2.spotify": PLAYING}))
    w = music.MusicWidget(linux=music_linux)
    msg = w.poll()
    assert msg["t"] == "track"
    assert msg["n"] == "Make Them Know"
    assert msg["a"] == "Drake"
    assert msg["st"] == 1
    assert msg["pos"] == 65 and msg["dur"] == 245


def test_a_paused_player_reports_stopped_not_missing(monkeypatch):
    _patch(monkeypatch, FakeGdbus(
        replies={"org.mpris.MediaPlayer2.spotify": PAUSED}))
    msg = music.MusicWidget(linux=music_linux).poll()
    assert msg["st"] == 0
    assert msg["n"] == "Quiet One"


def test_no_player_reads_the_same_as_it_does_on_a_mac(monkeypatch):
    _patch(monkeypatch, FakeGdbus(names="(['org.freedesktop.DBus'],)"))
    msg = music.MusicWidget(linux=music_linux).poll()
    assert msg["why"] == "No music player running"


def test_a_player_with_nothing_queued_is_named(monkeypatch):
    _patch(monkeypatch, FakeGdbus(
        replies={"org.mpris.MediaPlayer2.spotify": STOPPED}))
    msg = music.MusicWidget(linux=music_linux).poll()
    assert "Spotify" in msg["why"]


def test_a_bus_name_becomes_something_readable():
    assert music._pretty("org.mpris.MediaPlayer2.spotify") == "Spotify"
    assert music._pretty(
        "org.mpris.MediaPlayer2.firefox.instance_1_23") == "Firefox"
    assert music._pretty("") == "The player"


def test_a_mac_is_untouched_by_any_of_this(monkeypatch):
    """The AppleScript path must not change shape because a second one now
    exists beside it."""
    calls = []

    def osa(script):
        calls.append(script)
        return "closed", None

    w = music.MusicWidget(osa=osa, linux=None)
    assert w.poll()["why"] == "No music player running"
    assert calls, "the AppleScript path was not taken"


# --- the regression that sent a Linux user to buy a Mac ---------------


def test_the_backend_is_chosen_by_platform_alone(monkeypatch):
    """available() used to also run `gdbus --version` and demand a zero exit.

    That assumed a flag nobody had checked against a real gdbus -- and when
    the probe failed, pc/music.py fell through to the AppleScript path, so a
    Linux desktop was told "Spotify control needs a Mac". Wrong, and pointing
    at the wrong operating system.
    """
    monkeypatch.setattr(music_linux.sys, "platform", "linux")
    assert music_linux.available() is True
    monkeypatch.setattr(music_linux.sys, "platform", "darwin")
    assert music_linux.available() is False


def test_no_gdbus_says_install_gdbus_not_buy_a_mac(monkeypatch):
    """The sentence a Linux user gets when the tool is missing has to name the
    tool they are missing."""
    def no_gdbus(*args, **kw):
        raise FileNotFoundError("gdbus")

    monkeypatch.setattr(music_linux.subprocess, "run", no_gdbus)
    w = music.MusicWidget(linux=music_linux)
    why = w.poll().get("why", "")
    assert "gdbus" in why
    assert "Mac" not in why


def test_a_linux_widget_never_reaches_applescript(monkeypatch):
    """The structural version of the bug: whatever goes wrong on Linux, the
    macOS branch must not be the thing that answers."""
    called = []

    monkeypatch.setattr(music_linux.sys, "platform", "linux")
    w = music.MusicWidget(osa=lambda s: called.append(s) or ("closed", None))
    _patch(monkeypatch, FakeGdbus(names="(['org.freedesktop.DBus'],)"))
    msg = w.poll()
    assert not called, "the AppleScript path ran on Linux"
    assert msg["why"] == "No music player running"
