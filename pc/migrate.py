"""Move a Blink installation onto its Overwatch names.

Everything this fork keeps on a machine used to live in ~/.blink, under
names starting `blink-`. It lives in ~/.overwatch now. That rename is
invisible to anyone installing for the first time and quietly destructive
to anyone who is not: the state directory holds the OTA signing key, the
launcher's slots, and the board's last-known firmware version, and
~/.claude/settings.json points INTO it by absolute path for the status
line and ten hook events.

So the move is done for them, once, rather than left as a paragraph in a
release note. A user who never reads this still has their key.

What it deliberately does NOT do: touch the login service. That is a
launchd plist, a systemd unit or a Scheduled Task, all of them written by
`install` and all of them naming the old binary. Re-registering a service
is not a data migration, and doing it halfway -- removing the old one
without successfully writing the new -- leaves a desk with no daemon and
no error anyone will see. run() reports the leftover instead, and
`install` is what replaces it.

Nothing here raises. It runs on the way into every command, including the
ones someone reaches for when something is already wrong.
"""
import os
import shutil
import sys

from pc import cli

# The shims, by the name each had and the name it wants. These are
# referenced from settings.json by absolute path, so renaming the file
# without rewriting that reference gives a status line that silently
# stops rendering -- which is how it would be found: not at all.
SHIMS = (
    ("blink-statusline.sh", "overwatch-statusline.sh"),
    ("blink-hook.sh", "overwatch-hook.sh"),
    ("blink-bridge.vbs", "overwatch-bridge.vbs"),
)

# Files inside the state directory whose CONTENTS name the old paths. The
# two markers are how install_hooks and install_statusline recognise their
# own commands in settings.json; a marker still holding the old command
# makes `uninstall` refuse to remove the hooks it put there, on the
# grounds that they look like somebody else's.
MARKERS = ("statusline-installed-command", "hooks-installed-commands")

# ...and the shims themselves, whose CONTENTS name the state directory.
# Renaming the file is not enough: the hook shim computes its state
# directory as "$HOME/.blink/$sub", so a shim that moved and was renamed
# still writes where it always did. That is not theoretical -- it
# recreated ~/.blink within the same minute the move finished, on the
# first hook that fired afterwards.
#
# Both locations: the installer writes one copy beside the state and one
# in bin/, and settings.json points at the bin/ copy.
SHIM_DIRS = (".", "bin")

# Service registrations that name the old binary. Reported, never touched.
OLD_SERVICE = {
    "darwin": ("com.blink.bridge",
               "~/Library/LaunchAgents/com.blink.bridge.plist"),
    "linux": ("blink-bridge.service",
              "~/.config/systemd/user/blink-bridge.service"),
    "win32": ("BlinkBridge", "Task Scheduler"),
}


def old_home():
    """Where a Blink install kept its state, under the same HOME."""
    return os.path.join(cli._home(), ".blink")


def needed():
    """Is there an old installation to move, and nowhere it has gone yet?

    Both existing is not a migration: it is two installations, and picking
    one to overwrite is not a decision this gets to make quietly.
    """
    return os.path.isdir(old_home()) and not os.path.exists(cli.overwatch_home())


def _rewrite(path, pairs):
    """Replace each (old, new) in a text file, leaving it alone on error.

    Byte-for-byte except for the replacements -- no reformatting, no
    re-encoding. One of the files this walks past is a PEM private key,
    which is why it is given an explicit list and not a directory.
    """
    try:
        with open(path, encoding="utf-8") as f:
            before = f.read()
    except (OSError, UnicodeDecodeError):
        return False
    after = before
    for old, new in pairs:
        after = after.replace(old, new)
    if after == before:
        return False
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(after)
        os.replace(tmp, path)            # atomic; a half-written marker
        return True                      # would be worse than an old one
    except OSError:
        return False


def _pairs():
    r"""Every string that has to change, most specific first.

    Home-AGNOSTIC on purpose: `/.blink`, not old_home(). A rehearsal
    against a copy of a real machine caught why. settings.json holds
    whatever spelling of home was current when the installer wrote it,
    and that need not be the one os.path.expanduser returns now -- a
    symlinked home, /Users/x against /private/..., an account that moved.
    When the absolute form missed, the bare shim names still matched, and
    the result was `/Users/x/.blink/overwatch-statusline.sh`: a path wrong
    in exactly the way that survives being read back.

    Anchored on `/.blink` there is nothing for the directory step to miss,
    so the bare names can only ever land inside a path already moved.

    Order still matters. `/.blink` is a substring of
    `/.blink/blink-hook.sh`, so the directory must not go first.

    SEPARATOR-agnostic too, and on Windows that is not a nicety -- it is the
    difference between this function working and doing nothing at all. Every
    string it has to rewrite on Windows is spelled with FORWARD slashes:

      - the shim bodies are POSIX sh, and compute their state directory as
        "$HOME/.blink/$sub" on every platform;
      - the commands in settings.json and in the two markers are written by
        install_statusline.windows_bash_path, which converts every backslash
        to a forward slash because a backslash is an escape under Git Bash.

    Built with os.sep alone, the pairs on Windows read `\.blink\blink-hook.sh`
    and matched none of it, so a Windows migration silently moved the directory
    and left every reference inside it pointing at ~/.blink. Five tests said so
    on every push (2026-09-26); they had been read as "Windows path noise".

    Both spellings, so a mixed path is handled too: `\.blink/blink-hook.sh`
    loses its directory to the `\.blink` pair and its filename to the bare
    name at the end.
    """
    # dict.fromkeys, not a set: on POSIX os.sep IS "/" and the two collapse to
    # one entry, and the order below is load-bearing.
    seps = list(dict.fromkeys(("/", os.sep)))
    out = []
    for sep in seps:
        out += [(sep + ".blink" + sep + old, sep + ".overwatch" + sep + new)
                for old, new in SHIMS]
    for sep in seps:
        out.append((sep + ".blink", sep + ".overwatch"))
    # Last, and only now: the shims are not all direct children of the
    # state directory -- the hook shim is installed into bin/ as well.
    out += list(SHIMS)
    return out


def run(settings_path=None):
    """Do it. Returns a list of lines describing what happened, or [].

    Empty means there was nothing to do, which is the common case and the
    one that must stay silent: this runs on the way into every command.
    """
    if not needed():
        return []
    src, dst = old_home(), cli.overwatch_home()
    said = []
    try:
        os.rename(src, dst)
    except OSError as e:
        # Same HOME, so a rename should not cross a device -- but a
        # mounted or synced home can, and a copy is still better than
        # refusing. shutil.move handles both.
        try:
            shutil.move(src, dst)
        except (OSError, shutil.Error):
            return ["could not move %s to %s: %s" % (src, dst, e)]
    said.append("moved %s to %s" % (src, dst))

    # Both locations. The installer puts the hook shim in the state
    # directory AND in bin/, and settings.json may name either.
    for where in (dst, os.path.join(dst, "bin")):
        for old, new in SHIMS:
            a, b = os.path.join(where, old), os.path.join(where, new)
            if os.path.exists(a) and not os.path.exists(b):
                try:
                    os.rename(a, b)
                    said.append("renamed %s in %s"
                                % (old, os.path.basename(where) or "."))
                except OSError as e:
                    said.append("could not rename %s: %s" % (old, e))

    pairs = _pairs()
    for name in MARKERS:
        if _rewrite(os.path.join(dst, name), pairs):
            said.append("rewrote " + name)
    for sub in SHIM_DIRS:
        for _, new_name in SHIMS:
            if _rewrite(os.path.join(dst, sub, new_name), pairs):
                said.append("repointed %s in %s" % (new_name, sub))

    sp = settings_path or cli.settings_path()
    if _rewrite(sp, pairs):
        said.append("repointed the status line and hooks in " + sp)

    leftover = OLD_SERVICE.get(
        "linux" if sys.platform.startswith("linux") else sys.platform)
    if leftover:
        name, where = leftover
        # CHECK, do not assume. This said "is still registered"
        # unconditionally, which on a machine that never had the service
        # installed is a sentence about something that does not exist --
        # and the one thing a migration report must not do is invent work.
        # Windows keeps its tasks in a database rather than a file, so
        # there is nothing to stat; it is left to `install` to sort out.
        if where != "Task Scheduler" and os.path.exists(
                os.path.expanduser(where)):
            said.append("the old %s service is still registered and names "
                        "a binary that has moved -- run `overwatch install`"
                        " to replace it" % name)
    return said


def run_quietly(log=None):
    """run(), with its report printed and never its exception.

    Called on the way into every command, so a migration that goes wrong
    must not be the reason `status` cannot tell you what is wrong.
    """
    try:
        lines = run()
    except Exception as e:                     # noqa: BLE001 - see docstring
        lines = ["migration failed: %s" % e]
    if lines and log:
        for line in lines:
            log("[migrate] " + line)
    return lines
