#ifndef UI_MUSIC_H
#define UI_MUSIC_H

#include <lvgl.h>
#include <stdbool.h>

/*
 * The transport page: what is playing, and three buttons.
 *
 * An overlay on the gauge screen for the same reason ui_launcher.c is one --
 * the LVGL heap cannot hold a second full screen (ui_settings.h:8,
 * usage_view_deinit). Two overlays and the gauges share one screen; none of
 * them is ever allocated twice.
 */

/* What the computer says the player is doing. Absent is not paused: a machine
 * with Spotify closed, or one that has never answered, must not draw a pause
 * button that would start music nobody asked for. */
enum music_state {
	MUSIC_UNKNOWN = -1,	/* no answer, or Spotify is not running */
	MUSIC_PAUSED = 0,
	MUSIC_PLAYING = 1,
};

void ui_music_attach(lv_obj_t *scr);

void ui_music_open(void);
void ui_music_close(void);
bool ui_music_is_open(void);

/*
 * A fresh reading from the computer.
 *
 * `pos_s` and `dur_s` are seconds, -1 for unknown. The position is TICKED
 * LOCALLY between readings by ui_music_tick_1s(), which is the same split
 * the gauges already use for their countdowns: the daemon does the arithmetic
 * it alone can do and the board keeps the display moving in between. A track
 * message every two seconds would otherwise draw a progress bar that jumps.
 */
void ui_music_set_track(const char *artist, const char *name,
			  int state, int pos_s, int dur_s);

/*
 * Advance the local position one second. Drive it from the mode loop beside
 * usage_view_tick_1s(), not from a timer of its own -- see that function.
 */
void ui_music_tick_1s(void);

/*
 * The computer cannot see the player, and why.
 *
 * `reason` is drawn verbatim and the board keeps 47 characters of it, so the
 * daemon sends the sentence rather than a code. This is a separate call from
 * set_track because "Spotify is not running" and "the Mac will not let me ask"
 * are different problems with different cures, and a page that shows "--" for
 * both teaches the owner nothing.
 */
void ui_music_set_unavailable(const char *reason);

/* The overlay itself, so ui_pages.c can hang its rail inside it -- the rail
 * must be hidden and shown with the page it belongs to, not managed
 * separately. NULL before attach. */
lv_obj_t *ui_music_panel(void);

/*
 * Forget the overlay, because the screen under it has been deleted.
 *
 * usage_view_deinit() deletes gauge_scr (it is lv_obj_create(NULL), a screen
 * of its own), and these overlays are its children -- so they die with it and
 * every pointer here becomes dangling. The setters are called from the
 * PROTOCOL thread, which knows nothing about a mode change, so without this
 * the next arriving message writes through freed memory. usage_view.c:618
 * nulls its own pointers for exactly this reason and says so.
 */
void ui_music_detach(void);

#endif /* UI_MUSIC_H */
