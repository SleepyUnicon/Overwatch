#ifndef UI_PANEL_H
#define UI_PANEL_H

#include <lvgl.h>
#include <stdbool.h>

/*
 * A page whose CONTENT is described by the daemon.
 *
 * Every other page in this firmware is hand-written C: ui_music.c knows what a
 * track is, ui_launcher.c knows what a slot is, usage_view.c knows what a dial
 * is. Each new feature therefore costs a firmware build, a release and an OTA
 * to every unit -- which is invisible in one feature and enormous across
 * thirty, and quietly bends every idea toward extending a page that already
 * exists.
 *
 * This page knows what a ROW is, and nothing else. What the rows mean arrives
 * over the cable. After this, a new feature is Python.
 *
 * See V2/README.md for the message and the reasoning behind its shape.
 */

/*
 * How many panels the board will hold, and how much fits in one.
 *
 * FOUR tiles, not three. Both of the first two panels that wanted them wanted
 * exactly four -- left/right/full/next for a window, and mute/camera/share/
 * leave for a call -- and a fourth costs 20 bytes of line. At four they are
 * 66 px wide, which is about eight characters of montserrat_14: PANEL_TILE_MAX
 * is still 12, so a long label on a four-tile panel overflows its button. The
 * daemon picks the words; keep them short.
 *
 * PANEL_ROWS and PANEL_TILES are budgeted against proto.c's LINE_MAX of 512:
 * one panel has to arrive in one line, and five rows with three tiles is 409
 * bytes at the field lengths below. Six rows also fits, at 467, and was not
 * taken -- a hundred bytes of margin is worth more than a sixth row, because
 * the failure when a line overruns is a panel that silently loses its tail.
 *
 * PANEL_MAX is how many panel PAGES the board holds. It costs one `struct
 * panel` of TEXT each -- and NOT a set of LVGL objects each, which an earlier
 * version of this comment claimed. There is exactly one set of widgets (panel,
 * title_lbl, row_lbl[], tile_btn[]) and switching slots repaints it; see
 * paint(). So the cost of a slot is the model, not the view.
 *
 * Measured, 2026-09-29, by reading the `model` symbol out of zephyr.elf with
 * nm at both settings rather than trusting the summary line:
 *
 *   PANEL_MAX 2 -> model is 520 bytes    (0x208)
 *   PANEL_MAX 3 -> model is 780 bytes    (0x30c)
 *
 * so a slot is 260 bytes, and the third one did not move the reported
 * dram1_0_seg figure at all: 72,964 B / 74.22% before and after. Do not read
 * that as "slots are free" -- read it as 260 bytes being smaller than the
 * granularity that report shows. A fourth slot is affordable on this
 * arithmetic; measure it the same way rather than trusting this paragraph,
 * because RAM is still the binding constraint on this board and the WiFi
 * build already fails to link by 18 KB.
 */
#define PANEL_MAX	3
#define PANEL_ROWS	5
#define PANEL_TILES	4

#define PANEL_TITLE_MAX	20
#define PANEL_LABEL_MAX	14
#define PANEL_VALUE_MAX	18
#define PANEL_TILE_MAX	12

/*
 * What a value MEANS, not what colour to paint it.
 *
 * The daemon says "warn"; the board decides what warn looks like. That split
 * is why a panel is readable in both themes without the daemon knowing which
 * one is on -- ui_theme.c holds two sets of values and the light set's green
 * is nearly invisible on the dark ground, so a daemon sending 0x0A7A34 would
 * be wrong half the time and have no way to know it.
 */
enum panel_tone {
	PANEL_TONE_PLAIN = 0,	/* ordinary ink */
	PANEL_TONE_DIM,		/* secondary: timestamps, units, asides */
	PANEL_TONE_OK,
	PANEL_TONE_WARN,
	PANEL_TONE_BAD,
};

/*
 * Build the page on `scr`, hidden. Call once, from ui_pages_init().
 *
 * Every object is created HERE and only ever updated afterwards, never
 * created and destroyed as panels change. ui_launcher.c makes the same choice
 * for its tiles and gives the reason: the LVGL pool has no room for churn.
 */
void ui_panel_attach(lv_obj_t *scr);

void ui_panel_open(void);
void ui_panel_close(void);
bool ui_panel_is_open(void);

/*
 * Forget the objects, because the screen under them has been deleted.
 *
 * usage_view_deinit() deletes the screen these hang off, and messages arrive
 * on the PROTOCOL thread, which knows nothing about a mode change. Without
 * this the next panel written goes through freed memory. The MODEL survives:
 * it is this module's own memory, so a theme change rebuilds the screen and
 * ui_panel_refresh() puts the words back.
 */
void ui_panel_detach(void);

/*
 * Take a `panel` message off the wire.
 *
 * Returns true if it was for us and was understood. A malformed one is
 * ignored rather than partially applied: half a panel is a panel that reads
 * as current and is not.
 */
bool ui_panel_on_message(const char *json);

/* Is there anything to show? The page is skipped in navigation until the
 * daemon has sent at least one panel, so a board whose daemon does not use
 * them does not gain an empty page. */
bool ui_panel_any(void);

/* How many panels have arrived, for the left/right move within the page. */
int ui_panel_count(void);

/* Show panel `i`, clamped to what exists. */
void ui_panel_show(int i);

/* Which one is showing. */
int ui_panel_current(void);

/* The overlay itself, so ui_pages.c can hang its home arrow inside it -- the
 * arrow must be hidden and shown with the page it belongs to. NULL before
 * attach. */
lv_obj_t *ui_panel_panel(void);

/*
 * Repaint from the stored model.
 *
 * Called after a theme change, which rebuilds every screen: the model here
 * survives that, the LVGL objects do not, so this puts the words back.
 */
void ui_panel_refresh(void);

#endif /* UI_PANEL_H */
