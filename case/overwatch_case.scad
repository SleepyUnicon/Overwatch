// =====================================================================
// Overwatch - the case
//
// A bezel that shows the PICTURE and nothing else, and an EMPTY tray that
// plugs into the back of it. Two printed parts, no screws, no posts, and
// nothing inside the body at all.
//
// WHAT CHANGED, AND WHY
//
// The version before this had two faults that between them cost a panel.
//
//   1. The aperture was sized to the GLASS and the glass was a press fit
//      in it -- 0.3 mm nominal, which an FDM hole can easily print
//      UNDERSIZE. The only way the panel went in was by being pressed,
//      and pressing a glass module into a too-small hole cracks the flex
//      between the glass and its board. The module then lights up white
//      and never draws, with nothing in any log to say why.
//
//   2. Four snap pegs sat at x=+/-40, y=+/-12 -- INSIDE the panel's
//      +/-43 x +/-25 footprint. To reach their sockets they travelled
//      through the space the board occupies, so assembling it would
//      press four posts into the back of the panel. They were moved out
//      of the corners to save border and never checked against the board.
//
// Both are gone. The lip now overlaps the glass, so the glass does not
// pass through the aperture AT ALL -- it goes in from behind and rests
// against the lip. There is no press fit left to be tight. And there are
// no pegs, because there is nothing inside.
//
// THE HALVES JOIN AT THE RIM. The bezel carries a 1.4 mm rim reaching
// back past the board; the tray's spigot plugs into it. Friction, and the
// join is at the perimeter where there is room for it -- not through the
// middle where the panel is.
//
// PRINT ORIENTATION
//   bezel  face DOWN. The chamfer round the window then prints as an
//          overhang off the bed's first layer, which is where it is
//          cleanest, and the face people look at gets the bed finish.
//   tray   open side UP.
// =====================================================================

$fn = 48;

// ---- the panel, measured -------------------------------------------
pcb_w      = 86.0;
pcb_h      = 50.0;
pcb_t      = 1.6;
glass_w    = 69.0;
glass_h    = 50.0;   // the full height of the board
glass_left =  8.0;   // UNUSED, kept as the raw measurement. Careful:
                     // "left" here is off the photograph, not the
                     // model's +x. See WHICH WAY IS RIGHT.
glass_pro  =  3.4;   // glass stands this proud of its board

// The whole module, front to back: 8.0 measured. Glass 3.4 + PCB 1.6
// leaves 3.0 of ribbon and driver reaching BACK into the tray, which is
// the figure the tray's depth has to start from. The perch was sized
// against an assumed 5.8, so it was conservative rather than wrong.
disp_d     =  8.0;
panel_back = disp_d - glass_pro - pcb_t;   // 3.0, into the tray

// The LIT area, and where it sits on the BOARD.
//
// Measured on the board itself, 2026-09-24: the picture starts 11 mm in
// from one end of the 86 mm board and 17 mm in from the other, so it is
// 58.0 wide and its centre is 3.0 mm off the board's.
//
// Two independent measurements agree on this. Reading off the printed
// case gave 13 and 20 from the CASE edge; with the board inset 2.4 each
// side that is 10.6 and 17.6 from the board edge, against 11 and 17 here
// -- within 0.6 mm. The board reading is the one used, because it does
// not depend on the case having printed to size.
//
// 58.0 also lands 0.4 mm off the nominal 57.6 for a 2.8" 4:3 panel, which
// is the kind of agreement that means both numbers are probably right.
//
// The picture is centred vertically: 3 mm from the board edge at the top
// and 3 at the bottom, measured.
act_w      = 58.0;
// MEASURED too, now. The glass is the board's full 50 mm height and the
// picture starts 3 mm in from the board edge top and bottom, so it is 44
// tall. That was derived as 43.5 (4:3 from the measured 58.0 width); the
// measurement is 0.5 more. 58.0 x 44.0 is 1.318:1 against a nominal
// 1.333, which is either a slightly wide panel or a rounded reading --
// and well inside the 1 mm the window carries either way.
act_h      = 44.0;

// WHICH WAY IS RIGHT
//
// The screen's face is at z=0 and the body runs back to +z, so the
// viewer looks along +z with +y up. In a right-handed frame that puts
// the viewer's RIGHT at NEGATIVE x. Not positive. This is the whole
// trap: every left and right in the notes -- the 11/17 borders, "USB on
// the right" -- is from in front of the screen, and writing them against
// +x mirrors the case. The port lands on the far side and the wide
// border goes with it, and a box this symmetric will not look wrong in
// any render.
//
// So don't write act_cx as a signed guess. Derive it from the border
// the viewer sees on their right, and it cannot come out mirrored.
bez_right  = 17.0;   // border on the viewer's RIGHT, measured
bez_left   = 11.0;   // and on their left -- 11 + 58 + 17 = 86 = pcb_w
act_cx     = -pcb_w / 2 + bez_right + act_w / 2;   // = +3.0

// ---- the ESP32 ------------------------------------------------------
// From the board's own spec sheet, not estimated. The model previously
// carried 52 x 28 with no allowance at all for the pins, which was wrong
// in both directions: 3.7 mm too long, and it would have sat the board
// flat on the floor and bent 38 header pins.
esp_l      = 48.26;  // PCB length
esp_w      = 27.94;  // PCB width
esp_t      =  1.60;  // PCB thickness
esp_pins   =  8.50;  // header pins hanging BELOW the board
esp_shield =  3.10;  // WROOM module, above the board

// USB-C, on the short end. Centred on the width (13.97 from either edge),
// 8.94 across the metal shell, 3.16 tall from the PCB's top surface, and
// it overhangs the board's end by 1.20.
usb_shell_w = 8.94;
usb_shell_h = 3.16;
usb_over    = 1.20;

// The opening has to pass a PLUG, not the receptacle: a USB-C overmould
// is a good deal bigger than the 8.94 x 3.16 socket it goes into. These
// are the spec's maximum cable-plug overmould, so any compliant cable
// fits; usb_fit is the whole allowance, print shrink included (FDM holes
// come out 0.2-0.4 under).
usb_plug_w = 12.35;
usb_plug_h =  6.50;
usb_fit    =  0.60;

function usb_w() = usb_plug_w + usb_fit;   // 12.95
function usb_h() = usb_plug_h + usb_fit;   //  7.10

// ---- the ESP32's perch ----------------------------------------------
// The board lies FLAT against the back wall, component side toward it,
// just below the vents -- the arrangement in the mock-up. Its pins and
// the dupont shells point forward into the body, which is the only place
// with room for them.
//
// THE STANDOFF IS SET BY THE PLUG, NOT THE SOCKET. The connector is only
// 3.16 tall, so 4 mm would clear it. But a USB-C plug's overmould is
// about 7 across, centred on that socket, and at 4 mm it reaches z=39.08
// against a back wall at 38 -- the cable fouls the case before it seats.
//
//   s=4 -> plug reaches 39.08   FOULS
//   s=5 -> plug reaches 38.08   FOULS
//   s=6 -> plug reaches 37.08   clears
// The display's own connectors sit on the BACK of the panel and start
// right at the edge on the case's right-hand side -- negative x, the same
// edge the USB comes out of. The spigot's nose overlaps the board by 1.2
// all the way round, so on that edge it would land straight on them.
//
// Nothing inboard of the spigot's inner face needs any help: that is open
// cavity, 33 deep. Only the 1.2 band where the nose overhangs the board
// is in the way, so that band is cut back over the connectors' height.
// The spigot keeps its full OUTER face there, so it still locates in the
// rim -- it just stops touching the board on that one edge.
panel_conn = 3.4;    // connector height off the board, 3.0 measured + 0.4

esp_stand  = 6.0;    // board's component face to the back wall
// The slot is cut to the BOARD, not to a round number. It used to leave
// 0.50 a side on the width and 0.30 on the thickness -- the board sat in
// it loose enough to rattle.
//
// FDM takes some of this back: a slot prints 0.1-0.2 narrow. So 0.15 a
// side lands near zero slack in the plastic, which is what snug means.
// It is THE number to open up if the board will not go in. Do not force
// it -- forcing a fit is how the first display's flex went.
esp_fit    = 0.15;   // per side, on the width     -> slot 28.24 / 27.94
esp_fit_t  = 0.15;   // total, on the thickness    -> slot  1.75 /  1.60

rail_back  = 1.5;    // material behind the slot
rail_grip  = 1.0;    // how far the rails reach over the board's edges

// ---- the vent -------------------------------------------------------
// Two rows of hexagons across the top of the back wall, with the board
// directly underneath.
//
// The size is not a style choice. The slanted underside has risen to
// y=-15.56 by the time it reaches the back wall, so the usable height
// there is 42.96 -- and the board takes 27.94 of it. That leaves about
// 12 mm for two rows, which sets the cell.
hex_r      = 2.6;
hex_gap    = 1.3;

// ---- clearances -----------------------------------------------------
// 1.0 everywhere the panel touches, not 0.4. The old 0.4 is what made it
// a press fit, and a press fit is what broke the flex.
clear      = 1.0;

// The window is drawn 1 mm LARGER than the lit area all round. Too large
// shows a sliver of the glass's black border, which nobody minds. Too
// small covers picture, which cannot be fixed without reprinting.
act_margin = 1.0;

// ---- the bezel ------------------------------------------------------
wall       = 2.0;
face_w     = pcb_w + 2 * clear + 2 * 1.4;   // 90.8
face_h     = pcb_h + 2 * clear + 2 * 1.4;   // 54.8
corner_r   = 4.0;

lip_t      = 1.2;    // plastic in front of the glass
ap_r       = 0.4;    // window corner radius: half a nozzle, i.e. square

// How far the window opens out toward the face, on the LEFT and RIGHT
// only. The taper is what lets a fingertip reach the corners of the
// picture. Chamfering the top and bottom too cost 3 mm of border where
// there is only 5.4, leaving a 1.4 mm knife edge -- so those stay square.
chamf      = 3.0;

// The rim the tray plugs into. 1.4 is what is left between the PCB pocket
// and the outer face, and it is enough: it locates, it does not carry
// load.
rim_d      = 5.0;
rim_fit    = 0.2;    // per side. THE number to tune if the tray is loose.

bezel_d    = lip_t + glass_pro + pcb_t + rim_d;

// ---- the tray -------------------------------------------------------
// Sized so the TRAY comes out 40.0 deep on its own -- rim_d + tray_d +
// back_t. The assembled case is 6.2 more than that, because the bezel
// stands in front of the tray: 46.2.
tray_d     = 33.0;
back_t     = 2.0;

// ---- the slant ------------------------------------------------------
lean       = 15;     // the underside, so it sits back on a desk

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

// Everything below the desk plane: through the bezel's bottom front
// edge, rising at `lean` as it goes back.
module desk_cut(drop = 0) {
	translate([0, -face_h / 2 + drop, 0])
		rotate([-lean, 0, 0])
		translate([-200, -400, -200])
		cube([400, 400, 400]);
}

// The seats for the panel take their corner radius from the CLEARANCE,
// and that is not a style choice.
//
// A sharp corner in a pocket rounded by r clears by r - sqrt(2)*|clear-r|
// while r > clear, and by the full `clear` once r <= clear. So r = clear
// is the point where the corner clears exactly as much as the flats do,
// and going sharper than that buys nothing at all.
//
// It cannot go sharper anyway. The seat's corner is at (44, 26) and the
// outer profile's corner arc is centred at (41.4, 23.4) with r=4, which
// leaves 0.323 mm of wall at a dead-square corner -- under one extrusion,
// so it would print as a hole. Corner relief is out for the same reason:
// a circle centred on the corner has to be smaller than 0.323 to stay
// inside the wall.
//
//    seat r    wall at the corner    corner clearance
//      1.5          0.944                 0.793      (what V1 had)
//      1.0          0.737                 1.000      <- here
//      0.0          0.323                 1.000      unprintable
//
// What actually stopped the first V1 sitting down was the CLEARANCE, not
// the rounding: at clear = 0.4 the board's corner fell 1.556 from the arc
// centre against a 1.5 radius and fouled by 0.056 before the printer
// added its own. At clear = 1.0 it clears by the full millimetre.
seat_r = clear;

// =====================================================================
// front_bezel
// =====================================================================

module front_bezel() {
	// The window sits where the PICTURE is, measured -- see act_cx. It
	// used to be derived from the glass's position on the board, which
	// assumed the lit area was centred on the glass. It is not.
	cx = act_cx;

	ap_w = act_w + 2 * act_margin;
	ap_h = act_h + 2 * act_margin;

	difference() {
		union() {
			rbox(face_w, face_h, lip_t + glass_pro + pcb_t,
			     corner_r);
			// the rim, reaching back past the board for the tray
			translate([0, 0, lip_t + glass_pro + pcb_t])
				difference() {
					rbox(face_w, face_h, rim_d, corner_r);
					translate([0, 0, -1])
						rbox(pcb_w + 2 * clear,
						     pcb_h + 2 * clear,
						     rim_d + 2,
						     corner_r - 1.4);
				}
		}

		// The window, chamfered: narrow at the glass, opening out
		// toward the face. The taper keeps the corners from catching
		// a fingertip on the way to the edge of the picture, and it
		// makes the border look thinner than it is.
		translate([cx, 0, 0])
			hull() {
				// SQUARE corners. The display's own corners are
				// sharp, so a rounded window leaves four
				// crescents of black glass showing at the
				// corners and nothing else. ap_r is half a
				// nozzle: as square as an FDM part gets.
				// Chamfered on the LEFT and RIGHT only -- the
				// height is the same at both ends of the
				// hull, so the top and bottom walls stay
				// square.
				//
				// Chamfering all four edges cost 3.0 mm of
				// border top and bottom, where there is only
				// 5.4 to begin with: it left a 1.4 mm knife
				// edge against sides of 9.4 and 15.4. The
				// sides can afford the taper and the top and
				// bottom cannot, so only the sides get it.
				translate([0, 0, -0.01])
					linear_extrude(0.01)
					rrect(ap_w + 2 * chamf, ap_h, ap_r);
				translate([0, 0, lip_t])
					linear_extrude(0.01)
					rrect(ap_w, ap_h, ap_r);
			}
		// and straight on through the rest of the lip
		translate([cx, 0, lip_t - 0.01])
			linear_extrude(glass_pro + pcb_t + 2)
			rrect(ap_w, ap_h, ap_r);

		// the glass recess -- the glass rests against the lip here.
		// SQUARE, with corner relief: the glass has sharp corners.
		translate([cx, 0, lip_t])
			linear_extrude(glass_pro + pcb_t + 2)
			rrect(glass_w + 2 * clear, glass_h + 2 * clear, seat_r);

		// the board's own pocket, behind the glass. Square too -- and
		// this is the one that mattered: it is the seat that held the
		// first V1 off.
		translate([0, 0, lip_t + glass_pro])
			linear_extrude(pcb_t + rim_d + 2)
			rrect(pcb_w + 2 * clear, pcb_h + 2 * clear, seat_r);

		desk_cut();
	}
}

// The tray's empty volume. One shape, used twice: to hollow the box, and
// to clip whatever stands inside it. Nothing in here may be taken on
// trust to fit -- the underside slants, so the cavity is NARROWER at the
// back than at the front. By the back wall its floor has climbed to
// y = -15.56, and the ESP32's stop reaches -17.57, so unclipped it drove
// a 3 mm tab clean through the bottom of the case.
module tray_inside() {
	difference() {
		union() {
			// Through the SPIGOT it is the spigot's width, less a
			// wall each side -- that part has to stay slim enough
			// to enter the bezel's rim.
			translate([0, 0, -1])
				rbox(pcb_w + 2 * clear - 2 * rim_fit
				     - 2 * wall,
				     pcb_h + 2 * clear - 2 * rim_fit
				     - 2 * wall,
				     rim_d + 1,
				     corner_r - 1.4 - wall);
			// Through the BODY it is the body's width, less a
			// wall each side. It used to carry the spigot's
			// width all the way back, which made the sides 3.6
			// thick instead of 2.0 and cost 1.6 mm a side of
			// room that the body had no reason to give up.
			translate([0, 0, rim_d - 0.01])
				rbox(face_w - 2 * wall, face_h - 2 * wall,
				     tray_d + 0.01, corner_r - wall);
		}
		desk_cut((lip_t + glass_pro + pcb_t) * tan(lean)
			 + wall / cos(lean));
	}
}

// =====================================================================
// back_tray  -- an empty box
// =====================================================================
module back_tray() {
	sp_w = pcb_w + 2 * clear - 2 * rim_fit;   // plugs into the bezel's rim
	sp_h = pcb_h + 2 * clear - 2 * rim_fit;

	// where the nose overhangs the board, on the connector edge
	conn_out = -(pcb_w / 2);            // the board's edge, -43.0
	conn_in  = -(sp_w / 2 - wall) + 1;  // 1 past the spigot's inner face

	difference() {
		union() {
			// the spigot, entering the bezel
			rbox(sp_w, sp_h, rim_d, corner_r - 1.4);
			// the body
			translate([0, 0, rim_d])
				rbox(face_w, face_h, tray_d + back_t,
				     corner_r);
		}

		// Hollow it, leaving the back wall. One cut through both, so
		// the inside is a single empty volume with no step in it.
		//
		// The cavity's FLOOR has to follow the slant, not sit flat.
		// As a plain box its floor was at y=-23.80 while the slanted
		// underside climbs past that at z=7.24 and reaches -15.56 by
		// the back wall -- so from 7 mm back the slant cut the bottom
		// wall clean away and kept going into the cavity. The case
		// had no bottom for most of its length.
		//
		// Offset vertically by wall/cos(lean), which is what gives a
		// true `wall` measured PERPENDICULAR to a sloping face.
		tray_inside();

		// the connector relief -- see panel_conn
		translate([(conn_out + conn_in) / 2, 0, panel_conn / 2 - 1])
			cube([conn_in - conn_out, sp_h + 2, panel_conn + 2],
			     center = true);

		// The USB port, in the RIGHT SIDE wall, positioned from the
		// board rather than guessed. The board's port end butts the
		// wall, the port is centred on the board's width, and it sits
		// usb_shell_h/2 above the PCB's top face.
		//
		// A stadium, not a rectangle -- the plug is round-ended, so a
		// square hole only ever reads as a square hole with a plug
		// rattling in it.
		translate([-(face_w / 2 - wall / 2), 0, usb_z()])
			rotate([0, 90, 0])
			linear_extrude(wall + 2, center = true)
			hull() for (s = [-1, 1])
				translate([0, s * (usb_w() - usb_h()) / 2])
					circle(r = usb_h() / 2, $fn = 48);

		// the vents: two rows of hexagons across the top
		for (row = [0, 1])
			for (i = [-5 : 5]) {
				pitch = 2 * hex_r + hex_gap;
				x = i * pitch + (row == 0 ? 0 : pitch / 2);
				y = vent_top() - hex_r - row * pitch * 0.866;
				if (abs(x) + hex_r < (face_w - 16) / 2)
					// Start INSIDE the cavity, not 1 mm
					// down from the outer face. The wall
					// spans 38..40; this used to start at
					// 39 and left a 1 mm skin across every
					// cell -- the same fault as the port.
					translate([x, y, rim_d + tray_d - 1])
						linear_extrude(back_t + 2)
						circle(r = hex_r, $fn = 6);
			}

		// The SAME slant as the bezel's, continued.
		//
		// The tray sits (lip_t + glass_pro + pcb_t) behind the bezel
		// in the assembly, so for one unbroken underside its cut has
		// to start that much further up the slope. It used to be
		// translate([0,0,rim_d]) desk_cut(wall), which works out 1.00
		// mm off and leaves a step in the line at the joint.
		desk_cut((lip_t + glass_pro + pcb_t) * tan(lean));
	}

	// --- the ESP32's perch -------------------------------------
	//
	// Two rails standing off the back wall, each with a groove the
	// board's long edges slide into. The board goes in from the RIGHT
	// until its port end meets the wall, so the USB-C lines up with the
	// slot by construction.
	//
	// The rails' inner faces sit INSIDE the board's width, which is only
	// possible because it slides in sideways -- they could not capture
	// an edge they did not overlap.
	// Negative x is the viewer's right -- see "WHICH WAY IS RIGHT". The
	// board's port end butts THAT wall, so the USB comes out on the
	// right of the screen, which is where it was asked for.
	x_wall = -(face_w / 2 - wall);    // the board's port end
	x_in   = x_wall + esp_l;          // its inboard end
	z_wall = rim_d + tray_d;          // back wall, inside
	z_comp = z_wall - esp_stand;      // the board's component face
	z_sold = z_comp - esp_t;          // and its solder face

	y_grip = esp_w / 2 - rail_grip;   // the lip's inner edge, over the board
	y_slot = esp_w / 2 + esp_fit;     // where the board's edge stops
	y_out  = y_slot + rail_back;      // the rail's outer face

	// ...clipped to the cavity, so the rails and the stop can be sized
	// for the BOARD without either of them reaching the slanted floor.
	intersection() {
		union() {
			for (y = [-1, 1])
				difference() {
					// the rail
					translate([(x_wall + x_in) / 2,
						   y * (y_grip + y_out) / 2,
						   (z_sold - 1.2 + z_wall)
						   / 2])
						cube([esp_l, y_out - y_grip,
						      z_wall - z_sold + 1.2],
						     center = true);
					// The slot the board's edge slides
					// into. Cut from the centreline
					// outward, so it stays open inboard
					// -- a slot closed on both sides is
					// one the board cannot enter.
					translate([(x_wall + x_in) / 2,
						   y * y_slot / 2,
						   (z_sold + z_comp) / 2])
						cube([esp_l + 2, y_slot,
						      esp_t + esp_fit_t],
						     center = true);
				}

			// the stop at the inboard end
			translate([x_in + 1.5, 0, (z_sold + z_wall) / 2])
				cube([3, 2 * y_out, z_wall - z_sold],
				     center = true);
		}
		tray_inside();
	}
}

// Where the vent field starts, just under the wall's top edge.
function vent_top() = face_h / 2 - 3;

// The USB opening's centre. The connector sits on the board's component
// face, which is esp_stand in from the back wall, and extends back toward
// the wall -- so the shell's middle is half its height further back.
function usb_z() = rim_d + tray_d - esp_stand + usb_shell_h / 2;

// =====================================================================
//   openscad -D 'PART="front"' -o front_bezel.stl overwatch_case.scad
// =====================================================================
PART = "all";

if (PART == "front")     front_bezel();
else if (PART == "back") back_tray();
else {
	front_bezel();
	translate([0, 0, lip_t + glass_pro + pcb_t]) back_tray();
}
