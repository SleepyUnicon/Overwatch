/*
 * The idle face. See ui_face.h for why it is drawn and not played.
 *
 * Geometry lives in ONE table and nothing else knows a coordinate. Adding a
 * mood is a row; the tick, the blend and the scheduler all pick it up with no
 * further change. That is the whole reason this is a table rather than a
 * switch full of lv_obj_set_size calls.
 */
#include "ui_face.h"

#include <zephyr/kernel.h>

/* The panel, and where the features sit on it. */
#define SCR_W 320
#define SCR_H 240
#define EYE_OFF 42		/* each eye's centre, from the middle */
#define EYE_CY 98
#define MOUTH_CY 158

/* Ink on the unlit ground; the ground itself is in the header, because
 * ui_sleep paints the screen with it before the face is built. */
#define GROUND UI_FACE_GROUND
#define INK 0xF2F4F7

/* One expression. All lengths in pixels; brow_rot in 0.1 degree units. */
struct look {
	int16_t eye_w, eye_h, eye_r;
	int16_t eye_dx, eye_dy;		/* gaze, from the resting centre */
	int16_t brow_dy;		/* 0 parks the brows off-screen */
	int16_t brow_rot;
	int16_t mouth_w, mouth_h, mouth_r, mouth_dy;
	uint8_t speed;			/* 1 slow .. 8 instant */
};

/*
 * The moods.
 *
 * ANGRY is the only one that needs the brows, and it is also the only one
 * that asks the renderer for anything unusual: LVGL rotates them, which needs
 * LV_DRAW_SW_COMPLEX (this build has it). If a future build loses that, the
 * brows land as flat bars lowered over the eyes and the face still reads as
 * stern -- the mood degrades rather than breaking, which is why the brows are
 * separate objects instead of a rotated eye.
 */
static const struct look LOOKS[FACE__COUNT] = {
	[FACE_NEUTRAL]   = { 46, 58, 18,   0,   0,   0,    0,  58, 10, 5,  0, 3 },
	/* Eyes squeezed to happy arcs, sitting high, over a wider mouth. */
	[FACE_HAPPY]     = { 46, 30, 15,   0,  -6,   0,    0,  74, 14, 7,  2, 4 },
	/* Wide open over a small round mouth: the "look at me" face. */
	[FACE_ATTENTION] = { 52, 66, 20,   0,  -2,   0,    0,  30, 18, 9,  0, 6 },
	[FACE_ANGRY]     = { 46, 40, 14,   0,   4, -34,  130,  46,  8, 4,  6, 5 },
	[FACE_SLEEPY]    = { 46, 14,  7,   0,   8,   0,    0,  40,  8, 4,  6, 2 },
	/* Fast, and only the eye height moves -- a blink that slid the mouth
	 * would read as a flinch. */
	[FACE_BLINK]     = { 46,  6,  3,   0,   0,   0,    0,  58, 10, 5,  0, 8 },
	[FACE_LOOK_L]    = { 46, 58, 18, -14,   0,   0,    0,  58, 10, 5,  0, 4 },
	[FACE_LOOK_R]    = { 46, 58, 18,  14,   0,   0,    0,  58, 10, 5,  0, 4 },
	[FACE_LOOK_U]    = { 46, 58, 18,   0, -12,   0,    0,  58, 10, 5,  0, 4 },
	[FACE_LOOK_D]    = { 46, 58, 18,   0,  12,   0,    0,  58, 10, 5,  0, 4 },
};

static lv_obj_t *root, *eye[2], *brow[2], *mouth;
static struct look now_l;		/* what is drawn, mid-blend */
static enum ui_face_expr target = FACE_NEUTRAL;
static bool scheduled = true;
static int64_t next_blink, next_mood;
static int16_t bob;			/* ATTENTION's nudge, in pixels */

/*
 * A PRNG of our own rather than sys_rand32_get().
 *
 * That call needs an entropy source configured, and a face that twitches is
 * not a reason to add one to a build that does not otherwise want it. The
 * face only needs "not the same every time"; xorshift seeded from the clock
 * is more than enough, and it cannot fail to be available.
 */
static uint32_t rng_state;

static uint32_t rnd(void)
{
	rng_state ^= rng_state << 13;
	rng_state ^= rng_state >> 17;
	rng_state ^= rng_state << 5;
	return rng_state;
}

static uint32_t rnd_between(uint32_t lo, uint32_t hi)
{
	return lo + (rnd() % (hi - lo + 1));
}

static lv_obj_t *block(lv_obj_t *parent, uint32_t colour)
{
	lv_obj_t *o = lv_obj_create(parent);

	lv_obj_remove_style_all(o);
	lv_obj_clear_flag(o, LV_OBJ_FLAG_SCROLLABLE);
	/* Not clickable: the tap that wakes the board belongs to the screen
	 * underneath, and a hit test that stops on an eye is a face you
	 * cannot dismiss by poking it in the eye. */
	lv_obj_clear_flag(o, LV_OBJ_FLAG_CLICKABLE);
	lv_obj_set_style_bg_color(o, lv_color_hex(colour), 0);
	lv_obj_set_style_bg_opa(o, LV_OPA_COVER, 0);
	lv_obj_set_style_border_width(o, 0, 0);
	lv_obj_set_style_pad_all(o, 0, 0);
	return o;
}

void ui_face_create(lv_obj_t *parent)
{
	rng_state = (uint32_t)k_uptime_get() | 1u;

	root = block(parent, GROUND);
	lv_obj_set_size(root, SCR_W, SCR_H);
	lv_obj_set_pos(root, 0, 0);

	for (int i = 0; i < 2; i++) {
		/* Brows first, so an eye drawn after covers the parked brow
		 * rather than the other way round. */
		brow[i] = block(root, INK);
		lv_obj_set_size(brow[i], 52, 9);
		lv_obj_set_style_radius(brow[i], 4, 0);
		lv_obj_set_style_transform_pivot_x(brow[i], 26, 0);
		lv_obj_set_style_transform_pivot_y(brow[i], 4, 0);
	}
	for (int i = 0; i < 2; i++) {
		eye[i] = block(root, INK);
	}
	mouth = block(root, INK);

	now_l = LOOKS[FACE_NEUTRAL];
	target = FACE_NEUTRAL;
	scheduled = true;
	bob = 0;
	next_blink = k_uptime_get() + rnd_between(1500, 4000);
	next_mood = k_uptime_get() + rnd_between(5000, 9000);
}

void ui_face_set(enum ui_face_expr e)
{
	if (e >= 0 && e < FACE__COUNT) {
		target = e;
	}
}

void ui_face_hold(enum ui_face_expr e)
{
	scheduled = false;
	ui_face_set(e);
}

void ui_face_idle(void)
{
	scheduled = true;
}

/* Ease one number toward another. Integer, and it always ARRIVES: without
 * the final nudge a difference of 1 would divide to 0 forever and leave the
 * face a pixel short of every expression it ever aimed at. */
static int16_t ease(int16_t cur, int16_t want, uint8_t speed)
{
	int16_t d = want - cur;

	if (d == 0) {
		return cur;
	}
	int16_t step = (int16_t)((d * speed) / 8);

	if (step == 0) {
		step = d > 0 ? 1 : -1;
	}
	return cur + step;
}

static void blend(const struct look *want)
{
	uint8_t s = want->speed;

	now_l.eye_w = ease(now_l.eye_w, want->eye_w, s);
	now_l.eye_h = ease(now_l.eye_h, want->eye_h, s);
	now_l.eye_r = ease(now_l.eye_r, want->eye_r, s);
	now_l.eye_dx = ease(now_l.eye_dx, want->eye_dx, s);
	now_l.eye_dy = ease(now_l.eye_dy, want->eye_dy, s);
	now_l.brow_dy = ease(now_l.brow_dy, want->brow_dy, s);
	now_l.brow_rot = ease(now_l.brow_rot, want->brow_rot, s);
	now_l.mouth_w = ease(now_l.mouth_w, want->mouth_w, s);
	now_l.mouth_h = ease(now_l.mouth_h, want->mouth_h, s);
	now_l.mouth_r = ease(now_l.mouth_r, want->mouth_r, s);
	now_l.mouth_dy = ease(now_l.mouth_dy, want->mouth_dy, s);
}

static void draw(void)
{
	for (int i = 0; i < 2; i++) {
		int sign = i ? 1 : -1;
		int cx = SCR_W / 2 + sign * EYE_OFF + now_l.eye_dx;

		lv_obj_set_size(eye[i], now_l.eye_w, now_l.eye_h);
		lv_obj_set_style_radius(eye[i], now_l.eye_r, 0);
		lv_obj_set_pos(eye[i], cx - now_l.eye_w / 2,
			       EYE_CY + now_l.eye_dy + bob - now_l.eye_h / 2);

		/*
		 * brow_dy of 0 means "no brows", and parking them off the top
		 * is how that is spelt -- not hiding them. A hidden object
		 * that becomes visible arrives at its final position with no
		 * travel, so ANGRY would snap its brows on while every other
		 * feature eased. Parked, they slide down into place with the
		 * rest of the face.
		 */
		lv_obj_set_pos(brow[i], cx - 26,
			       EYE_CY + bob - now_l.eye_h / 2
			       + (now_l.brow_dy ? now_l.brow_dy : -90));
		lv_obj_set_style_transform_rotation(
			brow[i], sign * now_l.brow_rot, 0);
	}
	lv_obj_set_size(mouth, now_l.mouth_w, now_l.mouth_h);
	lv_obj_set_style_radius(mouth, now_l.mouth_r, 0);
	lv_obj_set_pos(mouth, SCR_W / 2 - now_l.mouth_w / 2,
		       MOUTH_CY + now_l.mouth_dy + bob - now_l.mouth_h / 2);
}

/*
 * What it does when left alone.
 *
 * Weighted so the face is mostly calm: it looks around and blinks, and only
 * now and then has a mood. A face that cycled evenly through eight
 * expressions would not read as idle, it would read as a demo reel.
 */
static enum ui_face_expr pick_mood(void)
{
	uint32_t r = rnd() % 100;

	if (r < 34) return FACE_NEUTRAL;
	if (r < 48) return FACE_LOOK_L;
	if (r < 62) return FACE_LOOK_R;
	if (r < 70) return FACE_LOOK_U;
	if (r < 78) return FACE_LOOK_D;
	if (r < 88) return FACE_HAPPY;
	if (r < 95) return FACE_ATTENTION;
	return FACE_ANGRY;
}

void ui_face_tick(void)
{
	if (!root) {
		return;
	}
	int64_t t = k_uptime_get();

	if (scheduled) {
		/*
		 * The blink is a DETOUR, not a mood: it aims at FACE_BLINK
		 * for a moment and then puts the mood back. Letting it become
		 * the target would lose whatever the face was doing, so a
		 * blink during ANGRY would leave it neutral afterwards.
		 */
		static enum ui_face_expr before_blink = FACE_NEUTRAL;
		static int64_t blink_until;

		if (blink_until && t >= blink_until) {
			blink_until = 0;
			target = before_blink;
		} else if (!blink_until && t >= next_blink) {
			before_blink = target;
			target = FACE_BLINK;
			blink_until = t + 110;
			/* Twice in quick succession sometimes, the way people
			 * actually blink. */
			next_blink = t + (rnd() % 5 == 0
					  ? rnd_between(260, 420)
					  : rnd_between(2600, 6500));
		}

		if (!blink_until && t >= next_mood) {
			target = pick_mood();
			next_mood = t + rnd_between(4000, 11000);
		}
	}

	/* ATTENTION bobs. It is the one mood that is asking to be noticed,
	 * and a face that only changes shape is easy to miss out of the
	 * corner of an eye; movement is not. */
	if (target == FACE_ATTENTION) {
		bob = ((t / 140) % 2) ? -3 : 3;
	} else {
		bob = ease(bob, 0, 3);
	}

	blend(&LOOKS[target]);
	draw();
}
