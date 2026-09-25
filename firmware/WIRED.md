# Running this firmware on a discrete ESP32 + panel

Verified working on hardware, 2026-09-23: ESP32 DevKitC (WROOM-32, CP2102,
USB-C) and a standalone KMRTM28028-SPI 2.8" module on 13 Dupont jumpers,
instead of the ESP32-2432S028 "CYD" this firmware was written for.

Screen draws, colours correct, touch lands on target, daemon connects,
gauges render.

## Wiring

The CYD pin map is UNCHANGED. The panel is wired to the pins the firmware
already expects, so nothing in `boards/esp32_devkitc_esp32_procpu.overlay`
needed touching. 13 wires:

| Module pin  | ESP32    | |
|---|---|---|
| VCC         | 3V3      | |
| GND         | GND      | |
| RESET       | EN       | resets with the board |
| CS          | GPIO 15  | |
| D/C         | GPIO 2   | |
| SDI (MOSI)  | GPIO 13  | |
| SCK         | GPIO 14  | |
| LED         | GPIO 21  | no transistor - see backlight note |
| SDO (MISO)  | **not connected** | GPIO 12 straps flash voltage |
| T_CLK       | GPIO 25  | |
| T_CS        | GPIO 33  | |
| T_DIN       | GPIO 32  | |
| T_OUT       | GPIO 39  | printed `VN` on the DevKitC |
| T_IRQ       | GPIO 36  | printed `VP` on the DevKitC |

**`SDO` stays off.** It would land on GPIO 12, which the ESP32 samples at
reset to choose its flash voltage. The CYD's panel never drives MISO, which
is why the display is declared `write-only` and the CYD gets away with wiring
it; a module that does drive it stops the board booting, and the wire you were
told to fit is the last thing you would suspect.

**`T_OUT`, not `T_DO`.** Both spellings exist on these modules.

**`VP` / `VN`, not 36 / 39.** The DevKitC silkscreen uses the old Espressif
names, so those two pins are not where you will look for them.

## Build

```sh
export OVERWATCH_ZEPHYR="$HOME/zephyrproject"     # see the zsh note below
cd firmware
west build -p always --sysbuild -d build-sb -b esp32_devkitc/esp32/procpu . -- \
  -DSB_CONFIG_BOOTLOADER_MCUBOOT=y -DUSE_CCACHE=0 \
  -DEXTRA_DTC_OVERLAY_FILE=boards/wired.overlay \
  -DEXTRA_CONF_FILE=wired.conf \
  -DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE="\"$HOME/.overwatch/ota_signing_key_p256.pem\""
```

Two files carry every difference from a CYD build:

- **`boards/wired.overlay`** - drops the panel SPI clock from 32 MHz to 10.
  32 was measured on the CYD's own PCB; a 20 cm jumper has no ground plane
  under it and the panel never latches its init.
- **`boards/wired.overlay`** also toggles the touch inversion - see below.
- **`wired.conf`** - `CONFIG_OVERWATCH_PANEL_PILOT=y`. Measured here: with the
  stock production correction (MADCTL MV|MY, BGR cleared) this module rendered
  MIRRORED, and turning the board 180 degrees did not undo it, which rules out
  rotation. The pilot path compiles that correction away and leaves the
  driver's own MADCTL - which is right for this module in BOTH respects, mirror
  and colour order. The arcs render blue, so red and blue are not swapped.

## Flash

The build's `zephyr.signed.bin` is signed but NOT confirmed - flashing it
directly gives a board that reverts at 90 s and looks like a crash loop. Use
the repo's own tool:

```sh
python3 ../tools/sign_confirmed.py --build-dir build-sb --out build-sb/zephyr.confirmed.bin
esptool.py --port /dev/cu.usbserial-0001 --baud 115200 \
  write_flash 0x1000 build-sb/mcuboot/zephyr/zephyr.bin \
              0x20000 build-sb/zephyr.confirmed.bin
```

MCUboot only needs writing once; later app-only flashes are just the 0x20000
half.

## Two things that bite on macOS

**`tools/lib_zephyr.sh` fails under zsh.** It searches with `$HOME/zephyr-v*`,
and zsh makes an unmatched glob a fatal error where bash leaves it literal.
macOS has defaulted to zsh since Catalina. `export OVERWATCH_ZEPHYR` to skip the
search. (Upstream bug - a `setopt nullglob` or a `set -o noglob` guard would
fix it.)

**`west sdk install` cannot bootstrap.** It lists installed SDKs before
installing one, and with none installed the lookup aborts the command. Install
the SDK manually from the `_minimal` bundle and run `./setup.sh -t
xtensa-espressif_esp32_zephyr-elf -c`; the `-c` writes the registration the
command was looking for.

## Touch

Both axes are inverted relative to the CYD, and `wired.overlay` corrects it by
deleting the board overlay's `invert-x` and adding `invert-y`.

Diagnosed with the touch echo that ships enabled (`ui_touchfx.c` draws a white
circle where a press registers): a tap on the top-left bloomed bottom-right,
top-right bloomed bottom-left. Diagonally opposite on both is a 180 degree
turn of the touch plane, not a scale or offset error - which is why toggling
two flags fixed it and no recalibration was needed.

The cause is this file's own panel change. The CYD overlay's `invert-x` was
fitted against the PRODUCTION panel's MADCTL (MV|MY); `CONFIG_OVERWATCH_PANEL_PILOT`
leaves the driver's own (MV), so the display's row order flipped and the
mapping solved against the old one stopped holding. Anyone turning the pilot
flag on for a different module should expect to toggle these two as well.

The overlay warns that the invert flags apply BEFORE the ROTATED_90
compensation, so flipping one from on-screen symptoms misleads. Flipping BOTH
does not: it is a 180 degree rotation, and rotations commute, so it lands the
same either side of the compensation.

**The four ADC numbers were NOT refitted.** `min-x` / `max-x` / `min-y` /
`max-y` in the CYD overlay were measured on one specific unit, and this module
happens to land close enough that taps hit their targets. If a future panel
does not, `firmware/trace.conf` builds with `CONFIG_OVERWATCH_TOUCH_TRACE`, which
dumps every raw XPT2046 report as CSV over the console; `tools/touch_trace.py`
captures it and `tools/touch_trace_analyze.py` reduces it.

## Running the daemon from source

The packaged installer (`overwatch install`) expects the frozen binary. Built from
source, the two halves are installed by hand:

```sh
mkdir -p ~/.overwatch/bin
cp tools/overwatch-statusline.sh tools/overwatch-hook.sh ~/.overwatch/bin/
chmod +x ~/.overwatch/bin/overwatch-*.sh

cp ~/.claude/settings.json ~/.claude/settings.json.before-overwatch   # back up FIRST

python3 -c "
import sys, os; sys.path.insert(0, '.')
from pc import install_statusline, install_hooks
S = os.path.expanduser('~/.claude/settings.json')
print(install_statusline.install(S, os.path.expanduser('~/.overwatch/bin/overwatch-statusline.sh')))
print(install_hooks.install(S, os.path.expanduser('~/.overwatch/bin/overwatch-hook.sh')))
"
```

Use the repo's installer functions rather than hand-editing the JSON: they
chain an existing statusline instead of replacing it, and touch no key but
their own. Adds `statusLine` and ten `hooks` events. `uninstall()` on the same
two modules reverses it.

The shims are POSIX sh and need nothing else - they write into `~/.overwatch/` and
pass the payload through unchanged. Copying them to `~/.overwatch/bin` rather than
pointing at the repo means moving the checkout does not break the hooks.

**Settings are read at session start**, so a Claude Code session that was
already open when this ran will not fire them. Start a new one.

Then the daemon, in a terminal of its own:

```sh
source ~/zephyrproject/.venv/bin/activate
python3 claude_usage_bridge.py --port /dev/cu.usbserial-0001
```

**Ctrl-C to stop it, never Ctrl-Z.** Suspending leaves the process alive and
still holding the serial port, so the next daemon finds the board taken and
waits forever - which reads as a hang rather than as the mistake it is.

## Not yet verified

- **The backlight.** It is driven straight off GPIO 21 with no transistor.
  Working, but out of the pin's rated current; watch for it running warm.
- **OTA.** Never exercised on this hardware. The board is on its own signing
  key, so it will not take upstream's releases by design.
