/* See ui_qr.h for why a board has to show an address at all. */
#include "ui_qr.h"

#include <string.h>

/*
 * Dark on light, always, whatever the theme is doing.
 *
 * A QR is read by a camera looking for contrast in a known polarity, and
 * light-on-dark ("inverted") codes are refused outright by plenty of
 * scanners -- including, for years, the iOS camera. A code the theme made
 * pretty and unscannable would fail in exactly the situation it exists for:
 * a stranger holding a phone at a board they have never used.
 */
#define QR_DARK 0x101418
#define QR_LIGHT 0xFFFFFF

/* The quiet zone the spec asks for, in pixels rather than modules. Without
 * it the code runs to the edge of its own widget and a scanner has nothing
 * to lock onto. lv_qrcode draws the light ground but not the margin. */
#define QUIET 8

lv_obj_t *ui_qr_panel(lv_obj_t *parent, const char *url, int size)
{
	lv_obj_t *box = lv_obj_create(parent);

	lv_obj_remove_style_all(box);
	lv_obj_clear_flag(box, LV_OBJ_FLAG_SCROLLABLE);
	lv_obj_set_size(box, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
	lv_obj_set_flex_flow(box, LV_FLEX_FLOW_COLUMN);
	lv_obj_set_flex_align(box, LV_FLEX_ALIGN_CENTER,
			      LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
	lv_obj_set_style_pad_row(box, 8, 0);

	lv_obj_t *pad = lv_obj_create(box);

	lv_obj_remove_style_all(pad);
	lv_obj_clear_flag(pad, LV_OBJ_FLAG_SCROLLABLE);
	lv_obj_set_size(pad, size + 2 * QUIET, size + 2 * QUIET);
	lv_obj_set_style_bg_color(pad, lv_color_hex(QR_LIGHT), 0);
	lv_obj_set_style_bg_opa(pad, LV_OPA_COVER, 0);
	lv_obj_set_style_radius(pad, 4, 0);

	lv_obj_t *qr = lv_qrcode_create(pad);

	lv_qrcode_set_size(qr, size);
	lv_qrcode_set_dark_color(qr, lv_color_hex(QR_DARK));
	lv_qrcode_set_light_color(qr, lv_color_hex(QR_LIGHT));
	lv_qrcode_update(qr, url, strlen(url));
	lv_obj_center(qr);

	lv_obj_t *txt = lv_label_create(box);

	/* Without the scheme. It is 8 characters of "https://" that nobody
	 * needs to type and that push the rest below a readable size on a
	 * 320 px panel -- every browser adds it back. */
	const char *shown = url;

	if (strncmp(shown, "https://", 8) == 0) {
		shown += 8;
	}
	lv_label_set_text(txt, shown);
	lv_obj_set_style_text_color(txt, lv_color_hex(QR_DARK), 0);
	lv_obj_set_style_text_font(txt, &lv_font_montserrat_14, 0);

	return box;
}
