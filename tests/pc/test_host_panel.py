"""The host panel, on both platforms it claims to support.

Was V2/mac_panel.py, which ran `pmset` and `vm_stat` on Linux too -- so a
Linux desk got a panel titled "This Mac" carrying one row, every other
reading having come from a command that is not installed. A panel confidently
wrong about the machine it describes is worse than no panel, and these are
the tests that would have said so.

The Linux readings are driven by fake /proc and /sys trees. That is the whole
reason those paths are module constants: reading the real ones would make
every assertion depend on the machine running the suite.
"""
import os

import pytest

from V2 import host_panel as hp


@pytest.fixture
def linux(monkeypatch, tmp_path):
    """Pretend to be Linux, with a /proc and /sys of our own."""
    monkeypatch.setattr(hp, "_LINUX", True)
    monkeypatch.setattr(hp, "_DARWIN", False)

    up = tmp_path / "uptime"
    up.write_text("396355.11 1580146.25\n")
    monkeypatch.setattr(hp, "PROC_UPTIME", str(up))

    mem = tmp_path / "meminfo"
    mem.write_text("MemTotal:       16330196 kB\n"
                   "MemFree:          311396 kB\n"
                   "MemAvailable:    8165098 kB\n"
                   "Buffers:          142020 kB\n")
    monkeypatch.setattr(hp, "PROC_MEMINFO", str(mem))

    power = tmp_path / "power_supply"
    power.mkdir()
    monkeypatch.setattr(hp, "POWER_SUPPLY", str(power))

    def no_subprocess(*a, **kw):
        raise AssertionError("Linux must not spawn a process for these")

    monkeypatch.setattr(hp.subprocess, "run", no_subprocess)
    return power


def _battery(power, name="BAT0", capacity="64", status="Discharging"):
    d = power / name
    d.mkdir()
    (d / "capacity").write_text(capacity + "\n")
    (d / "status").write_text(status + "\n")


# --- the bug: macOS commands on a Linux box ---------------------------


def test_linux_reads_files_and_never_spawns_anything(linux):
    """The fixture asserts it: subprocess.run raises if anything calls it.

    /proc and /sys answer all four questions with an open(), and every spawn
    avoided is spawn cost off the daemon's only loop -- which matters here
    because panels are also built during the connection handshake.
    """
    _battery(linux)
    panel = hp.build()
    assert panel is not None
    assert [r.label for r in panel.rows] == ["Uptime", "Disk", "Memory",
                                             "Battery"]


def test_the_panel_is_not_called_this_mac_on_linux(linux):
    assert hp.build().title == "This PC"


def test_the_tile_is_the_one_that_works_on_this_platform(linux):
    """macOS sleeps the display; Linux has no portable equivalent -- xset is
    X11 only and does nothing under Wayland -- so it locks through logind."""
    assert hp.build().tiles == ["Lock screen"]


# --- the readings -----------------------------------------------------


def test_uptime_comes_from_proc(linux):
    assert hp._uptime() == "4d 14h"


def test_a_short_uptime_reads_in_minutes(linux, tmp_path):
    p = tmp_path / "up2"
    p.write_text("900.5 100.0\n")
    hp.PROC_UPTIME = str(p)
    assert hp._uptime() == "15m"


def test_memory_uses_memavailable_not_memfree(linux):
    """MemFree excludes the cache Linux hands back on demand, and reads as
    alarmingly small -- 1.9% here against a true 50%."""
    text, tone = hp._memory()
    assert text == "50% free"
    assert tone is None


def test_low_memory_is_toned(linux, tmp_path):
    p = tmp_path / "mem2"
    p.write_text("MemTotal: 1000 kB\nMemAvailable: 50 kB\n")
    hp.PROC_MEMINFO = str(p)
    assert hp._memory() == ("5% free", "bad")


def test_a_battery_is_read_from_sysfs(linux):
    _battery(linux, capacity="64", status="Discharging")
    assert hp._battery() == ("64%", None)


def test_a_charging_battery_says_so(linux):
    _battery(linux, capacity="21", status="Charging")
    text, tone = hp._battery()
    assert "charging" in text
    assert tone is None, "charging is not a warning, whatever the level"


def test_a_low_battery_is_toned(linux):
    _battery(linux, capacity="12", status="Discharging")
    assert hp._battery() == ("12%", "bad")


def test_a_desktop_has_no_battery_row(linux):
    assert hp._battery() == (None, None)
    assert "Battery" not in [r.label for r in hp.build().rows]


def test_a_power_supply_that_is_not_a_battery_is_ignored(linux):
    """AC adapters live in the same directory and have no capacity."""
    (linux / "AC").mkdir()
    (linux / "AC" / "online").write_text("1\n")
    assert hp._battery() == (None, None)


# --- disk, which is the same syscall on both --------------------------


def test_disk_warns_on_space_left_not_a_percentage(monkeypatch):
    """A percentage cannot be computed honestly from statvfs on macOS: an
    APFS volume sits in a container, so f_blocks is the whole container. df
    reported 21% here where the same arithmetic that is right on ext4 said
    90% -- and 90% paints a row red for no reason.
    """
    class FakeStat:
        f_frsize = 4096
        f_blocks = 100000000

        def __init__(self, avail):
            self.f_bavail = avail
            self.f_bfree = avail

    for avail_gb, want in ((100, None), (15, "warn"), (5, "bad")):
        monkeypatch.setattr(
            os, "statvfs",
            lambda _p, g=avail_gb: FakeStat(int(g * (1024 ** 3) / 4096)))
        _, gb = hp._disk()
        assert round(gb) == avail_gb
        tone = None
        if gb < hp.DISK_BAD_GB:
            tone = "bad"
        elif gb < hp.DISK_WARN_GB:
            tone = "warn"
        assert tone == want, avail_gb


# --- failure behaviour ------------------------------------------------


def test_a_machine_that_answers_nothing_leaves_the_board_alone(monkeypatch):
    """None rather than an empty panel: a page that goes blank looks broken,
    where a page that stops changing looks like a quiet machine."""
    monkeypatch.setattr(hp, "_LINUX", False)
    monkeypatch.setattr(hp, "_DARWIN", False)
    monkeypatch.setattr(os, "statvfs",
                        lambda _p: (_ for _ in ()).throw(OSError()))
    assert hp.build() is None


def test_an_unreadable_proc_file_costs_only_its_row(linux):
    hp.PROC_MEMINFO = "/no/such/meminfo"
    rows = [r.label for r in hp.build().rows]
    assert "Memory" not in rows
    assert "Uptime" in rows


def test_a_tap_on_a_tile_that_is_not_there_does_nothing(linux, monkeypatch):
    ran = []
    monkeypatch.setattr(hp, "_run", lambda *a: ran.append(a) or "")
    hp.on_tap(2)
    assert not ran
