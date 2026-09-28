"""The first real panel: what this Mac is doing.

Deliberately unremarkable. Its job is to prove the V2 path end to end with
something a person would actually glance at -- uptime, disk, battery, memory --
rather than to be clever. If this is boring and correct, the next twenty panels
are an afternoon each.

Everything here is read with the tools macOS already ships. No new dependency,
and nothing in pc/requirements.txt changes: CLAUDE.md is clear that the
customer's download does not grow for a decoration.
"""
import subprocess
import sys
import time

from V2.panel import Panel, Row

# Each reading is a process spawn, so this is not on the fast tick. Ten seconds
# is far below anything a person would notice on a disk or an uptime, and far
# above the cost of asking.
POLL_S = 10.0

# Below this, free space stops being an idle curiosity.
DISK_WARN_PCT = 90
DISK_BAD_PCT = 95


def _run(*argv):
    """A short-lived command's stdout, or None.

    Never raises. This runs inside the daemon's only loop, and a panel is
    decoration on a device whose job is the dials -- it does not get to stop
    them because `pmset` moved.
    """
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=4)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout if p.returncode == 0 else None


def _uptime():
    """How long since boot, as "3d 4h" or "18m".

    From kern.boottime rather than parsing `uptime`, whose output is written
    for people and changes shape between "1 day", "1:05" and "23 mins".
    """
    out = _run("sysctl", "-n", "kern.boottime")
    if not out or "sec = " not in out:
        return None
    try:
        secs = int(out.split("sec = ")[1].split(",")[0])
    except (IndexError, ValueError):
        return None
    up = int(time.time()) - secs
    if up < 0:
        return None
    d, rem = divmod(up, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return "%dd %dh" % (d, h)
    if h:
        return "%dh %dm" % (h, m)
    return "%dm" % m


def _disk():
    """(free text, percent used) for the boot volume."""
    out = _run("df", "-k", "/")
    if not out:
        return None, None
    lines = out.strip().splitlines()
    if len(lines) < 2:
        return None, None
    f = lines[1].split()
    try:
        avail_kb = int(f[3])
        pct = int(f[4].rstrip("%"))
    except (IndexError, ValueError):
        return None, None
    gb = avail_kb / (1024.0 * 1024.0)
    return ("%.0f GB free" % gb if gb >= 10 else "%.1f GB free" % gb), pct


def _battery():
    """(text, tone) or (None, None) on a machine without one."""
    out = _run("pmset", "-g", "batt")
    if not out or "InternalBattery" not in out:
        return None, None
    pct = None
    for tok in out.replace(";", " ").split():
        if tok.endswith("%"):
            try:
                pct = int(tok.rstrip("%"))
            except ValueError:
                pass
            break
    if pct is None:
        return None, None
    charging = "AC Power" in out or "charging" in out
    text = "%d%%%s" % (pct, " charging" if charging else "")
    if charging or pct >= 40:
        tone = None
    elif pct >= 20:
        tone = "warn"
    else:
        tone = "bad"
    return text, tone


def _memory():
    """Free memory as a percentage of the page pool, from vm_stat."""
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
    free = pages.get("Pages free", 0) + pages.get("Pages inactive", 0)
    pct = 100.0 * free / total
    tone = None if pct >= 25 else ("warn" if pct >= 10 else "bad")
    return "%.0f%% free" % pct, tone


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

    free, pct = _disk()
    if free:
        tone = None
        if pct is not None and pct >= DISK_BAD_PCT:
            tone = "bad"
        elif pct is not None and pct >= DISK_WARN_PCT:
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
    return Panel("This Mac", rows, tiles=["Sleep screen"])


def on_tap(tile):
    """Tile 0 puts the display to sleep.

    A physical button for the thing you otherwise reach for a menu to do, and
    the safest possible first action to prove the tap path with: the person
    pressing it is sitting in front of the screen, and any key or the trackpad
    brings it straight back.
    """
    if tile != 0:
        return
    if _run("pmset", "displaysleepnow") is None:
        print("[panel] could not sleep the display", file=sys.stderr)
