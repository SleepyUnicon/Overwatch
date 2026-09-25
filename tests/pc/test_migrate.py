"""The Blink -> Overwatch move, which runs once on somebody's real machine.

These are written against a fake HOME rather than mocks, because what is
being tested is what ends up on disk: a signing key that survived, a
settings.json that still points at a file that exists, and a marker whose
contents `uninstall` will still recognise as ours.
"""
import json
import os

import pytest

from pc import cli, migrate


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A HOME with a Blink installation in it, as 1.3.3 would have left it."""
    monkeypatch.setattr(cli, "_home", lambda: str(tmp_path))
    old = tmp_path / ".blink"
    (old / "bin").mkdir(parents=True)
    (old / "blink-statusline.sh").write_text("#!/bin/sh\necho hi\n")
    (old / "blink-hook.sh").write_text("#!/bin/sh\nexit 0\n")
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


def test_it_says_the_old_service_is_still_registered(home):
    said = migrate.run()
    assert any("still registered" in line for line in said)


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
