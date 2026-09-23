# The Overwatch films

Four eight-second clips at 1080x1920, built headless in Blender from the same
STLs the case prints from. Nothing is modelled twice: change
`case/overwatch_case.scad`, re-export, and the next render picks it up.

```sh
BL=/Applications/Blender.app/Contents/MacOS/Blender

$BL --background --python scene.py -- --shot reveal  --portrait \
    --res 1080 1920 --samples 64 --anim overwatch_reveal_9x16.mp4

$BL --background --python scene.py -- --shot widgets --portrait \
    --res 1080 1920 --samples 64 --anim overwatch_widgets_9x16.mp4

$BL --background --python scene.py -- --shot sweeps  --portrait \
    --res 1080 1920 --samples 64 --anim overwatch_sweeps_9x16.mp4

$BL --background --python scene.py -- --shot hand    --portrait \
    --res 1080 1920 --samples 64 --anim overwatch_hand_9x16.mp4
```

Drop `--portrait` for 16:9. A single frame, for iterating on the look without
waiting for 240 of them:

```sh
$BL --background --python scene.py -- --shot widgets --portrait \
    --still 85 --res 405 720 --samples 20 --render look.png
```

## Shot 2 - the widgets

The three pages, swiped. Gauges, Spotify, launcher, and back to gauges so the
clip LOOPS - it is going on a feed, and a hard cut back to the first frame is
the one thing a viewer always notices.

The swipe is not a texture swap. `make_screen.py` stacks the three pages into
one tall image and the material maps a third of it onto the panel; sliding the
mapping IS the swipe, so the transition is whatever easing the keys carry.
13 frames of travel, which is about 0.45 s - what a deliberate page change
feels like on the panel.

The barbell is cropped at the sides here on purpose. The subject is the
screen, and holding the whole 182 mm silhouette in frame would put the panel
too far away to read.

## Shot 3 - the sweeps

Four fast moves, each snapping to a new angle and settling, with a push-in on
the third. `snap()` keys them QUAD / EASE_OUT rather than SINE / EASE_IN_OUT,
which is the whole difference between a camera whipping somewhere and a
camera drifting there. Lit from frame one; nothing is being revealed.

## Shot 4 - the hand

A finger, not a hand. A modelled hand that is not very good is worse than no
hand at all; a finger entering soft and slightly out of focus reads as a hand
without claiming to be one. It is a capsule with a warm subsurface skin
shader, and motion blur does most of the work.

**The swipe travels UP, not sideways.** `ui_pages.c` walks the stack
vertically, so a horizontal swipe here would show a gesture the firmware does
not implement.

## Shot 1 - the reveal

| | |
|---|---|
| 0.0 - 1.0 s | Near-dark. Only the rims are up, so the barbell reads as a silhouette before anything else does. |
| 1.0 - 3.0 s | Key and fill come up. The form arrives. |
| 4.0 - 5.0 s | The panel wakes - a stutter, then it holds. |
| 5.0 - 8.0 s | Settles onto the hero three-quarter as the camera rises and slows. |

The order is the whole point: light first, screen second. A panel that is lit
from frame one has nothing left to give at frame 130.

## The launcher icons

`icons/` holds the six app icons, extracted from the installed bundles on this
Mac with `sips` - Claude, Illustrator, Photoshop, Spotify, Brave and PCSX2.
Real icons rather than drawn approximations: a launcher showing what it
launches is the ordinary thing, and hand-drawn near-misses of six brand marks
would look worse and sit less comfortably.

**The firmware draws these icons now.** `tools/encode_icons.py` turns this
directory into `firmware/src/icons_gen.h` - 6 icons at 40x40, RGB565A8,
28 KB of flash - and `ui_launcher.c` draws them, falling back to text for any
key it was not built with. So the clips and the board agree.

Re-run the encoder if you change the icons:

```sh
python3 tools/encode_icons.py --in reveal/icons --size 40
```

## 9:16

`cam_d.sensor_fit = 'HORIZONTAL'` is load-bearing in portrait. On AUTO,
Blender fits the sensor to the LARGER dimension - which in 9:16 is the height
- and the barbell, the widest thing and the whole silhouette, runs off both
edges. Fitting to width is what makes the framing mean the same thing in
either aspect.

## Decisions worth keeping

**EEVEE, not Cycles.** Cycles on the M4 rendered one 960x540 frame in 2 min 11 -
about eight hours for the sequence. EEVEE with raytraced shadows does this
lighting at roughly a second a frame. For a dark studio with four area lights
and one emitter, the difference on screen does not pay for the difference in
time.

**The screen is the real UI.** `make_screen.py` draws the shipping layout -
two arcs, their percentages, the countdowns, the wordmark and the session pips
- at 8x panel resolution so it stays sharp when the camera is close. It is an
emitter, so it lights the bezel around it.

**Emission is 1.85, not 5.** AgX desaturates anything near clipping, and at 5
the blue arcs rendered white. The number is set by what survives the transform,
not by what looks bright in isolation.

**The floor is rough, not dark.** Three rounds of darkening the floor did
nothing about the bright pool in the corner of frame, because it was a
SPECULAR reflection of the rim lights and specular ignores base colour.
Roughness 0.62 and specular level 0.18 are what actually reached it.

**The lights are aimed by constraints,** not by hand-written euler angles. The
hand-set version put a hot pool of floor in the opening frame.

**0.2 mm layer lines.** A wave texture along the print's own Z drives a 0.09
bump. Almost invisible, and it is the difference between a render of a 3D
print and a render of an injection moulding.

## Blender 5 gotchas this script already handles

Three API changes that each cost a debugging round:

- **`action.fcurves` is gone.** Keyframes live in slotted actions now;
  `fcurves_of()` handles both shapes.
- **The compositor is a node GROUP on the scene** (`compositing_node_group`),
  there is no `scene.node_tree` and no Composite node - and the group's Image
  input does NOT carry the render. Wire the group input straight to the output
  and every frame comes out black. Use a Render Layers node inside the group.
- **Node settings are SOCKETS now.** `glare.glare_type` does not exist;
  it is `glare.inputs["Type"]`, and the enum values are title case (`Bloom`,
  `High`), not upper.
- **Video output needs `image_settings.media_type = 'VIDEO'` first.** Setting
  `file_format = 'FFMPEG'` on its own is rejected with a list that does not
  mention video at all.

## Knobs

| | |
|---|---|
| Length | `FPS, SECS` near the top of the animation block |
| Camera | the `(dist, lift)` pairs and the pivot's start/end angles |
| Exposure | each light's `energy`, and the `ramp()` calls that bring them up |
| Screen wake | the `ramp(bs, ...)` stutter keys |
| Bloom | the `put(glare, ...)` calls |

## What this is not

It is a render of a model that has never been printed. The layer lines are
procedural, the plastic is ideal, and nothing sags. When a real one exists,
a photograph of it beats this - use this until then.
