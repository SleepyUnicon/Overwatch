/*
 * The cross, and the tap path that has to exist beside it.
 *
 * docs/multi-provider.md 4d is the reason this file draws controls rather than
 * relying on the swipe: a sliding finger on this panel loses contact, one
 * stroke arrives as five or six presses, and even with the stitching in
 * ui_swipe.c "it lands about half the time". Every navigation on this device
 * has a tap path. This is the widget pages' one.
 */
#include "ui_pages.h"

#include "ui_launcher.h"
#include "ui_music.h"
#include "ui_swipe.h"
#include "ui_theme.h"
#include "usage_view.h"

#define COL_BG		lv_color_hex(ui_theme()->bg)
#define COL_TEXT	lv_color_hex(ui_theme()->text)
#define COL_DIM		lv_color_hex(ui_theme()->dim)

/*
 * The home strip, in the band the old page rail occupied.
 *
 * At the bottom rather than on the edge the page was opened from, which would
 * have matched the gesture more neatly and cost more than it was worth: the
 * launcher's grid is laid out against a fixed area (ui_launcher.c's BTN_H and
 * its six tiles), and taking 24 px off the side would have meant re-fitting
 * it. This band was ALREADY reserved for the rail, so nothing moves.
 *
 * 320 x 40 is the full width. ui_settings.c:1499 measured 72 x 48 as the point
 * where a control becomes reliably hittable here; this is 8 px under that in
 * height and four times over it in width, which is the same compromise the
 * rail made and for the same reason -- the misses that matter on this panel
 * are horizontal, because the thumb arrives from the side of the case.
 */
#define HOME_H		40
#define HOME_Y		(240 - HOME_H)

static enum ui_page cur = UI_PAGE_GAUGES;

/* Which way each spoke lies from the centre. Read both ways: to open MUSIC you
 * go LEFT, and from MUSIC you come home going the other way. */
static const enum ui_dir spoke_dir[UI_PAGE_N] = {
	[UI_PAGE_MUSIC]    = UI_DIR_LEFT,
	[UI_PAGE_LAUNCHER] = UI_DIR_RIGHT,
};

static enum ui_dir opposite(enum ui_dir d)
{
	switch (d) {
	case UI_DIR_LEFT:  return UI_DIR_RIGHT;
	case UI_DIR_RIGHT: return UI_DIR_LEFT;
	case UI_DIR_UP:    return UI_DIR_DOWN;
	default:           return UI_DIR_UP;
	}
}

static void show_only(enum ui_page p)
{
	/*
	 * Close first, open second, always in that order. Both overlays are
	 * full-screen children of one screen, and opening before closing
	 * leaves two of them stacked for the rest of the frame -- which is
	 * invisible, right up until the one underneath is the one taking the
	 * touch.
	 */
	if (p != UI_PAGE_MUSIC) {
		ui_music_close();
	}
	if (p != UI_PAGE_LAUNCHER) {
		ui_launcher_close();
	}
	if (p == UI_PAGE_MUSIC) {
		ui_music_open();
	} else if (p == UI_PAGE_LAUNCHER) {
		ui_launcher_open();
	}
	cur = p;
}

enum ui_move ui_pages_would(enum ui_dir dir)
{
	if (dir >= UI_DIR_N) {
		return UI_MOVE_NONE;
	}
	if (cur != UI_PAGE_GAUGES) {
		/*
		 * On a spoke, exactly one direction does anything: back.
		 * Every other stroke is refused rather than being taken as
		 * "go to the page on the far side", which would turn one
		 * mis-read gesture into two pages of travel.
		 */
		return dir == opposite(spoke_dir[cur]) ? UI_MOVE_DONE
						       : UI_MOVE_NONE;
	}
	switch (dir) {
	case UI_DIR_LEFT:
	case UI_DIR_RIGHT:
		return UI_MOVE_DONE;
	case UI_DIR_UP:
		return UI_MOVE_SETTINGS;
	case UI_DIR_DOWN:
		return UI_MOVE_FACE;
	default:
		return UI_MOVE_NONE;
	}
}

enum ui_move ui_pages_go(enum ui_dir dir)
{
	enum ui_move m = ui_pages_would(dir);

	if (m != UI_MOVE_DONE) {
		/* SETTINGS and FACE are the caller's to run; NONE is nothing.
		 * Either way this module does not touch the overlays. */
		return m;
	}
	if (cur != UI_PAGE_GAUGES) {
		show_only(UI_PAGE_GAUGES);
		return UI_MOVE_DONE;
	}
	show_only(dir == UI_DIR_LEFT ? UI_PAGE_MUSIC : UI_PAGE_LAUNCHER);
	return UI_MOVE_DONE;
}

enum ui_page ui_pages_current(void)
{
	return cur;
}

bool ui_pages_at_centre(void)
{
	return cur == UI_PAGE_GAUGES;
}

void ui_pages_home(void)
{
	show_only(UI_PAGE_GAUGES);
}

/* --- the tap path ------------------------------------------------- */

static void on_home_tap(lv_event_t *e)
{
	ARG_UNUSED(e);

	/*
	 * A tap that followed a stroke is not a tap.
	 *
	 * LVGL sends CLICKED on release whenever an object was pressed and
	 * nothing scrolled; it does not withdraw it because the touch turned
	 * out to be a swipe. ui_swipe.h:dragging() exists for exactly this and
	 * the edge strips already call it -- without it a swipe that begins on
	 * this strip moves twice, once as a swipe and once as the button press
	 * it left behind.
	 */
	if (ui_swipe_dragging()) {
		return;
	}
	ui_pages_home();
}

/*
 * The way back, named.
 *
 * The rail this replaces drew two chevrons and a row of position dots, which
 * told you there were other pages and never told you what they were. On a
 * cross there is only one place to go from here, so the control says where
 * that is in words -- the one piece of furniture a first-time user needs on
 * this screen, and it is cheaper than the dots it replaces.
 */
static void build_home(lv_obj_t *parent)
{
	lv_obj_t *b = lv_btn_create(parent);

	lv_obj_set_size(b, 320, HOME_H);
	lv_obj_set_pos(b, 0, HOME_Y);
	lv_obj_set_style_bg_color(b, COL_BG, 0);
	lv_obj_set_style_border_width(b, 0, 0);
	lv_obj_set_style_radius(b, 0, 0);
	lv_obj_set_style_shadow_width(b, 0, 0);
	lv_obj_clear_flag(b, LV_OBJ_FLAG_SCROLLABLE);
	/* A swipe that starts here must still reach the screen, or putting a
	 * target under the strip would kill the gesture it backs up. */
	lv_obj_add_flag(b, LV_OBJ_FLAG_GESTURE_BUBBLE);
	lv_obj_add_event_cb(b, on_home_tap, LV_EVENT_CLICKED, NULL);

	lv_obj_t *l = lv_label_create(b);

	lv_label_set_text(l, LV_SYMBOL_LEFT "  USAGE");
	lv_obj_set_style_text_color(l, COL_DIM, 0);
	lv_obj_center(l);
}

void ui_pages_init(lv_obj_t *scr)
{
	ui_music_attach(scr);
	ui_launcher_attach(scr);
	/* The strips live on the overlays, so they are hidden with them and
	 * the gauge screen keeps the bottom edge it already uses for its own
	 * provider zone. */
	build_home(ui_music_panel());
	build_home(ui_launcher_panel());
	cur = UI_PAGE_GAUGES;
}

void ui_pages_detach(void)
{
	ui_music_detach();
	ui_launcher_detach();
	/* Home, not "wherever we were". The screen is going away and the mode
	 * that rebuilds it starts at the gauges; leaving `cur` on a widget
	 * page would show an overlay that no longer exists. */
	cur = UI_PAGE_GAUGES;
}
