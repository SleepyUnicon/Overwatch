#include "ui_theme.h"

#include "cfg_store.h"

/*
 * The measured light set. Each ratio is against this palette's own bg, taken
 * from usage_view.c where they were checked rather than chosen.
 */
static const struct ui_palette light = {
	.bg        = 0xFFFFFF,	/* plain white ground */
	.panel     = 0xF1F3F6,	/* cards, barely off the ground */
	.track     = 0xDCE0E6,	/* the unfilled arc */
	.text      = 0x111418,	/* near-black ink, 18.5:1 */
	.dim       = 0x5C6470,	/* secondary ink, 5.98:1 */

	.green     = 0x0A7A34,	/* 5.46:1 */
	.amber     = 0x8A5A00,	/* 5.93:1 */
	.red       = 0xC11A00,	/* 6.15:1 */
	.grey      = 0x78808C,	/* 3.99:1 -- "no data", never load-bearing */
	.other     = 0x4387DF,	/* anything else: a cool blue */

	.line      = 0xE2E6EB,
	.danger_bg = 0xFDECEA,	/* a red TINT; the ink on it stays COL_RED */
	.danger_bd = 0xE6A69E,

	.green_ink = 0x06210F,
	.amber_ink = 0x1A1405,
	.red_ink   = 0x2A0A06,
};

/*
 * The dark set the widget pages shipped with. The severity colours are the
 * brighter variants: on 0x0E1116 the light set's 0x0A7A34 is nearly invisible,
 * which is the whole reason two sets exist rather than one plus a tint.
 */
static const struct ui_palette dark = {
	.bg        = 0x0E1116,
	.panel     = 0x161A20,
	.track     = 0x272C34,
	.text      = 0xE6E8EB,
	.dim       = 0x8A9199,

	.green     = 0x2ECC71,
	.amber     = 0xF1C40F,
	.red       = 0xE74C3C,
	.grey      = 0x8A9199,
	.other     = 0x4387DF,

	.line      = 0x20252D,
	.danger_bg = 0x1E1412,
	.danger_bd = 0x7A2B23,

	.green_ink = 0x06210F,
	.amber_ink = 0x1A1405,
	.red_ink   = 0x2A0A06,
};

static bool is_dark;
static bool rebuild_wanted;

const struct ui_palette *ui_theme(void)
{
	return is_dark ? &dark : &light;
}

bool ui_theme_is_dark(void)
{
	return is_dark;
}

void ui_theme_init(void)
{
	is_dark = cfg_get_dark();
	rebuild_wanted = false;
}

bool ui_theme_set_dark(bool want)
{
	if (want == is_dark) {
		return false;
	}
	is_dark = want;
	/*
	 * Persisted before the repaint, not after. The repaint is the slow
	 * half and the one that can be interrupted by an unplug; a board that
	 * came back on the old theme after the user watched it change would
	 * be reporting a write that did not happen.
	 */
	(void)cfg_set_dark(want);
	rebuild_wanted = true;
	return true;
}

bool ui_theme_rebuild_pending(void)
{
	return rebuild_wanted;
}

void ui_theme_rebuild_clear(void)
{
	rebuild_wanted = false;
}
