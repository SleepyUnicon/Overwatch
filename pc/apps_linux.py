"""The launcher's Linux half: desktop entries instead of .app bundles.

pc/webconfig.py finds apps by looking for `.app` directories under
/Applications, and pc/widgets.py launches one with `open -a`. Neither means
anything on Linux, so the picker offered an empty list and a tile ran the app's
NAME as a bare command -- which works for "firefox" by accident and for almost
nothing else.

Linux has a standard for this: the freedesktop Desktop Entry spec. Every
installed application leaves a `.desktop` file in a known place, carrying the
name a person recognises and the command that starts it.

Nothing new is required. These are ini files read with configparser, from the
standard library, and the command comes out of the file rather than from a
launcher tool that may not be installed.
"""
import configparser
import os
import shlex

# Where the spec says to look, plus the two packaging systems that put their
# exports somewhere else. XDG_DATA_DIRS would be the strictly correct source
# for the middle three, but it is frequently unset in the environment a login
# service inherits -- and a launcher that works from a terminal and not from
# the daemon is worse than one that simply looks in the usual places.
APP_DIRS = (
    os.path.expanduser("~/.local/share/applications"),
    "/usr/local/share/applications",
    "/usr/share/applications",
    os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
    "/var/lib/flatpak/exports/share/applications",
    "/var/lib/snapd/desktop/applications",
)

# Field codes the spec says a launcher must expand: %f %F %u %U and friends.
# There is nothing to expand them WITH -- the board taps a tile, it does not
# hand over a document -- so they are dropped. Left in, they arrive as literal
# "%U" arguments and some applications open a file named that.
_FIELD_CODES = {"%f", "%F", "%u", "%U", "%d", "%D", "%n", "%N",
                "%i", "%c", "%k", "%v", "%m"}


def _read_entry(path):
    """(name, argv) from one .desktop file, or (None, None) to skip it."""
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        # utf-8 by spec. errors="replace" rather than raising: one badly
        # encoded file installed by one package must not empty the picker.
        with open(path, encoding="utf-8", errors="replace") as f:
            cp.read_file(f)
    except (OSError, configparser.Error):
        return None, None
    if not cp.has_section("Desktop Entry"):
        return None, None
    e = cp["Desktop Entry"]

    if e.get("Type", "Application") != "Application":
        return None, None
    # NoDisplay is "this exists but is not for people" -- MIME handlers,
    # settings panels, half of what ships on a desktop. Hidden means deleted.
    if e.get("NoDisplay", "false").strip().lower() == "true":
        return None, None
    if e.get("Hidden", "false").strip().lower() == "true":
        return None, None

    name = (e.get("Name") or "").strip()
    exec_line = (e.get("Exec") or "").strip()
    if not name or not exec_line:
        return None, None

    try:
        argv = shlex.split(exec_line)
    except ValueError:
        return None, None
    argv = [a for a in argv if a not in _FIELD_CODES]
    # A trailing field code can also be glued to an argument ("--file=%f").
    argv = [a for a in argv if not any(c in a for c in _FIELD_CODES)]
    if not argv:
        return None, None

    if e.get("Terminal", "false").strip().lower() == "true":
        # A terminal application launched from a login service has no terminal
        # to appear in, so it would start and vanish. Not offered rather than
        # offered and dead.
        return None, None
    return name, argv


def entries():
    """{display name: argv} for every application worth showing.

    First definition wins. The directories are searched in precedence order --
    a user's own ~/.local override before the system copy -- which is the
    order the spec gives and the one that makes a customised launcher work.
    """
    found = {}
    for d in APP_DIRS:
        if not os.path.isdir(d):
            continue
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for entry in names:
            if not entry.endswith(".desktop"):
                continue
            name, argv = _read_entry(os.path.join(d, entry))
            if name and name not in found:
                found[name] = argv
    return found


def names():
    """Every launchable application, sorted the way a person reads a list."""
    return sorted(entries(), key=str.lower)


def argv_for(name):
    """The command that starts `name`, as a LIST, or None.

    A list and never a shell string, for the reason pc/widgets._argv_for gives:
    the name arrives from a file the customer owns, and the difference between
    a list and a string is the difference between launching an app called
    `x; rm -rf ~` and running the second half of it.
    """
    if not name:
        return None
    table = entries()
    argv = table.get(name)
    if argv:
        return argv
    # Case-insensitively, because the config may have been typed by hand or
    # written by an older version that stored the name differently.
    low = name.lower()
    for have, argv in table.items():
        if have.lower() == low:
            return argv
    return None
