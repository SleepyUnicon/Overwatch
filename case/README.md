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

## The ESP32's perch

The board lies **flat against the back wall**, component side toward it, with
its pins and dupont shells pointing forward into the body — the only place with
room for them. Two rails stand off the wall, each with a groove the board's
long edges slide into. It goes in **from the right** until its port end meets
the wall, so the USB-C lines up with the slot by construction.

The rails' inner faces sit *inside* the board's width, which only works because
it slides in sideways — they could not capture an edge they did not overlap.

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

### The port

Positioned **from the board**, not guessed. The USB-C is centred on the 27.94
width and sits on the board's front face, so the opening's centre is
`esp_rib + esp_t + shell_h/2` in from the back wall — z=15.8. The connector
shell spans 14.2–17.4 and the 7 mm slot spans 12.3–19.3, so a plug's overmould
has room either side of the receptacle.
