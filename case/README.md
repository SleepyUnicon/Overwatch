# The Overwatch case

A bezel that shows the **picture and nothing else**, and an **empty** tray that
plugs into the back of it. Two printed parts, no screws, no posts, nothing
inside the body at all.

| part | | print it |
|---|---|---|
| `front_bezel.stl` | 90.8 × 54.8 × 11.2 | face **down** |

Assembled the case is **46.2 mm** front to back — the bezel stands 6.2 in front of the tray, so the tray's own 40.0 is not the whole depth.
| `back_tray.stl` | 90.8 × 53.1 × 40.0 | open side **up** |

```sh
openscad -D 'PART="front"' -o front_bezel.stl overwatch_case.scad
```

## What changed, and why

The version before this had two faults that between them cost a panel.

**The aperture was sized to the glass, and the glass was a press fit in it** —
0.3 mm nominal, which an FDM hole can easily print *undersize*. The only way
the panel went in was by being pressed, and pressing a glass module into a
too-small hole cracks the flex between the glass and its board. It then lights
up white and never draws, with nothing in any log to say why.

**Four snap pegs sat inside the panel's footprint** — x=±40, y=±12 against a
board of ±43 × ±25. To reach their sockets they travelled through the space the
board occupies, so assembling it would have pressed four posts into the back of
the panel. They had been moved out of the corners to save border and never
checked against the board.

Both are gone. **The lip now overlaps the glass**, so the glass does not pass
through the aperture at all — it goes in from behind and rests against the lip.
There is no press fit left to be tight. And there are no pegs, because there is
nothing inside.

## The window

Sized to the **lit area**, not the glass. The glass carries 5.7 mm of dead
black each side and 3.4 top and bottom; that dead black was the border you
could see. It is under plastic now.

| | |
|---|---|
| at the glass | 59.6 × 45.2 |
| at the face | 63.6 × 49.2 — chamfered out 2.0 per side |
| visible border | 13.6 sides, 2.8 top and bottom |

The **chamfer is on the left and right only** — 3 mm per side. It keeps the
corners from catching a fingertip reaching for the edge of the picture.

Chamfering all four edges cost 3 mm of border top and bottom, where there is
only 5.4 to begin with: it left a **1.4 mm knife edge** against sides of 9.4
and 15.4. The sides can afford the taper and the top and bottom cannot, so the
top and bottom walls stay square and the border there is 4.4.

The window sits on the **glass's** centre, not the board's — 8 mm of red on
the left against 9 on the right, so centring it on the board would put the
picture half a millimetre out.

### Where the picture actually is

**Measured on the board, 2026-09-24**: the picture starts 11 mm in from one end
of the 86 mm board and 17 mm in from the other — so it is **58.0 wide** and its
centre is **3.0 mm off the board's**.

Two independent measurements agree. Reading off the printed case gave 13 and 20
from the *case* edge; with the board inset 2.4 each side that is 10.6 and 17.6
from the board edge, against 11 and 17 here — within 0.6 mm. The board reading
is the one used, because it does not depend on the case having printed to size.

58.0 also lands 0.4 mm off the nominal 57.6 for a 2.8" 4:3 panel. That kind of
agreement usually means both numbers are right.

The window is drawn 1 mm larger all round, so it sits **1.0 mm outside the
picture on every side** — a sliver of black glass shows and nothing is covered,
which is the direction to err.

**The vertical inset has not been measured.** The picture is assumed centred on
the board's 50 mm, which the glass being full height makes likely — but it is
an assumption, not a measurement. If it turns out to be off, `act_h` and a
vertical offset are the two numbers to add.

### Square corners

`ap_r` is 0.4 — half a nozzle, i.e. as square as an FDM part gets. The
display's own corners are sharp, so a rounded window would leave four crescents
of black glass showing at the corners and nothing else.

## Clearances

**1.0 mm everywhere the panel touches**, against 0.4 before. The old 0.4 is
what made it a press fit, and the press fit is what broke the flex.

## How the halves join

At the **rim**. The bezel carries a 1.4 mm rim reaching back past the board;
the tray's spigot plugs into it. Friction — and the join is at the perimeter
where there is room for it, not through the middle where the panel is.

`rim_fit` (0.2 per side) is the number to tune. Loose, lower it; will not
seat, raise it. Only the tray needs reprinting.

## The panel's seats, and why they are not dead square

The panel has sharp corners, so the seats are cut as square as the geometry
allows — but "as square as allows" is a real limit here, not a shrug.

**The corner radius comes from the clearance.** A sharp corner in a pocket
rounded by *r* clears by `r − √2·|clear − r|` while *r* > clear, and by the
full `clear` once *r* ≤ clear. So `seat_r = clear` is the point where the
corner clears exactly as much as the flats do, and sharper buys **nothing**.

**It cannot go sharper anyway.** The seat's corner is at (44, 26); the outer
profile's corner arc is centred at (41.4, 23.4) with r=4. Dead square leaves
**0.323 mm** of wall there — under one extrusion, so it prints as a hole.

| seat r | wall at the corner | corner clearance |
|---|---|---|
| 1.5 | 0.944 | 0.793 ← what V1 had |
| **1.0** | **0.737** | **1.000** ← here |
| 0.0 | 0.323 | 1.000 — unprintable |

Corner *relief* — a small circle centred on the corner — is out for the same
reason: it would have to be under 0.323 to stay inside the wall. Tried it; it
punched straight through the outside face at all four corners.

### What actually held the first V1 off was the clearance

Not the rounding. At `clear` = 0.4 the board's corner fell **1.556** from the
arc centre against a **1.5** radius: fouling by 0.056 before the printer added
its own corner fillet. At `clear` = 1.0 it clears by the full millimetre. The
rounding only mattered because the clearance was too small to absorb it.

## The bezel-to-tray joint

Measured off the two STLs, on the mating flats:

```
bezel rim opening   ±44.00   outer ±45.40   (a 1.40 ring)
tray spigot         ±43.80   inner ±41.80   (a 2.00 wall)
                 -> 0.20 a side
```

Two surfaces land **at the same moment**: the tray's shoulder on the rim's back
face at z=11.2, and the spigot's nose on the board's back face at z=6.2. The
spigot is 5.0 long and the rim cavity is 5.0 deep, so the joint closes flush
with no step — and the panel is held with **zero nominal slack**.

That is the one number to watch. It is right if the panel really is 3.4 of
glass on a 1.6 board; if it measures 5.2 rather than 5.0, the difference goes
into the glass. Standing the spigot off 0.3 would trade that risk for 0.3 of
play — the shoulder would still be the hard stop, so the joint stays flush.

The corners clear comfortably: the spigot's corner-most point is 0.054 from the
rim opening's arc centre against a 1.0 radius.

## The connector edge

The display's connectors sit on the **back** of the panel and start right at
the edge on the case's right-hand side — negative x, the same edge the USB
comes out of. The spigot's nose overlaps the board by 1.2 all the way round,
so on that edge it landed straight on them.

Nothing *inboard* of the spigot's inner face needed any help: that is open
cavity, 33 deep. Only the 1.2 band where the nose overhangs the board was in
the way, so that band is cut back over `panel_conn` = 3.4 (the 3.0 measured
behind the board, plus 0.4).

```
spigot's -x wall at z=1.0 (in the relief) : -43.80 .. -43.00   0.8 thick
spigot's -x wall at z=4.5 (past it)       : -43.80 .. -41.80   2.0 thick
```

The spigot keeps its full **outer** face there, so it still locates in the
rim — it just stops touching the board on that one edge. The panel bears on
the other three, which is plenty given the glass is also carried by the lip
all the way round.

## The ESP32's perch

The board lies **flat against the back wall**, component side toward it, with
its pins and dupont shells pointing forward into the body — the only place with
room for them. Two rails stand off the wall, each with a groove the board's
long edges slide into. It goes in **from the right** until its port end meets
the wall, so the USB-C lines up with the slot by construction.

The rails' inner faces sit *inside* the board's width, which only works because
it slides in sideways — they could not capture an edge they did not overlap.

### The slot is cut to the board

| | board | slot | slack |
|---|---|---|---|
| width | 27.94 | **28.24** | 0.15 a side |
| thickness | 1.60 | **1.75** | 0.15 total |

It used to leave 0.50 a side and 0.30 on the thickness, which is a rattle, not
a fit. FDM takes most of the new figure back — a slot prints 0.1–0.2 narrow —
so 0.15 lands near zero slack in the plastic.

`esp_fit` is the number to open up if the board will not go in. **Do not force
it.** Forcing a fit is how the first display's flex went.

The three faces are now named rather than derived by arithmetic on the rail's
centreline: `y_grip` (the lip's inner edge, over the board), `y_slot` (where
the board's edge stops) and `y_out` (the rail's outer face). The slot is cut
from the centreline outward so it stays open inboard — a slot closed on both
sides is one the board cannot enter.

### Everything inside is clipped to the cavity

The perch is sized for the **board**, then intersected with `tray_inside()`,
the same shape that hollows the box. Without that clip the end stop — board
width plus the gap plus both rails, 35.14 across — drove a 3 mm tab straight
through the bottom of the case, and the rails broke through by 0.41 over their
last few millimetres.

The cavity is not a box. The underside slants at 15°, so it is **narrower at
the back**: its floor is at −17.43 where the board's groove sits (z 30.4–32.0)
but has climbed to −15.56 by the back wall. A part that clears the floor at
the front can still be outside the case at the back. Clipping makes that
impossible to get wrong again, whatever the perch is later resized to.

### The numbers are the board's own

| | spec | the model used to say |
|---|---|---|
| length | **48.26** | 52.0 — 3.7 too long |
| width | **27.94** | 28.0 |
| pins below the board | **8.50** | *nothing at all* |

### The standoff is set by the PLUG, not the socket

`esp_stand` = 6.0 mm. The connector is only 3.16 tall, so 4 would clear it —
but a USB-C plug's overmould is about 7 across, centred on that socket:

| standoff | plug reaches | back wall at 38 |
|---|---|---|
| 4 | 39.08 | **fouls** |
| 5 | 38.08 | **fouls** |
| **6** | **37.08** | clears by 0.92 |

At 4 mm the cable hits the case before it seats — and the socket would have
looked perfectly fine in a render.

## The vents

**Two rows of hexagons across the top of the back wall**, with the board
directly underneath.

The cell size is not a style choice. The slanted underside has risen to
y = −15.56 by the time it reaches the back wall, so the usable height there is
**42.96 mm** — and the board takes 27.94 of it. That leaves about 12 mm for two
rows, which sets `hex_r` at 2.6.

The board is centred on y=0, spanning −13.97 to 13.97: clear of the floor by
1.59 and topping out just under the vents at 13.6.

### They were sealed too, and by the same arithmetic

The cell was extruded from `rim_d + tray_d + back_t - 1` = 39, through
`back_t + 2` = 4, so it cut 39→43. The back wall spans **38→40**. Every cell
kept a 1 mm skin on its inside face — the identical fault to the port, one
wall over. It now starts at `rim_d + tray_d - 1` = 37.

**Genus was how both were caught.** A closed box with *n* holes through its
walls is genus *n*: it read 0 while both were skinned, and 1 once only the port
was open.

It is not the check to keep, though — genus counts *every* handle, including
three small channels where the lower rail merges into the sloping floor. Shrink
the rails (`-D esp_l=5`) and the tray reads exactly 22, one port and 21 cells.

Cast a ray through each cell instead. That answers the question actually being
asked — **is this hole a hole** — and it does not care what else the part does.

### The port

A **stadium, not a rectangle** — 12.95 × 7.10, fully round-ended, centred at
z = 33.58. Its position is derived, not chosen: `rim_d + tray_d - esp_stand +
usb_shell_h/2`, which puts it on the socket's centreline by construction.

The size is the **plug's**, not the receptacle's. The spec's maximum cable
overmould is 12.35 × 6.50; `usb_fit` adds 0.60 for slop and for FDM printing
holes 0.2–0.4 under. Sizing this opening 8.94 × 3.16 to match the socket would
look right and pass no cable at all.

#### It was sealed shut, and the cavity was why

The opening is cut `wall + 2` long, from x 42.4 to 46.4 — correct for a 2.0
wall whose inner face is at 43.4. But `tray_inside()` carried the **spigot's**
width all the way to the back, putting the real inner face at 41.8 and making
the sides 3.6 thick. The cut stopped 0.6 short and left a skin across the port.

The same mistake cost the board its slot. `x_wall` is `face_w/2 - wall` =
43.4, so the stop sits 48.26 from there — but with the cavity ending at 41.8
the gap was only 46.66, and the ESP32 is 48.26. **It would not have gone in.**

The cavity now steps: the spigot's width through the spigot, where it has a
rim to enter, and the body's width through the body, where it has no reason to
give up 1.6 mm a side. Both faults close together.

A useful tell: a hollow box with a hole through one wall is **genus 1**. While
the skin was there OpenSCAD reported genus 0.

#### Which side is it on?

The viewer's **right**, which is **negative x**. That sign is the whole trap
and I had it backwards.

The screen's face is at z=0 and the body runs back to +z, so the viewer looks
**along +z** with +y up. For a right-handed frame, a viewer whose forward is
+z and whose up is +y has their right hand pointing at **−x**. Write "the USB
is on the right" as +x and the case comes out mirrored — port on the far side,
and the wide border mirrored with it.

Nothing catches this. The box is symmetric enough that no render looks wrong,
and the relational check — *is the port on the same side as the wide border?* —
passes happily while **both** are on the wrong side. It took putting the part
on a build plate, with the slant on the bottom where it belongs, to see it.

So `act_cx` is no longer a signed guess. It is derived from the border the
viewer actually sees on their right:

```
bez_right = 17.0;                                  // measured
act_cx    = -pcb_w/2 + bez_right + act_w/2;        // = +3.0
```

and the board's port end butts `-(face_w/2 - wall)`. Both now read 18.35 on
the viewer's right and 12.35 on their left, against the measured 17 and 11.

#### Could the opening be socket-sized?

Only if the socket's mouth is flush with the outside. It sits `usb_over` = 1.20
proud of the board's end, and the board butts the inner face at 43.4, so the
mouth lands at 44.6 — 0.8 behind the outer face at 45.4. Whatever passes
through that last 0.8 mm has to be plug-shaped.

To get a 9.5 × 3.8 opening instead, pocket the wall 0.8 deep where the board's
end lands, bringing the socket flush; the overmould then stops against the
outside of the case and 1.2 mm of wall remains around the pocket. It hangs
entirely on `usb_over` being right — measure it before committing to it.
