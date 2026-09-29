"""Is there a call on, and where is it.

WHY URLS AND NOT WINDOW TITLES, ON MACOS

A browser window's title is only ever the ACTIVE tab, so a call in a
background tab is invisible to it -- and a title is user content besides:
"(99) Zoho People" tells you nothing stable. The browser's own AppleScript
dictionary hands over every tab's URL, background ones included, and a host
name does not change when somebody renames a meeting.

It also needs no Accessibility grant, which matters: System Events refuses
window titles outright on a machine that has not given one (-1728), and that
is the machine this was written on.

On X11 there is no equivalent -- no browser publishes its tabs to the window
manager -- so Linux matches window TITLES via wmctrl and is honestly weaker
for it: a call in a background tab will not be seen. That is a limitation,
recorded here rather than papered over.

AN OPEN TAB IS NOT A CALL. meet.google.com is a landing page; it is
meet.google.com/abc-defg-hij that means you are in something. Every web
service here therefore needs a path beyond the host before it counts.

PRIVACY: every tab's URL passes through this module and NONE of it is logged
or sent anywhere. Only the matched service's name reaches the board, never the
room, the query string, or any other tab.
"""
import os
import re
import shutil
import subprocess
import sys

TIMEOUT_S = 6

# (label, url pattern, title pattern, native process names)
#
# The url pattern must match a host AND something after it, so an idle landing
# page is not mistaken for a call in progress.
SERVICES = (
    ("Zoho Meeting",
     r"meeting\.zoho\.(?:com|eu|in|com\.au|jp)/(?:meeting/)?\w",
     r"\bzoho meeting\b",
     ()),
    ("Google Meet",
     r"meet\.google\.com/[a-z]{3,}",
     r"\bmeet\b.*[a-z]{3,}-[a-z]{3,}",
     ()),
    ("Zoom",
     r"zoom\.(?:us|com)/(?:j|wc|s|my)/\w",
     r"\bzoom meeting\b",
     ("zoom.us", "Zoom", "zoom")),
    ("Teams",
     r"teams\.(?:microsoft|live)\.com/.*\w",
     r"\bmicrosoft teams\b",
     ("Microsoft Teams", "Teams", "teams")),
    ("Webex",
     r"\w+\.webex\.com/(?:meet|wbxmjs|webappng)/\w",
     r"\bwebex\b",
     ("Webex", "Cisco Webex Meetings")),
    ("Jitsi",
     r"meet\.jit\.si/\w",
     r"\bjitsi\b",
     ()),
    ("Whereby",
     r"whereby\.com/[\w-]{2,}",
     r"\bwhereby\b",
     ()),
)

# Asking a Chromium-family browser for its tabs is a one-liner; asking one
# that is NOT RUNNING launches it. So every query is gated on the process
# list, and this is the set worth asking.
_MAC_BROWSERS = ("Brave Browser", "Google Chrome", "Google Chrome Canary",
                 "Chromium", "Microsoft Edge", "Arc", "Vivaldi", "Opera",
                 "Safari")

# A record separator that will not turn up inside a URL.
_SEP = "\u001f"


def _run(argv):
    """(stdout, err_or_None). Never raises."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True,
                           timeout=TIMEOUT_S)
    except FileNotFoundError:
        return None, "%s is not installed" % argv[0]
    except (OSError, subprocess.SubprocessError):
        return None, "%s did not run" % argv[0]
    if p.returncode != 0:
        return None, "%s refused" % argv[0]
    return (p.stdout or "").strip(), None


def _linux():
    return sys.platform.startswith("linux")


# ---------------------------------------------------------------- macOS

def _mac_processes():
    """Names of the visible application processes.

    Needs only the Automation grant `install` already asks for -- process
    names are allowed where window titles are not.
    """
    out, err = _run(["osascript", "-e",
                     'tell application "System Events" to get name of every'
                     ' application process whose background only is false'])
    if err or not out:
        return []
    return [n.strip() for n in out.split(",") if n.strip()]


def _mac_tabs(browser):
    """[(window index, tab index, url)] for one RUNNING browser.

    One osascript for the lot: a call per tab would be a dozen round trips
    every refresh. The window and tab indices come back so `show()` can raise
    the right tab rather than merely the right browser.
    """
    script = (
        'set out to ""\n'
        'tell application "%s"\n'
        '  set wc to count of windows\n'
        '  repeat with wi from 1 to wc\n'
        '    set tc to count of tabs of window wi\n'
        '    repeat with ti from 1 to tc\n'
        '      set out to out & wi & "%s" & ti & "%s" &'
        ' (URL of tab ti of window wi) & "\\n"\n'
        '    end repeat\n'
        '  end repeat\n'
        'end tell\n'
        'return out' % (browser, _SEP, _SEP))
    out, err = _run(["osascript", "-e", script])
    if err:
        # Reported, not swallowed. If a browser's dictionary turns out to
        # differ -- Safari's has been known to -- the log says which browser
        # and the panel does not pretend there is no call.
        print("[meeting] could not read tabs from %s" % browser,
              file=sys.stderr)
        return []
    found = []
    for line in (out or "").splitlines():
        parts = line.split(_SEP)
        if len(parts) != 3:
            continue
        wi, ti, url = parts
        if wi.strip().isdigit() and ti.strip().isdigit():
            found.append((int(wi), int(ti), url.strip()))
    return found


def _mac_detect():
    procs = _mac_processes()
    if not procs:
        return None, "could not list applications"
    lowered = [p.lower() for p in procs]

    # A native meeting app is the stronger signal: it is only running at all
    # because there is a call.
    for label, _u, _t, natives in SERVICES:
        for n in natives:
            if n.lower() in lowered:
                return {"service": label, "where": n, "kind": "app"}, None

    for browser in _MAC_BROWSERS:
        if browser.lower() not in lowered:
            continue
        for wi, ti, url in _mac_tabs(browser):
            for label, pat, _t, _n in SERVICES:
                if re.search(pat, url, re.I):
                    return {"service": label, "where": browser,
                            "kind": "tab", "browser": browser,
                            "window": wi, "tab": ti}, None
    return None, None


def _mac_show(call):
    if call.get("kind") == "app":
        _run(["osascript", "-e",
              'tell application "%s" to activate' % call["where"]])
        return True, None
    b = call.get("browser")
    script = ('tell application "%s"\n'
              '  set active tab index of window %d to %d\n'
              '  set index of window %d to 1\n'
              '  activate\n'
              'end tell' % (b, call["window"], call["tab"], call["window"]))
    _, err = _run(["osascript", "-e", script])
    return (err is None), err


# ---------------------------------------------------------------- Linux

def _linux_titles():
    """[(window id, title)] for every window, via wmctrl."""
    if not shutil.which("wmctrl"):
        return None, "install wmctrl to see calls"
    out, err = _run(["wmctrl", "-l"])
    if err:
        return None, err
    found = []
    for line in (out or "").splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4:
            found.append((parts[0], parts[3]))
    return found, None


def _linux_procs():
    """Lowercased process names, from /proc. No pgrep dependency."""
    names = []
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open("/proc/%s/comm" % pid, encoding="utf-8",
                          errors="replace") as fh:
                    names.append(fh.read().strip().lower())
            except OSError:
                continue
    except OSError:
        return []
    return names


def _linux_detect():
    procs = _linux_procs()
    for label, _u, _t, natives in SERVICES:
        for n in natives:
            if n.lower() in procs:
                return {"service": label, "where": n, "kind": "app"}, None

    titles, err = _linux_titles()
    if err:
        return None, err
    for wid, title in titles or []:
        for label, _u, pat, _n in SERVICES:
            if re.search(pat, title, re.I):
                return {"service": label, "where": title, "kind": "window",
                        "wid": wid}, None
    return None, None


def _linux_show(call):
    if call.get("kind") == "window" and call.get("wid"):
        _, err = _run(["wmctrl", "-i", "-a", call["wid"]])
        return (err is None), err
    if call.get("kind") == "app":
        return False, "no window to raise"
    return False, "nothing to raise"


# ----------------------------------------------------------------- api

def detect():
    """(call, err). call is None when there is no call, which is not an error.

    The two are separate returns on purpose: `players()` in music_linux once
    folded "gdbus is missing" into "nothing is playing", and the panel told a
    Linux user to buy a Mac. "No call" and "I could not look" are different
    sentences and each gets its own.
    """
    if _linux():
        return _linux_detect()
    if sys.platform == "darwin":
        return _mac_detect()
    return None, "call detection is macOS and X11 only"


def show(call):
    """Bring the call to the front. (ok, err)."""
    if not call:
        return False, "no call to show"
    if _linux():
        return _linux_show(call)
    if sys.platform == "darwin":
        return _mac_show(call)
    return False, "call detection is macOS and X11 only"
