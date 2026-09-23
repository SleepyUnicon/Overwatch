# Overwatch

A personal fork of [BLINK](https://github.com/KfirLevy258/Blink) that adds two
widget pages beside the usage gauges: a Spotify transport and an app launcher
for the Mac mini.

Written September 2026. Read this first if you are coming back to it cold.

## What state it is in

**The computer half is proven. The board half has never been compiled.**

That split is the whole status, and it is worth being blunt about because the
two halves feel equally finished when you read the code and are not.

| | State |
|---|---|
| `pc/widgets.py`, `pc/spotify.py`, `pc/widget_bridge.py` | 32 tests passing, exercised end to end against the real bridge |
| `firmware/src/ui_launcher.*`, `ui_spotify.*`, `ui_pages.*` | Written against the real LVGL 9 and Zephyr APIs in this tree. Never built. Expect compile errors on the first run. |
| The page-stack logic | Modelled and exercised over 17 transitions, in Python. That model is not the C. |

Nothing here has touched a board. There isn't one yet.

## The idea, in one paragraph

BLINK's board already talks back to the computer -- `pref`, `ping`,
`ota_query` and `ota_flash` have gone up the cable since the first release, and
`ota_flash` means a tap on the panel already makes the computer download a file
and reflash the device. Launching an app is a smaller claim on the host than
the product already makes. So the widgets ride the link that exists rather than
adding one.

## The case

`case/` holds a two-part 3D-printable enclosure - the weightlifter holding the
barbell, screen as its body - modelled parametrically in OpenSCAD from the
reference artwork's own proportions. It renders and exports clean STLs and has
never been printed. `case/README.md` carries the detail.

It does not depend on the firmware at all. If the widget build stalls, the case
still prints and still holds a board running upstream's stock firmware.

## The reveal

`reveal/` builds an eight-second product film headless in Blender, from the
same STLs the case prints from - change the SCAD, re-export, re-render.
`reveal/README.md` has the shot breakdown, the knobs, and the four Blender 5
API changes that each cost a debugging round.

## What was added

    firmware/src/ui_launcher.{c,h}   six buttons, app icons, one message each
    firmware/src/icons_gen.h         generated: 6 icons, RGB565A8, 28 KB flash
    tools/encode_icons.py            PNG -> that header
    firmware/src/ui_spotify.{c,h}    now playing, three transport buttons
    firmware/src/ui_pages.{c,h}      the flat page stack and its tap rail
    pc/widgets.py                    slot number -> app, and the ack
    pc/spotify.py                    one osascript call, three commands
    pc/widget_bridge.py              Bridge subclass; no edits to his bridge
    tests/pc/test_widgets.py         14 tests
    tests/pc/test_spotify.py         18 tests

## What was changed in his files

143 lines added, 6 removed, across five files. `git status` still shows it
un-committed on purpose -- that is the clearest view of the fork there is.

- `proto.c` / `proto.h` -- two send functions, three inbound handlers
- `ui_settings.c` -- navigation routed through `ui_pages_can_step()` instead of
  `usage_view_can_page()`, so the vertical swipe walks the longer stack
- `main.c` -- `ui_pages_init()` at three mode sites, `ui_spotify_tick_1s()`
  beside the gauge tick, `ui_pages_detach()` at the deinit
- `CMakeLists.txt` -- three sources
- `prj.conf` -- `CONFIG_LV_USE_IMAGE=y` for the launcher's icons

Everything else is additive. The daemon side is a *subclass*, which is
deliberate: he ships releases on his own cadence, and a fork that patches his
files turns every one of them into a merge conflict.

## Decisions worth not re-litigating

**Overlays, never a second LVGL screen.** `usage_view_deinit()` records why --
with no PSRAM the heap cannot hold two, which is why the settings panel is an
overlay too. A second screen does not fail at build time. It fails as an
allocation returning NULL somewhere in a repaint, once both are populated.

**No new gesture, because there were none left.** Left opens settings, right
replays the boot clip, up and down walk the stack, and both edge strips are
already tap targets. The widget pages are reached by continuing past the end of
the providers -- `usage_view_can_page()` was already the function that knows
where that end is.

**Every navigation has a tap path.** Swipes land about half the time on this
panel and that is physics, not tuning. See `docs/multi-provider.md` 4d before
touching any of it.

**The board sends a slot number, never an app name or a path.** The computer
owns the table. Nothing the panel can say names a program the daemon has not
already agreed to run.

**`tell application "Spotify"` launches Spotify.** The read script is guarded
with `application "Spotify" is running`, which does not. There is a test
pinning that string, because it is the kind of line someone tidies away.

**Spotify's `duration` is milliseconds; `player position` is seconds.** Range-
checked at the parser, which is the only place the unit is known -- the same
way this codebase already handles the desktop cache sitting beside Codex.

## Where to pick up

1. Buy an **ESP32-2432S028R**. The R matters: resistive touch, XPT2046. The
   whole swipe implementation is built around its physics.
2. Toolchain: Homebrew, then **Zephyr 4.3.x and SDK 0.17.4**. Not 4.4.0, which
   cannot build this firmware, and do not register SDK 1.0.1 alongside 0.17.4.
3. Generate your own signing key into `~/.blink/`. Your board will then accept
   updates only from you, never from his feed. Back it up off the machine.
4. **Flash his stock firmware first, unmodified.** It separates "can I build
   and flash at all" from "does my code work", and if step 2 was miserable you
   find out without my code confusing the question.
5. Then build this tree. `firmware/README.md` has the exact commands and
   `tools/dev.sh flash` is the loop -- it stops the daemon first, because only
   one process can own the serial port.
6. Point `claude_usage_bridge.py` at `WidgetBridge` instead of `Bridge`.

Known unknowns for the first build: the LVGL symbol names
(`LV_SYMBOL_PLAY`/`PAUSE`/`PREV`/`NEXT`/`UP`/`DOWN`), and whether the rail's
160x40 tap halves are big enough -- 48 px was his measured floor and these are
40. `ui_pages.c` names the remedy if they miss.

## Licence

Upstream is PolyForm Noncommercial 1.0.0 with an added permission. Build as
many as you like for yourself, change them, give them away. **Selling is the
one thing forbidden** -- a unit, a printed case, the software, or any product
whose substantial value is a work based on it. Renaming it Overwatch does not
change that.

If you pass a copy to anyone, `LICENSE` and its `Required Notice:` line go with
it. That is the licence's own requirement, not a courtesy.
