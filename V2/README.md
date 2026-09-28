# V2 — pages the board does not have to be rebuilt for

Everything in here exists to answer one problem: **every page is hand-written C.**
`ui_music.c`, `ui_launcher.c`, the gauges. Adding a feature means writing a page,
building the firmware, cutting a release and pushing an OTA to every unit.

That cost is invisible in any single feature and enormous across thirty. It also
quietly bends every idea toward "extend the page that already exists", which is
how a device meant to watch a whole desk ends up only watching one thing.

So: **one C page that renders a layout described by the daemon.** Write it once.
After that a new feature is Python only — no firmware build, no release, no OTA,
and it can be changed on a running unit in the time it takes to restart a
daemon.

## What a panel is

A title, up to five rows of label-and-value, and up to three tiles you can
press. That is the whole vocabulary, and it is deliberately small:

| Feature | How it maps |
| --- | --- |
| Shop takings today | rows: orders, revenue, last order |
| 3D print progress | rows: job, percent, ETA, nozzle, bed |
| Mac vitals | rows: CPU, memory, disk, network |
| Next meeting | rows: what and when; tile: "Join" |
| Mic mute | row: state; tile: "Mute" |

Five rows covers nearly everything worth glancing at. Anything that does not
fit is probably two panels.

## Why it is shaped by two hard numbers

**`LINE_MAX` is 512 bytes** (`firmware/src/proto.c`). One panel has to arrive in
one line, so the vocabulary is budgeted against it. Five rows and three tiles is
409 bytes at the maximum field lengths below, leaving about a hundred spare. Six
rows fits too, and was not taken: the margin is worth more than the row.

| Field | Max |
| --- | --- |
| title | 20 |
| row label | 14 |
| row value | 18 |
| tile label | 12 |

**RAM is the scarce resource.** `dram1_0_seg` is 74% full and the WiFi build
already fails to link by 18 KB. So: fixed-size static buffers, no allocation,
LVGL objects built once at init and only ever *updated* — never created and
destroyed as panels change. `ui_launcher.c` says the same thing about its own
tiles and it is right: the LVGL pool has no room for churn.

## The message

Flat keys, because `msg_parse.c` reads flat keys and nothing else — no arrays,
no nesting. `after_colon()` matches `"key"` followed by a colon, so short keys
cannot collide with longer ones (`"t"` does not match inside `"title"`).

Daemon to board:

```json
{"t":"panel","v":2,"p":0,"title":"Shop today","n":3,
 "l0":"Orders","v0":"14","c0":"ok",
 "l1":"Revenue","v1":"KSh 48,200",
 "l2":"Last","v2":"3 min ago","c2":"dim",
 "tn":1,"b0":"Refresh"}
```

* `p` — which panel, `0` to `PANEL_MAX - 1`
* `n` — how many rows are present
* `l<i>` `v<i>` — label and value
* `c<i>` — tone: `ok` `warn` `bad` `dim`, absent means ordinary ink. These are
  roles, not colours; the board resolves them through `ui_theme()` so a panel
  looks right in both themes without the daemon knowing which is on.
* `tn`, `b<i>` — tile count and labels

Board to daemon, when a tile is pressed:

```json
{"t":"panel_tap","v":2,"p":0,"i":0}
```

The board sends **which tile**, never what it means — the same split the
launcher already uses, where the board sends a slot number and `pc/widgets.py`
decides what to run. A message from the panel cannot name an action this side
has not already agreed to.

## Where it sits in the navigation

`ui_pages.h` describes a cross: gauges in the centre, music left, launcher
right, settings up, face down. All four directions were taken.

Panels take **down**, and the face keeps the tap cue it already has at the
bottom of the gauge screen. That cue is not new and not a workaround — it is
how the face is reached today, and the vertical swipe to it was redundant with
it.

With more than one panel, left and right move between them *within* the panel
page, and up comes home. That keeps the rule the cross exists to protect: one
move out, one move back.

**This is the one decision here worth arguing with.** It changes a navigation
the cross was carefully designed around, and it is a one-line change to undo.

## Layout

The files here are new; the hooks into existing ones are deliberately small.

```
V2/
  README.md           this
  firmware/
    ui_panel.h        the page's contract
    ui_panel.c        the page
  panel.py            the daemon half: build panels, route taps
```

Three existing files gain a few lines each, and nothing more:

* `firmware/CMakeLists.txt` — the new sources and include path
* `firmware/src/ui_pages.h/.c` — one page in the enum, one hook
* `pc/widget_bridge.py` — register the panel widget

That split is on purpose. Experimental work lives here where it can be read,
changed and abandoned in one place; the mature firmware keeps its shape.
