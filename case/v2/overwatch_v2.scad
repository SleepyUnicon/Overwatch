// =====================================================================
// Overwatch V2 - the wedge
//
// A slanted screen on a flat base. Two printed parts, no screws.
//
//   v2_shell   the wedge: slanted front with the window, vertical back
//              with the USB port and a honeycomb vent, closed top and
//              sides, OPEN BOTTOM.
//   v2_base    the bottom, which snaps in and carries the ESP32.
//
// EVERYTHING ENTERS FROM UNDERNEATH. The panel, the loom and the board
// all go in through the bottom, so the shell has no seam anywhere you
// look at it.
//
// WHY THE PORT REACHES THE BACK HERE, AND COULD NOT IN V1
//
// A DevKitC carries its USB connector on a SHORT END, in the plane of
// the board. V1 laid it against a vertical back wall, so that port
// pointed at a SIDE wall -- the back slot cut there would have opened
// onto solid board.
//
// Lying it flat on a HORIZONTAL base turns the port to face sideways-on,
// i.e. horizontally. Aim that end at the back wall and it exits the back.
// The board's long axis has to run front-to-back for that, which is what
// sets the depth.
//
// THE DEPTH IS NOT 52, AND NOT 52 PLUS THE LEAN EITHER
//
// The panel leans back OVER the base, so the board sits under it -- they
// overlap in plan, and adding the two was wrong. But the panel's back
// surface is a sloping line, z(y) = y*tan(lean) + panel_d/cos(lean), and
// the board has to start behind wherever that line is at the board's own
// height. At 20 degrees with the cables lying flat that is 13.7, so
// 13.7 + 52 + walls = 68. Let the dupont shells stand up instead and it
// costs 5 mm more case.
//
// PRINT ORIENTATION
//   shell  on its BACK. The back is flat, the open bottom faces sideways,
//          and the slanted front becomes a 20-degree overhang -- inside
//          the 45 rule, so no supports.
//   base   flat, posts up.
// =====================================================================

$fn = 48;

// ---- the panel, measured -------------------------------------------
pcb_w      = 86.0;
pcb_h      = 50.0;
pcb_t      = 1.6;
glass_w    = 69.0;
glass_h    = 50.0;   // the full height of the board
glass_left =  8.0;   // red showing on the left
glass_pro  =  3.4;   // glass stands this proud of the PCB
panel_d    = 10.8;   // glass face to the back of its cables

// ---- the ESP32 ------------------------------------------------------
esp_l      = 52.0;   // long axis: runs front-to-back
esp_w      = 28.0;
esp_h      =  6.0;   // bare board on its standoffs, cables led away flat
usb_w      = 11.0;   // USB-C, plus room
usb_h      =  5.5;
usb_z      =  4.0;   // port centre above the base's inner face

// ---- print settings -------------------------------------------------
wall       = 2.0;
clear      = 0.4;
bezel      = 1.2;
glass_gap  = 0.5;    // per side. 0.3 was too tight: an FDM hole comes
                     // out 0.2-0.4 undersize, so it can print smaller
                     // than the glass and then the panel only goes in by
                     // being pressed -- which cracks the flex between the
                     // glass and its board. Costs 0.4 mm of visible gap.

// The front face has to be THICKER than the wall, or the panel has
// nowhere to sit. Glass stands 3.4 proud of its board, so 3.4 of face in
// front of the PCB is what makes the glass finish flush; the board's own
// 1.6 sits behind that. 2 mm of wall would leave the glass standing 1.4
// proud and the pocket cutting clean through the face -- which is what
// the first render showed, a front you could see straight through.
front_t    = glass_pro + pcb_t;   // 5.0

// ---- room for the flex ----------------------------------------------
// The glass is 69 wide on an 86 board, so its flex has to get down to the
// PCB at one of the two SHORT edges -- the 8 mm and 9 mm red strips. The
// pocket gave those edges 0.4 mm, which is nothing: a flex that wraps the
// edge, or merely stands proud of it, is gripped by the pocket wall. A
// panel went white after being fitted, and this is the likeliest reason.
//
// Relieved over the MIDDLE of each short edge only. Relieving the whole
// edge would leave the board unlocated in X and the picture would wander
// in the window; leaving a land top and bottom keeps it placed while the
// flex gets its room.
flex_gap   = 1.5;    // extra clearance at each short edge
flex_land  = 9.0;    // pocket wall kept at each corner, to locate the board

// ---- the wedge ------------------------------------------------------
// 20 degrees, and the reasoning is in BRIEF.md: at a desk your sight line
// drops about 41 degrees, so a screen aimed straight at you would lean 49
// -- which costs 90 mm of depth and is not buildable. 20 leaves 29 off
// axis, which an ILI9341 takes without washing out.
lean       = 20;

face_w     = pcb_w + 2 * (wall + clear);        // 90.8
face_len   = pcb_h + 2 * (wall + clear);        // 54.8, measured UP THE SLOPE
// The face has to come out EXACTLY face_len long, because that is what
// the window is centred in. height = face_len*cos(lean) does that.
// It was face_len*cos(lean) + wall + 2, which made the face 59.1 and
// dropped the panel 2.2 mm off the bottom edge.
height     = face_len * cos(lean);
depth      = 70.0;
corner_r   = 4.0;

// ---- the base -------------------------------------------------------
base_t     = 2.5;
lip_h      = 5.0;    // how far the base's lip reaches up inside the shell
lip_fit    = 0.25;   // per side. THE number to tune if the base is loose.

// ---- the ESP32's cradle ---------------------------------------------
// The board slides in from the BACK until its port end meets the shell's
// back wall, so the USB-C lines up with the hole by construction rather
// than by being placed carefully.
//
// The first version was two bare 5 mm pegs. They held the board off the
// floor at roughly the right height and did nothing else: nothing located
// it sideways, nothing stopped it sliding, and nothing held it down --
// so plugging a cable in would simply push the board off them.
esp_lift   = 3.0;    // standoff, so the port centres on the hole
rail_t     = 3.0;    // the side rails
rail_h     = 5.6;    // tall enough to get a lip over the board
rail_gap   = 0.8;    // per side, around the board's 28 mm width
clip_over  = 1.0;    // how far the rails' lip reaches over the board

// ---- keying ---------------------------------------------------------
// A rib on ONE SIDE rail of the lip, well forward of centre, and a slot
// for it in the shell's matching side wall.
//
// It was on the BACK rail first, blocked by the leaning front wall when
// reversed -- but only by 0.52 mm, because the lip's front is already set
// back 1.95 mm to clear that lean and a reversed base simply eats the
// slack. The setback fights the keying.
//
// Off-centre along the LENGTH cannot be symmetric: reversed, the rib
// lands at depth - key_y, where the shell's wall is solid, and is blocked
// by its full depth with nothing to absorb it.
key_y      = 20.0;   // forward of the middle, so reversing moves it 30 mm
key_w      = 24.0;   // along the length.
                     //
                     // Was 10, which worked and could not be FOUND: at
                     // 10 x 3 it reads as a print artefact rather than a
                     // feature, and a tab that small snaps off the first
                     // time the base is prised out. Length is free here
                     // -- the blocking depth is what does the keying, and
                     // that is unchanged -- so it buys visibility and
                     // strength for nothing.
key_t      = 1.5;    // how far the rib stands out sideways
key_h      = 4.0;

// ---- the vent -------------------------------------------------------
hex_r      = 3.4;    // across the flats
hex_gap    = 1.6;    // web between cells

// =====================================================================
// helpers
// =====================================================================

module rrect(w, h, r) {
	hull() for (x = [-1, 1], y = [-1, 1])
		translate([x * (w / 2 - r), y * (h / 2 - r)]) circle(r);
}

// The side profile: a right trapezoid. Vertical back, flat base, front
// leaning back by `lean`. Extruded along X to make the wedge.
module wedge_profile(d, h, inset = 0) {
	offset(r = -inset)
		polygon([[0, 0],
			 [h * tan(lean), h],
			 [d, h],
			 [d, 0]]);
}

module wedge(d, h, w, inset = 0) {
	rotate([90, 0, 90])
		linear_extrude(w, center = true)
		wedge_profile(d, h, inset);
}

// ONE CONVENTION, STATED ONCE, because mixing two of them cost a whole
// render: wedge() rotates a profile by [90,0,90], which maps local
// (x,y,z) to world (z,x,y). So for everything below:
//
//     world X = WIDTH      (centred on 0)
//     world Y = DEPTH      (0 at the front edge, +depth at the back)
//     world Z = HEIGHT     (0 at the base)
//
// The first version wrote every cut with Y as height and Z as depth --
// the other way round -- so the window, the port and the vent all landed
// outside the solid and removed nothing. The shell rendered as a plain
// featureless box, which is exactly what that looks like.

// A frame whose XY plane IS the slanted front face, origin at the middle
// of the bottom front edge, local +Y running UP THE SLOPE.
//
// Going up a back-leaning face moves BACK as well as up, so local +Y has
// to land on (0, sin(lean), cos(lean)). rotate([a,0,0]) sends (0,1,0) to
// (0, cos a, sin a), so a = 90 - lean. Local +Z then points forward and
// up -- the OUTWARD normal -- so cuts extrude in -Z, into the wall.
module on_front() {
	rotate([90 - lean, 0, 0]) children();
}

// Honeycomb, drawn in XZ to face the back wall.
module hex_field(w, h, t) {
	pitch = hex_r * 2 + hex_gap;
	rows  = ceil(h / (pitch * 0.866)) + 1;
	cols  = ceil(w / pitch) + 1;

	rotate([-90, 0, 0])
		for (r = [-rows : rows], c = [-cols : cols]) {
			x = c * pitch + (r % 2 == 0 ? 0 : pitch / 2);
			y = r * pitch * 0.866;
			// The whole CELL has to be inside the field, not just
			// its centre. Testing the centre alone leaves half
			// hexes hanging off the edge, which read as damage
			// rather than as a vent.
			if (abs(x) + hex_r < w / 2 && abs(y) + hex_r < h / 2)
				translate([x, y, -t / 2])
					cylinder(r = hex_r, h = t, $fn = 6);
		}
}

// =====================================================================
// v2_shell
// =====================================================================
module v2_shell() {
	// Where the glass sits on the slanted face, measured UP THE SLOPE.
	// The glass is not centred on the board -- 8 mm of red left against
	// 9 right -- so the window is not centred either.
	ap_cx = -pcb_w / 2 + glass_left + glass_w / 2;
	ap_cy = face_len / 2;

	difference() {
		union() {
			difference() {
				wedge(depth, height, face_w);

				// hollow: the same wedge one wall in
				wedge(depth, height, face_w - 2 * wall, wall);

				// open the bottom
				translate([0, depth / 2, wall / 2])
					cube([face_w - 2 * wall + 0.01, depth,
					      wall + 0.02], center = true);
			}

			// Thicken the front face behind the panel, to front_t.
			// Added AFTER the hollow, or the hollow would take it
			// straight back off.
			on_front()
				translate([0, ap_cy, -front_t])
				linear_extrude(front_t - wall)
				rrect(pcb_w + 2 * clear + 4,
				      pcb_h + 2 * clear + 4, 2);
		}

		// the window, through the whole face
		on_front()
			translate([ap_cx, ap_cy, -front_t - 2])
			linear_extrude(front_t + 4)
			rrect(glass_w + 2 * glass_gap,
			      glass_h + 2 * glass_gap, 1.5);

		// The pocket the panel drops into from behind. Only the back
		// 1.6 of the face, so glass_pro of ledge is left under the
		// red strips to hold the board -- the same two ledges V1
		// relies on, for the same reason: the glass is the full
		// height of the board, so there is no red top or bottom.
		on_front()
			translate([0, ap_cy, -front_t - 2])
			linear_extrude(pcb_t + clear + 2)
			rrect(pcb_w + 2 * clear, pcb_h + 2 * clear, 1.5);

		// Relief for the flex, at both short edges. Both, because
		// which one it exits is not something a photo settles, and
		// relieving the unused side costs nothing.
		on_front()
			for (x = [-1, 1])
				translate([x * (pcb_w / 2 + clear + flex_gap / 2),
					   ap_cy, -front_t - 2])
					linear_extrude(pcb_t + clear + 2)
					square([flex_gap + 1,
						pcb_h + 2 * clear
						- 2 * flex_land],
					       center = true);

		// the USB port, in the vertical back wall
		translate([0, depth - wall / 2, base_t + usb_z])
			cube([usb_w, wall + 2, usb_h], center = true);

		// the honeycomb, above the port
		translate([0, depth - wall / 2, height * 0.60])
			hex_field(face_w - 24, height * 0.44, wall + 4);

		// the keyway the base's rib drops into, in the LEFT wall
		translate([-(face_w / 2 - wall), key_y, key_h / 2 + 0.6])
			cube([key_t * 2 + 1, key_w + 0.6, key_h + 0.6],
			     center = true);
	}
}

// =====================================================================
// v2_base
// =====================================================================
module v2_base() {
	bw = face_w - 2 * wall - 2 * lip_fit;
	bd = depth - 2 * wall - 2 * lip_fit;

	// WHERE THE LIP'S FRONT EDGE GOES, and why it is not simply
	// (depth - bd)/2.
	//
	// The shell's front wall LEANS, so the cavity's front boundary moves
	// BACK as it rises: Y = z*tan(lean) + wall/cos(lean). A straight
	// sided lip clears at the bottom and fouls harder the further in it
	// goes -- at lip_h it was 1.7 mm inside the wall, which is why the
	// base would not seat and why it felt like it was hitting the screen.
	//
	// Set back to clear at the lip's TALLEST point, which is the only
	// place that matters.
	lip_y0 = lip_h * tan(lean) + wall / cos(lean) + lip_fit;
	lip_y1 = depth - wall - lip_fit;

	// The board, sliding back until its port end meets the back wall.
	esp_y1 = depth - wall;
	esp_y0 = esp_y1 - esp_l;

	difference() {
		union() {
			// the plate, the shell's own footprint so it closes
			// the bottom flush
			translate([0, depth / 2, -base_t])
				linear_extrude(base_t)
				rrect(face_w, depth, corner_r);

			// the lip that locates it inside the shell
			translate([0, (lip_y0 + lip_y1) / 2, 0])
				linear_extrude(lip_h)
				difference() {
					rrect(bw, lip_y1 - lip_y0,
					      max(0.5, corner_r - wall));
					rrect(bw - 2 * wall,
					      lip_y1 - lip_y0 - 2 * wall,
					      max(0.5, corner_r - 2 * wall));
				}

			// --- the cradle ------------------------------------
			// pads, to lift the board so its port centres on the
			// hole in the back wall
			for (x = [-1, 1], y = [esp_y0 + 3, esp_y1 - 3])
				translate([x * esp_w / 3, y, 0])
					cylinder(d = 5, h = esp_lift);

			// side rails, with a lip over the board's edges. The
			// board slides in from the back, under the lip.
			for (x = [-1, 1])
				translate([x * (esp_w / 2 + rail_gap
						+ rail_t / 2),
					   (esp_y0 + esp_y1) / 2, 0]) {
					// Lifted by rail_h/2, because
					// center=true centres on ALL THREE
					// axes -- the rails were half buried
					// under the plate, topping out at 2.8
					// while their own lips sat at 4.6, so
					// the two never touched.
					translate([0, 0, rail_h / 2])
						cube([rail_t, esp_l, rail_h],
						     center = true);
					// the lip, reaching inward over the
					// board at just above its top face
					// OVERLAPS the rail by 0.4 rather than
					// butting against it. Butting leaves
					// coincident faces, which OpenSCAD
					// does not merge -- the two lips came
					// out as loose slivers. This is the
					// FOURTH time this trap has bitten in
					// this project: posts, loom clips,
					// snap barbs, now these. Anything
					// added to anything else gets an
					// overlap, not a shared face.
					translate([-x * (rail_t / 2
							 + clip_over / 2 - 0.2),
						   0,
						   esp_lift + 1.6
						   + clip_over / 2])
						cube([clip_over + 0.4,
						      esp_l - 6, clip_over],
						     center = true);
				}

			// the key: a rib on the LEFT rail of the lip
			translate([-(bw / 2 + key_t / 2), key_y,
				   key_h / 2 + 0.6])
				cube([key_t, key_w, key_h], center = true);

			// a stop at the front, so pushing a cable in cannot
			// drive the board forward off its pads
			// Centred in X and standing ON the plate, not through
			// it -- the same center= trap as the rails.
			translate([0, esp_y0 - 1.5, rail_h / 2])
				cube([esp_w + 2 * rail_gap + 2 * rail_t,
				      3, rail_h], center = true);
		}

		// a finger notch, so the base can be prised back out
		translate([0, 6, -base_t - 1])
			linear_extrude(base_t + 2) rrect(18, 5, 2);
	}
}

// =====================================================================
//   openscad -D 'PART="shell"' -o v2_shell.stl overwatch_v2.scad
// =====================================================================
PART = "all";

if (PART == "shell")     v2_shell();
else if (PART == "base") v2_base();
else { v2_shell(); v2_base(); }
