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


def test_the_pane_link_is_the_settings_url():
    """Verified against macOS 26 on 2026-09-30: exits 0 and lands on the right
    page. Pinned because a wrong URL fails silently -- `open` succeeds and the
    user gets the front page of System Settings."""
    assert macperm.AX_PANE.startswith("x-apple.systempreferences:")
    assert "Privacy_Accessibility" in macperm.AX_PANE


def test_opening_the_pane_is_refused_off_mac(monkeypatch):
    monkeypatch.setattr(macperm.sys, "platform", "linux")
    ok, err = macperm.ax_open_pane()
    assert not ok and "macOS" in err
