"""The Blink -> Overwatch move, which runs once on somebody's real machine.

These are written against a fake HOME rather than mocks, because what is
being tested is what ends up on disk: a signing key that survived, a
settings.json that still points at a file that exists, and a marker whose
contents `uninstall` will still recognise as ours.
"""
import json
import os
import sys

import pytest

from pc import cli, migrate


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A HOME with a Blink installation in it, as 1.3.3 would have left it."""
    monkeypatch.setattr(cli, "_home", lambda: str(tmp_path))
    old = tmp_path / ".blink"
    (old / "bin").mkdir(parents=True)
    for d in (old, old / "bin"):
        # The shims name the state directory INSIDE themselves, which is
        # the whole point of test_the_shims_stop_writing_to_the_old_home.
        (d / "blink-statusline.sh").write_text(
            '#!/bin/sh\nDIR="$HOME/.blink/state"\n')
        (d / "blink-hook.sh").write_text(
            '#!/bin/sh\nDIR="$HOME/.blink/$sub"\nexit 0\n')
    (old / "ota_signing_key_p256.pem").write_text("-----BEGIN EC KEY-----\n")
    (old / "apps.json").write_text('["Claude", "", "", "", "", ""]')
    (old / "statusline-installed-command").write_text(
        "sh %s/.blink/blink-statusline.sh\n" % tmp_path)
    (old / "hooks-installed-commands").write_text(
        "sh %s/.blink/blink-hook.sh SessionStart\n" % tmp_path)
    return tmp_path


@pytest.fixture
def settings(home):
    """A settings.json pointing into the old home, as the installer wrote it."""
    p = home / ".claude"
    p.mkdir()
    sp = p / "settings.json"
    sp.write_text(json.dumps({
        "statusLine": {"type": "command",
                       "command": "sh %s/.blink/blink-statusline.sh" % home},
        "hooks": {"SessionStart": [{"hooks": [{
            "type": "command",
            "command": "sh %s/.blink/blink-hook.sh SessionStart" % home}]}]},
    }, indent=2))
    return sp


def test_it_knows_when_there_is_nothing_to_do(home):
    migrate.run()
    # Second time is a no-op: the old home is gone, so needed() is False and
    # a re-run must not report a move it did not make.
    assert migrate.run() == []


def test_both_present_is_not_a_migration(home):
    """Two installations is not one that moved, and picking a winner quietly
    is how somebody loses a signing key."""
    (home / ".overwatch").mkdir()
    assert migrate.needed() is False
    assert migrate.run() == []
    assert (home / ".blink").is_dir()          # untouched


def test_the_state_moves_whole(home):
    migrate.run()
    new = home / ".overwatch"
    assert not (home / ".blink").exists()
    assert (new / "ota_signing_key_p256.pem").read_text().startswith(
        "-----BEGIN EC KEY-----")
    assert json.loads((new / "apps.json").read_text())[0] == "Claude"


def test_the_shims_are_renamed(home):
    migrate.run()
    new = home / ".overwatch"
    assert (new / "overwatch-statusline.sh").exists()
    assert (new / "overwatch-hook.sh").exists()
    assert not (new / "blink-statusline.sh").exists()


def test_settings_json_points_at_a_file_that_exists(home, settings):
    migrate.run(settings_path=str(settings))
    data = json.loads(settings.read_text())
    cmd = data["statusLine"]["command"]
    assert ".blink" not in cmd
    # The whole point: the path it names has to be real afterwards.
    assert os.path.exists(cmd.split()[-1])
    hook = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert os.path.exists(hook.split()[1])


def test_the_markers_are_rewritten_so_uninstall_still_recognises_them(home):
    """install_hooks compares settings.json against this marker to decide
    what is ours. A marker left holding the old command makes `uninstall`
    walk away from hooks it installed itself."""
    migrate.run()
    new = home / ".overwatch"
    marker = (new / "hooks-installed-commands").read_text()
    assert ".blink" not in marker
    assert "overwatch-hook.sh" in marker


def _apply(pairs, text):
    for old, new in pairs:
        text = text.replace(old, new)
    return text


def test_the_rewrite_handles_the_spellings_windows_actually_uses(monkeypatch):
    """The bug that had five of these failing on every push since the rebrand.

    _pairs() was built from os.sep, which is a backslash on Windows -- but
    every string it has to rewrite there is spelled with FORWARD slashes:

      - the shims are POSIX sh and compute "$HOME/.blink/$sub" everywhere;
      - the commands in settings.json and in both markers go through
        install_statusline.windows_bash_path, which turns every backslash into
        a forward slash because a backslash is an escape under Git Bash, and
        replaces the home with a literal "$USERPROFILE".

    So on Windows the pairs read `\\.blink\\blink-hook.sh`, matched nothing, and a
    migration moved the directory while leaving every reference inside it
    pointing at ~/.blink -- which the hook shim then recreated on the next tool
    call. Both separators now, so the mixed form works too.

    Driven through _pairs() with os.sep forced rather than through run(), so it
    runs on every platform: a fix only Windows CI can see is a fix that comes
    back.
    """
    monkeypatch.setattr(migrate.os, "sep", chr(92))
    pairs = migrate._pairs()

    for label, text in (
            ("the shim body, always forward slashes",
             '#!/bin/sh\nDIR="$HOME/.blink/$sub"\nexit 0\n'),
            ("a marker written by windows_bash_path",
             'bash "$USERPROFILE/.blink/blink-hook.sh" SessionStart'),
            ("a native path Python wrote",
             "C:" + chr(92) + "Users" + chr(92) + "k" + chr(92)
             + ".blink" + chr(92) + "blink-statusline.sh"),
            ("the two mixed together",
             "C:" + chr(92) + "Users" + chr(92) + "k" + chr(92)
             + ".blink/blink-hook.sh"),
    ):
        after = _apply(pairs, text)
        assert ".blink" not in after, "%s: still names the old home" % label
        assert "blink-" not in after, "%s: still names an old shim" % label
        assert ".overwatch" in after, "%s: nothing was moved" % label


def test_posix_pairs_are_unchanged_by_the_windows_fix(monkeypatch):
    """Adding the second separator must not have changed POSIX behaviour.

    With os.sep == "/" the two spellings collapse to one, so the list is the
    same seven pairs in the same order it always was. Order is load-bearing --
    the docstring on _pairs() says why -- so this pins the sequence, not just
    the set.
    """
    monkeypatch.setattr(migrate.os, "sep", "/")
    assert migrate._pairs() == [
        ("/.blink/blink-statusline.sh", "/.overwatch/overwatch-statusline.sh"),
        ("/.blink/blink-hook.sh", "/.overwatch/overwatch-hook.sh"),
        ("/.blink/blink-bridge.vbs", "/.overwatch/overwatch-bridge.vbs"),
        ("/.blink", "/.overwatch"),
        ("blink-statusline.sh", "overwatch-statusline.sh"),
        ("blink-hook.sh", "overwatch-hook.sh"),
        ("blink-bridge.vbs", "overwatch-bridge.vbs"),
    ]


def test_the_directory_is_replaced_before_the_bare_name(home):
    """`/.blink` is a substring of `/.blink/blink-hook.sh`. Replacing the
    directory first leaves `/.overwatch/blink-hook.sh`: wrong, and plausible
    enough to survive a read-through."""
    pairs = migrate._pairs()
    keys = [a for a, _ in pairs]
    d = os.sep + ".blink"
    assert keys.index(d) > 0
    for a in keys[:keys.index(d)]:
        assert a.startswith(d + os.sep)


def test_the_rewrite_does_not_depend_on_how_home_is_spelled(home, settings):
    """The one a rehearsal against a real machine caught.

    settings.json holds whatever spelling of home the installer saw, which
    need not be the one expanduser returns now. When the absolute form
    missed, the bare shim names still matched and produced
    `/somewhere-else/.blink/overwatch-statusline.sh` -- migrated-looking
    and broken.
    """
    settings.write_text(settings.read_text().replace(
        str(home), "/somewhere/else"))
    migrate.run(settings_path=str(settings))
    text = settings.read_text()
    assert ".blink" not in text
    assert "/somewhere/else/.overwatch/overwatch-statusline.sh" in text


@pytest.mark.skipif(sys.platform == "win32",
                    reason="there is no file to stat: Windows keeps its "
                           "Scheduled Tasks in a database, so run() reports "
                           "nothing by design. Pinned below instead.")
def test_it_says_the_old_service_is_still_registered(home, monkeypatch):
    monkeypatch.setattr(migrate.os.path, "exists",
                        lambda p: True if ".plist" in str(p)
                        or "systemd" in str(p) else os.path.lexists(p))
    said = migrate.run()
    assert any("still registered" in line for line in said)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only behaviour")
def test_on_windows_it_says_nothing_about_a_scheduled_task(home):
    """The other half of the test above, and a deliberate difference.

    The other three platforms register a login service as a FILE, so run() can
    stat it and only mention it when it is really there. Windows keeps its
    Scheduled Tasks in a database with nothing to stat, so run() says nothing
    and leaves it to `overwatch install` to sort out -- see the comment beside
    the "Task Scheduler" check.

    Without this, the skip above is the only thing this suite says about
    Windows here, and a skip is not a statement about behaviour.
    """
    assert not any("still registered" in line for line in migrate.run())


def test_it_does_not_invent_a_service_that_was_never_installed(home):
    """It said this unconditionally. On a machine that never had the login
    service, that is a sentence about something which does not exist, and
    the one thing a migration report must not do is invent work."""
    said = migrate.run()
    assert not any("still registered" in line for line in said)


def test_a_failure_is_reported_rather_than_raised(home, monkeypatch):
    def boom(*a, **k):
        raise OSError("disk went away")
    monkeypatch.setattr(migrate.os, "rename", boom)
    monkeypatch.setattr(migrate.shutil, "move", boom)
    said = migrate.run()
    assert said and "could not move" in said[0]
    assert (home / ".blink").is_dir()          # nothing lost


def test_run_quietly_swallows_anything(home, monkeypatch):
    monkeypatch.setattr(migrate, "run", lambda: 1 / 0)
    lines = migrate.run_quietly()
    assert lines and "migration failed" in lines[0]


def test_the_shims_stop_writing_to_the_old_home(home):
    """Renaming the file is not enough. The hook shim computes its state
    directory as "$HOME/.blink/$sub", so a shim that moved and was renamed
    still writes where it always did -- which recreated ~/.blink within a
    minute of the move, on the first hook that fired afterwards."""
    migrate.run()
    new = home / ".overwatch"
    for sub in (".", "bin"):
        for name in ("overwatch-hook.sh", "overwatch-statusline.sh"):
            body = (new / sub / name).read_text()
            assert ".blink" not in body, "%s/%s still writes to the old home" % (sub, name)
            assert ".overwatch" in body
