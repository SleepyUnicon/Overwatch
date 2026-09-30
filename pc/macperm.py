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

import json
import os
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


# ===================================================================== AX
#
# ACCESSIBILITY IS NOT AUTOMATION, AND IT IS WORSE.
#
# Automation (above) at least prompts: the first osascript raises a dialog, and
# preflight() exists to make that happen while somebody is at the keyboard.
# macOS NEVER PROMPTS FOR ACCESSIBILITY. The app has to be added by hand, in a
# pane the user has to be told to open, and until then everything that needs it
# fails with -1728 and no dialog anywhere.
#
# And it does not stay granted. Measured on the owner's Mac, 2026-09-30:
#
#     $ codesign -d -r- ~/.overwatch/bin/overwatch
#     # designated => cdhash H"40cb6c2b4aae6e125a537afb9f2e24d70d3b3acc"
#
# That is the whole designated requirement -- a raw content hash, which is all
# an ad-hoc signature can produce. TCC records the grant against it, so every
# `overwatch update` writes a new binary, gets a new cdhash, and the grant no
# longer matches anything. It is not lost by accident; it cannot survive.
#
# Nothing in this file fixes that. A stable requirement needs a real signing
# identity, where it becomes `identifier "..." and certificate leaf[...] =
# TEAMID` and does not move when the bytes do. That is the same Developer ID
# enrolment notarisation needs -- see docs/notarisation.md.
#
# What IS fixable is the silence. Losing the grant looked exactly like a
# feature that had stopped working, twice, and cost an afternoon before anyone
# read the designated requirement. So: check it, remember the answer, and when
# it goes from granted to not, say which of the two happened.

# `UI elements enabled` is System Events' own report of whether the CALLER is
# trusted for Accessibility. It needs Automation to ask at all, which is why a
# missing Automation grant is reported as "unknown" rather than "denied" --
# they are different problems with different cures, and answering the wrong one
# is how this project once told a Linux user to buy a Mac.
AX_PROBE = 'tell application "System Events" to get UI elements enabled'

# Deep links into System Settings, newest scheme first.
#
# NOT verified to land on the right page, and the comment here used to claim it
# was. What was actually checked was that `open` exited 0 and System Settings
# came to the front -- which it does for a URL that lands somewhere else
# entirely. On macOS 27 the old identifier opens the Accessibility FEATURES
# pane (VoiceOver, Zoom, Hover Text), which is a different thing with the same
# name, and the person following the instruction ends up switching on nothing.
#
# `open` reports success either way, so there is no way from here to tell a
# good landing from a bad one. That is why AX_HOW is the words and the URL is
# only a convenience: the words are what a person can follow when the link
# misses, and they do not rot between releases of macOS.
AX_PANES = (
    # macOS 13+ System Settings.
    "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension"
    "?Privacy_Accessibility",
    # Older System Preferences.
    "x-apple.systempreferences:com.apple.preference.security"
    "?Privacy_Accessibility",
)
AX_PANE = AX_PANES[0]

# The path, in words -- and the words MOVED.
#
# On macOS 26 and earlier this list is Privacy & Security > Accessibility. On
# macOS 27 there is no such entry: Apple renamed it "Device Control and Data
# Access", and the only Accessibility left is the top-level pane that
# configures VoiceOver and Zoom, which is a different thing that happens to
# share the name.
#
# Seen on the owner's machine, 2026-09-30, macOS 27.0.1: told to open
# Privacy & Security > Accessibility, they found no such row, went to the
# pane that IS called Accessibility, and granted nothing. Twice. The deep
# link had been landing on "Device Control and Data Access" the whole time
# and I read that as another wrong guess rather than as the answer.
#
# Both names, because a person on either version has to recognise theirs.
AX_HOW = ("System Settings > Privacy & Security > Device Control and Data "
          "Access (called Accessibility before macOS 27; NOT the "
          "Accessibility pane in the sidebar), then switch on Overwatch")

# Short enough for a panel row, where the long form does not fit.
AX_WHERE_SHORT = "Device Control"


def ax_check(run=subprocess.run):
    """Is Accessibility granted to THIS binary? (granted, state).

    state is None when granted, else "denied" or "unknown". Unknown covers the
    cases where the question could not be put -- no Automation, osascript
    missing, a timeout -- because "I could not ask" is a different sentence
    from "the answer is no", and only one of them is fixed in the
    Accessibility pane.
    """
    if sys.platform != "darwin":
        return True, None          # nothing to grant; not a problem to report
    try:
        p = run(["osascript", "-e", AX_PROBE], capture_output=True, text=True,
                timeout=TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return False, "unknown"
    if p.returncode != 0:
        # Automation refused, or System Events did not answer. Either way this
        # is not a statement about Accessibility.
        return False, "unknown"
    answer = (p.stdout or "").strip().lower()
    if answer == "true":
        return True, None
    if answer == "false":
        return False, "denied"
    return False, "unknown"


def ax_explain(state, what="the window and tool panels"):
    """One sentence to act on, and never the raw AppleScript error."""
    if state == "denied":
        return ("macOS is blocking Accessibility, so %s cannot move windows or "
                "send keystrokes. Turn it on in %s." % (what, AX_HOW))
    return ("Could not check macOS Accessibility -- Automation has to be on "
            "first. %s" % HOW)


def ax_open_pane(run=subprocess.run):
    """Put the pane on screen. (ok, err).

    Because "System Settings > Privacy & Security > Accessibility" is four
    levels deep and the list it lands on is long. A person who has just been
    told a permission is missing should not also have to go looking for it.
    """
    if sys.platform != "darwin":
        return False, "macOS only"
    for url in AX_PANES:
        try:
            p = run(["open", url], capture_output=True, text=True,
                    timeout=TIMEOUT_S)
        except (OSError, subprocess.SubprocessError):
            continue
        if p.returncode == 0:
            # Deliberately NOT reported as "opened the right page". `open`
            # cannot tell us that, and claiming it is how the wrong pane got
            # recommended in the first place.
            return True, None
    return False, "could not open System Settings"


# --- remembering, so a loss can be told from a never-had ---------------

AX_STATE = "accessibility.json"


def _ax_path(home=None):
    """Resolved on every call, never at import.

    The same rule the rest of pc/ follows: a module-level expanduser is read
    once, at import, and a test that sets HOME afterwards is talking to the
    wrong file without being told.
    """
    base = home or os.path.join(os.path.expanduser("~"), ".overwatch")
    return os.path.join(base, AX_STATE)


def ax_last_known(home=None):
    """What we saw last time: True, False, or None for never looked."""
    try:
        with open(_ax_path(home), encoding="utf-8") as fh:
            v = json.load(fh).get("granted")
    except (OSError, ValueError):
        return None
    return v if isinstance(v, bool) else None


def ax_note(granted, home=None):
    """Record today's answer and say what CHANGED. One of:

        "lost"    -- had it, does not now. Almost always an update: the
                     designated requirement is a cdhash and the bytes moved.
        "gained"  -- someone ticked the box.
        None      -- no change, or nothing to compare against.

    The distinction is the whole point of the file. "Accessibility off" on a
    machine that never had it is a setup step nobody has done yet; the same
    words on a machine that had it five minutes ago are a regression, and
    telling a person to go and switch on something they already switched on
    reads as the software being broken -- which, in the sense that matters to
    them, it is.
    """
    before = ax_last_known(home)
    path = _ax_path(home)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"granted": bool(granted)}, fh)
        os.replace(tmp, path)
    except OSError:
        # Not being able to remember is not worth failing over; the caller
        # still gets a truthful "no change".
        return None
    if before is None or before == bool(granted):
        return None
    return "gained" if granted else "lost"


AX_LOST = (
    "Accessibility was granted and is not any more. An update replaced the"
    " program, and macOS keys that permission to the exact bytes it was"
    " granted to -- the designated requirement is a content hash, so a new"
    " build is a different program as far as it is concerned. Switch"
    " Overwatch back on in %s. It will keep happening on every update until"
    " the program is signed with a Developer ID." % AX_HOW)
