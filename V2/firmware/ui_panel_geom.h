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
#define PANEL_TILE_BOTTOM	14

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
#define PANEL_TEXT_ROWS_FOR(n, all) ((n) > PANEL_TILES_ONE_ROW ? 3 : (all))

/* Top of the tile block, for a screen `h` tall holding `n` tiles. */
#define PANEL_TILE_TOP(h, n)	((h) - PANEL_TILE_BOTTOM \
				 - PANEL_TILE_ROWS(n) * PANEL_TILE_H \
				 - (PANEL_TILE_ROWS(n) - 1) * PANEL_TILE_GAP)

#endif /* UI_PANEL_GEOM_H */
