"""Noticing that a board never came back from a flash.

The gap this closes: a write can VERIFY and the image still not run -- a bad
build does exactly that, and slot0 has no revert behind it. ota.flash() is then
right to report success, and until this existed nothing in the system ever
mentioned the board again. The daemon reconnected, waited for a hello that was
never coming, and the log simply stopped.

Measured on 2026-09-29: that silence read as a wedged daemon and cost about
fifteen minutes of looking in the wrong place. It was not wedged; it was
waiting, correctly, for a board that could not answer.
"""
import claude_usage_bridge as bridge
from pc import ota


LIMIT = bridge.SILENT_AFTER_FLASH_S


def test_nothing_to_say_when_no_flash_has_happened():
    assert bridge.silent_since_flash(None, False, False, 1000.0) == (False, None)


def test_quiet_is_allowed_while_the_board_is_still_rebooting():
    """Five seconds to reboot; ninety before this has an opinion. Warning
    inside its own reboot time would cry wolf on every successful update."""
    say, pending = bridge.silent_since_flash(100.0, False, False, 100.0 + 5)
    assert say is False
    assert pending == 100.0


def test_it_says_so_once_the_board_has_been_quiet_too_long():
    say, pending = bridge.silent_since_flash(100.0, False, False,
                                             100.0 + LIMIT + 1)
    assert say is True
    assert pending == 100.0


def test_it_says_so_only_once():
    """A line per poll tick would bury the recovery instructions it is there
    to surface."""
    say, _ = bridge.silent_since_flash(100.0, True, False, 100.0 + LIMIT + 60)
    assert say is False


def test_a_board_that_comes_back_clears_the_clock():
    """And clears it rather than merely suppressing the warning: the next
    flash has to start its own timer, not inherit this one's."""
    say, pending = bridge.silent_since_flash(100.0, False, True,
                                             100.0 + LIMIT + 1)
    assert say is False
    assert pending is None


def test_a_board_that_comes_back_after_a_warning_still_clears_it():
    say, pending = bridge.silent_since_flash(100.0, True, True, 500.0)
    assert say is False
    assert pending is None


def test_the_threshold_is_past_mcuboots_own_window():
    """MCUboot's revert window is ninety seconds. Anything still silent after
    that is not waiting on the bootloader."""
    assert bridge.SILENT_AFTER_FLASH_S >= 90.0


def test_the_warning_carries_something_to_act_on():
    """The point of noticing is the instructions, so the two are checked
    together: a warning with no command in it is a warning that sends someone
    to ask rather than to fix."""
    note = ota.recovery_note("/dev/ttyUSB0", "2.3.0")
    assert "write_flash 0x20000" in note
    assert "/dev/ttyUSB0" in note
    assert "sha256" in note
