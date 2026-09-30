/* Standalone host test for the panel's tile grid.
 *
 * Build & run:
 *   cc -I ../../V2/firmware host_test.c -o /tmp/panelgeom && /tmp/panelgeom
 *
 * Six tiles arrived because somebody wanted six, and six across a 320 px
 * screen is 41 px a tile -- five characters of montserrat_14, which fits
 * neither "Select" nor "Direct". So they wrap to two rows of three at 90 px,
 * and that second row occupies the space two text rows were using.
 *
 * None of that is visible from the daemon and none of it is visible in a unit
 * test of the Python. It is arithmetic, it decides whether labels are readable
 * and whether buttons sit on top of text, and the only other way to check it
 * is to flash a board and look -- which is how the panel went a whole day
 * being wrong about something else entirely.
 */
#include <stdio.h>
#include "ui_panel_geom.h"

#define SCR_W	320
#define SCR_H	240
#define ALL_ROWS	5

/* About eight pixels a character at montserrat_14, measured off the existing
 * four-tile row: 66 px held "Sleep screen" at twelve characters only because
 * it was allowed to overflow. Eight is the honest figure for a label that
 * must FIT. */
#define PX_PER_CHAR	8

static int failures;
#define CHECK(c, m) do { if (!(c)) { printf("FAIL: %s\n", m); failures++; } \
	else { printf("PASS: %s\n", m); } } while (0)

static int tile_top(int n)
{
	int rows = PANEL_TILE_ROWS(n);

	return SCR_H - PANEL_TILE_BOTTOM - rows * PANEL_TILE_H
	       - (rows - 1) * PANEL_TILE_GAP;
}

int main(void)
{
	/* --- the shape ------------------------------------------------ */
	CHECK(PANEL_TILE_COLS(1) == 1, "one tile is one column");
	CHECK(PANEL_TILE_COLS(4) == 4, "four tiles stay on one row");
	CHECK(PANEL_TILE_COLS(5) == 3, "five tiles wrap to three columns");
	CHECK(PANEL_TILE_COLS(6) == 3, "six tiles are three columns");
	CHECK(PANEL_TILE_ROWS(4) == 1, "four tiles are one row");
	CHECK(PANEL_TILE_ROWS(5) == 2, "five tiles are two rows");
	CHECK(PANEL_TILE_ROWS(6) == 2, "six tiles are two rows");

	/* --- labels have to fit --------------------------------------- */
	{
		int w4 = PANEL_TILE_W_IN(SCR_W, PANEL_TILE_COLS(4));
		int w6 = PANEL_TILE_W_IN(SCR_W, PANEL_TILE_COLS(6));

		CHECK(w4 >= 8 * PX_PER_CHAR,
		      "a four-tile button holds eight characters");
		CHECK(w6 >= 8 * PX_PER_CHAR,
		      "a six-tile button still holds eight characters");
		/* The whole reason for wrapping. A flat row of six would be
		 * 41 px, and this is the assertion that stops someone
		 * 'simplifying' the grid back into a line. */
		CHECK(PANEL_TILE_W_IN(SCR_W, 6) < 6 * PX_PER_CHAR,
		      "six across one row would NOT hold six characters");
		CHECK(w6 > PANEL_TILE_W_IN(SCR_W, 6),
		      "wrapping makes the buttons wider, not narrower");
	}

	/* --- nothing lands on top of anything else -------------------- */
	{
		int n;

		for (n = 1; n <= 6; n++) {
			int rows_shown = PANEL_TEXT_ROWS_FOR(n, ALL_ROWS);
			int text_bottom = PANEL_ROW_TOP + rows_shown * PANEL_ROW_H;
			char msg[96];

			snprintf(msg, sizeof msg,
				 "%d tiles clear the %d text rows drawn with them",
				 n, rows_shown);
			CHECK(text_bottom <= tile_top(n), msg);

			snprintf(msg, sizeof msg,
				 "%d tiles stay on the screen", n);
			CHECK(tile_top(n) >= 0
			      && tile_top(n) + PANEL_TILE_ROWS(n) * PANEL_TILE_H
				 + (PANEL_TILE_ROWS(n) - 1) * PANEL_TILE_GAP
				 <= SCR_H, msg);
		}
	}

	/* --- a full row of tiles fits across ------------------------- */
	{
		int n;

		for (n = 1; n <= 6; n++) {
			int cols = PANEL_TILE_COLS(n);
			int w = PANEL_TILE_W_IN(SCR_W, cols);
			int span = cols * w + (cols - 1) * PANEL_TILE_GAP;
			char msg[96];

			snprintf(msg, sizeof msg,
				 "%d tiles fit across the screen", n);
			CHECK(span + 2 * PANEL_SIDE <= SCR_W, msg);
		}
	}

	/* --- the five-row case is unchanged --------------------------- */
	/* ALL_ROWS mirrors PANEL_ROWS in ui_panel.h. Not included here -- that
	 * header needs LVGL -- and tests/pc/test_panel.py already pins the
	 * Python mirror against the real define, so the two cannot drift
	 * without something failing. */
	CHECK(PANEL_TEXT_ROWS_FOR(1, ALL_ROWS) == ALL_ROWS,
	      "one tile still leaves all five text rows");
	CHECK(PANEL_TEXT_ROWS_FOR(4, ALL_ROWS) == ALL_ROWS,
	      "four tiles still leave all five text rows");
	CHECK(PANEL_TEXT_ROWS_FOR(5, ALL_ROWS) < ALL_ROWS,
	      "wrapping costs text rows, and says so");

	if (failures) {
		printf("\n%d check(s) failed\n", failures);
		return 1;
	}
	printf("\nall checks passed\n");
	return 0;
}
