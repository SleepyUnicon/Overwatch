#ifndef UI_LAUNCHER_H
#define UI_LAUNCHER_H

#include <lvgl.h>
#include <stdbool.h>

/*
 * A grid of buttons that launch apps on the tethered computer.
 *
 * An OVERLAY on the gauge screen, not an LVGL screen of its own, and that is
 * not a style preference. usage_view_deinit() records why: with no PSRAM the
 * LVGL heap cannot hold two full screens, which is why ui_settings.c is an
 * overlay too (ui_settings.h:8). CONFIG_LV_Z_MEM_POOL_SIZE is 30720 and a
 * redraw allocates transient draw tasks on top of whatever is live. A second
 * screen does not fail at build time -- it fails as an allocation that returns
 * NULL somewhere in a repaint, on a customer's desk, once both are populated.
 *
 * Six buttons and no more. Three columns at 96 px is 288 of the panel's 320,
 * and the remaining 32 is the four gaps; a fourth column puts a target under
 * 72 px, which ui_settings.c:1499 already measured as the point where a
 * control stops being reliably hittable on this panel.
 */
void ui_launcher_attach(lv_obj_t *scr);

/* Show or hide the grid. Safe before attach; does nothing then. */
void ui_launcher_open(void);
void ui_launcher_close(void);
bool ui_launcher_is_open(void);

/*
 * The daemon answered a launch.
 *
 * `ok` false means the computer tried and failed -- no such app, most often.
 * The button says so rather than staying silent, because the alternative is a
 * tap that looks identical whether it worked or not, on a device whose whole
 * argument is that it tells you the truth about a number.
 */
void ui_launcher_result(int slot, bool ok);

/*
 * What each button shows, from the daemon.
 *
 * The value is an ICON KEY - "spotify", "photoshop" - not a filename and not
 * a path. src/icons_gen.h holds what the board can draw; a key that is not in
 * that table is drawn as TEXT instead, which is what keeps a slot pointed at
 * some app nobody shipped an icon for from becoming a blank tile.
 *
 * The board ships knowing nothing about which apps exist: the computer owns
 * that list, so a change there does not need a reflash. Until the first of
 * these arrives the grid draws dim placeholders and refuses taps -- a button
 * that names nothing cannot launch anything, and one that looks live and
 * answers nothing is the failure ui_settings.c called out on the provider
 * pill (docs/multi-provider.md 4b).
 */
void ui_launcher_set_slot(int slot, const char *key);

/* The overlay itself, so ui_pages.c can hang its rail inside it -- the rail
 * must be hidden and shown with the page it belongs to, not managed
 * separately. NULL before attach. */
lv_obj_t *ui_launcher_panel(void);

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
void ui_launcher_detach(void);

#endif /* UI_LAUNCHER_H */
