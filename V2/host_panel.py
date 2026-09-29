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
import subprocess
import sys
import time

from V2.panel import Panel, Row

POLL_S = 10.0

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

    statvfs rather than parsing `df`: one syscall, no process, and no output
    format to keep up with -- df's columns move between platforms, which is
    the class of thing this file was already getting wrong.

    Only the SPACE LEFT is taken from it. See DISK_WARN_GB for why the
    percentage is not.
    """
    try:
        st = os.statvfs("/")
    except OSError:
        return None, None
    if not st.f_blocks:
        return None, None
    gb = (st.f_bavail * st.f_frsize) / (1024.0 ** 3)
    return ("%.0f GB free" % gb if gb >= 10 else "%.1f GB free" % gb), gb


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
        total = vals.get("MemTotal")
        # MemAvailable is the kernel's own estimate of what a new workload
        # could have, which is the honest number -- MemFree excludes the cache
        # Linux will hand back on demand and reads as alarmingly small.
        avail = vals.get("MemAvailable", vals.get("MemFree"))
        if not total or avail is None:
            return None, None
        pct = 100.0 * avail / total
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
        pct = 100.0 * (pages.get("Pages free", 0)
                       + pages.get("Pages inactive", 0)) / total
    else:
        return None, None
    tone = None if pct >= 25 else ("warn" if pct >= 10 else "bad")
    return "%.0f%% free" % pct, tone


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


def _title():
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

    None rather than an empty panel when nothing could be read: a page that
    goes blank looks broken, where a page that stops changing looks like a
    machine that is not doing much.
    """
    rows = []

    up = _uptime()
    if up:
        rows.append(Row("Uptime", up, tone="dim"))

    free, gb = _disk()
    if free:
        tone = None
        if gb is not None and gb < DISK_BAD_GB:
            tone = "bad"
        elif gb is not None and gb < DISK_WARN_GB:
            tone = "warn"
        rows.append(Row("Disk", free, tone=tone))

    mem, mem_tone = _memory()
    if mem:
        rows.append(Row("Memory", mem, tone=mem_tone))

    batt, batt_tone = _battery()
    if batt:
        rows.append(Row("Battery", batt, tone=batt_tone))

    if not rows:
        return None
    tile = _tile()
    return Panel(_title(), rows, tiles=[tile] if tile else [])


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
