#ifndef UI_FACE_H
#define UI_FACE_H

#include <lvgl.h>
#include <stdbool.h>

/*
 * The idle face: two eyes and a mouth, DRAWN rather than played.
 *
 * The sleep screen used to play encoded clips -- sleepanim_claude_loop.h and
 * its siblings, around 300 KB each. That is the right shape for one filmed
 * animation and the wrong one for a face with moods: every expression would
 * be another blob, and every combination of expression and gaze another
 * still. Eight moods times five gaze directions is not a clip library, it is
 * a sprite sheet nobody can edit.
 *
 * So the face is five rectangles and a table. An expression is a set of
 * numbers -- eye box, gaze offset, brow, mouth -- and the tick lerps toward
 * whichever is current, which makes every expression blend into every other
 * one for free and costs a few hundred bytes rather than a few hundred KB.
 */
/*
 * The face's ground, which ui_sleep paints the screen with too.
 *
 * Deliberately NOT the theme's background. This screen shows when nobody is
 * looking, often overnight in a dark room, and the light theme's near-white
 * ground at full backlight is a lamp.
 */
#define UI_FACE_GROUND 0x0E1013

enum ui_face_expr {
	FACE_NEUTRAL,
	FACE_HAPPY,
	FACE_ATTENTION,		/* wide eyes, small mouth, and it bobs */
	FACE_ANGRY,
	FACE_SLEEPY,
	FACE_BLINK,
	FACE_LOOK_L,
	FACE_LOOK_R,
	FACE_LOOK_U,
	FACE_LOOK_D,
	FACE__COUNT
};

/* Build the face on `parent`, which it fills. Safe to call again: the old
 * one is dropped first. */
void ui_face_create(lv_obj_t *parent);

/* Aim at an expression. The tick walks there rather than jumping. */
void ui_face_set(enum ui_face_expr e);

/*
 * Advance it. Call about every 30 ms from whatever loop owns the screen.
 *
 * Does two jobs: eases the drawn geometry toward the current expression, and
 * runs the idle scheduler that decides when to blink, glance around and
 * change mood. A caller that only wants a fixed expression can still call
 * this -- ui_face_hold() turns the scheduler off.
 */
void ui_face_tick(void);

/* Stop the scheduler and stay on `e` until told otherwise. */
void ui_face_hold(enum ui_face_expr e);

/* Let the scheduler run again. */
void ui_face_idle(void);

#endif /* UI_FACE_H */
