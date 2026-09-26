/* WCAG contrast for the panel's palettes, computed on the host.
 *
 * Build & run:
 *   cc -lm -I ../../firmware/src host_test.c -o /tmp/ctest && /tmp/ctest
 *
 * A desk gauge is read from across a room, sometimes in daylight, by people
 * whose colour vision varies. "Looks fine on my monitor" is not a check, and
 * the panel has already shipped two colours that failed one: the swipe
 * chevrons sat at 2.76:1 against the background, under the 3:1 minimum for a
 * graphic element -- on the one affordance that exists purely to be noticed --
 * and the two provider colours measured 1.02:1 against EACH OTHER, meaning
 * they were separated by hue alone and carried no signal at all for anyone who
 * could not resolve that hue.
 *
 * Neither was visible in the source, and neither would have been caught by the
 * layout test or by looking at a render. They are arithmetic, so they are
 * checked as arithmetic.
 *
 * BOTH PALETTES, AND READ RATHER THAN COPIED.
 *
 * This file used to carry its own list of eight colours and then grep
 * usage_view.c to prove the two still agreed. That worked until the ten
 * scattered #define COL_* were gathered into firmware/src/ui_theme.c: the
 * defines in usage_view.c became lv_color_hex(ui_theme()->bg) with no value in
 * them, so the grep found nothing, called all eight drifted, and the failure
 * read as an eight-colour disaster rather than "the values moved house".
 *
 * Worse than the noise was what the noise hid. Every rule below had been
 * running against the copy in this file, and that copy was the gauge screen's
 * old dark set -- values which by then existed nowhere in the firmware.
 * Meanwhile the real dark palette had been taken from the widget pages, which
 * had never had the severity ramp fixed, so dark mode shipped a 2.30x inverted
 * band and a green at 0.775 saturation: precisely the two faults this file
 * exists to forbid. A test that duplicates the thing it checks can stay
 * perfectly green about a product that is broken.
 *
 * So there is no copy any more. Both palettes are parsed out of ui_theme.c at
 * run time and both are checked. If the file cannot be read, or a field cannot
 * be found in it, that is a FAILURE and not a skip -- the old version printed
 * SKIP and passed, which is the other half of how this went unnoticed.
 */
#include <ctype.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failures;
#define CHECK(c, m) do { if (!(c)) { printf("FAIL: %s\n", m); failures++; } \
	else { printf("PASS: %s\n", m); } } while (0)

static double chan(unsigned c)
{
	double v = c / 255.0;

	return v <= 0.03928 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4);
}

static double luminance(unsigned rgb)
{
	return 0.2126 * chan((rgb >> 16) & 0xFF) +
	       0.7152 * chan((rgb >> 8) & 0xFF) +
	       0.0722 * chan(rgb & 0xFF);
}

static double contrast(unsigned a, unsigned b)
{
	double la = luminance(a), lb = luminance(b);
	double hi = la > lb ? la : lb, lo = la > lb ? lb : la;

	return (hi + 0.05) / (lo + 0.05);
}

/*
 * HSV saturation, 0..1. Grey is 0.
 *
 * Added because contrast alone said the palette was fine while the panel said
 * the green was grey, and both were telling the truth: #4AB07D cleared 7:1
 * against the background at 0.58 saturation, and 0.58 on an ILI9341 is a
 * grey-green. Luminance is what a colour WEIGHS; saturation is whether it is
 * a colour at all, and this file only ever checked the first one.
 */
static double saturation(unsigned rgb)
{
	unsigned r = (rgb >> 16) & 0xFF, g = (rgb >> 8) & 0xFF, b = rgb & 0xFF;
	unsigned hi = r > g ? (r > b ? r : b) : (g > b ? g : b);
	unsigned lo = r < g ? (r < b ? r : b) : (g < b ? g : b);

	return hi == 0 ? 0.0 : (double)(hi - lo) / (double)hi;
}

/*
 * The colour as the PANEL will actually show it.
 *
 * The display is RGB565: five bits of red, six of green, five of blue. Every
 * number in this file used to be checked at 24-bit precision, against a
 * hardware that has never displayed a 24-bit colour in its life. The drift is
 * small, but "small" is not a thing to assume when the whole point of the file
 * is that eyeballing it was not good enough.
 */
static unsigned as_rgb565(unsigned rgb)
{
	unsigned r = (rgb >> 16) & 0xFF, g = (rgb >> 8) & 0xFF, b = rgb & 0xFF;

	/* Quantise, then expand back the way the panel does: the top bits are
	 * replicated into the bottom ones. */
	r = ((r >> 3) << 3) | (r >> 5);
	g = ((g >> 2) << 2) | (g >> 6);
	b = ((b >> 3) << 3) | (b >> 5);
	return (r << 16) | (g << 8) | b;
}

static unsigned identity(unsigned rgb)
{
	return rgb;
}

/* ----------------------------------------------------- reading the source -- */

/* Only the roles the rules below are about. ui_theme.c carries more. */
#define FIELDS 8
static const char *FIELD[FIELDS] = {
	"bg", "text", "dim", "green", "amber", "red", "grey", "other",
};

struct palette { unsigned v[FIELDS]; int seen[FIELDS]; };

static unsigned at(const struct palette *p, const char *name)
{
	for (int i = 0; i < FIELDS; i++) {
		if (strcmp(FIELD[i], name) == 0) {
			return p->v[i];
		}
	}
	printf("FAIL: no field named %s\n", name);
	failures++;
	return 0;
}

/*
 * Is this line the designated initialiser for `name`?
 *
 * The guard on the character after the name is load-bearing: ".green" is a
 * prefix of ".green_ink" and ui_theme.c carries both, so without it the ink
 * colour is whichever of the two the parser happened to meet first.
 */
static int is_field(const char *line, const char *name)
{
	char needle[32];
	const char *a;

	snprintf(needle, sizeof(needle), ".%s", name);
	a = strstr(line, needle);
	if (!a) {
		return 0;
	}
	a += strlen(needle);
	return !(*a == '_' || isalnum((unsigned char)*a));
}

static FILE *open_theme(void)
{
	FILE *f = fopen("firmware/src/ui_theme.c", "r");

	/* The runner invokes this from the repository root; a person running
	 * the cc line in the header above is sitting in this directory. */
	return f ? f : fopen("../../firmware/src/ui_theme.c", "r");
}

/* Fill `out` from `static const struct ui_palette <which> = { ... }`.
 * Returns 0, or -1 having printed and counted the reason. */
static int load(const char *which, struct palette *out)
{
	char needle[64], line[512];
	FILE *f = open_theme();
	int inside = 0;

	memset(out, 0, sizeof(*out));
	if (!f) {
		printf("FAIL: cannot open firmware/src/ui_theme.c\n");
		failures++;
		return -1;
	}
	snprintf(needle, sizeof(needle), "struct ui_palette %s", which);
	while (fgets(line, sizeof(line), f)) {
		if (!inside) {
			inside = strstr(line, needle) != NULL;
			continue;
		}
		if (line[0] == '}') {
			break;
		}
		for (int i = 0; i < FIELDS; i++) {
			const char *h;

			if (out->seen[i] || !is_field(line, FIELD[i])) {
				continue;
			}
			h = strstr(line, "0x");
			if (!h) {
				continue;
			}
			out->v[i] = (unsigned)strtoul(h, NULL, 16);
			out->seen[i] = 1;
		}
	}
	fclose(f);

	for (int i = 0; i < FIELDS; i++) {
		if (!out->seen[i]) {
			printf("FAIL: the %s palette has no .%s in ui_theme.c\n",
			       which, FIELD[i]);
			failures++;
			return -1;
		}
	}
	return 0;
}

/* ------------------------------------------------------------- the rules -- */

/* Text has to clear 4.5:1; a graphic element 3:1 (WCAG 1.4.3, 1.4.11). */
static const char *TEXT[] = { "text", "dim" };
static const char *GRAPHIC[] = { "green", "amber", "red", "grey", "other" };

/*
 * Every ratio rule, at one bit depth.
 *
 * Run twice per palette: a palette that passes at 24 bits and fails at 16 is a
 * palette that passes here and fails on the desk.
 */
static void ratios(const char *pal, const char *depth,
		   const struct palette *p, unsigned (*q)(unsigned))
{
	unsigned bg = q(at(p, "bg"));
	char msg[192];

	for (unsigned i = 0; i < sizeof(TEXT) / sizeof(TEXT[0]); i++) {
		double r = contrast(q(at(p, TEXT[i])), bg);

		snprintf(msg, sizeof(msg), "%s/%s: %s is readable text"
			 " (%.2f:1 >= 4.5)", pal, depth, TEXT[i], r);
		CHECK(r >= 4.5, msg);
	}
	for (unsigned i = 0; i < sizeof(GRAPHIC) / sizeof(GRAPHIC[0]); i++) {
		double r = contrast(q(at(p, GRAPHIC[i])), bg);

		snprintf(msg, sizeof(msg), "%s/%s: %s is a visible graphic"
			 " (%.2f:1 >= 3)", pal, depth, GRAPHIC[i], r);
		CHECK(r >= 3.0, msg);
	}

	/*
	 * THE SEVERITY BAND MUST STAY FLAT.
	 *
	 * On a dark panel brightness is attention, so a ramp whose middle step
	 * is the brightest inverts its own meaning. That is exactly what
	 * shipped, twice: amber at 11.39:1 against red at 4.95:1, a 2.30x
	 * spread with the merely-getting-close colour shouting over the
	 * critical one -- once on the gauge screen, and then again in the dark
	 * column of ui_theme.c once the palettes were gathered there.
	 *
	 * The fix was not a brighter red. A red luminous enough to outshine a
	 * yellow is a pale salmon and stops reading as red, which is physics
	 * rather than taste. So luminance is held flat and urgency is carried
	 * by saturation and by the arc's own area instead -- and THIS is the
	 * check that keeps someone from "improving" one step later.
	 */
	{
		double g = contrast(q(at(p, "green")), bg);
		double a = contrast(q(at(p, "amber")), bg);
		double r = contrast(q(at(p, "red")), bg);
		double hi = g > a ? (g > r ? g : r) : (a > r ? a : r);
		double lo = g < a ? (g < r ? g : r) : (a < r ? a : r);

		snprintf(msg, sizeof(msg), "%s/%s: the severity band is flat,"
			 " not inverted (%.2fx spread <= 1.35)",
			 pal, depth, hi / lo);
		CHECK(hi / lo <= 1.35, msg);
	}
}

static void check_palette(const char *pal, const struct palette *p)
{
	static const char *severity[] = { "green", "amber", "red" };
	char msg[192];

	ratios(pal, "24-bit", p, identity);
	ratios(pal, "RGB565", p, as_rgb565);

	/*
	 * A SEVERITY COLOUR MUST ACTUALLY BE A COLOUR.
	 *
	 * This is the check that was missing when the user looked at the board
	 * and said the green looked grey. The ramp had been built to carry
	 * urgency in its saturation -- 0.58, 0.66, 0.72 -- which put its
	 * safest, most-often-displayed step nearest to grey, on a panel whose
	 * own gamma takes another bite out of it.
	 *
	 * 0.85 rather than something gentler because the failure was not
	 * marginal: at 0.58 the green read as grey to the naked eye at 60 cm.
	 * There is no reason for a green/amber/red ramp to sit anywhere but
	 * near the top of the range -- flat LUMINANCE is what the band rule
	 * above is protecting, and saturation costs it nothing.
	 */
	for (unsigned i = 0; i < sizeof(severity) / sizeof(severity[0]); i++) {
		double sv = saturation(at(p, severity[i]));

		snprintf(msg, sizeof(msg), "%s: %s is saturated enough to read"
			 " as a colour (%.2f >= 0.85)", pal, severity[i], sv);
		CHECK(sv >= 0.85, msg);
	}
}

int main(void)
{
	struct palette light, dark;
	int got_light, got_dark;

	/*
	 * There are no provider colours to compare any more.
	 *
	 * They used to have to differ from each other in BRIGHTNESS rather than
	 * hue alone -- the check that caught #10A37F, which cleared the
	 * background comfortably and was still invisible as a distinction. One
	 * provider per page retires the whole question: identity is carried by
	 * a name under the brand and a position on the rail, and severity is
	 * the only thing colour is spent on.
	 */
	got_light = load("light", &light) == 0;
	got_dark = load("dark", &dark) == 0;

	if (got_light) {
		check_palette("light", &light);
	}
	if (got_dark) {
		check_palette("dark", &dark);
	}

	/* Two themes, or one of them is not a theme. Cheap, and it would catch
	 * a copy-paste of the whole struct -- which is close to what happened
	 * when the dark column was filled in from the widget pages. */
	if (got_light && got_dark) {
		CHECK(at(&light, "bg") != at(&dark, "bg"),
		      "the two palettes have different grounds");
	}

	if (failures) {
		printf("\n%d FAILED\n", failures);
		return 1;
	}
	printf("\nall contrast checks passed\n");
	return 0;
}
