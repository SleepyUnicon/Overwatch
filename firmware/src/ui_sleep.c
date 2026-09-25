/*
 * Sleep mode (docs/sleep-mode-design.md).
 *
 * A DRAWN face, for as long as whatever put the board to sleep still holds --
 * the host silent, or the reading no longer moving. It sits on a plain LVGL
 * screen that also takes the tap, and every pass services the protocol, so
 * the first word from a waking app is heard within a frame.
 *
 * It used to be three encoded clips: closing, looping, opening. Those were
 * the Blink eyes, and they were a filmed animation -- one expression, played
 * back. ui_face.c draws instead, which is what lets the face have moods at
 * all: see the note at the top of ui_face.h for why a clip library was the
 * wrong shape for this.
 */
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <lvgl.h>

#include "bootclip.h"
#include "proto.h"
#include "sleep_gate.h"
#include "ui_boot.h"
#include "ui_face.h"
#include "ui_qr.h"
#include "ui_settings.h"
#include "ui_sleep.h"
#include "usage_freshness.h"
#include "usage_view.h"

#define PEEK_MS 10000

static volatile bool tapped;

static void tap_cb(lv_event_t *e)
{
	ARG_UNUSED(e);
	tapped = true;
}

static bool (*wake_when)(void);

/*
 * Every reason to stop dozing, asked in one place.
 *
 * wake_when() is the caller's reason -- the app spoke again, or the reading
 * started moving. ui_settings_busy() is this file's own, and it is here
 * because of what dozing takes away rather than because of anything the
 * sleep design says.
 *
 * Settings are asked for by a left swipe on the gauge screen, or by a tap on
 * the right edge zone -- which is the route that still works over the
 * CONNECTING takeover, where the swipe is deliberately refused. Neither
 * gesture opens anything: both raise a flag that ui_settings_service() acts
 * on, and the only call to that lives in the mode loop this function has
 * taken over. So on the shipped build -- USB-only, one loop -- a request made
 * during a peek latched and nothing ever answered it. The panel then opened
 * by itself whenever the board next woke, which is the same bug wearing the
 * other face.
 *
 * That bites hardest in the state that causes it. A board plugged into a
 * computer with no daemon installed, or one that cannot open the port, dozes
 * after 60 s over the CONNECTING screen -- and settings is exactly where the
 * owner goes to fix that. A tap gave them ten seconds of dashboard; it did
 * not give them control.
 *
 * Waking rather than servicing the latch here is deliberate. ui_slide_run()
 * must be driven from a mode loop in thread context, never from under a clip
 * player or an LVGL callback (ui_slide.h), and a peek that opened the panel
 * would then have to decide what to do when its ten seconds ran out with the
 * user halfway through the list. Ending the doze hands the request back to
 * the loop that owns it, and the panel slides in on that loop's first pass.
 */
static bool woken(void)
{
	return wake_when() || ui_settings_busy();
}

static bool tap_only(void)
{
	return tapped;
}

static bool awake_or_tap(void)
{
	return woken() || tapped;
}

static void service(void)
{
	proto_service();
	lv_timer_handler();
	k_sleep(K_MSEC(5));
}

/* A tap: the dashboard as it was, with a word about why nothing moves. Ten
 * seconds, or until there is something new to show, then back to dozing. */
static void peek(lv_obj_t *prev, lv_obj_t *sleep_scr, const char *note)
{
	int64_t until = k_uptime_get() + PEEK_MS;

	lv_scr_load(prev);
	ui_settings_notice(note);
	lv_refr_now(NULL);
	while (k_uptime_get() < until && !woken()) {
		service();
	}
	ui_settings_notice_dismiss();
	if (!woken()) {
		lv_scr_load(sleep_scr);
		lv_refr_now(NULL);
	}
}

void ui_sleep_run(bool (*awake)(void), const char *peek_note)
{
	lv_obj_t *prev = lv_scr_act();
	lv_obj_t *scr = lv_obj_create(NULL);

	wake_when = awake;
	/*
	 * Tell the dashboard it is asleep, before anything else.
	 *
	 * service() below keeps the protocol running for the whole sleep, so
	 * every usage_view setter goes on being called with nobody looking --
	 * and the status-change popup is the one that would ACT on that, by
	 * putting a card on a screen that is not loaded and leaving it there:
	 * the 1 s tick that expires it is driven from the mode loop this
	 * function has taken over. A tap's peek would then show a sentence
	 * from hours ago as though it were news.
	 */
	usage_view_set_sleeping(true);
	/*
	 * And take What's new down, because it would eat the tap below.
	 *
	 * That screen is a full 320x240 on lv_layer_top, which sits above
	 * every screen -- so lv_scr_load() does not hide it and the closing
	 * clip, drawn straight to the panel, only paints over it. The tap is
	 * the part that matters: lv_obj_create hands out LV_OBJ_FLAG_CLICKABLE
	 * by default (lv_obj.c:495), so the hit test finds this overlay before
	 * it finds `scr`, tap_cb never runs, and a board dozing with the screen
	 * open cannot be woken by touching it at all. Every OTHER modal here is
	 * narrower than the panel and leaves a live strip down each side, which
	 * is why this is the first one to reach the tap.
	 *
	 * The notice underneath is left alone: the peek replaces it with its
	 * own note a moment later, and that path has worked since it was
	 * written.
	 */
	ui_settings_whatsnew_dismiss();
	lv_obj_clear_flag(scr, LV_OBJ_FLAG_SCROLLABLE);
	lv_obj_add_flag(scr, LV_OBJ_FLAG_CLICKABLE);
	lv_obj_set_style_bg_color(scr, lv_color_hex(UI_FACE_GROUND), 0);
	lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);
	lv_obj_add_event_cb(scr, tap_cb, LV_EVENT_CLICKED, NULL);
	lv_scr_load(scr);
	lv_refr_now(NULL);
	printk("[sleep] dozing (face)\n");

	/*
	 * A board that has NEVER met a daemon shows the way to one instead
	 * of a face.
	 *
	 * This is the screen somebody who was handed a built kit is looking
	 * at, and the face -- charming on a working desk -- tells them
	 * nothing at all. It cannot tell their computer anything either: see
	 * ui_qr.h. So it shows the address, and they carry it across.
	 *
	 * Asked of proto_host_version() rather than of "is a host talking
	 * now", because the two differ exactly when it matters. A board
	 * whose daemon is merely asleep HAS been set up and wants its face
	 * back; one that has never been introduced has not.
	 */
	if (!proto_host_version()[0]) {
		lv_obj_set_style_bg_color(scr, lv_color_hex(0xFDFAF1), 0);

		lv_obj_t *title = lv_label_create(scr);

		lv_label_set_text(title, "Set me up");
		lv_obj_set_style_text_color(title, lv_color_hex(0x101418), 0);
		lv_obj_set_style_text_font(title, &lv_font_montserrat_20, 0);
		lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 16);

		lv_obj_t *qr = ui_qr_panel(scr, ui_qr_setup_url(), 120);

		lv_obj_align(qr, LV_ALIGN_CENTER, 0, 18);
	} else {
		ui_face_create(scr);
	}
	lv_refr_now(NULL);
	while (!woken()) {
		/*
		 * service() sleeps 5 ms and the face wants about 30, so the
		 * tick is paced against the clock rather than the loop. Tying
		 * it to the iteration count would make every expression six
		 * times faster than it was drawn to be, and would change
		 * again the day service() changes its sleep.
		 */
		int64_t next_frame = 0;

		tapped = false;
		while (!woken() && !tapped) {
			int64_t t = k_uptime_get();

			if (t >= next_frame) {
				/* No-op when the setup screen is up: the
				 * face was never built, and ui_face_tick
				 * returns on its own null check. */
				ui_face_tick();
				next_frame = t + 30;
			}
			service();
		}
		if (tapped && !woken()) {
			peek(prev, scr, peek_note);
		}
	}
	printk("[sleep] waking\n");

	/*
	 * Back to the dashboard as it was -- flagged old only if it still IS.
	 *
	 * This used to stamp STALE unconditionally, which was right for the
	 * one caller that existed and wrong for both of the others. A board
	 * dozing because its reading stopped moving wakes on a FRESH reading,
	 * which has already set the dot green; stamping amber over it labels
	 * the very frame that woke us as old. And a board dozing before it
	 * ever met a daemon has no reading at all to call old.
	 *
	 * The test is the display's own bound, not the dozing one. Whether to
	 * doze is a question about the person and is answered in hours;
	 * whether the dot is amber is a question about the number and is
	 * answered in half an hour, the same 1800 s the daemon uses to set the
	 * `stale` flag it normally tells us. Asking the four-hour question
	 * here left a board waking from an hour's doze green over an hour-old
	 * reading until the next usage message landed, up to a minute later.
	 *
	 * It is also the reading's own AGE, not the desk's. main.c dozes on
	 * usage_freshness_active_age_s, because that decision is about the
	 * person; this dot describes the figure beside it, so it keeps asking
	 * how old the figure is even when the two answers differ by hours --
	 * which they do exactly when the daemon is re-offering a remembered
	 * five-hour reading. A board woken by a live status line whose dial is
	 * still this morning's SHOULD say the reading is old, because it is.
	 */
	lv_scr_load(prev);
	lv_obj_del(scr);
	/* The face's objects were children of that screen and have just gone
	 * with it. See ui_face_forget. */
	ui_face_forget();
	/*
	 * Eyes open: the popup may speak again, from the NEXT change. The
	 * counts that arrived during the sleep were recorded as they came, so
	 * this does not release a backlog -- waking shows what is true now.
	 */
	usage_view_set_sleeping(false);
	if (usage_view_have_data() &&
	    sleep_reading_is_stale(usage_freshness_age_s(k_uptime_get()))) {
		usage_view_set_status(USAGE_STATUS_STALE);
	}
	lv_refr_now(NULL);
}


void ui_sleep_show_face(void)
{
	/* Cleared first: `tapped` is a static that outlives the last doze, and
	 * a stale one would end this the frame it started -- the face would
	 * flash and vanish with no way to tell that from a crash. */
	tapped = false;
	ui_sleep_run(tap_only, NULL);
}
