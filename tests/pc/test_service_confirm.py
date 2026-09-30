"""How long to wait before believing a service manager's "not running".

The bug this closes was not a wrong answer -- it was a right answer given too
early. `overwatch update` replaces a 12.8 MB PyInstaller bundle and bounces the
agent; macOS then has to assess the signature of a freshly written binary and
its fifty-one inner Mach-O files before it will exec anything. Measured on the
owner's Mac, 2026-09-30, updating 2.3.0 -> 2.3.1:

    10:21:57  kickstart
    10:22:02  gave up, printed "launchd reports it is not running"
    10:22:08  the new daemon's first log line

So the claim was true when it was checked, false six seconds later, and it told
the reader to run `overwatch install` for nothing. It did that on two
consecutive updates before anyone looked at the timestamps.
"""
import itertools

from pc import cli


def _times(budget_s=None):
    """When each probe happens, in seconds from the bounce."""
    d = (cli._confirm_delays() if budget_s is None
         else cli._confirm_delays(budget_s))
    return [0.0] + list(itertools.accumulate(d))[:-1]


def test_the_budget_covers_a_start_that_takes_eleven_seconds():
    """The measured case. Five seconds missed it by more than half."""
    assert cli.CONFIRM_BUDGET_S >= 11.0
    assert sum(cli._confirm_delays()) >= 11.0


def test_something_probes_around_the_eleven_second_mark():
    """Not just "the budget is big enough" -- a schedule that jumped 8s to 20s
    would satisfy that and still add nine seconds to every broken install."""
    assert any(abs(t - 11.0) <= 3.5 for t in _times())


def test_a_service_that_is_already_up_costs_nothing(monkeypatch):
    """The ordinary kickstart answers in 0.02s -- measured three times running.
    A generous budget must not turn that into a wait."""
    slept = []
    monkeypatch.setattr(cli.time, "sleep", lambda s: slept.append(s))
    assert cli._confirm_running(lambda: True) is True
    assert slept == [], "did not need to wait and should not have"


def test_a_slow_start_is_still_caught(monkeypatch):
    """The whole point: the ninth probe is around eleven seconds, which is
    where the real one came up."""
    monkeypatch.setattr(cli.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def probe():
        calls["n"] += 1
        return calls["n"] >= 9

    assert cli._confirm_running(probe) is True


def test_it_gives_up_eventually_rather_than_hanging(monkeypatch):
    """A daemon that genuinely cannot start must still get an answer, and the
    loop has to be bounded however sleep behaves."""
    monkeypatch.setattr(cli.time, "sleep", lambda _s: None)
    calls = {"n": 0}

    def probe():
        calls["n"] += 1
        return False

    assert cli._confirm_running(probe) is False
    # Ticks, not a wall-clock deadline: the failure-path tests patch sleep to a
    # no-op, and a deadline read off time.monotonic() would spin against a
    # clock that still moves -- thirty real seconds per test.
    assert 5 <= calls["n"] <= 40, calls["n"]


def test_the_last_wait_is_actually_spent(monkeypatch):
    """Returning after the final sleep without looking again would make the
    budget shorter than it claims to be."""
    monkeypatch.setattr(cli.time, "sleep", lambda _s: None)
    n = len(cli._confirm_delays())
    calls = {"n": 0}

    def probe():
        calls["n"] += 1
        return calls["n"] > n          # only the very last look succeeds

    assert cli._confirm_running(probe) is True


def test_a_long_wait_says_something(monkeypatch, capsys):
    """Thirty silent seconds reads as a hang, which is what the five-second
    budget was protecting against and is worth keeping."""
    monkeypatch.setattr(cli.time, "sleep", lambda _s: None)
    assert cli._confirm_running(lambda: False) is False
    assert "still waiting" in capsys.readouterr().err


def test_the_wait_is_mentioned_only_once(monkeypatch, capsys):
    monkeypatch.setattr(cli.time, "sleep", lambda _s: None)
    cli._confirm_running(lambda: False)
    assert capsys.readouterr().err.count("still waiting") == 1


def test_a_short_budget_can_be_asked_for(monkeypatch):
    """So a test -- or a caller with a reason -- is not stuck with thirty."""
    monkeypatch.setattr(cli.time, "sleep", lambda _s: None)
    assert sum(cli._confirm_delays(1.0)) < sum(cli._confirm_delays())


def test_the_restart_message_still_means_what_the_caller_checks():
    """_RESTART_OK is compared with ==, because three backends report failure
    as a string that STARTS with "restarted". Nothing here may loosen that."""
    assert cli._RESTART_OK == "restarted"
    assert cli.restart_left_it_down(
        "restarted, but launchd reports it is not running -- see /tmp/x.log")
    assert not cli.restart_left_it_down("restarted")
