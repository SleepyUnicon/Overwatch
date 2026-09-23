# The Overwatch case

A front **bezel** that covers the red board and nothing else, and a back
**tray** that carries the ESP32 and wears the stand legs. They snap together.
No screws.

| part | what it is | print it |
|---|---|---|
| `front_bezel.stl` | the frame. Glass sits flush in it. | face **down** |
| `back_tray.stl` | the box. ESP32 mounts here, USB out of the **right side**. | back wall **down**, no supports |

```sh
openscad -D 'PART="front"' -o front_bezel.stl overwatch_case.scad
```

## The bezel

Measured 2026-09-23:

| | |
|---|---|
| red PCB | 86.0 x 50.0 |
| glass | 69.0 x 50.0 — **the full height of the board** |
| red showing | 8.0 left, 9.0 right, **nothing top or bottom** |

So the aperture follows the **glass**, not the lit area. Earlier versions
sized it to the active display and needed 14 mm of lip each side to reach it
— that is the fat border that kept coming back however the numbers were
nudged. Sized to the glass, the frame only laps the two red strips:

| edge | border |
|---|---|
| top, bottom | **2.4 mm** — wall and clearance, and that is the whole lot |
| left | 10.4 mm — 2.4 of wall over 8.0 of red board |
| right | 11.4 mm — 2.4 of wall over 9.0 of red board |

The glass sits **flush** in the aperture. There is no lip over it: the active
area reaches within about 0.5 mm of the glass edge top and bottom, so any lip
at all would cover picture. The module is held by the two ledges under the red
strips instead, which is what those strips are for.

The aperture is **not centred**, because the glass is not: 8 mm of red on the
left against 9 on the right. Centring the hole would put the picture 0.5 mm
off and show a different amount of red down each side.

### It is a 2.8" module

The silkscreen says so: `2.8 TFT SPI 240*320`, `KJ4RTM28028-SPI`. An earlier
version of this file called it 3.2", inferred from "active display 10 mm from
the left, 10.8 from the right" — 86 - 10 - 10.8 = 65.2 wide, which really is a
3.2" diagonal. Those two readings were almost certainly to the edge of the
dark **glass**, not the lit pixels; a 2.8" active area is 57.6 x 43.2.

**It does not change the case.** The aperture follows the glass (69 x 50),
measured directly. The active area only decides whether the picture looks
centred in the hole.

## Four hidden snaps — nothing on the front face

Printed **snap pegs on the tray**, clicking into **blind sockets** in the
bezel. No screws, and nothing visible from the front.

An earlier version used through-holes with a countersink. It worked, and it
was wrong: a countersunk through-hole is indistinguishable from a screw hole,
and four of them on the front is the one place they must not be. "Snap on" has
to mean invisible or it has bought nothing over screws.

**Where the room is.** The bezel's cross-section changes partway down:

```
z 0.0 .. 3.4   the frame -- 10.6 mm bands left and right
z 3.4 .. 5.0   the PCB pocket opens; only 2.0 mm of rim left
```

So the halves meet rim to rim, 2 × 2, with no overlap to snap into — which is
why the skirt failed and why a peg cannot grip the edge. But those **10.6 mm
bands are solid for the first 3.4 mm**, and a socket entered from behind can
live in them without ever breaking through.

The socket, in tray coordinates (0 at the tray's face, bezel running −5.0 … 0):

```
bore  -2.6 ..  0.0   at 3.4, what the barb squeezes through
ring  -3.8 .. -2.6   at 4.2, what it springs out into
solid -5.0 .. -3.8   1.2 mm of front skin. Nothing shows.
```

The peg is **split** so the two prongs can close to clear the bore. A solid one
would have to stretch the bezel, and PLA does not stretch, it cracks.

They cost no border: the pegs sit in the side bands, where the panel's own dead
red strip already forces 10 mm of bezel. A 5 mm peg fits with room over, so the
border stays **2.4 mm**.

## Depth, and the tolerances

39.8 mm total: 5.0 of frame, 32.8 of cavity, 2.0 of back wall.

Three tolerances, and they are different numbers because they are different
risks:

| | | why |
|---|---|---|
| `clear` | 0.4 | around the PCB in plan. It either fits or it does not, and 0.4 covers print swell over an 86 mm span. |
| `glass_gap` | 0.3 | around the glass, per side. Tight on purpose — this gap is **visible**, it runs right around the picture, and the glass carries no load. |
| `depth_tol` | 2.0 | slack in the depth stack. The two numbers that set it (10.8 module with cables, 25.0 ESP32 with cables) are ruler readings of squashy things, so this one is generous. Costs 2 mm nobody sees; saves a lid that will not close. |

## The slanted bottom

The **whole underside** is the foot: one flat plane, cut at 15 degrees to the
screen, that the case sits on. Two fins did the same job and looked like an
afterthought.

It costs something, and the cost is worth knowing if you change `lean`. The
desk plane rises `tan(lean)` per mm of depth — 10.7 mm over this case's 39.8 —
while the cavity floor sits only 2 mm above the case bottom. So a slanted
bottom starts eating into the cavity **7.5 mm back from the front**. Keeping a
full-height cavity all the way to the rear would mean growing the case 10.7 mm
taller, which is a **13.1 mm bottom bezel instead of 2.4**. Not worth it.

The way out is that full height is only needed for the **panel**, in the first
5.8 mm. Behind that only the ESP32 has to fit, and it can ride high. So the
cavity floor is cut by the *same* plane one `wall` higher — which keeps the
wall an even 2 mm the whole way along the slant instead of tapering to a knife
edge — and the ESP32 sits on that rising floor.

Raise `lean` much past 15 and the ESP32 bay runs out of headroom. The check is
in the README's arithmetic, not in the model: nothing stops you.

## Printing, and what the slant fixed

**Both parts print flat with no supports.**

That is new. With legs on the back, the tray had two bad choices and no good
one — back wall down put the legs *through the bed*, and front opening down
meant bridging the open 86.8 x 50.8 cavity. Slanting the whole bottom removed
the problem: the tray now prints back wall down with the opening up, and the
slanted underside is simply an angled side wall at 15 degrees from vertical,
well inside the 45 rule.

## How the panel goes in

**From behind.** The board drops into the pocket from the back of the bezel
and is caught by two **8.6 mm ledges** under the red strips. It cannot fall
through the front because it is 86 mm wide against a 69.6 mm hole.

Top and bottom have **no ledge at all** — 0.1 mm, which is nothing. That is
not an oversight: the glass is the full 50 mm height of the board, so there is
no red up there to grip. The board is held on two sides and pressed forward
against those ledges by the tray. The glass then stands 3.4 mm proud through
the aperture and finishes flush with the bezel's face.

## The loom

13 dupont jumpers between the panel's header and the ESP32.

**The rule is: the loom goes sideways, never backwards.** Depth is the one
dimension being fought for — every millimetre of it shows in how thick the
case looks — while the cavity is 86.8 wide and the ESP32 is only 52. Those
**34.8 mm of spare width** are free depth, so the board is pushed to the port
side and the whole of the other side is the loom's.

13 wires of 26 AWG at about 1.3 mm over the insulation bundle to roughly
`sqrt(13) x 1.3 = 4.7 mm`; call it 7 loosely gathered. The channel is **9 mm**,
so the bundle is guided rather than squeezed. A loom crushed into its channel
pulls on the crimps every time the case is closed, and **the crimp is where
dupont wires fail, not the wire.**

Two C-clips hold it, mouths facing the middle of the case — you press the
bundle in from the side. Deliberately not closed rings: a closed channel has
to be *threaded*, and threading 13 stiff jumpers through a 9 mm hole during
assembly is exactly how they get pulled out of their shells.

There is also a **zip-tie slot beside the USB port**. Tie the lead inside the
case and a tug on the cable pulls on the case rather than the socket, which is
the joint that tears off a DevKitC.

### The number to check

`panel_d = 10.8` is your measurement of the module **with its cables**. If
the header's dupont shells stand straight off the back of the board they are
about 14 mm on their own, and 14 + 25 for the ESP32 is 39 against a 32.8 mm
cavity — it would not close. Measure the module front-to-back with a jumper
seated, square to the board. If it is over about 12, raise `panel_d` and
`cavity_d` follows, or fit right-angle headers.

## Two checks worth keeping

`overwatch_case.scad` asserts at render time, because the failures above were
silent:

- screw posts must land in the solid band beside the aperture, not over it;
- the lower posts must clear the **slanted** cavity floor. That floor rises
  0.268 mm per mm of depth, so the tight point is the back wall — at
  `scr_y = 18` the posts went 3.9 mm out through the bottom of the case. 12
  keeps them 2.1 mm clear.

When checking an STL for loose parts, count **shells minus internal voids**.
A blind screw hole is its own closed surface, so the tray reads as 5 shells
and is a single solid with four blind holes — a raw shell count calls that
broken when it is correct.

## A note on judging renders

The parts are **modelled face-down** — face in XY, depth along Z. In a raw
render the device's "down" is horizontal, so a leg pointing at the floor looks
like a spike sticking sideways out of the back, and a wrong one looks fine.
The `all` view rotates the assembly upright for exactly this reason. Judge the
stance there and nowhere else.
