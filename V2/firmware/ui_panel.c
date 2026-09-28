/* See ui_panel.h for why this page exists at all. */
#include "ui_panel.h"

#include <stdio.h>
#include <string.h>

#include "msg_parse.h"
#include "proto.h"
#include "ui_theme.h"
#include "usage_layout.h"

#define COL_BG		lv_color_hex(ui_theme()->bg)
#define COL_PANEL	lv_color_hex(ui_theme()->panel)
#define COL_TEXT	lv_color_hex(ui_theme()->text)
#define COL_DIM		lv_color_hex(ui_theme()->dim)
#define COL_GREEN	lv_color_hex(ui_theme()->green)
#define COL_AMBER	lv_color_hex(ui_theme()->amber)
#define COL_RED		lv_color_hex(ui_theme()->red)

/*
 * Geometry. Borrowed from the launcher's so the two pages feel like one
 * device: same title position, same margins, same tile height.
 */
/* Every name here is prefixed. usage_layout.h already defines TITLE_Y for the
 * gauge screen, and this file redefined it -- a warning today and, the moment
 * the two numbers differ, a page that draws its title somewhere its own
 * header does not describe. */
#define PANEL_TITLE_Y	16
#define PANEL_ROW_TOP	52
#define PANEL_ROW_H	26
#define PANEL_SIDE	16
#define PANEL_TILE_H	34
#define PANEL_TILE_GAP	8
#define PANEL_TILE_Y	(SCR_H - PANEL_TILE_H - 14)
#define PANEL_TILE_W	((SCR_W - 2 * PANEL_SIDE \
			  - (PANEL_TILES - 1) * PANEL_TILE_GAP) / PANEL_TILES)

/*
 * The MODEL, separate from the objects that draw it.
 *
 * Two reasons, and the second is the one that bites. A theme change tears the
 * whole screen down and builds it again, so every lv_obj_t here becomes NULL;
 * if the words lived only in the labels they would be gone. And messages
 * arrive on the protocol thread while the LVGL thread may be mid-rebuild, so
 * writing straight into objects is a use-after-free waiting for the right
 * moment.
 *
 * Fixed size, no allocation: dram1_0_seg is 74% full and the WiFi build
 * already fails to link by 18 KB. This costs
 * PANEL_MAX * (20 + 5*(14+18+1) + 3*12) = 2 * 221 = 442 bytes, paid whether
 * or not the daemon ever sends a panel.
 */
struct row {
	char label[PANEL_LABEL_MAX + 1];
	char value[PANEL_VALUE_MAX + 1];
	uint8_t tone;
};

struct panel {
	bool used;
	char title[PANEL_TITLE_MAX + 1];
	int nrows;
	struct row rows[PANEL_ROWS];
	int ntiles;
	char tiles[PANEL_TILES][PANEL_TILE_MAX + 1];
};

static struct panel model[PANEL_MAX];
static int showing;

static lv_obj_t *panel;
static lv_obj_t *title_lbl;
static lv_obj_t *row_lbl[PANEL_ROWS];
static lv_obj_t *row_val[PANEL_ROWS];
static lv_obj_t *tile_btn[PANEL_TILES];
static lv_obj_t *tile_lbl[PANEL_TILES];
static lv_obj_t *empty_lbl;

static lv_color_t tone_colour(uint8_t tone)
{
	switch (tone) {
	case PANEL_TONE_DIM:	return COL_DIM;
	case PANEL_TONE_OK:	return COL_GREEN;
	case PANEL_TONE_WARN:	return COL_AMBER;
	case PANEL_TONE_BAD:	return COL_RED;
	default:		return COL_TEXT;
	}
}

/* "ok" -> PANEL_TONE_OK. An unknown word is PLAIN rather than an error: a
 * daemon that learns a tone this firmware predates should lose the colour,
 * not the row. */
static uint8_t tone_of(const char *s)
{
	if (strcmp(s, "dim") == 0) {
		return PANEL_TONE_DIM;
	}
	if (strcmp(s, "ok") == 0) {
		return PANEL_TONE_OK;
	}
	if (strcmp(s, "warn") == 0) {
		return PANEL_TONE_WARN;
	}
	if (strcmp(s, "bad") == 0) {
		return PANEL_TONE_BAD;
	}
	return PANEL_TONE_PLAIN;
}

/* ------------------------------------------------------------------ paint */

static void paint(void)
{
	const struct panel *p = &model[showing];

	if (!panel) {
		return;
	}

	lv_label_set_text(title_lbl, p->used ? p->title : "");

	/*
	 * A panel that has arrived but says nothing is still a page somebody
	 * swiped to. Saying so is better than a blank screen, which reads as a
	 * fault -- the same judgement ui_launcher.c makes about its dim
	 * placeholders.
	 */
	if (!p->used) {
		lv_obj_clear_flag(empty_lbl, LV_OBJ_FLAG_HIDDEN);
	} else {
		lv_obj_add_flag(empty_lbl, LV_OBJ_FLAG_HIDDEN);
	}

	for (int i = 0; i < PANEL_ROWS; i++) {
		bool live = p->used && i < p->nrows;

		if (!live) {
			lv_obj_add_flag(row_lbl[i], LV_OBJ_FLAG_HIDDEN);
			lv_obj_add_flag(row_val[i], LV_OBJ_FLAG_HIDDEN);
			continue;
		}
		lv_obj_clear_flag(row_lbl[i], LV_OBJ_FLAG_HIDDEN);
		lv_obj_clear_flag(row_val[i], LV_OBJ_FLAG_HIDDEN);
		lv_label_set_text(row_lbl[i], p->rows[i].label);
		lv_label_set_text(row_val[i], p->rows[i].value);
		lv_obj_set_style_text_color(row_lbl[i], COL_DIM, 0);
		lv_obj_set_style_text_color(row_val[i],
					    tone_colour(p->rows[i].tone), 0);
	}

	for (int i = 0; i < PANEL_TILES; i++) {
		bool live = p->used && i < p->ntiles;

		if (!live) {
			lv_obj_add_flag(tile_btn[i], LV_OBJ_FLAG_HIDDEN);
			continue;
		}
		lv_obj_clear_flag(tile_btn[i], LV_OBJ_FLAG_HIDDEN);
		lv_label_set_text(tile_lbl[i], p->tiles[i]);
		lv_obj_set_style_bg_color(tile_btn[i], COL_PANEL, 0);
		lv_obj_set_style_text_color(tile_lbl[i], COL_TEXT, 0);
	}
}

/* ------------------------------------------------------------------- taps */

static void on_tile(lv_event_t *e)
{
	int i = (int)(intptr_t)lv_event_get_user_data(e);

	if (i < 0 || i >= PANEL_TILES) {
		return;
	}
	/*
	 * A panel number and a tile number, never what the tile MEANS.
	 *
	 * The same split proto_send_launch() spells out at length: the daemon
	 * owns the table of what a tile does, so nothing the board can say
	 * names an action the daemon has not already agreed to perform.
	 */
	if (model[showing].used && i < model[showing].ntiles) {
		proto_send_panel_tap(showing, i);
	}
}

/* ------------------------------------------------------------------ attach */

void ui_panel_attach(lv_obj_t *scr)
{
	if (panel) {
		return;
	}

	panel = lv_obj_create(scr);
	lv_obj_set_size(panel, SCR_W, SCR_H);
	lv_obj_set_pos(panel, 0, 0);
	lv_obj_set_style_bg_color(panel, COL_BG, 0);
	lv_obj_set_style_border_width(panel, 0, 0);
	lv_obj_set_style_pad_all(panel, 0, 0);
	lv_obj_clear_flag(panel, LV_OBJ_FLAG_SCROLLABLE);
	lv_obj_add_flag(panel, LV_OBJ_FLAG_HIDDEN);

	title_lbl = lv_label_create(panel);
	lv_label_set_text(title_lbl, "");
	lv_obj_set_style_text_color(title_lbl, COL_DIM, 0);
	lv_obj_align(title_lbl, LV_ALIGN_TOP_MID, 0, PANEL_TITLE_Y);

	empty_lbl = lv_label_create(panel);
	lv_label_set_text(empty_lbl, "Nothing to show yet");
	lv_obj_set_style_text_color(empty_lbl, COL_DIM, 0);
	lv_obj_align(empty_lbl, LV_ALIGN_CENTER, 0, 0);

	for (int i = 0; i < PANEL_ROWS; i++) {
		int y = PANEL_ROW_TOP + i * PANEL_ROW_H;

		row_lbl[i] = lv_label_create(panel);
		lv_obj_set_pos(row_lbl[i], PANEL_SIDE, y);
		lv_obj_add_flag(row_lbl[i], LV_OBJ_FLAG_HIDDEN);

		/*
		 * The value is RIGHT-aligned and the label left, so the two
		 * columns line up however long either string is. A value that
		 * grows -- "9" to "1,284" -- would otherwise walk across the
		 * screen as the number changed, which is the one thing a
		 * glanceable readout must not do.
		 */
		row_val[i] = lv_label_create(panel);
		lv_obj_set_style_text_align(row_val[i], LV_TEXT_ALIGN_RIGHT, 0);
		lv_obj_align(row_val[i], LV_ALIGN_TOP_RIGHT, -PANEL_SIDE, y);
		lv_obj_add_flag(row_val[i], LV_OBJ_FLAG_HIDDEN);
	}

	for (int i = 0; i < PANEL_TILES; i++) {
		tile_btn[i] = lv_btn_create(panel);
		lv_obj_set_size(tile_btn[i], PANEL_TILE_W, PANEL_TILE_H);
		lv_obj_set_pos(tile_btn[i], PANEL_SIDE + i * (PANEL_TILE_W + PANEL_TILE_GAP),
			       PANEL_TILE_Y);
		lv_obj_set_style_border_width(tile_btn[i], 0, 0);
		lv_obj_set_style_radius(tile_btn[i], 6, 0);
		/* A swipe that starts on a tile must still reach the page
		 * underneath, or the navigation goes dead wherever a tile
		 * happens to be. ui_settings.c hit this first. */
		lv_obj_add_flag(tile_btn[i], LV_OBJ_FLAG_GESTURE_BUBBLE);
		lv_obj_add_event_cb(tile_btn[i], on_tile, LV_EVENT_CLICKED,
				    (void *)(intptr_t)i);
		lv_obj_add_flag(tile_btn[i], LV_OBJ_FLAG_HIDDEN);

		tile_lbl[i] = lv_label_create(tile_btn[i]);
		lv_label_set_text(tile_lbl[i], "");
		lv_obj_center(tile_lbl[i]);
	}

	paint();
}

void ui_panel_open(void)
{
	if (panel) {
		lv_obj_clear_flag(panel, LV_OBJ_FLAG_HIDDEN);
		lv_obj_move_foreground(panel);
	}
}

void ui_panel_close(void)
{
	if (panel) {
		lv_obj_add_flag(panel, LV_OBJ_FLAG_HIDDEN);
	}
}

bool ui_panel_is_open(void)
{
	return panel && !lv_obj_has_flag(panel, LV_OBJ_FLAG_HIDDEN);
}

lv_obj_t *ui_panel_panel(void)
{
	return panel;
}

void ui_panel_detach(void)
{
	panel = title_lbl = empty_lbl = NULL;
	for (int i = 0; i < PANEL_ROWS; i++) {
		row_lbl[i] = row_val[i] = NULL;
	}
	for (int i = 0; i < PANEL_TILES; i++) {
		tile_btn[i] = tile_lbl[i] = NULL;
	}
}

void ui_panel_refresh(void)
{
	paint();
}

/* ---------------------------------------------------------------- the wire */

bool ui_panel_any(void)
{
	for (int i = 0; i < PANEL_MAX; i++) {
		if (model[i].used) {
			return true;
		}
	}
	return false;
}

int ui_panel_count(void)
{
	int n = 0;

	/* Contiguous from 0 on purpose. The daemon fills slots in order, and a
	 * gap would make left/right land on a blank page with no way to tell
	 * it from a panel that has nothing to say. */
	while (n < PANEL_MAX && model[n].used) {
		n++;
	}
	return n;
}

void ui_panel_show(int i)
{
	int n = ui_panel_count();

	if (n <= 0) {
		showing = 0;
		return;
	}
	if (i < 0) {
		i = 0;
	}
	if (i >= n) {
		i = n - 1;
	}
	showing = i;
	paint();
}

int ui_panel_current(void)
{
	return showing;
}

bool ui_panel_on_message(const char *json)
{
	char buf[PANEL_VALUE_MAX + 1];
	char key[16];
	double d;
	int slot;
	struct panel next;

	if (!msg_get_str(json, "t", buf, sizeof(buf))
	    || strcmp(buf, "panel") != 0) {
		return false;
	}
	if (!msg_get_double(json, "p", &d)) {
		return false;
	}
	slot = (int)d;
	if (slot < 0 || slot >= PANEL_MAX) {
		return false;
	}

	/*
	 * Built aside and copied in at the end, never written in place.
	 *
	 * A message that runs out halfway -- a line clipped at LINE_MAX, a
	 * field the daemon forgot -- would otherwise leave half the old panel
	 * under half the new one. That reads as current and is not, which is
	 * the failure this whole page is least able to survive: nobody
	 * double-checks a number on a desk gauge.
	 */
	memset(&next, 0, sizeof(next));
	next.used = true;

	if (!msg_get_str(json, "title", next.title, sizeof(next.title))) {
		next.title[0] = '\0';
	}

	if (msg_get_double(json, "n", &d)) {
		next.nrows = (int)d;
	}
	if (next.nrows < 0) {
		next.nrows = 0;
	}
	if (next.nrows > PANEL_ROWS) {
		next.nrows = PANEL_ROWS;
	}

	for (int i = 0; i < next.nrows; i++) {
		snprintf(key, sizeof(key), "l%d", i);
		if (!msg_get_str(json, key, next.rows[i].label,
				 sizeof(next.rows[i].label))) {
			/* A row with no label is the tail of a truncated line.
			 * Stop here and keep what is whole. */
			next.nrows = i;
			break;
		}
		snprintf(key, sizeof(key), "v%d", i);
		if (!msg_get_str(json, key, next.rows[i].value,
				 sizeof(next.rows[i].value))) {
			next.rows[i].value[0] = '\0';
		}
		snprintf(key, sizeof(key), "c%d", i);
		if (msg_get_str(json, key, buf, sizeof(buf))) {
			next.rows[i].tone = tone_of(buf);
		}
	}

	if (msg_get_double(json, "tn", &d)) {
		next.ntiles = (int)d;
	}
	if (next.ntiles < 0) {
		next.ntiles = 0;
	}
	if (next.ntiles > PANEL_TILES) {
		next.ntiles = PANEL_TILES;
	}
	for (int i = 0; i < next.ntiles; i++) {
		snprintf(key, sizeof(key), "b%d", i);
		if (!msg_get_str(json, key, next.tiles[i],
				 sizeof(next.tiles[i]))) {
			next.ntiles = i;
			break;
		}
	}

	model[slot] = next;
	if (slot == showing) {
		paint();
	}
	return true;
}
