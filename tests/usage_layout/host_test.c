/* Standalone host test for the gauge screen's geometry.
 *
 * Build & run:
 *   cc -I ../../firmware/src host_test.c -o /tmp/laytest && /tmp/laytest
 *
 * This exists because "the boxes do not overlap" and "the screen reads well"
 * are different claims, and only the first one is checkable without pixels.
 * tools/panel_render/render.sh covers the second; this covers the first, and
 * has caught a hint-line collision, a bar butting flush against its own
 * readout, and a countdown sliced by its own inner ring -- none of which were
 * visible in the source.
 *
 * It asserts from usage_layout.h, the same header the screen is built from, so
 * the check cannot drift away from the code.
 *
 * Vertical geometry is exact: every unlabelled label on this screen is
 * FONT_LINE_H tall and that is a constant. Horizontal extents for text use the
 * declared *_MAX_W budgets, and the real strings are checked against them.
 */
#include <stdio.h>
#include <string.h>
#include "usage_layout.h"

static int failures;
#define CHECK(c, m) do { if (!(c)) { printf("FAIL: %s\n", m); failures++; } \
	else { printf("PASS: %s\n", m); } } while (0)

/* Same PASS/FAIL-plus-failures-counter shape as CHECK above, spelled for a
 * pair of numbers so a mismatch prints both sides instead of just the
 * condition that failed. */
#define EXPECT_EQ(got, want) do { \
	long g_ = (long)(got), w_ = (long)(want); \
	if (g_ == w_) { \
		printf("PASS: %-28s -> %ld\n", #got, g_); \
	} else { \
		printf("FAIL: %-28s -> %ld (want %ld)\n", #got, g_, w_); \
		failures++; \
	} \
} while (0)

struct box { const char *name; int x0, y0, x1, y1; };

/* TOP_MID: x is an offset of the object's CENTRE from the screen centre. */
static struct box top_mid(const char *name, int xoff, int y, int w, int h)
{
	struct box b;
	b.name = name;
	b.x0 = SCR_MID_X + xoff - w / 2;
	b.x1 = b.x0 + w;
	b.y0 = y;
	b.y1 = y + h;
	return b;
}

/* TOP_RIGHT with a positive `in` offset from the right bezel. */
static struct box right_top(const char *name, int in, int y, int w, int h)
{
	struct box b;
	b.name = name;
	b.x1 = SCR_W - in;
	b.x0 = b.x1 - w;
	b.y0 = y;
	b.y1 = y + h;
	return b;
}

/* BOTTOM_MID with a positive `up` offset from the bottom edge. */
static struct box bottom_mid(const char *name, int up, int w, int h)
{
	struct box b;
	b.name = name;
	b.x0 = SCR_MID_X - w / 2;
	b.x1 = b.x0 + w;
	b.y1 = SCR_H - up;
	b.y0 = b.y1 - h;
	return b;
}

static int overlaps(struct box a, struct box b)
{
	return a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
}

static int on_screen(struct box b)
{
	return b.x0 >= 0 && b.y0 >= 0 && b.x1 <= SCR_W && b.y1 <= SCR_H;
}

/* Per-character width bounds for montserrat_14. A declared budget has to be
 * wide enough for its string and not absurdly wider -- a budget nobody sized
 * is how two widgets end up "clearing" each other on paper while touching on
 * the panel. */
#define CHAR_W_MIN 8
#define CHAR_W_MAX 14

#define BUDGET_FITS(budget, str) \
	((budget) >= (int)strlen(str) * CHAR_W_MIN && \
	 (budget) <= (int)strlen(str) * CHAR_W_MAX)

int main(void)
{
	/* The gauges. */
	struct box arc_l = top_mid("arc L", -GAUGE_CX, GAUGE_ARC_Y,
				   GAUGE_ARC_SZ, GAUGE_ARC_SZ);
	struct box arc_r = top_mid("arc R", GAUGE_CX, GAUGE_ARC_Y,
				   GAUGE_ARC_SZ, GAUGE_ARC_SZ);
	/* Height is GAUGE_PCT_FONT_H, not FONT_LINE_H: this label is drawn at
	 * montserrat_20, not the screen's default 14. */
	struct box pct_l = top_mid("percentage L", -GAUGE_CX, GAUGE_PCT_Y,
				   80, GAUGE_PCT_FONT_H);
	/* The caption sits INSIDE the ring, on the line above the percentage --
	 * it is no longer a row under the gauge, and GAUGE_NAME_Y is gone. Its
	 * width budget is the ring's hollow, the same as the percentage's,
	 * because anything wider paints over the coloured track. */
	struct box name_l = top_mid("SESSION caption", -GAUGE_CX,
				    GAUGE_UNIT_Y, GAUGE_PCT_MAX_W, FONT_LINE_H);
	struct box name_r = top_mid("WEEKLY caption", GAUGE_CX, GAUGE_UNIT_Y,
				    GAUGE_PCT_MAX_W, FONT_LINE_H);

	/* ONE countdown per gauge. The second provider is a page now, not a
	 * second line, so the only thing under a gauge is its own duration. */
	struct box cd_l = top_mid("countdown L", -GAUGE_CX,
				  GAUGE_CD_Y, GAUGE_CD_MAX_W, FONT_LINE_H);
	struct box cd_r = top_mid("countdown R", GAUGE_CX,
				  GAUGE_CD_Y, GAUGE_CD_MAX_W, FONT_LINE_H);

	/* The brand, and the status line that took the space under it when the
	 * provider's name moved to the bottom.
	 *
	 * RIGHT-aligned, BRAND_RIGHT_OFF in from the bezel. This modelled a
	 * centred wordmark long after usage_view.c stopped drawing one: the
	 * middle became the only place a top affordance could go, so the brand
	 * moved right and an arrow took the centre. A centred model put the
	 * word's left edge at 105, which is LEFT of PIP_WALL_X, so the test
	 * reported the pip row sliding under a logo that is nowhere near it. */
	struct box brand = right_top("brand", BRAND_RIGHT_OFF, TITLE_Y,
				     BRAND_W, FONT_LINE_H);
	struct box status = top_mid("status", 0, STATUS_Y,
				    STATUS_MAX_W, FONT_LINE_H);

	/* The clock shares STATUS_Y with the hint -- one of them is visible at
	 * a time, so they may overlap each other and must not overlap anything
	 * else. Width is the worst case the format can produce, not "12:04":
	 * 0, 4, 6, 8 and 9 all round to 9 px, so four digits and a 3 px colon. */
	struct box clock = top_mid("clock", 0, STATUS_Y, 4 * 9 + 3, FONT_LINE_H);

	/* The pip row's own bounding box, built from the same constants the
	 * checks below already asserted individually -- so the clock/pip
	 * overlap check and the row's own left/right clearance share one
	 * definition instead of two copies of the same arithmetic. */
	struct box pips;
	pips.name = "pip row";
	pips.x0 = PIP_X0;
	pips.y0 = PIP_Y;
	pips.x1 = PIP_X0 + PIP_MAX * PIP_PITCH - (PIP_PITCH - PIP_SZ);
	pips.y1 = PIP_Y + PIP_SZ;

	/* The provider pill: whose numbers these are, and the button that
	 * changes it. Padded, so it is taller than a bare line. */
	struct box who = bottom_mid("provider pill", PILL_BOTTOM_OFF,
				    PILL_MAX_W, PILL_H);

	/* The page rail, below everything. */
	struct box rail = bottom_mid("page rail", RAIL_BOTTOM_OFF,
				     RAIL_PAGES_MAX * RAIL_PITCH -
					     (RAIL_PITCH - RAIL_DOT_W),
				     RAIL_H);

	struct box all[] = { arc_l, arc_r, pct_l, name_l, name_r,
			     cd_l, cd_r, brand, status, clock, pips,
			     who, rail };

	for (unsigned i = 0; i < sizeof(all) / sizeof(all[0]); i++) {
		char msg[64];

		snprintf(msg, sizeof(msg), "%s fits on the panel", all[i].name);
		CHECK(on_screen(all[i]), msg);
	}

	/* --- the gauges do not meet --- */
	CHECK(!overlaps(arc_l, arc_r), "the two gauges do not overlap");
	/* Inside its ring, not under it. The old form asserted the ring ended
	 * above the caption, which was true while the caption was a row below
	 * the gauge and became a 7 px "overlap" against a constant nothing
	 * read once it moved in. Containment is the claim now. */
	CHECK(name_l.y0 >= arc_l.y0 && name_l.y1 <= arc_l.y1,
	      "the caption sits inside its ring");
	CHECK(name_l.x0 >= arc_l.x0 && name_l.x1 <= arc_l.x1,
	      "the caption stays within its ring's hollow");

	/* --- the ring hollow --- */
	/*
	 * The percentage must clear the arc's own stroke, not merely fit
	 * inside the ring's outer bounding box -- text drawn as wide as the
	 * ring would paint over the coloured track. "1000%" is the longest
	 * string this label is ever asked to hold: pct_int() in usage_view.c
	 * clamps at PCT_DISPLAY_MAX (1000). Measured straight from
	 * lv_font_montserrat_20.c's own glyph_dsc table, not guessed: '1' is
	 * 7 px, '0' is 13 px, '%' is 17 px, so "1000%" is 7+13*3+17 = 63 px.
	 */
	CHECK(63 <= GAUGE_ARC_SZ - 2 * GAUGE_ARC_W,
	      "the widest percentage this label ever shows clears the arc's stroke");
	/* --- one countdown per gauge --- */
	CHECK(cd_l.x1 <= cd_r.x0,
	      "the two gauges' countdowns do not meet in the middle");
	CHECK(cd_l.y0 >= GAUGE_ARC_Y + GAUGE_ARC_SZ,
	      "countdowns sit below the rings, not inside them");
	CHECK(cd_l.y0 >= name_l.y1, "countdowns sit below the caption");
	CHECK(!overlaps(cd_l, who), "countdowns clear the provider pill");
	CHECK(!overlaps(cd_r, who), "countdowns clear the provider pill");

	/* --- the header block stacks without touching --- */
	CHECK(status.y0 >= brand.y1,
	      "the status line sits below the brand, not on it");
	CHECK(arc_l.y0 >= status.y1,
	      "the gauges start below the status line");

	/* The clock shares STATUS_Y with the status/hint line rather than
	 * owning a row, so its own box is checked against the same neighbours:
	 * it sits under the brand, clears the arcs below, and -- since it left
	 * the pip row's corner for this shared row -- no longer collides with
	 * the pips it used to sit beside.
	 *
	 * Against status.y0, not the STATUS_Y macro: clock is built two lines
	 * above from that same macro, so comparing it to the macro can never
	 * fail -- it would still pass with the clock's own top_mid() call
	 * edited to some other row. Comparing to status.y0 instead asserts the
	 * actual invariant this block is about: clock and status occupy the
	 * same row as each other, and a future edit that moves either one off
	 * that row fails here. */
	EXPECT_EQ(clock.y0, status.y0);
	CHECK(clock.y1 <= GAUGE_ARC_Y,
	      "the clock's line box clears the arcs below it");
	CHECK(clock.y0 >= brand.y1,
	      "the clock sits under the brand, not on it");
	CHECK(!overlaps(clock, pips),
	      "the clock no longer collides with the pip row it vacated");

	/*
	 * Two header rows again, not three. The clock shares STATUS_Y with the
	 * status/hint line instead of owning a corner, so the arcs get their
	 * 20 px back.
	 */
	EXPECT_EQ(STATUS_Y, TITLE_Y + FONT_LINE_H + 2);

	/*
	 * The ring is centred in the band that is FREE, not pinned under the
	 * header.
	 *
	 * This used to read GAUGE_ARC_Y == STATUS_Y + FONT_LINE_H + 4, which
	 * held while the dials sat directly beneath the header at 44. They were
	 * moved to 75 because at 44 they read as pinned to the top with 66 px
	 * of nothing below them. The invariant that replaced it is the one the
	 * header states: equal slack above and below, in the band between the
	 * header's last line and the face cue.
	 */
	{
		int above = GAUGE_ARC_Y - HDR_BOTTOM_Y;
		int below = FACE_CUE_TOP_Y - (GAUGE_ARC_Y + GAUGE_ARC_SZ);
		int skew = above > below ? above - below : below - above;
		char msg[96];

		CHECK(above > 0, "the ring clears the header");
		CHECK(below > 0, "the ring clears the face cue");
		/* Bounded, not equal. 75 was chosen when the cue was 26 px
		 * tall and began at 212; it is 18 px and begins at 220 now, so
		 * the gaps are 35 and 45. A line height is the most asymmetry
		 * that can pass -- enough to tolerate the cue being redrawn,
		 * nowhere near the 66 px that made the dials read as pinned to
		 * the top, which is the fault this guards. */
		snprintf(msg, sizeof(msg), "the ring sits near the middle of the"
			 " free band (%d above, %d below)", above, below);
		CHECK(skew <= FONT_LINE_H, msg);
	}

	/*
	 * The unit-plus-percentage PAIR is centred on the ring, not the
	 * percentage alone.
	 *
	 * Centre-derived rather than a literal either way: the old literal 90
	 * was 3 px high, which e7df2f2 fixed and this must not un-fix. But the
	 * claim moved when the unit line was stacked above the number -- the
	 * percentage on its own now measures 9 px low, correctly, because it is
	 * the pair that has to look centred.
	 *
	 * One pixel low is allowed and is the right way to miss: the ring's gap
	 * is at the bottom.
	 */
	{
		int top = GAUGE_UNIT_Y;
		int bottom = GAUGE_PCT_Y + GAUGE_PCT_FONT_H;
		int pair_mid = (top + bottom) / 2;
		int ring_mid = GAUGE_ARC_Y + GAUGE_ARC_SZ / 2;
		char msg[96];

		snprintf(msg, sizeof(msg), "the unit/percentage pair centres on"
			 " the ring (%d vs %d)", pair_mid, ring_mid);
		CHECK(pair_mid >= ring_mid && pair_mid <= ring_mid + 2, msg);
	}

	/*
	 * The pip row runs from the bezel to the brand, not from the clock to
	 * the brand: the clock shares STATUS_Y with the status/hint line now
	 * and is asserted against this row separately, above. Only the right
	 * edge here is still a measurement -- the wall derived from "OVERWATCH"
	 * below -- and a font bump must fail here rather than slide pips under
	 * the logo.
	 */
	/*
	 * The clock has left this corner for the row under the brand, so the
	 * row's left edge is now the bezel, not a time string. Its right edge
	 * is still the wordmark.
	 *
	 * Derived from the header, never typed. The literal that used to sit
	 * below was 134: the left edge of a CENTRED "BLINK", summed by hand
	 * from the font's advance table. The rebrand made the word nine glyphs
	 * instead of five and a later change moved it to the right bezel, and
	 * neither touched the number -- so this asserted a position two
	 * revisions stale and failed for it while the screen was right.
	 */
	CHECK(pips.x0 >= SCR_RIGHT_MARGIN_MIN,
	      "the pip row is not flush against the left bezel");
	CHECK(pips.x1 <= PIP_WALL_X,
	      "a full pip row clears the wall");
	CHECK(PIP_WALL_X <= brand.x0,
	      "the wall is left of the brand's real left edge");
	EXPECT_EQ(brand.x0, SCR_W - BRAND_RIGHT_OFF - BRAND_W);
	EXPECT_EQ(PIP_MAX, 11);
	/*
	 * Counts mode: three groups of pip + gap + one digit, with a gap
	 * between them. Asserted for the SINGLE-digit case only, which is the
	 * one the metrics are sized for -- a wider tally is measured at draw
	 * time and stopped at the wall (refresh_dots), because no constant
	 * here can know how many digits a tally has. PIP_NUM_ADV is the
	 * measured advance of the widest digit; if a font bump breaks that,
	 * this fails rather than the numerals creeping onto the brand.
	 */
	CHECK(PIP_X0 + 4 * (PIP_SZ + PIP_NUM_GAP + PIP_NUM_ADV)
	      + 3 * PIP_GROUP_GAP <= PIP_WALL_X,
	      "four counted groups clear the brand");
	/*
	 * And the row's Y, which had no assertion at all -- which is why a
	 * tally whose line box ended exactly on STATUS_Y got as far as a
	 * review. The label is FONT_LINE_H tall whatever is written in it, so
	 * this is the check the numeral needs and the pip does not.
	 */
	CHECK(PIP_NUM_Y + FONT_LINE_H <= STATUS_Y,
	      "the tally's line box clears the hint line");
	/*
	 * One centre line for the whole header: the tally's box, the pip and
	 * the health dot, at three different heights.
	 *
	 * Neither of these bites the way the clearance above does, and saying
	 * so is the point. PIP_NUM_Y subtracts FONT_LINE_H / 2 and the first
	 * check adds it straight back, so the two cancel exactly -- no font
	 * change can fail it, and it reduces to the second. What it does still
	 * catch is PIP_NUM_Y being rewritten with the wrong sign or the wrong
	 * operand, which is the mistake this row has already made once. The
	 * second fails only on an even DOT_SZ against an odd PIP_SZ.
	 *
	 * Both are written down anyway, because the shared centre line is the
	 * rule this row is built on, and a rule with no assertion is exactly
	 * how the Y above went unchecked until a tally landed on the hint line.
	 */
	EXPECT_EQ(PIP_NUM_Y + FONT_LINE_H / 2, HDR_ROW_Y + DOT_SZ / 2);
	EXPECT_EQ(PIP_Y + PIP_SZ / 2, HDR_ROW_Y + DOT_SZ / 2);

	/* --- the bottom stacks: countdowns, pill, rail --- */
	CHECK(who.y0 >= cd_l.y1,
	      "the provider pill sits below the countdowns");
	CHECK(!overlaps(rail, who),
	      "the page rail clears the provider pill above it");
	CHECK(!overlaps(rail, cd_l) && !overlaps(rail, cd_r),
	      "the page rail clears both countdowns");
	CHECK(rail.y1 <= SCR_H - 2,
	      "the page rail is not flush against the bottom bezel");

	/* --- the text budgets are real --- */
	/* A bare duration. The provider's name moved under the brand, which is
	 * what let this budget shrink -- and shrinking it is the check that
	 * the name really did leave, rather than merely being hidden. */
	CHECK(BUDGET_FITS(GAUGE_CD_MAX_W, "00m 00s"),
	      "GAUGE_CD_MAX_W is sized for a bare countdown, not guessed");
	CHECK(!BUDGET_FITS(GAUGE_CD_MAX_W, "claude  00m 00s"),
	      "GAUGE_CD_MAX_W no longer has room for a named one");
	/* Sized for the LONGEST tag the buffer can hold, not the one we happen
	 * to ship: provider1_tag is char[12], so eleven characters is what has
	 * to fit without reaching the clock and the status dot in the corners. */
	CHECK(BUDGET_FITS(PILL_MAX_W, "claude code"),
	      "PILL_MAX_W is sized for the longest tag, not guessed");
	/* The status line replaced a 140 px name with a whole sentence, so it
	 * needs the width the name never did -- and it must still clear the
	 * bezel. */
	CHECK(BUDGET_FITS(STATUS_MAX_W, "Reading is old - showing last known"),
	      "STATUS_MAX_W holds the longest thing the status says");
	CHECK(STATUS_MAX_W + 2 * SCR_RIGHT_MARGIN_MIN <= SCR_W,
	      "the status line still clears both bezels");

	/* --- the font assumption these clearances rest on --- */
	CHECK(FONT_LINE_H == 16,
	      "FONT_LINE_H still matches LV_FONT_DEFAULT_MONTSERRAT_14");

	/*
	 * The hint is one line, and it clears the gauges.
	 *
	 * This used to assert the opposite of its second half: that a SECOND
	 * line would land on the arcs, "so it must ellipsize". That was true
	 * while the arcs began at 44 -- a second line starts at 40 and there
	 * were 4 px between them. The arcs moved to 75 and a second line now
	 * ends at 56, clear by 19, so the claim became false and the check
	 * failed on a layout that had got roomier.
	 *
	 * usage_view.c still ellipsizes, and says why: the slack "is a side
	 * effect of a layout choice and not a promise". So the collision is not
	 * the reason and must not be asserted as one. What is worth holding is
	 * the clearance itself, for the line that is actually drawn -- and the
	 * headroom is reported so a future change that eats it is visible in
	 * the output rather than only in a pass.
	 */
	CHECK(STATUS_Y + FONT_LINE_H < GAUGE_ARC_Y + 4,
	      "a one-line hint clears the gauges");
	{
		int slack = GAUGE_ARC_Y - (STATUS_Y + 2 * FONT_LINE_H);
		char msg[96];

		snprintf(msg, sizeof(msg), "the hint line has %d px of headroom"
			 " before the gauges", slack > 0 ? slack : 0);
		CHECK(STATUS_Y + FONT_LINE_H <= GAUGE_ARC_Y, msg);
	}

	/* --- the status-change popup --- */
	/*
	 * A popup on a full 320x240 panel is always a card ON TOP of
	 * something, so WHAT IT MAY COVER is the design, and these are it:
	 * not the percentage, and not the pip row above it. Those two are
	 * what someone crossing the room reads without stopping, and covering
	 * either of them for five seconds makes the panel worse in exchange
	 * for a sentence nobody asked to read right then.
	 *
	 * Clearing the whole arc is the strictly stronger claim and is what
	 * is asserted -- the percentage sits inside the ring, and the ring's
	 * bottom is the last thing above the band the card takes.
	 */
	CHECK(TOAST_TOP_Y >= GAUGE_ARC_Y + GAUGE_ARC_SZ,
	      "the popup clears the gauges, and so the percentages inside them");
	/*
	 * The page rail stays visible. It is the only thing on the screen
	 * that says WHICH PROVIDER you are looking at, and a card that hid it
	 * would leave the reader unable to tell whose session the sentence is
	 * about -- which is most of the sentence's value on a two-page desk.
	 */
	CHECK(SCR_H - TOAST_BOTTOM_OFF <= SCR_H - RAIL_BOTTOM_OFF - RAIL_H,
	      "the popup clears the page rail, which names the provider");
	CHECK(TOAST_MAX_W + 2 * SCR_RIGHT_MARGIN_MIN <= SCR_W,
	      "the popup clears both bezels");
	/*
	 * One line, with its padding, and the padding is real. TOAST_H is
	 * derived from the band the card is allowed, so a rail or countdown
	 * that moved could squeeze it below a line's height without anybody
	 * noticing until the text was clipped on a desk.
	 */
	CHECK(TOAST_H >= FONT_LINE_H && TOAST_PAD_V > 0,
	      "the popup is tall enough for its line, and pads it");
	/*
	 * The sentences that carry NO project name must fit whole: there is
	 * nothing shorter for them to fall back to. The longest is the
	 * waiting one.
	 */
	CHECK(BUDGET_FITS(TOAST_MAX_W, "A session is waiting for you"),
	      "TOAST_MAX_W is sized for the longest unnamed sentence");
	/* A real project name still fits beside it. */
	CHECK(BUDGET_FITS(TOAST_MAX_W, "LiveClaudeUi is waiting for you"),
	      "an ordinary project name fits too");
	/*
	 * And the longest label the buffer can hold does NOT, which is why
	 * the label ellipsizes rather than wraps -- the same bargain the hint
	 * line makes, asserted here so LV_LABEL_LONG_DOT is not optional.
	 */
	CHECK(!BUDGET_FITS(TOAST_MAX_W,
			   "123456789012345678901234567 is waiting for you"),
	      "a pathological label overruns the card, so it must ellipsize");

	printf(failures ? "\n%d FAILED\n" : "\nall layout checks passed\n",
	       failures);
	return failures ? 1 : 0;
}
