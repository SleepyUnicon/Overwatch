# The car-dial UI, parked

A twin-scale speedometer that replaced the two arcs: outer yellow-green scale
for the 5-hour session, inner red for the week, two needles, a green LCD
reading Hello / Mark.

It worked on hardware - colours, needles, the lot - and was set aside on
2026-09-23 because it did not read the way the mockup promised at 2.8 inches.
Kept because the hard parts are solved and none of them are obvious:

- `dial_face.py` draws the artwork at 6x and downsamples, so the ticks and
  numerals are anti-aliased in a way the ESP32 cannot draw live.
- `encode_dial.py` turns that into an LVGL image descriptor header.
- **Image data is LITTLE-endian**, even though CONFIG_LV_COLOR_16_SWAP=y. The
  swap describes the display buffer; descriptors are read before it. Getting
  this wrong renders 0x0E1116 as a flat salmon.
- **LV_ATTRIBUTE_MEM_ALIGN is defined EMPTY** by LVGL's default config, so it
  does nothing. Arrays need an explicit `__attribute__((aligned(64)))` or
  lv_draw_buf_init warns once per draw, forever, down the same UART the
  daemon's protocol uses.

To revive: regenerate the header, re-apply the usage_view.c changes (needle
in place of arc, face image behind it), and add CONFIG_LV_USE_IMAGE=y.
