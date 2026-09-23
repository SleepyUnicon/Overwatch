#ifndef UI_THEME_H
#define UI_THEME_H

#include <stdbool.h>
#include <stdint.h>

/*
 * One palette, two sets of values, asked at draw time.
 *
 * Ten files used to carry their own #define COL_BG, which was survivable while
 * they agreed and stopped being survivable the moment they did not: the gauges
 * were moved to white and ui_music.c and ui_launcher.c stayed on 0x0E1116, so
 * the same swipe crossed from a white screen to a near-black one. Nobody chose
 * that. It was the cost of the constant living in ten places.
 *
 * Colours are held as uint32_t rather than lv_color_t so this header does not
 * drag lvgl.h into anything that only wants to know the theme. The callers
 * wrap them in lv_color_hex() at the point of use, which is where they already
 * were.
 *
 * LIGHT IS THE DEFAULT, and the light values are not a guess: they are the
 * measured set from usage_view.c, which carries its contrast ratio against
 * white in a comment beside each one. The dark values are the set the widget
 * pages shipped with. Neither is new here; this only gives them one home.
 *
 * Switching is a REBUILD, not a restyle. LVGL keeps no back-reference from a
 * styled object to the value it was given, so a live switch would mean walking
 * every object on every screen and knowing which role each colour played --
 * and getting one wrong leaves a single unreadable label that nobody finds
 * until a customer does. The screen is already torn down and rebuilt on a mode
 * change (ui_pages_detach/init), so the switch borrows that path.
 */
struct ui_palette {
	uint32_t bg;		/* the ground */
	uint32_t panel;		/* cards, barely off the ground */
	uint32_t track;		/* unfilled arcs, inactive marks */
	uint32_t text;		/* primary ink */
	uint32_t dim;		/* secondary ink */

	uint32_t green;		/* the severity ramp */
	uint32_t amber;
	uint32_t red;
	uint32_t grey;		/* no data yet */
	uint32_t other;		/* a provider that is not Claude or Codex */

	uint32_t line;		/* full-width section rules */
	uint32_t danger_bg;	/* factory tile: tinted, never solid red */
	uint32_t danger_bd;

	uint32_t green_ink;	/* ink ON a filled severity colour */
	uint32_t amber_ink;
	uint32_t red_ink;
};

/* The palette in force. Never NULL -- light until told otherwise. */
const struct ui_palette *ui_theme(void);

bool ui_theme_is_dark(void);

/*
 * Choose a theme and persist it. Does NOT repaint: the caller rebuilds, and
 * ui_theme_rebuild_pending() is how the mode loop finds out it should.
 * Returns true if the value actually changed.
 */
bool ui_theme_set_dark(bool dark);

/* Read the stored choice. Call once, after cfg_init(). */
void ui_theme_init(void);

/* Set by ui_theme_set_dark(), cleared by whoever does the rebuild. */
bool ui_theme_rebuild_pending(void);
void ui_theme_rebuild_clear(void);

#endif /* UI_THEME_H */
