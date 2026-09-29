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

_real_hostname = hp._hostname


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

    # No sensors by default. The ones that want them build their own, so a
    # test about memory is not also a test about hwmon.
    empty = tmp_path / "hwmon"
    empty.mkdir()
    monkeypatch.setattr(hp, "HWMON", str(empty))
    monkeypatch.setattr(hp, "THERMAL", str(tmp_path / "thermal-none"))
    monkeypatch.setattr(hp, "_hostname", lambda: "testbox")

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
    assert [r.label for r in panel.rows] == ["Disk free", "RAM free",
                                             "Battery", "Uptime"]


def test_the_panel_is_named_after_the_machine(linux, monkeypatch):
    """"This Mac" was wrong the moment the board was plugged into the Linux
    box, and would be ambiguous between two Macs anyway. The board moves --
    that is the whole reason this panel exists."""
    monkeypatch.setattr(hp, "_hostname", hp._hostname.__wrapped__
                        if hasattr(hp._hostname, "__wrapped__")
                        else _real_hostname)
    monkeypatch.setattr(hp.socket, "gethostname", lambda: "HackBookPro.local")
    assert hp.build().title == "HackBookPro"


def test_a_machine_with_no_name_falls_back_to_the_platform(linux, monkeypatch):
    monkeypatch.setattr(hp, "_hostname", _real_hostname)
    monkeypatch.setattr(hp.socket, "gethostname", lambda: "")
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


def test_memory_uses_memavailable_not_memfree(linux, monkeypatch):
    """MemFree excludes the cache Linux hands back on demand, and reads as
    alarmingly small -- 1.9% here against a true 50%, which is the difference
    between a calm row and a red one."""
    monkeypatch.setattr(hp, "_physical_ram_gb", lambda: 15.6)
    text, tone = hp._memory()
    assert text == "7.8 of 16 GB"
    assert tone is None


def test_low_memory_is_toned(linux, tmp_path, monkeypatch):
    p = tmp_path / "mem2"
    p.write_text("MemTotal: 16000000 kB\nMemAvailable: 800000 kB\n")
    monkeypatch.setattr(hp, "PROC_MEMINFO", str(p))
    # Pinned, or the total comes from whatever machine is running the suite:
    # sysconf is the authority for installed RAM and correctly overrides
    # MemTotal, which is what test_memory_uses_memavailable pins.
    monkeypatch.setattr(hp, "_physical_ram_gb", lambda: 15.3)
    text, tone = hp._memory()
    assert tone == "bad"
    assert text == "0.8 of 15 GB"


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


# --- disk, which is the same call on all three ------------------------

GB = 1024 ** 3


def _usage(free_gb, total_gb=400):
    """What shutil.disk_usage returns: a (total, used, free) named tuple."""
    import collections
    U = collections.namedtuple("usage", "total used free")
    return U(int(total_gb * GB), int((total_gb - free_gb) * GB),
             int(free_gb * GB))


def test_disk_warns_on_space_left_not_a_percentage(monkeypatch):
    """A percentage cannot be computed honestly on macOS: an APFS volume sits
    in a container, so the total is the whole container. df reported 21% here
    where the same arithmetic that is right on ext4 said 90% -- and 90% paints
    a row red for no reason.
    """
    for avail_gb, want in ((100, None), (15, "warn"), (5, "bad")):
        monkeypatch.setattr(hp.shutil, "disk_usage",
                            lambda _p, g=avail_gb: _usage(g))
        _, gb = hp._disk()
        assert round(gb) == avail_gb
        tone = None
        if gb < hp.DISK_BAD_GB:
            tone = "bad"
        elif gb < hp.DISK_WARN_GB:
            tone = "warn"
        assert tone == want, avail_gb


def test_the_disk_is_read_with_a_call_that_exists_on_windows(monkeypatch):
    """os.statvfs DOES NOT EXIST on Windows -- it raises AttributeError, which
    _disk's except clause never caught, so build() died and took the whole
    desk panel with it on a platform this project ships a signed binary for.
    Eleven tests said so on every push for a day.

    Asserting the absence of the old call, because "it works on my Mac" is
    exactly how it survived.
    """
    import V2.host_panel as mod
    src = open(mod.__file__, encoding="utf-8").read()
    # The CALL, not the word: the docstring explains why statvfs was dropped
    # and should go on saying so.
    assert "os.statvfs(" not in src
    assert "shutil.disk_usage(" in src


def test_the_boot_volume_is_not_hardcoded_to_a_slash():
    """"/" is not the boot volume on Windows -- it is a path on whatever drive
    happens to be current."""
    import V2.host_panel as mod
    src = open(mod.__file__, encoding="utf-8").read()
    assert 'disk_usage("/")' not in src
    assert "os.path.abspath(os.sep)" in src


# --- failure behaviour ------------------------------------------------


def test_a_machine_that_answers_nothing_leaves_the_board_alone(monkeypatch):
    """None rather than an empty panel: a page that goes blank looks broken,
    where a page that stops changing looks like a quiet machine."""
    monkeypatch.setattr(hp, "_LINUX", False)
    monkeypatch.setattr(hp, "_DARWIN", False)
    monkeypatch.setattr(hp.shutil, "disk_usage",
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


# --- temperature and fans ---------------------------------------------


def _hwmon(tmp_path, monkeypatch, sensors):
    """A /sys/class/hwmon tree. `sensors` is {file: (value, label)}."""
    root = tmp_path / "hwmon"
    root.mkdir(exist_ok=True)
    chip = root / "hwmon0"
    chip.mkdir()
    (chip / "name").write_text("coretemp\n")
    for fname, (value, label) in sensors.items():
        (chip / fname).write_text(str(value) + "\n")
        if label is not None:
            stem = fname[:-len("_input")]
            (chip / (stem + "_label")).write_text(label + "\n")
    monkeypatch.setattr(hp, "HWMON", str(root))
    return chip


def test_the_cpu_package_is_preferred_over_other_sensors(linux, tmp_path,
                                                         monkeypatch):
    """A machine publishes a dozen: the NVMe drive, the wifi card, each core.
    The one a person means is the package."""
    _hwmon(tmp_path, monkeypatch, {
        "temp1_input": (31000, "NVMe Composite"),
        "temp2_input": (54000, "Package id 0"),
        "temp3_input": (49000, "Core 1"),
    })
    assert hp._temperature() == ("54 C", None)


def test_a_hot_cpu_is_toned(linux, tmp_path, monkeypatch):
    _hwmon(tmp_path, monkeypatch, {"temp1_input": (93000, "Tctl")})
    assert hp._temperature() == ("93 C", "bad")
    _hwmon2 = tmp_path / "hwmon" / "hwmon0" / "temp1_input"
    _hwmon2.write_text("81000\n")
    assert hp._temperature() == ("81 C", "warn")


def test_thermal_zone_is_the_fallback(linux, tmp_path, monkeypatch):
    """Every ARM board and most laptops have one even with no hwmon."""
    z = tmp_path / "thermal" / "thermal_zone0"
    z.mkdir(parents=True)
    (z / "temp").write_text("47000\n")
    monkeypatch.setattr(hp, "THERMAL", str(tmp_path / "thermal"))
    assert hp._temperature() == ("47 C", None)


def test_a_sensor_talking_nonsense_is_ignored(linux, tmp_path, monkeypatch):
    _hwmon(tmp_path, monkeypatch, {"temp1_input": (9999000, "Package id 0")})
    assert hp._temperature() == (None, None)


def test_the_fastest_fan_is_the_one_reported(linux, tmp_path, monkeypatch):
    """Three fans means two idling and one working, and the working one
    answers "is it struggling"."""
    _hwmon(tmp_path, monkeypatch, {
        "fan1_input": (0, None),
        "fan2_input": (2400, None),
        "fan3_input": (1100, None),
    })
    assert hp._fan() == ("2400 rpm", None)


def test_fans_at_rest_say_so(linux, tmp_path, monkeypatch):
    _hwmon(tmp_path, monkeypatch, {"fan1_input": (0, None)})
    assert hp._fan() == ("idle", "dim")


def test_a_fanless_machine_has_no_fan_row(linux):
    assert hp._fan() == (None, None)
    assert "Fan" not in [r.label for r in hp.build().rows]


def test_macos_offers_no_temperature_or_fan(monkeypatch):
    """Both live behind the SMC, and every way to read them needs root
    (`sudo powermetrics`) or a third-party helper. A login service that set
    itself up with one command gets to assume neither, so the rows are absent
    rather than guessed at.
    """
    monkeypatch.setattr(hp, "_LINUX", False)
    monkeypatch.setattr(hp, "_DARWIN", True)
    assert hp._temperature() == (None, None)
    assert hp._fan() == (None, None)


def test_sensors_push_uptime_off_the_panel(linux, tmp_path, monkeypatch):
    """Six candidates, five rows. Uptime goes last because it is the least
    actionable thing here -- pleasant to know, and nobody ever did anything
    about it."""
    _hwmon(tmp_path, monkeypatch, {
        "temp1_input": (55000, "Package id 0"),
        "fan1_input": (1800, None),
    })
    _battery(linux)
    labels = [r.label for r in hp.build().rows]
    assert labels == ["Disk free", "RAM free", "Temp", "Fan", "Battery"]
    assert "Uptime" not in labels


def test_the_panel_still_fits_one_line_with_every_row(linux, tmp_path,
                                                      monkeypatch):
    """Five rows, a tile and a long hostname, against proto.c's 512."""
    from pc import protocol
    from V2 import panel as P

    _hwmon(tmp_path, monkeypatch, {
        "temp1_input": (55000, "Package id 0"),
        "fan1_input": (1800, None),
    })
    _battery(linux, capacity="87", status="Charging")
    monkeypatch.setattr(hp, "_hostname", lambda: "W" * P.TITLE_MAX)
    msg = hp.build().message(0)
    assert P.too_long(msg) == 0
    assert len(protocol.encode(msg)) < protocol.MAX_LINE_BYTES
