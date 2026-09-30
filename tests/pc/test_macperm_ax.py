"""Accessibility: detecting it, and telling a loss from a never-had.

Accessibility is not Automation and is worse in two ways. macOS never prompts
for it, so a missing grant is silent. And it does not survive an update:

    $ codesign -d -r- ~/.overwatch/bin/overwatch
    # designated => cdhash H"40cb6c2b4aae6e125a537afb9f2e24d70d3b3acc"

That is the entire designated requirement of an ad-hoc signature -- a content
hash. TCC records the grant against it, so a new build is a different program
and the grant matches nothing. Measured on the owner's Mac, 2026-09-30.

None of this is fixable here; a stable requirement needs a signing identity.
What is fixable is the silence, which twice looked like a broken feature.
"""
import json

import pytest

from pc import macperm


class R:
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


@pytest.fixture
def mac(monkeypatch):
    monkeypatch.setattr(macperm.sys, "platform", "darwin")


# --- the probe --------------------------------------------------------


def test_true_means_granted(mac):
    assert macperm.ax_check(run=lambda *a, **k: R(0, "true\n")) == (True, None)


def test_false_means_denied(mac):
    assert macperm.ax_check(run=lambda *a, **k: R(0, "false\n")) == (False,
                                                                    "denied")


def test_a_failed_probe_is_unknown_not_denied(mac):
    """`UI elements enabled` needs Automation to ask at all. No Automation is
    a different problem with a different cure, and answering the wrong one is
    how this project once told a Linux user to buy a Mac."""
    got = macperm.ax_check(run=lambda *a, **k: R(1, "", "not authorized (-1743)"))
    assert got == (False, "unknown")


def test_anything_unrecognised_is_unknown(mac):
    assert macperm.ax_check(run=lambda *a, **k: R(0, "maybe"))[1] == "unknown"


def test_a_missing_osascript_does_not_raise(mac):
    def boom(*a, **k):
        raise OSError("nope")
    assert macperm.ax_check(run=boom) == (False, "unknown")


def test_off_mac_there_is_nothing_to_grant(monkeypatch):
    """Not a problem to report on Linux or Windows -- there is no such
    permission there, and a warning about one would send somebody looking for
    a setting that does not exist."""
    monkeypatch.setattr(macperm.sys, "platform", "linux")
    assert macperm.ax_check() == (True, None)


# --- remembering ------------------------------------------------------


def test_nothing_is_known_before_the_first_look(tmp_path):
    assert macperm.ax_last_known(str(tmp_path)) is None


def test_the_first_look_reports_no_change(tmp_path):
    """There is nothing to have changed from."""
    assert macperm.ax_note(True, str(tmp_path)) is None


def test_losing_it_is_called_losing_it(tmp_path):
    d = str(tmp_path)
    macperm.ax_note(True, d)
    assert macperm.ax_note(False, d) == "lost"


def test_gaining_it_is_reported_too(tmp_path):
    d = str(tmp_path)
    macperm.ax_note(False, d)
    assert macperm.ax_note(True, d) == "gained"


def test_no_change_is_silent(tmp_path):
    d = str(tmp_path)
    macperm.ax_note(True, d)
    assert macperm.ax_note(True, d) is None
    assert macperm.ax_note(True, d) is None


def test_the_answer_survives_the_process(tmp_path):
    d = str(tmp_path)
    macperm.ax_note(True, d)
    assert macperm.ax_last_known(d) is True


def test_a_corrupt_file_reads_as_never_looked(tmp_path):
    """A half-written file must not be read as "you had it", which would turn
    the next check into a false "LOST"."""
    p = tmp_path / macperm.AX_STATE
    p.write_text("{not json", encoding="utf-8")
    assert macperm.ax_last_known(str(tmp_path)) is None
    assert macperm.ax_note(False, str(tmp_path)) is None


def test_a_file_with_the_wrong_shape_reads_as_never_looked(tmp_path):
    p = tmp_path / macperm.AX_STATE
    p.write_text(json.dumps({"granted": "yes please"}), encoding="utf-8")
    assert macperm.ax_last_known(str(tmp_path)) is None


def test_an_unwritable_home_does_not_raise(tmp_path, monkeypatch):
    """Not being able to remember is not worth failing a status command
    over."""
    monkeypatch.setattr(macperm.os, "makedirs",
                        lambda *a, **k: (_ for _ in ()).throw(OSError()))
    assert macperm.ax_note(True, str(tmp_path)) is None


def test_the_path_is_resolved_per_call_not_at_import(tmp_path, monkeypatch):
    """The rule the rest of pc/ follows: a module-level expanduser is read
    once, and a test that sets HOME afterwards talks to the wrong file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert str(tmp_path) in macperm._ax_path()


# --- what it says -----------------------------------------------------


def test_the_denial_names_where_to_fix_it():
    msg = macperm.ax_explain("denied")
    assert "System Settings" in msg and "Accessibility" in msg


def test_an_unknown_state_points_at_automation_instead():
    """Because that is the one that actually has to be fixed first."""
    msg = macperm.ax_explain("unknown")
    assert "Automation" in msg


def test_the_loss_message_explains_why_rather_than_just_asking_again():
    """Telling someone to switch on a thing they already switched on reads as
    the software being broken. It has to say what took it away."""
    assert "update" in macperm.AX_LOST
    assert "Developer ID" in macperm.AX_LOST
    assert "Accessibility" in macperm.AX_LOST


def test_the_pane_links_are_settings_urls():
    """NOT a claim that they land correctly. `open` exits 0 for a URL that
    opens the wrong pane, so nothing here -- or anywhere else -- can check
    that from code. On macOS 27 the older identifier opens the Accessibility
    FEATURES pane, which is a different thing with the same name."""
    assert macperm.AX_PANES
    for url in macperm.AX_PANES:
        assert url.startswith("x-apple.systempreferences:")
        assert "Privacy_Accessibility" in url


def test_the_words_say_which_accessibility_is_meant():
    """The one that matters, because the URL cannot be trusted and there are
    two panes with this name. A person sent to the wrong one switches on
    nothing and reports the feature as broken."""
    assert "Privacy & Security" in macperm.AX_HOW
    assert "NOT" in macperm.AX_HOW


def test_a_later_url_is_tried_when_the_first_fails(monkeypatch):
    tried = []

    class R:
        def __init__(self, rc): self.returncode = rc
        stdout = stderr = ""

    monkeypatch.setattr(macperm.sys, "platform", "darwin")
    monkeypatch.setattr(macperm, "AX_PANES", ("one", "two"))
    def run(argv, **k):
        tried.append(argv[-1])
        return R(1 if argv[-1] == "one" else 0)
    ok, err = macperm.ax_open_pane(run=run)
    assert ok and err is None
    assert tried == ["one", "two"]


def test_opening_the_pane_is_refused_off_mac(monkeypatch):
    monkeypatch.setattr(macperm.sys, "platform", "linux")
    ok, err = macperm.ax_open_pane()
    assert not ok and "macOS" in err


# --- whose answer is it, anyway ---------------------------------------


def test_the_daemon_records_a_refusal_it_hits(tmp_path, monkeypatch):
    """THE correction. macOS attributes a TCC grant to the RESPONSIBLE
    process, so `overwatch status` run from a terminal inherits the
    terminal's Accessibility -- it said "granted" while the daemon was
    logging the refusal in the same second, from the same executable at the
    same path. Measured 2026-09-30.

    So the daemon writes down what IT sees, and status reads that.
    """
    from pc import windows
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(windows.sys, "platform", "darwin")
    monkeypatch.setattr(windows, "_osa", lambda s: (None, "Accessibility off"))
    windows._mac_current()
    assert macperm.ax_last_known() is False


def test_the_daemon_records_a_grant_when_it_actually_reads_a_window(tmp_path,
                                                                   monkeypatch):
    """Proof rather than assumption: reading a window's geometry is the thing
    Accessibility gates, so getting it back is the evidence."""
    from pc import windows
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(windows.sys, "platform", "darwin")
    monkeypatch.setattr(windows, "_osa",
                        lambda s: ("Finder\nDesktop\n0\n0\n800\n600", None))
    fields, err = windows._mac_current()
    assert err is None and fields["app"] == "Finder"
    assert macperm.ax_last_known() is True


def test_bookkeeping_never_takes_down_a_panel(tmp_path, monkeypatch):
    """A panel builds every few seconds. Failing to write a note about
    permissions must not be what stops the screen updating."""
    from pc import windows
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(windows.sys, "platform", "darwin")
    monkeypatch.setattr(macperm, "ax_note",
                        lambda *a, **k: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(windows, "_osa",
                        lambda s: ("Finder\nDesktop\n0\n0\n800\n600", None))
    fields, err = windows._mac_current()
    assert err is None and fields["app"] == "Finder"


def test_nothing_is_recorded_off_mac(tmp_path, monkeypatch):
    from pc import windows
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(windows.sys, "platform", "linux")
    windows._record_ax(False)
    assert macperm.ax_last_known() is None


# --- which errors actually mean "denied" ------------------------------


def test_only_a_real_refusal_counts_as_denied():
    """-1719 and -1728 were in this list and should never have been.

        -25211  kAXErrorAPIDisabled     Accessibility really is off
        -1719   errAEIllegalIndex       no window at that index
        -1728   errAENoSuchObject       no such object
        -1743   errAEEventNotPermitted  AUTOMATION is off, a different cure

    The middle two fire when the frontmost application simply has no window --
    a Finder with everything closed, an agent with only a menu bar item. As a
    permission failure they make the panel say "Accessibility off" on a machine
    where it is fine, and send the owner to switch on something already on.
    Which happened here, twice, the second time after they had removed and
    re-added the entry on my advice.
    """
    from pc import windows
    assert windows._ax_denied("execution error: ... (-25211)")
    assert windows._ax_denied("osascript is not allowed assistive access.")
    assert not windows._ax_denied("execution error: ... (-1719)")
    assert not windows._ax_denied("execution error: ... (-1728)")
    assert not windows._ax_denied("execution error: ... (-1743)")


def test_an_empty_desktop_is_reported_as_an_empty_desktop(monkeypatch):
    """Not as a permission problem. The cure for one is a settings pane and
    the cure for the other is opening a window."""
    from pc import windows

    class P:
        returncode = 1
        stdout = ""
        stderr = "System Events got an error: ... (-1719)"

    monkeypatch.setattr(windows.subprocess, "run", lambda *a, **k: P())
    out, err = windows._osa("anything")
    assert out is None
    assert err == "nothing in front"


def test_an_unrecognised_refusal_logs_its_code(monkeypatch, capsys):
    """Every time this has gone wrong the answer was in an error nobody was
    printing. The code only -- the script names what the owner has open."""
    from pc import windows

    class P:
        returncode = 1
        stdout = ""
        stderr = "System Events got an error: something new (-9999)"

    monkeypatch.setattr(windows.subprocess, "run", lambda *a, **k: P())
    windows._osa("anything")
    err = capsys.readouterr().err
    assert "(-9999)" in err
    assert "something new" not in err, "the script's text must not be logged"


def test_the_instructions_name_the_pane_on_both_macos_versions():
    """macOS 27 renamed Privacy & Security > Accessibility to "Device Control
    and Data Access". Telling somebody on 27 to open "Accessibility" sends
    them to the VoiceOver pane, which is the only Accessibility left and does
    nothing for this -- measured on the owner's machine, twice, before anyone
    looked at the list instead of the instruction."""
    assert "Device Control and Data Access" in macperm.AX_HOW
    assert "Accessibility" in macperm.AX_HOW
    assert "macOS 27" in macperm.AX_HOW


def test_the_short_form_fits_a_panel_row():
    from V2 import panel as pm
    assert len(macperm.AX_WHERE_SHORT) <= pm.VALUE_MAX
