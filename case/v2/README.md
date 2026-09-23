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
