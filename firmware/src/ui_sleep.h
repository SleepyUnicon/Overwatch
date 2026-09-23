#ifndef UI_SLEEP_H
#define UI_SLEEP_H

#include <stdbool.h>

/*
 * Close the eyes, doze until `awake()` says otherwise, open them. Blocks for
 * the whole of it, servicing the daemon protocol between frames, and returns
 * with the previous screen restored. A tap while dozing shows the dashboard
 * with `peek_note` under it for ten seconds.
 *
 * `awake` is the caller's, not this file's, because there are two reasons to
 * doze and they end differently. A computer that went silent wakes when it
 * speaks. A computer whose daemon never stopped talking but has had nothing
 * new to say for hours cannot use that test at all -- it is true the whole
 * time it is dozing -- so it asks about the age of the reading instead. This
 * function used to hard-code the first test, which is why the second kind of
 * sleep could not be built on it.
 *
 * Must not be NULL: a doze with no way out is a bricked panel.
 */
void ui_sleep_run(bool (*awake)(void), const char *peek_note);

/*
 * The face as a PAGE rather than as a doze: play it, and come back on the
 * first touch anywhere.
 *
 * Its own entry point because the two uses want opposite things from a tap.
 * Dozing treats a tap as "show me the dashboard for ten seconds and carry on
 * sleeping", which is right when the board dozed off by itself and you want a
 * glance without ending it. Here the user ASKED for the face, so the only
 * thing a tap can sensibly mean is "done, take me back" -- and if it did not
 * mean that there would be no way out at all, which is what shipping
 * ui_sleep_run(NULL, NULL) did.
 */
void ui_sleep_show_face(void);

#endif /* UI_SLEEP_H */
