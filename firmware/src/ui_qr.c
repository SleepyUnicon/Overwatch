/* See ui_qr.h for why a board has to show an address at all. */
#include "ui_qr.h"

#include <stdio.h>
#include <string.h>

#include "proto.h"

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

	/*
	 * What is PRINTED is the address a person could type: no scheme, and
	 * no pairing fragment.
	 *
	 * The scheme is 8 characters nobody needs and every browser adds
	 * back. The fragment is worse -- it is 35 more, which turns a line
	 * that fits a 320 px panel into one that does not, to spell out a
	 * 32-character secret nobody is going to transcribe correctly. The
	 * QR carries it; anyone typing instead lands unpaired and has the
	 * bridge on 127.0.0.1 to finish the job.
	 */
	char shown[64];
	const char *from = url;
	size_t n;

	if (strncmp(from, "https://", 8) == 0) {
		from += 8;
	}
	n = strcspn(from, "#");
	if (n >= sizeof(shown)) {
		n = sizeof(shown) - 1;
	}
	memcpy(shown, from, n);
	shown[n] = '\0';
	lv_label_set_text(txt, shown);
	lv_obj_set_style_text_color(txt, lv_color_hex(QR_DARK), 0);
	lv_obj_set_style_text_font(txt, &lv_font_montserrat_14, 0);

	return box;
}

const char *ui_qr_setup_url(void)
{
	/* 8 more than the longest it can be, so a token that somehow grew
	 * truncates here into a code that fails to pair rather than
	 * overflowing. snprintf bounds it either way; the slack is so the
	 * normal case never comes close. */
	static char buf[sizeof(UI_QR_SETUP_URL) + 40];
	const char *tok = proto_pair_token();

	if (!tok || !tok[0]) {
		return UI_QR_SETUP_URL;
	}
	snprintf(buf, sizeof(buf), "%s#t=%s", UI_QR_SETUP_URL, tok);
	return buf;
}
