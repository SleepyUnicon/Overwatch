#ifndef UI_QR_H
#define UI_QR_H

#include <lvgl.h>

/*
 * Where somebody holding a board is sent.
 *
 * The board cannot send them itself. It is an ESP32 behind a CH340, so to a
 * computer it is a serial port and nothing else: it cannot autorun, cannot
 * present as a keyboard and type a URL, cannot mount a drive with a
 * shortcut on it. Those need native USB, which this silicon does not have.
 *
 * So the board shows the address and a person carries it across. That is the
 * whole reason this file exists, and it is why the QR is on the screen a
 * brand-new board sits at rather than tucked inside settings.
 */
#define UI_QR_SETUP_URL "https://sleepyunicon.github.io/Overwatch/"

/*
 * A QR with its address written underneath, centred on `parent`.
 *
 * The text is not decoration. A QR is unreadable to anyone without a phone
 * to hand, and the one person guaranteed to be looking at this screen is
 * sitting at the computer they are about to install on -- they can type it.
 *
 * `size` is the QR's side in pixels. Returns the container, so a caller can
 * position it; it is laid out already.
 */
lv_obj_t *ui_qr_panel(lv_obj_t *parent, const char *url, int size);

#endif /* UI_QR_H */
