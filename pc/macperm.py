"""macOS Automation (TCC) permission: one place to detect it and to ask.

Why this is its own module rather than a helper in either caller.

Two widgets need Automation and neither can get it for the other: the launcher
talks to System Events to find out whether an app is frontmost, and the music
page talks to whichever player is running. They fail the same way, for the same
reason, with the same cure -- and until now only pc/music.py said so, while
pc/widgets.py printed "could not read window state" and left the user to guess.

The part that makes this worth doing properly: the daemon is a LOGIN AGENT.
macOS shows the Automation prompt once, to whoever happens to be looking. For a
process that started at login that is nobody. The click is missed, the denial is
remembered, and from then on the board's launcher toggle is simply broken with
no message anywhere. Asking during `install` -- while the person is at the
keyboard, having just typed something -- is the whole point of preflight().
"""

import subprocess
import sys

# osascript's exit status for "Not authorized to send Apple events to X".
# Matched in stderr rather than by return code: osascript exits 1 for every
# script error, so the code alone cannot tell a denied grant from a typo.
TCC_DENIED = "-1743"

# Long enough for a cold System Events, short enough that a hung permission
# dialog does not stall the caller. The prompt itself does not block this --
# osascript returns the denial immediately and the dialog outlives it.
TIMEOUT_S = 10

PROBE = 'tell application "System Events" to return count of processes'


def classify(returncode, stderr):
    """None if the call worked, else 'denied' or 'failed'."""
    if returncode == 0:
        return None
    return "denied" if TCC_DENIED in (stderr or "") else "failed"


def check(script=PROBE, run=subprocess.run):
    """Exercise Automation once. Returns (ok, state) where state is as classify().

    On a machine that has never been asked, this is what RAISES the system
    prompt -- which is the point when it is called from install(). It is also
    safe to call when the answer is already yes: macOS remembers, and this
    costs one osascript spawn.
    """
    if sys.platform != "darwin":
        return True, None          # nothing to grant; not a failure
    try:
        p = run(["osascript", "-e", script], capture_output=True, text=True,
                timeout=TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return False, "failed"
    state = classify(p.returncode, p.stderr)
    return state is None, state


HOW = ("System Settings > Privacy & Security > Automation, "
       "then switch on System Events")


def explain(state, what="the launcher"):
    """One sentence a user can act on. Never the raw AppleScript error.

    The raw text names the script, and the script names what the user has
    open -- the same reflex CLAUDE.md applies to serial contents.
    """
    if state == "denied":
        return ("macOS is blocking Automation, so %s cannot tell which app is "
                "frontmost. Turn it on in %s." % (what, HOW))
    return "%s could not reach macOS Automation." % what.capitalize()


def preflight(out=None):
    """Ask for Automation now, at install time. Returns True if granted.

    Deliberately not fatal. Someone who declines still gets a working gauge, a
    working music page and apps that launch; what they lose is the launcher's
    minimise-if-frontmost half. Failing the install over that would be a
    worse trade than saying so and carrying on.
    """
    say = out or (lambda s: print(s))
    if sys.platform != "darwin":
        return True

    say("      Checking macOS Automation ...")
    ok, state = check()
    if ok:
        say("      granted")
        return True
    if state == "denied":
        say("      not granted.")
        say("      Apps will still launch and come to the front. What does")
        say("      not work is tapping an app that is already in front to")
        say("      minimise it.")
        say("      To turn it on: %s." % HOW)
    else:
        say("      could not check (macOS did not answer).")
    return False
