/*
 * The transport page.
 *
 * Reads as a display with three buttons, and the interesting half is which
 * side owns which fact. The computer owns everything true of the player; the
 * board owns only the second hand. See ui_music_tick_1s().
 */
#include "ui_music.h"

#include <stdio.h>
#include <string.h>

#include "proto.h"
#include "ui_theme.h"

/* Same palette, copied the way ui_setup.c:20 and ui_settings.c:40 copy it. */
#define COL_BG	lv_color_hex(ui_theme()->bg)
#define COL_TRACK	lv_color_hex(ui_theme()->track)
#define COL_TEXT	lv_color_hex(ui_theme()->text)
#define COL_DIM	lv_color_hex(ui_theme()->dim)
#define COL_GREEN	lv_color_hex(ui_theme()->green)
#define COL_GREEN_INK	lv_color_hex(ui_theme()->green_ink)
#define COL_PANEL	lv_color_hex(ui_theme()->panel)

/*
 * 28 characters, and the number comes from the panel rather than the wire.
 *
 * 320 px in montserrat_16 is about 34 characters, and the title has 16 px of
 * padding on each side. 28 leaves the longest name it will accept sitting
 * inside the panel rather than touching both edges. The daemon truncates to
 * the same figure (pc/spotify.py TEXT_MAX) so the board never receives more
 * than it can draw -- two copies of one constant, which is the arrangement
 * LABEL_MAX already has and the same reason: the alternative is the board
 * silently clipping something the daemon thought it had sent.
 */
#define TEXT_MAX	28

#define BTN_W		72
#define BTN_H		56
/* 140, not 162. ui_pages.c puts a 40 px rail at y=200 and the buttons ran to
 * 218 -- an overlap that draws correctly and then hands the rail's top 18 px
 * to whichever child LVGL happens to hit-test first. 140 + 56 = 196 clears it
 * with 4 px to spare. */
#define BTN_Y		140

static lv_obj_t *panel;
static lv_obj_t *lbl_name, *lbl_artist, *lbl_time, *bar;
static lv_obj_t *btn_play, *lbl_play;

static int st = MUSIC_UNKNOWN;
static int pos_s = -1, dur_s = -1;

static void draw_time(void)
{
	char buf[16];

	if (pos_s < 0 || dur_s <= 0) {
		lv_label_set_text(lbl_time, "");
		lv_bar_set_value(bar, 0, LV_ANIM_OFF);
		return;
	}
	snprintf(buf, sizeof(buf), "%d:%02d / %d:%02d",
		 pos_s / 60, pos_s % 60, dur_s / 60, dur_s % 60);
	lv_label_set_text(lbl_time, buf);
	/*
	 * Percent, not seconds, because lv_bar takes a range and the range
	 * changes with every track. Clamped because the local tick can run
	 * past the duration: a track that ends between two readings leaves
	 * the board counting into a song that has already finished, and a bar
	 * drawn past its own end looks like a fault rather than a stale
	 * reading.
	 */
	int pct = (int)((long)pos_s * 100 / dur_s);

	lv_bar_set_value(bar, pct > 100 ? 100 : pct, LV_ANIM_OFF);
}

static void draw_play_icon(void)
{
	/*
	 * The button shows what pressing it WILL DO, not what the player is
	 * doing. Playing -> a pause glyph. That is the convention every
	 * transport on the desk already follows, and getting it backwards
	 * makes the one control on this page lie about itself.
	 *
	 * UNKNOWN shows play and the button is disabled below, so the icon is
	 * never a promise the page cannot keep.
	 */
	lv_label_set_text(lbl_play,
			  st == MUSIC_PLAYING ? LV_SYMBOL_PAUSE : LV_SYMBOL_PLAY);
	lv_obj_set_style_bg_color(btn_play,
				  st == MUSIC_PLAYING ? COL_GREEN : COL_PANEL, 0);
	lv_obj_set_style_text_color(lbl_play,
				    st == MUSIC_PLAYING ? COL_GREEN_INK : COL_TEXT, 0);
}

void ui_music_set_track(const char *artist, const char *name,
			  int state, int pos, int dur)
{
	if (!panel) {
		return;
	}
	lv_label_set_text(lbl_name, name && name[0] ? name : "Nothing playing");
	lv_label_set_text(lbl_artist, artist ? artist : "");
	st = state;
	pos_s = pos;
	dur_s = dur;
	draw_play_icon();
	draw_time();
}

void ui_music_set_unavailable(const char *reason)
{
	if (!panel) {
		return;
	}
	/* Sentence case, and the board keeps 47 characters of it. */
	lv_label_set_text(lbl_name, reason && reason[0] ? reason : "No player");
	lv_label_set_text(lbl_artist, "");
	st = MUSIC_UNKNOWN;
	pos_s = dur_s = -1;
	draw_play_icon();
	draw_time();
}

void ui_music_tick_1s(void)
{
	/*
	 * Only while playing, and only when there is something to advance.
	 *
	 * Ticking a paused track would invent listening that did not happen,
	 * which is the same class of mistake as pc/protocol.secs_until
	 * refusing to send 0 for a window that has already rolled: the board
	 * is relaying somebody else's number and may not improve on it.
	 */
	if (!panel || st != MUSIC_PLAYING || pos_s < 0 || dur_s <= 0) {
		return;
	}
	if (pos_s < dur_s) {
		pos_s++;
		draw_time();
	}
}

static void on_cmd(lv_event_t *e)
{
	const char *cmd = (const char *)lv_event_get_user_data(e);

	/*
	 * No optimistic repaint here, deliberately -- and this is the one
	 * place this page differs from the launcher.
	 *
	 * The launcher flashes on tap because the computer's answer is the
	 * only feedback there is. Here the next poll arrives within two
	 * seconds carrying the real state, so flipping the icon locally would
	 * show a guess that the truth then overwrites -- and when the command
	 * fails, the guess is simply wrong for those two seconds. The player
	 * says what the player is doing.
	 */
	proto_send_music(cmd);
}

static lv_obj_t *mk_btn(lv_obj_t *parent, int x, const char *sym,
			const char *cmd, lv_obj_t **out_lbl)
{
	lv_obj_t *b = lv_btn_create(parent);

	lv_obj_set_size(b, BTN_W, BTN_H);
	lv_obj_set_pos(b, x, BTN_Y);
	lv_obj_set_style_bg_color(b, COL_PANEL, 0);
	lv_obj_set_style_border_width(b, 0, 0);
	lv_obj_set_style_radius(b, 6, 0);
	/* Both flags, for the reason ui_settings.c:195 records: in LVGL 9 a
	 * tap that drifts a few px bubbles up as a swipe, and the tap-like
	 * strokes on this panel measure 11-15 px (docs/multi-provider.md 4d). */
	lv_obj_clear_flag(b, LV_OBJ_FLAG_SCROLLABLE);
	lv_obj_clear_flag(b, LV_OBJ_FLAG_GESTURE_BUBBLE);
	lv_obj_add_event_cb(b, on_cmd, LV_EVENT_CLICKED, (void *)cmd);

	lv_obj_t *l = lv_label_create(b);

	lv_label_set_text(l, sym);
	lv_obj_set_style_text_color(l, COL_TEXT, 0);
	lv_obj_center(l);
	if (out_lbl) {
		*out_lbl = l;
	}
	return b;
}

void ui_music_attach(lv_obj_t *scr)
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

	lv_obj_t *hdr = lv_label_create(panel);

	lv_label_set_text(hdr, "Now playing");
	lv_obj_set_style_text_color(hdr, COL_DIM, 0);
	lv_obj_align(hdr, LV_ALIGN_TOP_MID, 0, 14);

	lbl_name = lv_label_create(panel);
	lv_obj_set_style_text_font(lbl_name, &lv_font_montserrat_16, 0);
	lv_obj_set_style_text_color(lbl_name, COL_TEXT, 0);
	lv_obj_set_width(lbl_name, 288);
	/* Scroll the overflow rather than wrap it: two lines would push the
	 * artist into the progress bar, and a title long enough to wrap is
	 * exactly the one worth reading all of. */
	lv_label_set_long_mode(lbl_name, LV_LABEL_LONG_SCROLL_CIRCULAR);
	lv_obj_align(lbl_name, LV_ALIGN_TOP_LEFT, 16, 46);
	lv_label_set_text(lbl_name, "Nothing playing");

	lbl_artist = lv_label_create(panel);
	lv_obj_set_style_text_color(lbl_artist, COL_DIM, 0);
	lv_obj_set_width(lbl_artist, 288);
	lv_label_set_long_mode(lbl_artist, LV_LABEL_LONG_DOT);
	lv_obj_align(lbl_artist, LV_ALIGN_TOP_LEFT, 16, 72);
	lv_label_set_text(lbl_artist, "");

	bar = lv_bar_create(panel);
	lv_obj_set_size(bar, 288, 6);
	lv_obj_set_pos(bar, 16, 108);
	lv_bar_set_range(bar, 0, 100);
	lv_obj_set_style_bg_color(bar, COL_TRACK, 0);
	lv_obj_set_style_bg_color(bar, COL_GREEN, LV_PART_INDICATOR);

	lbl_time = lv_label_create(panel);
	lv_obj_set_style_text_color(lbl_time, COL_DIM, 0);
	lv_obj_align(lbl_time, LV_ALIGN_TOP_LEFT, 16, 124);
	lv_label_set_text(lbl_time, "");

	/* Three buttons, centred: 72*3 + 16*2 = 248 in 320, so 36 each side. */
	mk_btn(panel, 36, LV_SYMBOL_PREV, "prev", NULL);
	btn_play = mk_btn(panel, 124, LV_SYMBOL_PLAY, "play", &lbl_play);
	mk_btn(panel, 212, LV_SYMBOL_NEXT, "next", NULL);
	draw_play_icon();
}

void ui_music_open(void)
{
	if (panel) {
		lv_obj_clear_flag(panel, LV_OBJ_FLAG_HIDDEN);
		lv_obj_move_foreground(panel);
	}
}

void ui_music_close(void)
{
	if (panel) {
		lv_obj_add_flag(panel, LV_OBJ_FLAG_HIDDEN);
	}
}

bool ui_music_is_open(void)
{
	return panel && !lv_obj_has_flag(panel, LV_OBJ_FLAG_HIDDEN);
}

lv_obj_t *ui_music_panel(void)
{
	return panel;
}

void ui_music_detach(void)
{
	panel = NULL;
	lbl_name = lbl_artist = lbl_time = bar = NULL;
	btn_play = lbl_play = NULL;
	st = MUSIC_UNKNOWN;
	pos_s = dur_s = -1;
}
