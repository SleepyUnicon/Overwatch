// =====================================================================
// Overwatch - the case
//
// A front BEZEL that covers the red board and nothing else, and a back
// TRAY that carries the ESP32 and wears the stand legs. They snap
// together. No screws.
//
// WHAT THE BEZEL ACTUALLY IS, measured 2026-09-23
//
//   red PCB      86.0 x 50.0
//   glass        69.0 x 50.0   <- the FULL height of the board
//   red showing   8.0 left, 9.0 right, and NOTHING top or bottom
//
// So the aperture follows the GLASS, not the lit area. Earlier versions
// sized it to the active display and had to leave 14 mm of lip each side
// to reach it -- which is the fat border that kept coming back however
// the numbers were nudged. Sized to the glass, the frame only has to lap
// the two red strips, and top and bottom it is pure wall:
//
//   top, bottom   2.4 mm   (wall + clearance, and that is the whole lot)
//   left         10.4 mm   (2.4 of wall over 8.0 of red board)
//   right        11.4 mm   (2.4 of wall over 9.0 of red board)
//
// The glass sits FLUSH in the aperture. There is no lip over it: the
// active area reaches within about 0.5 mm of the glass edge top and
// bottom, so any lip at all would cover picture. The module is held by
// the two ledges under the red strips instead, which is what they are
// for.
//
// NO SCREWS, and that is a bezel decision rather than a taste one. Corner
// posts for M3 have to clear the PCB corner, which puts the frame at
// 98 x 62 against this one's 90.8 x 54.8 -- 3.6 mm more border on every
// side, on the one dimension being minimised. The tray snaps in instead.
//
// PRINT ORIENTATION
//   front  face DOWN. The bezel is what people look at; it gets the bed.
//   back   open side UP, legs down.
// =====================================================================

$fn = 48;

// ---- the panel, measured -------------------------------------------
pcb_w      = 86.0;
pcb_h      = 50.0;
pcb_t      = 1.6;

glass_w    = 69.0;
glass_h    = 50.0;   // the full height of the board
glass_left =  8.0;   // red showing on the left
glass_pro  =  3.4;   // glass stands this proud of the PCB (5.0 - 1.6)

// Depth of the module front-to-back, glass face to the back of the
// dupont shells on its header.
panel_d    = 10.8;

// ---- the ESP32 ------------------------------------------------------
esp_w      = 52.0;
esp_h      = 28.0;
esp_d      = 25.0;   // with its cables seated
usb_w      = 12.0;
usb_h      =  8.0;

// ---- tolerances -----------------------------------------------------
// Asked for explicitly, and they are not all the same number because
// they are not all the same risk.
clear      = 0.4;    // around the PCB in plan. It either fits or it does
                     // not, and 0.4 covers print swell on a 86 mm span.
glass_gap  = 0.3;    // around the glass in the aperture, per side. Tight
                     // on purpose: this gap is VISIBLE, it runs right
                     // around the picture, and the glass is not load
                     // bearing.
depth_tol  = 2.0;    // slack in the depth stack. The two depths that set
                     // it -- 10.8 and 25.0 -- are ruler readings of
                     // squashy things (cable shells), so this is the one
                     // tolerance that is generous. Costs 2 mm of case
                     // nobody sees; saves a lid that will not close.

// ---- the shell ------------------------------------------------------
wall       = 2.0;
face_w     = pcb_w + 2 * (wall + clear);   // 90.8
face_h     = pcb_h + 2 * (wall + clear);   // 54.8
corner_r   = 4.0;

frame_t    = glass_pro + pcb_t;            // 5.0: glass flush, PCB behind
ledge      = 2.5;                          // how far the frame laps the
                                           // red strip, under the glass
back_t     = 2.0;

// The inside, from the back of the PCB to the inner face of the back
// wall: what is left of the module, then the ESP32, then the slack.
cavity_d   = (panel_d - frame_t) + esp_d + depth_tol;
body_d     = frame_t + cavity_d + back_t;

// ---- the snap -------------------------------------------------------
skirt_d    = 8.0;    // how far the frame's skirt reaches into the tray
catch_h    = 1.0;    // how far the catch stands out
catch_w    = 12.0;

// ---- the loom -------------------------------------------------------
// 13 dupont jumpers between the panel's header and the ESP32.
//
// THE RULE IS: the loom goes SIDEWAYS, never backwards. Depth is the one
// dimension being fought for -- every mm of it shows in the case's
// thickness -- while the cavity is 86.8 wide and the ESP32 is only 52, so
// there are 34.8 mm of width sitting unused. That column is free depth.
//
// 13 wires of 26 AWG at about 1.3 mm over the insulation bundle to
// roughly sqrt(13) * 1.3 = 4.7 mm, call it 7 loosely gathered. The
// channel is 9 so the bundle is guided, not squeezed: a loom squashed
// into its channel pulls on the crimps every time the case is closed,
// and the crimp is where dupont wires fail, not the wire.
loom_d     = 9.0;    // channel width for the bundle
loom_r     = 5.0;    // smallest radius the loom is asked to turn
esp_side   = 1;      // +1 puts the ESP32 on the USB side, loom opposite
tie_w      = 4.0;    // zip-tie slot, for strain relief at the port

// ---- the slant ------------------------------------------------------
// The WHOLE bottom is the foot: one flat plane, cut at `lean` to the
// screen, that the case sits on. Two fins did the same job and looked
// like an afterthought.
//
// It costs something and it is worth naming. The desk plane rises
// tan(lean) per mm of depth -- 10.7 mm over this case's 39.8 -- and the
// cavity floor is only 2 mm above the case bottom, so a slanted bottom
// eats into the cavity from 7.5 mm back. Keeping a full-height cavity all
// the way to the rear would mean growing the case 10.7 mm taller, which
// is a 13.1 mm bottom bezel instead of 2.4. Not worth it.
//
// The way out is that the full height is only needed for the PANEL, in
// the first 5.8 mm. Behind that only the ESP32 has to fit, and it can
// ride high. So the cavity floor follows the slant, one `wall` above it,
// and the ESP32 sits on that rising floor.
lean       = 15;

// =====================================================================
// helpers
// =====================================================================

module rrect(w, h, r) {
	hull() for (x = [-1, 1], y = [-1, 1])
		translate([x * (w / 2 - r), y * (h / 2 - r)]) circle(r);
}

module rbox(w, h, d, r) {
	linear_extrude(d) rrect(w, h, r);
}

// Everything below the desk plane: the plane through the bezel's bottom
// front edge, rising at `lean` as it goes back.
//
// rotate([-lean,0,0]) and not +: about X a point (y,z) goes to
// (y*cos - z*sin, y*sin + z*cos), so the top face's y only RISES with z
// when sin(a) is negative.
module desk_cut(drop = 0) {
	translate([0, -face_h / 2 + drop, 0])
		rotate([-lean, 0, 0])
		translate([-200, -400, -200])
		cube([400, 400, 400]);
}

// =====================================================================
// front_bezel
// =====================================================================
module front_bezel() {
	// The aperture, in the glass's own place on the board. The glass is
	// not centred -- 8 left against 9 right -- so the hole is not
	// centred either. Centring it would put the picture 0.5 mm off and
	// show a different amount of red down each side.
	ap_cx = -pcb_w / 2 + glass_left + glass_w / 2;

	difference() {
		union() {
			rbox(face_w, face_h, frame_t, corner_r);
			// the skirt that reaches into the tray
			translate([0, 0, frame_t])
				difference() {
					rbox(face_w - 2 * wall,
					     face_h - 2 * wall, skirt_d,
					     corner_r - wall);
					translate([0, 0, -1])
						rbox(face_w - 4 * wall,
						     face_h - 4 * wall,
						     skirt_d + 2,
						     corner_r - 2 * wall);
				}
		}

		// the glass aperture, straight through the frame
		translate([ap_cx, 0, -1])
			linear_extrude(frame_t + 2)
			rrect(glass_w + 2 * glass_gap,
			      glass_h + 2 * glass_gap, 1.5);

		// the pocket the board drops into from behind, leaving `ledge`
		// of frame under each red strip to hold it
		translate([0, 0, glass_pro])
			linear_extrude(pcb_t + clear + 1)
			rrect(pcb_w + 2 * clear, pcb_h + 2 * clear, 1.5);
	}

	// catches, on the skirt's left and right faces
	for (x = [-1, 1])
		translate([x * (face_w / 2 - wall), 0, frame_t + skirt_d - 2.5])
			scale([x, 1, 1])
			catch();
}

// The bezel, with its share of the slant taken off. Only 5 mm of depth,
// so only 1.3 mm of it -- but leaving it square would put a 1.3 mm step
// in the one line that is supposed to run unbroken from the front edge to
// the back foot.
module front_bezel_cut() {
	difference() {
		front_bezel();
		desk_cut();
	}
}

module catch() {
	// a ramp going in, a flat holding it
	rotate([0, 0, 90]) rotate([0, 90, 0])
		linear_extrude(catch_w, center = true)
		polygon([[0, 0], [0, catch_h], [2.5, 0]]);
}

// =====================================================================
// back_tray
// =====================================================================
module back_tray() {
	d = cavity_d + back_t;

	difference() {
		// the outer box, with the whole underside cut to the desk
		difference() {
			rbox(face_w, face_h, d, corner_r);
			desk_cut();
		}

		// The cavity, its floor cut by the SAME plane one wall higher.
		// That is what keeps the wall an even 2 mm the whole way along
		// the slant instead of tapering to a knife edge at the back.
		difference() {
			translate([0, 0, -1])
				rbox(face_w - 2 * wall, face_h - 2 * wall,
				     cavity_d + 1, corner_r - wall);
			desk_cut(wall);
		}

		// windows the frame's catches drop into
		for (x = [-1, 1])
			translate([x * (face_w / 2 - wall / 2), 0,
				   skirt_d - 2.5 + catch_h / 2])
				cube([wall * 2, catch_w + 0.6, 3.2],
				     center = true);

		// The USB slot, in the BACK WALL. That is the point of
		// mounting the board here: the port faces out through the one
		// wall with nothing in front of it, and the cable leaves
		// straight back instead of bending round a corner.
		//
		// Sat high enough to clear the rising cavity floor, which at
		// the back wall is 10.7 mm up from where it starts.
		translate([face_w / 2 - 24, -face_h / 2 + 16, cavity_d - 1])
			cube([usb_w, usb_h, back_t + 2]);

		// vents over the board
		for (i = [-3 : 3])
			translate([i * 7, face_h / 2 - 10, cavity_d - 1])
				linear_extrude(back_t + 2) rrect(2.6, 11, 1.2);

		// A zip-tie slot beside the port. The tie goes round the USB
		// lead inside the case, so a tug on the cable pulls on the
		// case and not on the board's socket -- which is the joint
		// that tears off a DevKitC.
		for (dy = [-1, 1])
			translate([face_w / 2 - 24 - 5, -face_h / 2 + 16 + 4
				   + dy * 7, cavity_d - 1])
				cube([tie_w, 2.2, back_t + 2], center = true);
	}

	// --- the loom's side of the cavity ---------------------------
	//
	// Two pillars with a gap the bundle drops behind. Not a closed
	// channel: a closed one has to be threaded, and threading 13 stiff
	// jumpers through a 9 mm hole during assembly is how they get
	// pulled out of their shells. This is a slot you press them into.
	lx = -esp_side * (face_w / 2 - wall - loom_d / 2 - 3);

	// At y = -4 and +14, both clear of the rising floor. The floor at the
	// back wall is up at about -14.7, so a pillar centred at -12 would
	// have had its lower half buried in it.
	for (ly = [-4, 14])
		translate([lx, ly, cavity_d - 9])
			difference() {
				cylinder(d = loom_d + 2 * 2.5, h = 9);
				translate([0, 0, -1])
					cylinder(d = loom_d, h = 11);
				// The mouth, facing the middle of the case.
				// Starts at the CENTRE and runs outward: the
				// first version started a whole loom_d out,
				// which is past the pillar's 7 mm outer
				// radius, so it removed nothing and left a
				// closed ring you would have to thread.
				scale([esp_side, 1, 1])
					translate([0, -(loom_d - 2) / 2, -1])
					cube([loom_d, loom_d - 2, 11]);
			}

	// The ESP32's shelf, pushed to the port side so the whole of the
	// other side is the loom's.
	for (dy = [-1, 1])
		translate([esp_side * 18, dy * 9, cavity_d - 5])
			cylinder(d = 5, h = 5);
}

// =====================================================================
//   openscad -D 'PART="front"' -o front_bezel.stl overwatch_case.scad
// =====================================================================
PART = "all";

if (PART == "front")     front_bezel_cut();
else if (PART == "back") back_tray();
else {
	// Stood up as it sits on a desk, which is the only orientation that
	// shows whether the legs work. The parts are MODELLED face-down, so
	// in a raw render the device's "down" is horizontal and a leg
	// pointing at the floor looks like a spike out of the back.
	rotate([90 + lean, 0, 0]) {
		front_bezel_cut();
		translate([0, 0, frame_t]) back_tray();
	}
}
