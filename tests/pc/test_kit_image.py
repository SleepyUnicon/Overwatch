"""Which .bin `overwatch flash` is willing to write to a blank board.

This path had no tests at all, which is a poor match for what it does: a kit
builder runs it exactly once, on a chip that has never been programmed, and a
mistake here looks identical to a soldering fault. There is no second signal --
the screen is dark either way.

The distinction being defended is between two files whose names differ by four
characters:

  overwatch-2.1.0.bin   the MERGED image -- MCUboot at 0x1000, app at 0x20000,
                        signed confirmed. tools/package_firmware.py makes it.
  overwatch-fw.bin      the app slot alone. What every release publishes, and
                        correct for an OTA, which lands in a board whose
                        bootloader is already there.

Flashing the second at offset 0 produces a board that does not boot.
"""
import os

from pc import cli


def test_a_versioned_image_is_a_kit_image():
    assert cli._is_kit_image("overwatch-2.1.0.bin")
    assert cli._is_kit_image("overwatch-1.3.3.bin")
    assert cli._is_kit_image("overwatch-10.20.30.bin")


def test_the_release_asset_is_not_a_kit_image():
    """The regression this file exists for.

    Assembling a unit means visiting the release page, and `overwatch-fw.bin`
    is sitting on it. Downloading the lot into dist/ is the obvious thing to
    do, and the old test -- starts with "overwatch-", ends with ".bin" --
    admitted it.
    """
    assert not cli._is_kit_image("overwatch-fw.bin")


def test_near_misses_are_rejected():
    for name in ("overwatch-.bin", "overwatch-2.1.bin", "overwatch-2.1.0.0.bin",
                 "overwatch-2.1.0-rc1.bin", "overwatch-v2.1.0.bin",
                 "notoverwatch-1.0.0.bin", "overwatch-2.1.0.tar.gz"):
        assert not cli._is_kit_image(name), name


def _stage(tmp_path, monkeypatch, *names):
    """A fake download directory, with `names` created oldest-first."""
    home = tmp_path / "overwatch"
    home.mkdir()
    monkeypatch.setattr(cli, "_self_path", lambda: str(home / "overwatch"))
    for i, n in enumerate(names):
        p = home / n
        p.write_bytes(b"\x00")
        # Distinct mtimes, ascending: _kit_image breaks ties on newest.
        os.utime(p, (1_000_000 + i * 60, 1_000_000 + i * 60))
    return home


def test_the_newest_versioned_image_wins(tmp_path, monkeypatch):
    """Re-running the packager must not leave the previous version to be
    picked up silently."""
    home = _stage(tmp_path, monkeypatch,
                  "overwatch-2.0.9.bin", "overwatch-2.1.0.bin")
    assert cli._kit_image() == str(home / "overwatch-2.1.0.bin")


def test_the_release_asset_does_not_win_even_when_it_is_newest(tmp_path,
                                                              monkeypatch):
    """The ordering that makes this dangerous.

    A builder flashes a board, then downloads the release assets -- so
    overwatch-fw.bin is the NEWEST .bin in the directory, and "newest wins"
    would hand it straight to esptool.
    """
    home = _stage(tmp_path, monkeypatch,
                  "overwatch-2.1.0.bin", "overwatch-fw.bin")
    assert cli._kit_image() == str(home / "overwatch-2.1.0.bin")


def test_an_explicit_path_is_an_instruction(tmp_path, monkeypatch):
    _stage(tmp_path, monkeypatch, "overwatch-2.1.0.bin")
    other = tmp_path / "somewhere-else.bin"
    other.write_bytes(b"\x00")
    assert cli._kit_image(str(other)) == str(other)


def test_an_explicit_path_that_does_not_exist_is_not_silently_replaced(
        tmp_path, monkeypatch):
    """Falling back to a directory scan here would flash something the
    builder did not name, having just been told the file they meant is
    missing."""
    _stage(tmp_path, monkeypatch, "overwatch-2.1.0.bin")
    assert cli._kit_image(str(tmp_path / "nope.bin")) is None
