#ifndef UI_PAGES_H
#define UI_PAGES_H

#include <lvgl.h>
#include <stdbool.h>

/*
 * A cross, not a stack.
 *
 *                     [ settings ]
 *                          ^
 *        [ music ]  <  [ gauges ]  >  [ launcher ]
 *                          v
 *                       [ face ]
 *
 * The stack this replaces was three pages on one line, walked with up and
 * down, and it had the failing every one-line menu has: nothing on the screen
 * said what was on either side of you, so the only way to find the launcher
 * was to swipe twice and see. "The user doesnt know how to use the thing" was
 * the report, and a line cannot answer it -- four labelled edges can, because
 * every destination is one move away and each one is named where you would
 * reach for it.
 *
 * HUB AND SPOKE. From the centre, each direction opens its own page. From any
 * page, the opposite direction comes home. Nothing else moves: there is no
 * music-to-launcher shortcut, because it would have to be two moves or a
 * diagonal, and this panel cannot read a diagonal (ui_swipe.h refuses
 * ambiguous ones on purpose). One move out, one move back, always.
 *
 * WHAT MOVED, AND WHY IT HAD TO
 *
 * Up and down used to walk the provider pages (Claude, Codex) before
 * continuing into the stack. The cross needs both for settings and the face,
 * so the providers move to the tap zone that was ALREADY cycling them --
 * mk_page_zone's 200x44 strip in ui_settings.c, which exists because a missed
 * vertical swipe used to be a dead end. Nothing is lost: the providers keep
 * the control that was measured to be the reliable one, and give up the
 * gesture that was not.
 *
 * Right used to replay the boot clip. That is a thing to show someone, not a
 * thing to navigate with, so it moves into settings where the rest of the
 * once-in-a-while lives.
 *
 * ARROWS FIRST, SWIPES SECOND. ui_pages.c's old header said it plainly and it
 * is still true: a finger sliding on this resistive panel keeps breaking
 * contact, one stroke arrives as five or six presses, and the gesture "lands
 * about half the time". Every direction here has a drawn arrow with an
 * invisible hit area behind it, and that arrow is the primary control. The
 * swipe is the shortcut for whoever has learnt it.
 */
enum ui_page {
	UI_PAGE_GAUGES = 0,	/* the centre */
	UI_PAGE_MUSIC,		/* left */
	UI_PAGE_LAUNCHER,	/* right */
	UI_PAGE_N,
};

/*
 * Settings and the face are NOT in that enum, deliberately.
 *
 * This module owns full-screen overlays that it shows and hides. Settings is a
 * panel ui_settings.c builds and tears down on its own schedule, and the face
 * is an animation ui_sleep.c plays; both are run from the mode loop rather
 * than from inside an LVGL event. Listing them here would mean this file
 * pretending to a control it does not have. Instead a move toward either is
 * reported, and the mode loop does the work -- the same split every other
 * deferred action in this UI already uses.
 */
enum ui_move {
	UI_MOVE_NONE = 0,	/* nothing there; the panel does not twitch */
	UI_MOVE_DONE,		/* an overlay was shown or hidden, here */
	UI_MOVE_SETTINGS,	/* caller should open settings */
	UI_MOVE_FACE,		/* caller should play the face */
};

enum ui_dir {
	UI_DIR_LEFT = 0,
	UI_DIR_RIGHT,
	UI_DIR_UP,
	UI_DIR_DOWN,
	UI_DIR_N,
};

/* Build the overlays. Call once, after usage_view_init(). */
void ui_pages_init(lv_obj_t *scr);

/*
 * Take one step. Runs on the LVGL thread, so it only shows and hides -- it
 * never drives a transition. See ui_swipe.h.
 */
enum ui_move ui_pages_go(enum ui_dir dir);

/* What a step would do, asked before a transition is armed. */
enum ui_move ui_pages_would(enum ui_dir dir);

enum ui_page ui_pages_current(void);
bool ui_pages_at_centre(void);

/* Back to the gauges from wherever we are. The sleep path uses this: a board
 * that dozed on the launcher should not wake showing it. */
void ui_pages_home(void);

/* Drop the overlays because the screen holding them was deleted. Call
 * wherever usage_view_deinit() is called; re-init with ui_pages_init(). */
void ui_pages_detach(void);

#endif /* UI_PAGES_H */
