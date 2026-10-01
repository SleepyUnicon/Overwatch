/*
 * Panel tile geometry. NO LVGL, NO ZEPHYR -- that is the whole point.
 *
 * Split out of ui_panel.h for the reason ui_slide_geom.h was split out of
 * ui_slide.c: this is arithmetic, it decides whether labels are readable and
 * whether buttons sit on top of text, and arithmetic that can only run on a
 * board is arithmetic nobody checks. tests/panel_geom includes this file and
 * nothing else.
 *
 * Tiles are a GRID, not a row. Six across a 320 px screen is 41 px a tile,
 * about five characters of montserrat_14 -- "Select" does not fit, and neither
 * does "Direct". Three across is 90 px, about eleven characters, which fits
 * every label worth writing. So more than four wraps to a second row of three.
 *
 * The cost is vertical: two rows of tiles begin 42 px higher than one, and
 * PANEL_ROW_TOP + 5 * PANEL_ROW_H already reaches 182. PANEL_TEXT_ROWS_FOR is
 * how many text rows survive a given tile count. paint() hides the rest
 * whatever arrives, and V2/panel.py trims them before sending, so neither side
 * can produce the overlap alone.
 */
#ifndef UI_PANEL_GEOM_H
#define UI_PANEL_GEOM_H

#define PANEL_TITLE_Y		16
#define PANEL_ROW_TOP		52
#define PANEL_ROW_H		26
#define PANEL_SIDE		16
#define PANEL_TILE_H		34
#define PANEL_TILE_GAP		8
/*
 * The home strip -- "< USAGE" -- lives at the bottom 40 px of every widget
 * page. ui_pages.c owns it (HOME_H), and this is a MIRROR of that number,
 * which tests/panel_geom pins against the real one.
 *
 * It is here because leaving it out cost a release. Tiles were laid out
 * against the screen, 240 px, so they ended at y=226 while the strip starts
 * at 200: twenty-six pixels of every tile row sat underneath it, and with six
 * tiles the entire second row was invisible. The owner photographed the board
 * showing "Left Right Top" and nothing else, which is the first time anyone
 * had seen this page on glass.
 *
 * tests/panel_geom checked that tiles stayed within the 240 px screen. They
 * did. It was the wrong bound, and no test on this side could have caught the
 * right one while the constant lived in another file.
 */
#define PANEL_HOME_H		40
#define PANEL_HOME_GAP		8
#define PANEL_TILE_BOTTOM	(PANEL_HOME_H + PANEL_HOME_GAP)

/* Above this many, tiles wrap. */
#define PANEL_TILES_ONE_ROW	4

#define PANEL_TILE_COLS(n)	((n) <= PANEL_TILES_ONE_ROW ? (n) : 3)
#define PANEL_TILE_ROWS(n)	(((n) + PANEL_TILE_COLS(n) - 1) \
				 / PANEL_TILE_COLS(n))
#define PANEL_TILE_W_IN(w, cols) (((w) - 2 * PANEL_SIDE \
				   - ((cols) - 1) * PANEL_TILE_GAP) / (cols))

/* `all` is the panel's full row count; the caller passes PANEL_ROWS. Taken as
 * an argument rather than read from ui_panel.h so this header stays free of
 * everything that file needs. */
/*
 * How many text rows survive beside `n` tiles, given `all` of them exist.
 *
 * Both numbers are smaller than they were, because both were computed against
 * a screen that is 40 px shorter than anyone had written down:
 *
 *   one tile row  -> tiles start at 158, so rows may reach 156: FOUR
 *   two tile rows -> tiles start at 116, so rows may reach 104: TWO
 *
 * Five rows never fitted even with a single row of tiles. The fifth was drawn
 * under the buttons.
 */
#define PANEL_TEXT_ROWS_FOR(n, all) \
	((n) > PANEL_TILES_ONE_ROW ? 2 : ((all) > 4 ? 4 : (all)))

/* Top of the tile block, for a screen `h` tall holding `n` tiles. */
#define PANEL_TILE_TOP(h, n)	((h) - PANEL_TILE_BOTTOM \
				 - PANEL_TILE_ROWS(n) * PANEL_TILE_H \
				 - (PANEL_TILE_ROWS(n) - 1) * PANEL_TILE_GAP)

#endif /* UI_PANEL_GEOM_H */
