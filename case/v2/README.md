# V2 — the wedge

A slanted screen on a flat base. **Two printed parts, no screws.**

| part | what it is | print it |
|---|---|---|
| `v2_shell.stl` | the wedge: slanted front with the window, vertical back with the port and honeycomb, closed top and sides, **open bottom** | on its **back** |
| `v2_base.stl` | the bottom, snaps in and carries the ESP32 | flat, posts up |

Everything enters from underneath — panel, loom and board — so the shell has
no seam anywhere you look at it.

```sh
openscad -D 'PART="shell"' -o v2_shell.stl overwatch_v2.scad
```

**90.8 wide x 70.0 deep x 53.2 tall.**

## Why the port reaches the back here, and could not in V1

A DevKitC carries its USB connector on a **short end, in the plane of the
board**. V1 laid it flat against a *vertical* back wall, so that port pointed
at a **side** wall — the back slot first cut there would have opened onto
solid board.

Lying it flat on a **horizontal** base turns the port to face horizontally.
Aim that end at the back wall and it exits the back. That is the whole trick,
and it only works because the base is flat.

## The depth is not 52, and not 52 plus the lean either

The panel leans back **over** the base, so the board sits under it — they
overlap in plan, and adding the two was wrong.

But the panel's back surface is a sloping line,
`z(y) = y·tan(lean) + panel_d/cos(lean)`, and the board has to start behind
wherever that line sits at the board's own height:

| ESP32 height | board starts at | case depth |
|---|---|---|
| 20 mm (dupont shells standing up) | 18.8 | 73.2 |
| 6 mm (bare board, cables led flat) | 13.7 | 68.1 |

**Lying the cables flat is worth 5 mm of case.** 70 is the built figure.

## 20 degrees

Sitting at a desk — eyes ~35 cm up, device ~40 cm away — your sight line drops
about **41°**, so a screen aimed straight at you would lean **49°**. That
costs 90 mm of depth and is not buildable here.

| lean | height | depth | off-axis |
|---|---|---|---|
| 15° | 48.3 | 64.9 | 34° |
| **20°** | **47.0** | **69.1** | **29°** |
| 25° | 45.3 | 73.1 | 24° |
| 30° | 43.3 | 77.0 | 19° |

29° off-axis is well inside what an ILI9341 takes without washing out. Past
25° the depth climbs faster than the viewing angle improves.

## One coordinate convention, stated once

`wedge()` rotates a profile by `[90,0,90]`, which maps local `(x,y,z)` to
world `(z,x,y)`. So throughout:

```
world X = WIDTH    (centred on 0)
world Y = DEPTH    (0 at the front edge, +depth at the back)
world Z = HEIGHT   (0 at the base)
```

The first version wrote every cut with Y as height and Z as depth — the other
way round — so the window, the port and the vent all landed outside the solid
and removed nothing. **The shell rendered as a featureless box**, which is
exactly what that looks like.

## The front face is thicker than the wall

The glass stands **3.4 mm proud of its board**, so 3.4 of face in front of the
PCB is what makes it finish flush; the board's own 1.6 sits behind that.
`front_t = 5.0`.

2 mm of wall would leave the glass standing 1.4 proud and the pocket cutting
clean through the face — a front you could see straight through, which is
what the second render showed.

The board is held by the two **ledges under the red strips**, as in V1, and
for the same reason: the glass is the full height of the board, so there is no
red top or bottom to grip.

## Two things the first print got wrong

**The base would not seat — it fouled the front.** The shell's front wall
leans, so the cavity's front boundary moves *back* as it rises:
`Y = z·tan(lean) + wall/cos(lean)`. The lip was drawn as a straight-sided
rectangle, so it cleared at the bottom and jammed harder the further in it
went:

| height | cavity starts at | lip front | |
|---|---|---|---|
| 0.0 | 2.13 | 2.25 | clears |
| 2.5 | 3.04 | 2.25 | **1.79 mm clash** |
| 5.0 | 3.95 | 2.25 | **1.70 mm clash** |

The lip's front is now set back to clear at its *tallest* point, which is the
only place that matters: `lip_h·tan(lean) + wall/cos(lean) + lip_fit` = 4.20.

**The ESP32 had nowhere to sit.** The first version was two bare pegs. They
held the board off the floor at roughly the right height and did nothing else
— nothing located it sideways, nothing stopped it sliding, nothing held it
down. Pushing a USB-C cable in would simply shove the board off them.

It is a cradle now: pads to set the height so the port centres on the hole,
side rails with a lip that the board slides under **from the back**, and a
stop at the front. The board slides back until its port end meets the shell's
back wall, so the connector lines up by construction rather than by careful
placement. Plug and unplug without the board moving.

## It only goes in one way

A rib on **one side rail** of the base's lip, 20 mm from the front, and a slot
for it in the shell's matching side wall.

It was on the *back* rail first, meant to be blocked by the leaning front wall
when reversed — but only by **0.52 mm**, because the lip's front is already set
back 1.95 mm to clear that lean, and a reversed base simply eats the slack. The
setback fights the keying.

Off-centre along the **length** cannot be symmetric. The rib spans Y 8–32;
reversed it lands at Y 38–62, where the shell's wall is solid. The two ranges
do not overlap at all, so it cannot even half-seat, and it is blocked by the
rib's full 1.25 mm with nothing to absorb it.

**24 × 4 mm, standing 1.5 proud.** It was 10 × 3 first, which keyed correctly
and could not be *found* — at that size it reads as a print artefact rather
than a feature, and a tab that small snaps off the first time the base is
prised out. Length is free here, since the blocking depth is what does the
keying, so it buys visibility and strength for nothing.

Telling front from back by eye, if you need to: the **finger notch** is on the
front edge, the **cradle rails** are at the back, and the lip sits 4.2 mm in at
the front against 2.25 at the back.

## Room for the flex

The glass is 69 wide on an 86 board, so its flex has to reach the PCB at one of
the two **short** edges — the 8 mm and 9 mm red strips. The pocket gave those
edges **0.4 mm**, which is nothing: a flex that wraps the edge, or merely
stands proud of it, is gripped by the pocket wall. A panel went white after
being fitted, and this is the likeliest reason.

Both short edges are now relieved by `flex_gap` (1.5 mm), over the middle of
the edge only. Relieving the whole edge would leave the board unlocated in X
and the picture would wander in the window; `flex_land` (9 mm) keeps a land at
each corner to place it.

Both edges, because which one the flex exits is not something a photo settles,
and relieving the unused side costs nothing.

## The number to tune

`lip_fit` (0.25 per side) is how tightly the base sits in the shell.

| symptom | change |
|---|---|
| base falls out or rattles | **lower** by 0.05 |
| will not seat, or the shell bows | **raise** by 0.05 |

Only `v2_base` needs reprinting; the shell is unchanged.

## Print notes

The shell prints **on its back**: the back is flat, the open bottom faces
sideways, and the slanted front becomes a 20° overhang — inside the 45° rule,
so no supports.
