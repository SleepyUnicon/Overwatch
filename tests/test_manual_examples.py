"""The manual's examples have to be things that actually work.

A configuration example in a printed document is worse than no example when it
is wrong: the reader has no way to tell, they copy it, the daemon drops the
slot, and the tile they were trying to make silently is not there. The kit goes
to people who did not build this and cannot read the source to check.

So the example is extracted from the document and run through the same
validator the daemon uses. If someone edits one without the other, this fails.
"""
import json
import pathlib
import re

from pc import apptools, widgets

MANUAL = (pathlib.Path(__file__).resolve().parent.parent
          / "docs" / "print" / "manual.html")


def _unescape(s):
    return (s.replace("&quot;", '"').replace("&lt;", "<")
             .replace("&gt;", ">").replace("&amp;", "&"))


def _apps_example():
    html = MANUAL.read_text(encoding="utf-8")
    m = re.search(r"<pre>(\[\s*\n.*?)</pre>", html, re.S)
    assert m, "the apps.json example has gone from the manual"
    return json.loads(_unescape(m.group(1)))


def test_the_apps_example_is_valid_json():
    _apps_example()          # raises if it is not


def test_the_apps_example_has_exactly_the_slots_there_are():
    """Six, because the launcher has six. An example with five would teach the
    reader the wrong shape of file."""
    assert len(_apps_example()) == widgets.SLOTS


def test_every_entry_in_the_example_survives_the_real_validator():
    """Not a re-implementation of the rules -- the daemon's own clean_entry,
    so the example cannot drift away from what the code accepts."""
    for i, entry in enumerate(_apps_example()):
        cleaned = widgets.clean_entry(entry)
        if entry == "":
            assert cleaned is None, "an empty slot is meant to be dropped"
            continue
        assert cleaned is not None, (
            "slot %d of the manual's example is rejected: %r" % (i, entry))


def test_the_example_shows_all_three_kinds_of_slot():
    """The whole point of the section. If someone trims it to plain names the
    keys and run forms stop being documented by anything but prose."""
    kinds = set()
    for entry in _apps_example():
        if isinstance(entry, str) and entry:
            kinds.add("app")
        elif isinstance(entry, dict):
            kinds.update(k for k in ("keys", "run") if k in entry)
    assert kinds == {"app", "keys", "run"}, kinds


def test_every_icon_the_manual_names_exists():
    """The manual lists the icon keys. An icon that is not there is drawn as
    text with no explanation, so a wrong list sends someone hunting."""
    html = MANUAL.read_text(encoding="utf-8")
    section = html.split("<code>icon</code></strong> — optional")[1]
    section = section.split("</li>")[0]
    named = set(re.findall(r"<code>([a-z0-9]+)</code>", section))
    assert named, "the manual stopped listing icon names"
    assert named <= set(widgets.ICON_KEYS), named - set(widgets.ICON_KEYS)


def test_the_manual_names_every_icon_there_is():
    """And the other direction: an icon nobody documents is one nobody uses."""
    html = MANUAL.read_text(encoding="utf-8")
    section = html.split("<code>icon</code></strong> — optional")[1]
    section = section.split("</li>")[0]
    named = set(re.findall(r"<code>([a-z0-9]+)</code>", section))
    assert set(widgets.ICON_KEYS) <= named, set(widgets.ICON_KEYS) - named


def test_the_cover_does_not_carry_a_hand_typed_version():
    """It did, and it read 2.1.0 for nine releases -- through 2.2.0 to 2.3.2 --
    on the front of the document that goes in the box. tools/make_kit.sh fills
    @VERSION@ and @DATE@ at build time; the cover must use them."""
    html = MANUAL.read_text(encoding="utf-8")
    cover = html.split('class="meta"')[1].split("</div>")[0]
    assert "@VERSION@" in cover and "@DATE@" in cover
    # The Release line only. "PolyForm Noncommercial 1.0.0" two lines below is
    # a licence version and is meant to be written out.
    release = [l for l in cover.splitlines() if "<b>Release</b>" in l][0]
    assert not re.search(r"\b\d+\.\d+\.\d+\b", release), (
        "a literal version number is back on the cover: %s" % release.strip())


# --- the tools.json example -------------------------------------------


def _tools_example():
    html = MANUAL.read_text(encoding="utf-8")
    m = re.search(r"<pre>(\{\s*\n.*?)</pre>", html, re.S)
    assert m, "the tools.json example has gone from the manual"
    return json.loads(_unescape(m.group(1)))


def test_the_tools_example_is_valid_json():
    _tools_example()


def test_every_tool_in_the_example_survives_the_real_validator():
    """Same bargain as the apps.json example: the reader cannot tell a bad one
    from a good one, and the kit goes to people who cannot read the source."""
    for app, tools in _tools_example().items():
        assert tools, app
        for t in tools:
            assert apptools.clean_tool(t) is not None, (app, t)


def test_the_example_stays_inside_the_tile_limit():
    for app, tools in _tools_example().items():
        assert len(tools) <= apptools.MAX_TOOLS, app


def test_the_manual_names_the_shortcuts_that_are_refused():
    """If the document says Overwatch refuses these, it has to be refusing
    exactly these -- a promise about safety that drifts is worse than none."""
    html = MANUAL.read_text(encoding="utf-8")
    # The refusal SENTENCE only. The paragraph after it says to use a
    # launcher `keys` tile instead, and "keys" is not a shortcut.
    section = html.split("Why the shipped tiles only change tools")[1]
    section = section.split("So Overwatch refuses")[1].split(".")[0]
    named = set(re.findall(r"<code>([a-z+]+)</code>", section))
    assert named, "the manual stopped naming the refused shortcuts"
    for keys in named:
        assert apptools.clean_tool({"label": "X", "keys": keys}) is None, keys


def test_the_manual_agrees_about_how_many_tiles_there_are():
    html = MANUAL.read_text(encoding="utf-8")
    assert "six to a page" in html or "Six is the limit" in html
    assert apptools.MAX_TOOLS == 6
