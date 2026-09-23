/*
 * The app-launcher page: six buttons, each one a message to the computer.
 *
 * The transport already existed. proto.c has sent board-to-daemon messages
 * since the first release -- pref, ping, ota_query and ota_flash -- and
 * ota_flash is the precedent that settles whether this is allowed to exist:
 * a tap on this panel already makes the computer download a file from the
 * internet and reflash the device. Launching an app is a smaller claim on
 * the host than the one the product already makes.
 */
#include "ui_launcher.h"

#include <stdio.h>
#include <string.h>

#include "proto.h"
#include "icons_gen.h"
#include "ui_theme.h"

/*
 * The palette, copied rather than shared, because that is how this codebase
 * does it: ui_setup.c:20 and ui_settings.c:40 each define their own and the
 * hexes agree. A shared colour header would be a better idea and a worse fit;
 * introducing one is a change to every UI file, not a detail of this one.
 */
#define COL_BG	lv_color_hex(ui_theme()->bg)
#define COL_TRACK	lv_color_hex(ui_theme()->track)
#define COL_TEXT	lv_color_hex(ui_theme()->text)
#define COL_DIM	lv_color_hex(ui_theme()->dim)
#define COL_RED	lv_color_hex(ui_theme()->red)
#define COL_GREEN	lv_color_hex(ui_theme()->green)
#define COL_AMBER	lv_color_hex(ui_theme()->amber)
#define COL_PANEL	lv_color_hex(ui_theme()->panel)

/*
 * Dark ink for the three bright fills, and this is not a taste call.
 *
 * The first draft put COL_TEXT (0xE6E8EB) on COL_AMBER (0xF1C40F): near-white
 * on yellow, which is roughly 1.4:1 and unreadable at arm's length on a panel
 * that is often the brightest thing on a desk. The house already had the
 * answer -- ui_setup.c:26 carries COL_GREEN_INK for exactly this -- and the
 * amber and red cases needed the same treatment. Each ink is its own fill
 * darkened, so the label reads as part of the button rather than a black
 * sticker on it.
 */
#define COL_AMBER_INK	lv_color_hex(ui_theme()->amber_ink)
#define COL_GREEN_INK	lv_color_hex(ui_theme()->green_ink)
#define COL_RED_INK	lv_color_hex(ui_theme()->red_ink)

/* Three columns of 96 with four 8 px gaps is exactly 320. See the header. */
#define LAUNCH_COLS		3
#define LAUNCH_ROWS		2
#define LAUNCH_SLOTS		(LAUNCH_COLS * LAUNCH_ROWS)
#define BTN_W			96
#define BTN_H			62
#define GAP			8
#define TOP_Y			52	/* under the title rule */

/* Longest app name the grid can draw at 96 px in montserrat_14. "Visual
 * Studio Code" is 19 and wraps to nothing useful, so the daemon sends a short
 * name and this is the backstop, not the policy. */
#define LABEL_MAX		14

/*
 * How long a tapped button stays lit before it goes back to rest.
 *
 * Two different facts are being shown in that window and they must not be
 * confused. The instant flash says THE BOARD SAW THE TAP; the colour it
 * settles into says what the COMPUTER did with it. Between them sits the
 * round trip, which is one serial line each way and measured at well under
 * 50 ms -- but "well under" is not "always", and a USB re-enumeration or a
 * busy daemon can stretch it. 1200 ms is long enough that an answer almost
 * always lands inside the lit window, so the ordinary case is one colour
 * change, not two.
 */
#define FLASH_MS		1200

static lv_obj_t *panel;			/* the overlay; NULL until attached */
static lv_obj_t *btn[LAUNCH_SLOTS];
static lv_obj_t *btn_lbl[LAUNCH_SLOTS];
static lv_obj_t *btn_img[LAUNCH_SLOTS];

/*
 * Every tile carries BOTH an image and a label, and shows one of them.
 *
 * The daemon sends a key, not a filename - "spotify", not a path - and the
 * board owns what it can draw. A key with no icon compiled in falls back to
 * being drawn as text, which is the whole reason a customer can point a slot
 * at something nobody shipped an icon for and still have a usable button.
 * Creating both once is cheaper than building and destroying one whenever the
 * daemon revises the table, and the LVGL pool has no room for churn.
 */
static const lv_image_dsc_t *icon_for(const char *key)
{
	if (!key || !key[0]) {
		return NULL;
	}
	for (int i = 0; i < ICON_TABLE_N; i++) {
		if (strcmp(icon_table[i].key, key) == 0) {
			return icon_table[i].dsc;
		}
	}
	return NULL;
}
static char slot_name[LAUNCH_SLOTS][LABEL_MAX + 1];
static lv_timer_t *cool[LAUNCH_SLOTS];

static bool slot_live(int slot)
{
	return slot >= 0 && slot < LAUNCH_SLOTS && slot_name[slot][0] != '\0';
}

static void paint_rest(int slot)
{
	if (!btn[slot]) {
		return;
	}
	/* A named slot sits on the panel colour; an unnamed one is dimmer than
	 * the panel it is on, which is the only honest way to draw a control
	 * that will not answer. */
	lv_obj_set_style_bg_color(btn[slot],
				  slot_live(slot) ? COL_PANEL : COL_TRACK, 0);
	lv_obj_set_style_text_color(btn_lbl[slot],
				    slot_live(slot) ? COL_TEXT : COL_DIM, 0);
	if (btn_img[slot]) {
		/* An unassigned slot has no icon to dim, but a live one that
		 * is mid-cooldown keeps full opacity - the tile colour is
		 * already saying what happened. */
		lv_obj_set_style_image_opa(btn_img[slot],
					   slot_live(slot) ? LV_OPA_COVER : LV_OPA_40, 0);
	}
}

static void cool_cb(lv_timer_t *t)
{
	int slot = (int)(intptr_t)lv_timer_get_user_data(t);

	if (slot >= 0 && slot < LAUNCH_SLOTS) {
		paint_rest(slot);
		cool[slot] = NULL;
	}
	lv_timer_delete(t);
}

static void arm_cooldown(int slot)
{
	/* Re-tapping the same button restarts the window rather than stacking
	 * a second timer on it -- two timers racing to repaint one button was
	 * how the settings notice used to flicker. */
	if (cool[slot]) {
		lv_timer_delete(cool[slot]);
		cool[slot] = NULL;
	}
	cool[slot] = lv_timer_create(cool_cb, FLASH_MS, (void *)(intptr_t)slot);
	if (cool[slot]) {
		lv_timer_set_repeat_count(cool[slot], 1);
	}
}

static void on_tap(lv_event_t *e)
{
	int slot = (int)(intptr_t)lv_event_get_user_data(e);

	if (!slot_live(slot)) {
		return;		/* nothing to launch; say nothing */
	}

	/* Light it NOW. This claims only that the board registered the press:
	 * the computer has not been asked yet, let alone answered. */
	lv_obj_set_style_bg_color(btn[slot], COL_AMBER, 0);
	lv_obj_set_style_text_color(btn_lbl[slot], COL_AMBER_INK, 0);
	arm_cooldown(slot);

	proto_send_launch(slot);
}

void ui_launcher_result(int slot, bool ok)
{
	if (!panel || slot < 0 || slot >= LAUNCH_SLOTS || !btn[slot]) {
		return;
	}
	lv_obj_set_style_bg_color(btn[slot], ok ? COL_GREEN : COL_RED, 0);
	/* The ink moves with the fill. Leaving it alone kept the amber ink from
	 * the tap, which is invisible on red. */
	lv_obj_set_style_text_color(btn_lbl[slot],
				    ok ? COL_GREEN_INK : COL_RED_INK, 0);
	arm_cooldown(slot);
}

void ui_launcher_set_slot(int slot, const char *key)
{
	if (slot < 0 || slot >= LAUNCH_SLOTS) {
		return;
	}
	snprintf(slot_name[slot], sizeof(slot_name[slot]), "%s", key ? key : "");

	if (!btn_lbl[slot] || !btn_img[slot]) {
		return;			/* not attached yet; attach() re-reads */
	}
	const lv_image_dsc_t *ic = icon_for(slot_name[slot]);

	if (ic) {
		lv_image_set_src(btn_img[slot], ic);
		lv_obj_clear_flag(btn_img[slot], LV_OBJ_FLAG_HIDDEN);
		lv_obj_add_flag(btn_lbl[slot], LV_OBJ_FLAG_HIDDEN);
	} else {
		lv_obj_add_flag(btn_img[slot], LV_OBJ_FLAG_HIDDEN);
		lv_obj_clear_flag(btn_lbl[slot], LV_OBJ_FLAG_HIDDEN);
		lv_label_set_text(btn_lbl[slot],
				  slot_name[slot][0] ? slot_name[slot] : "--");
	}
	paint_rest(slot);
}

void ui_launcher_attach(lv_obj_t *scr)
{
	if (panel) {
		return;
	}

	panel = lv_obj_create(scr);
	lv_obj_set_size(panel, 320, 240);
	lv_obj_set_pos(panel, 0, 0);
	lv_obj_set_style_bg_color(panel, COL_BG, 0);
	lv_obj_set_style_border_width(panel, 0, 0);
	lv_obj_set_style_pad_all(panel, 0, 0);
	lv_obj_clear_flag(panel, LV_OBJ_FLAG_SCROLLABLE);
	lv_obj_add_flag(panel, LV_OBJ_FLAG_HIDDEN);

	lv_obj_t *title = lv_label_create(panel);

	/* Sentence case, like every other line the customer reads. Centred
	 * because the page is reached sideways now and its name is the first
	 * thing that confirms which way you went. */
	lv_label_set_text(title, "Launchpad");
	lv_obj_set_style_text_color(title, COL_DIM, 0);
	lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 16);

	for (int i = 0; i < LAUNCH_SLOTS; i++) {
		int col = i % LAUNCH_COLS;
		int row = i / LAUNCH_COLS;

		btn[i] = lv_btn_create(panel);
		lv_obj_set_size(btn[i], BTN_W, BTN_H);
		lv_obj_set_pos(btn[i], GAP + col * (BTN_W + GAP),
			       TOP_Y + row * (BTN_H + GAP));
		lv_obj_set_style_border_width(btn[i], 0, 0);
		lv_obj_set_style_radius(btn[i], 6, 0);
		/*
		 * Both flags, and this is the bug ui_settings.c:195 already
		 * paid for: in LVGL 9 every child is born SCROLLABLE and
		 * GESTURE_BUBBLE, so a tap that drifts a few px on this
		 * jittery panel bubbles up as a swipe. Here that would close
		 * the launcher instead of launching the app under the finger
		 * -- and per docs/multi-provider.md 4d the tap-like strokes
		 * sit at 11-15 px, which is exactly the drift in question.
		 */
		lv_obj_clear_flag(btn[i], LV_OBJ_FLAG_SCROLLABLE);
		lv_obj_clear_flag(btn[i], LV_OBJ_FLAG_GESTURE_BUBBLE);
		lv_obj_add_event_cb(btn[i], on_tap, LV_EVENT_CLICKED,
				    (void *)(intptr_t)i);

		btn_lbl[i] = lv_label_create(btn[i]);
		lv_label_set_text(btn_lbl[i],
				  slot_name[i][0] ? slot_name[i] : "--");
		lv_obj_center(btn_lbl[i]);

		btn_img[i] = lv_image_create(btn[i]);
		lv_obj_center(btn_img[i]);
		/* The image must not eat the tap: the BUTTON is the control,
		 * and a child that takes the press leaves a tile that lights
		 * under the finger and launches nothing. */
		lv_obj_clear_flag(btn_img[i], LV_OBJ_FLAG_CLICKABLE);
		lv_obj_add_flag(btn_img[i], LV_OBJ_FLAG_HIDDEN);

		ui_launcher_set_slot(i, slot_name[i]);
	}
}

void ui_launcher_open(void)
{
	if (panel) {
		lv_obj_clear_flag(panel, LV_OBJ_FLAG_HIDDEN);
		lv_obj_move_foreground(panel);
	}
}

void ui_launcher_close(void)
{
	if (panel) {
		lv_obj_add_flag(panel, LV_OBJ_FLAG_HIDDEN);
	}
}

bool ui_launcher_is_open(void)
{
	return panel && !lv_obj_has_flag(panel, LV_OBJ_FLAG_HIDDEN);
}

lv_obj_t *ui_launcher_panel(void)
{
	return panel;
}

void ui_launcher_detach(void)
{
	panel = NULL;
	for (int i = 0; i < LAUNCH_SLOTS; i++) {
		btn[i] = btn_lbl[i] = btn_img[i] = NULL;
		/* The timers hung off the panel's children; the delete took
		 * the objects but an armed lv_timer is independent of them. */
		if (cool[i]) {
			lv_timer_delete(cool[i]);
			cool[i] = NULL;
		}
	}
}
