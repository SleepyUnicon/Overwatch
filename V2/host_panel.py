"""The first real panel: what this computer is doing.

Was V2/mac_panel.py, which shelled out to `pmset` and `vm_stat` and ran on
Linux anyway -- producing a panel titled "This Mac" with one row on it,
because every other reading came from a command that is not there. A panel
that is confidently wrong about the machine it is describing is worse than no
panel.

Deliberately unremarkable. Its job is to prove the V2 path end to end with
something a person would glance at, not to be clever. If this is boring and
correct, the next twenty panels are an afternoon each.

LINUX READS FILES, macOS RUNS COMMANDS, and that asymmetry is the point rather
than an inconsistency. /proc and /sys answer all four questions with an open()
and no process at all; macOS has no equivalent and needs sysctl, vm_stat and
pmset. Every spawn avoided is spawn cost off the daemon's only loop -- which
matters more than it looks, because panels are also built during the
connection handshake.

No new dependency, and nothing in pc/requirements.txt changes.
"""
import os
import shutil
import socket
import subprocess
import sys
import time

from V2.panel import Panel, Row

# Warn on what is LEFT, not on a percentage.
#
# A percentage cannot be computed honestly from statvfs on macOS: an APFS
# volume lives in a container, so f_blocks is the whole container while the
# space this volume has used is a fraction of it. Measured here, df reported
# 21% and the same arithmetic that is right on ext4 said 90% -- and 90% is the
# kind of wrong that paints a row red for no reason.
#
# Gigabytes remaining is the same number on every filesystem, and it is the
# one a person acts on anyway: "12 GB left" tells you whether an update will
# fit, where "83% full" does not.
DISK_WARN_GB = 20
DISK_BAD_GB = 10

# Module constants so a test can point them somewhere harmless. Reading the
# real /proc in a unit test would make the assertions depend on the machine
# running them.
PROC_UPTIME = "/proc/uptime"
PROC_MEMINFO = "/proc/meminfo"
POWER_SUPPLY = "/sys/class/power_supply"
HWMON = "/sys/class/hwmon"
THERMAL = "/sys/class/thermal"

# Which hwmon sensor is "the" temperature. A machine publishes a dozen -- the
# NVMe drive, the wifi card, each core -- and the one a person means is the
# CPU package. Matched on the label the kernel provides, in preference order;
# amd runs Tctl, intel runs Package id 0.
_CPU_LABELS = ("tctl", "tdie", "package id 0", "cpu", "core 0", "soc")

_LINUX = sys.platform.startswith("linux")
_DARWIN = sys.platform == "darwin"


def _run(*argv):
    """A short-lived command's stdout, or None. Never raises.

    This runs inside the daemon's only loop, and a panel is decoration on a
    device whose job is the dials -- it does not get to stop them because
    `pmset` moved.
    """
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=4)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout if p.returncode == 0 else None


def _read(path):
    """A file's contents, or None. The Linux half of everything below."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _fmt_uptime(seconds):
    if seconds is None or seconds < 0:
        return None
    d, rem = divmod(int(seconds), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return "%dd %dh" % (d, h)
    if h:
        return "%dh %dm" % (h, m)
    return "%dm" % m


def _uptime():
    if _LINUX:
        # "12345.67 89012.34" -- seconds since boot, then idle time.
        text = _read(PROC_UPTIME)
        if not text:
            return None
        try:
            return _fmt_uptime(float(text.split()[0]))
        except (IndexError, ValueError):
            return None
    if not _DARWIN:
        return None
    # From kern.boottime rather than parsing `uptime`, whose output is written
    # for people and changes shape between "1 day", "1:05" and "23 mins".
    out = _run("sysctl", "-n", "kern.boottime")
    if not out or "sec = " not in out:
        return None
    try:
        secs = int(out.split("sec = ")[1].split(",")[0])
    except (IndexError, ValueError):
        return None
    return _fmt_uptime(time.time() - secs)


def _disk():
    """(free text, free GB) for the boot volume, on any platform.

    shutil.disk_usage rather than parsing `df`: no process, and no output
    format to keep up with -- df's columns move between platforms, which is
    the class of thing this file was already getting wrong.

    And rather than os.statvfs, which this used and which DOES NOT EXIST ON
    WINDOWS. The claim "on any platform" in this docstring was false for a
    day: statvfs raises AttributeError there, not OSError, so the except below
    did not catch it and `build()` died -- taking the whole desk panel with it
    on a platform this project ships a signed binary for. Eleven tests said so
    on every push and nobody read them. shutil.disk_usage is the same syscall
    underneath on macOS and Linux (verified: 43.20 GB of 460.43 GB either way)
    and a real implementation on Windows.

    The root is os.sep made absolute, because "/" is not the boot volume on
    Windows -- it is a path on whatever drive happens to be current.

    Only the SPACE LEFT is taken from it. See DISK_WARN_GB for why the
    percentage is not.
    """
    try:
        st = shutil.disk_usage(os.path.abspath(os.sep))
    except (OSError, ValueError):
        return None, None
    if not st.total:
        return None, None
    gb = st.free / (1024.0 ** 3)
    total = st.total / (1024.0 ** 3)
    # "47 of 494 GB" says how full it is AND how much is left, in the 18
    # characters the row has. A bare percentage says neither usefully -- see
    # DISK_WARN_GB for why the percentage cannot be trusted here anyway.
    if total >= 1:
        text = "%.0f of %.0f GB" % (gb, total) if gb >= 10 \
            else "%.1f of %.0f GB" % (gb, total)
    else:
        text = "%.1f GB free" % gb
    return text, gb


def _physical_ram_gb():
    """Installed RAM, from sysconf -- no process, and right on both.

    vm_stat's page buckets do NOT sum to physical memory: compressed and
    wired-out pages are not among them, so a 16 GB Mac totalled 13 GB and the
    row said so. sysconf answers the question actually being asked, and
    SC_PAGE_SIZE is 16 KB on Apple Silicon against 4 KB on Intel -- assuming
    either is how a figure comes out four times wrong on half a fleet.
    """
    try:
        return (os.sysconf("SC_PAGE_SIZE")
                * os.sysconf("SC_PHYS_PAGES")) / (1024.0 ** 3)
    except (ValueError, OSError, AttributeError):
        return None


def _memory():
    """(text, tone) -- how much is free, as a percentage."""
    if _LINUX:
        text = _read(PROC_MEMINFO)
        if not text:
            return None, None
        vals = {}
        for line in text.splitlines():
            k, _, v = line.partition(":")
            v = v.strip().split(" ")[0]
            if v.isdigit():
                vals[k.strip()] = int(v)
        total_kb = vals.get("MemTotal")
        # MemAvailable is the kernel's own estimate of what a new workload
        # could have, which is the honest number -- MemFree excludes the cache
        # Linux will hand back on demand and reads as alarmingly small.
        avail_kb = vals.get("MemAvailable", vals.get("MemFree"))
        if not total_kb or avail_kb is None:
            return None, None
        pct = 100.0 * avail_kb / total_kb
        free_gb = avail_kb / (1024.0 ** 2)
        total_gb = _physical_ram_gb() or (total_kb / (1024.0 ** 2))
    elif _DARWIN:
        out = _run("vm_stat")
        if not out:
            return None, None
        pages = {}
        for line in out.splitlines():
            if ":" not in line:
                continue
            k, _, v = line.partition(":")
            v = v.strip().rstrip(".")
            if v.isdigit():
                pages[k.strip()] = int(v)
        total = sum(pages.get(k, 0) for k in
                    ("Pages free", "Pages active", "Pages inactive",
                     "Pages speculative", "Pages wired down"))
        if not total:
            return None, None
        free_pages = pages.get("Pages free", 0) + pages.get("Pages inactive", 0)
        pct = 100.0 * free_pages / total
        try:
            psize = os.sysconf("SC_PAGE_SIZE")
        except (ValueError, OSError):
            psize = 4096
        free_gb = free_pages * psize / (1024.0 ** 3)
        total_gb = _physical_ram_gb() or (total * psize / (1024.0 ** 3))
    else:
        return None, None
    tone = None if pct >= 25 else ("warn" if pct >= 10 else "bad")
    return "%.1f of %.0f GB" % (free_gb, total_gb), tone


def _battery():
    """(text, tone), or (None, None) on a machine without one."""
    pct = None
    charging = False
    if _LINUX:
        try:
            supplies = sorted(os.listdir(POWER_SUPPLY))
        except OSError:
            return None, None
        for name in supplies:
            if not name.startswith("BAT"):
                continue
            cap = _read(os.path.join(POWER_SUPPLY, name, "capacity"))
            status = (_read(os.path.join(POWER_SUPPLY, name, "status"))
                      or "").strip().lower()
            if cap and cap.strip().isdigit():
                pct = int(cap.strip())
                charging = status in ("charging", "full")
                break
    elif _DARWIN:
        out = _run("pmset", "-g", "batt")
        if not out or "InternalBattery" not in out:
            return None, None
        for tok in out.replace(";", " ").split():
            if tok.endswith("%"):
                try:
                    pct = int(tok.rstrip("%"))
                except ValueError:
                    pass
                break
        charging = "AC Power" in out or "charging" in out
    if pct is None:
        return None, None
    text = "%d%%%s" % (pct, " charging" if charging else "")
    if charging or pct >= 40:
        tone = None
    elif pct >= 20:
        tone = "warn"
    else:
        tone = "bad"
    return text, tone


def _hwmon_files(suffix):
    """Every /sys/class/hwmon/*/X<suffix> path, with its label if it has one.

    Yields (value_path, label). The label is the sibling *_label file, which
    most sensors have and none are required to.
    """
    try:
        chips = sorted(os.listdir(HWMON))
    except OSError:
        return
    for chip in chips:
        d = os.path.join(HWMON, chip)
        try:
            entries = sorted(os.listdir(d))
        except OSError:
            continue
        for name in entries:
            if not name.endswith(suffix):
                continue
            label = (_read(os.path.join(
                d, name[:-len(suffix)] + "_label")) or "").strip().lower()
            if not label:
                label = (_read(os.path.join(d, "name")) or "").strip().lower()
            yield os.path.join(d, name), label


def _temperature():
    """(text, tone) -- the CPU package, in degrees.

    Linux only. macOS keeps this behind the SMC, and every way to read it
    needs either root (`sudo powermetrics`) or a third-party helper installed
    -- neither of which a login service that set itself up with one command
    gets to assume. The row is simply absent there rather than guessed at.
    """
    if not _LINUX:
        return None, None

    best = None
    for path, label in _hwmon_files("_input"):
        if "temp" not in os.path.basename(path):
            continue
        raw = (_read(path) or "").strip()
        if not raw.lstrip("-").isdigit():
            continue
        # Millidegrees by convention, but a few chips report degrees.
        c = int(raw) / 1000.0 if abs(int(raw)) > 1000 else float(raw)
        rank = next((i for i, want in enumerate(_CPU_LABELS)
                     if want in label), len(_CPU_LABELS))
        if best is None or rank < best[0]:
            best = (rank, c)

    if best is None:
        # No hwmon, or nothing labelled. thermal_zone0 is the fallback every
        # ARM board and most laptops have.
        raw = (_read(os.path.join(THERMAL, "thermal_zone0", "temp")) or "").strip()
        if raw.lstrip("-").isdigit():
            best = (0, int(raw) / 1000.0)
    if best is None:
        return None, None

    c = best[1]
    if not -40 < c < 150:               # a sensor talking nonsense
        return None, None
    tone = None if c < 75 else ("warn" if c < 90 else "bad")
    return "%.0f C" % c, tone


def _fan():
    """(text, tone) -- the fastest fan, in rpm, or (None, None).

    Fastest rather than first: a machine with three fans has two idling and
    one working, and the working one is the answer to "is it struggling".
    A fanless machine publishes nothing, which is not a failure.
    """
    if not _LINUX:
        return None, None
    fastest = None
    for path, _label in _hwmon_files("_input"):
        if "fan" not in os.path.basename(path):
            continue
        raw = (_read(path) or "").strip()
        if raw.isdigit():
            rpm = int(raw)
            if fastest is None or rpm > fastest:
                fastest = rpm
    if fastest is None:
        return None, None
    if fastest == 0:
        return "idle", "dim"
    return "%d rpm" % fastest, None


def _hostname():
    """What to call this machine, short enough for the title.

    The board moves between computers -- that is the whole reason this row
    exists -- so "This Mac" was wrong the moment it was plugged into the
    Linux box, and would be ambiguous even between two Macs.
    """
    name = ""
    try:
        name = socket.gethostname() or ""
    except OSError:
        pass
    # "HackBookPro.local" and "desk.lan" are the same machine as their stems.
    for suffix in (".local", ".lan", ".home", ".localdomain"):
        if name.lower().endswith(suffix):
            name = name[:-len(suffix)]
            break
    name = name.split(".")[0].strip()
    return name or _generic_title()


def _generic_title():
    """When the machine will not say what it is called."""
    if _DARWIN:
        return "This Mac"
    if _LINUX:
        return "This PC"
    return "This computer"


def _tile():
    """The one action, which is not the same action on both.

    macOS has a direct "sleep the display". Linux has no portable equivalent
    -- `xset dpms force off` is X11 only and does nothing under Wayland -- so
    it locks instead, through logind, which is there wherever systemd is. Both
    are the same gesture: put the screen away without touching what is on it.
    """
    if _DARWIN:
        return "Sleep screen"
    if _LINUX:
        return "Lock screen"
    return None


def build():
    """The panel, or None to leave whatever is on the board alone.

    MORE CANDIDATES THAN ROWS, on purpose. ui_panel.h holds five, and a Linux
    laptop with sensors offers six. They are gathered in the order a person
    would want them and the tail falls off -- so a machine that reports its
    temperature shows it, and one that cannot shows its uptime instead of a
    blank line where a reading should be.

    Uptime is last because it is the least actionable thing here. It is
    pleasant to know and nobody ever did anything about it.

    None rather than an empty panel when nothing could be read: a page that
    goes blank looks broken, where a page that stops changing looks like a
    machine that is not doing much.
    """
    rows = []

    free, gb = _disk()
    if free:
        tone = None
        if gb is not None and gb < DISK_BAD_GB:
            tone = "bad"
        elif gb is not None and gb < DISK_WARN_GB:
            tone = "warn"
        rows.append(Row("Disk free", free, tone=tone))

    mem, mem_tone = _memory()
    if mem:
        rows.append(Row("RAM free", mem, tone=mem_tone))

    temp, temp_tone = _temperature()
    if temp:
        rows.append(Row("Temp", temp, tone=temp_tone))

    fan, fan_tone = _fan()
    if fan:
        rows.append(Row("Fan", fan, tone=fan_tone))

    batt, batt_tone = _battery()
    if batt:
        rows.append(Row("Battery", batt, tone=batt_tone))

    up = _uptime()
    if up:
        rows.append(Row("Uptime", up, tone="dim"))

    if not rows:
        return None
    tile = _tile()
    # Panel() truncates to ROWS_MAX itself; the slice is here so the INTENT
    # is visible at the point the order is chosen rather than being a
    # surprise two files away.
    return Panel(_hostname(), rows[:5], tiles=[tile] if tile else [])


def on_tap(tile):
    """Tile 0 puts the screen away.

    The safest possible action to prove the tap path with: whoever pressed it
    is sitting in front of the screen, and a key or the trackpad brings it
    straight back.
    """
    if tile != 0:
        return
    if _DARWIN:
        ok = _run("pmset", "displaysleepnow") is not None
    elif _LINUX:
        ok = _run("loginctl", "lock-session") is not None
    else:
        return
    if not ok:
        print("[panel] could not put the screen away", file=sys.stderr)
