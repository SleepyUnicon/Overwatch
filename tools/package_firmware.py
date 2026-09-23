#!/usr/bin/env python3
"""Merge a built tree into ONE file a kit builder can flash at offset 0.

Why this exists: `tools/release.sh` publishes `blink-fw.bin`, which is the app
slot alone. That is right for the feed it serves -- an OTA lands in slot 1 of a
board whose MCUboot is already there. It is useless to somebody holding a chip
that has never been programmed, which is every kit.

A blank ESP32 needs the bootloader at 0x1000 and the app at 0x20000. Handing a
kit builder two files and two offsets invites transposing them, and a board
flashed with the app at 0x1000 is a board that does not boot and gives no clue
why. One file at one offset removes the class of mistake.

Two things this does NOT do, deliberately:

  * Build. It merges what is already in the build directory, so what ships is
    the tree you tested. Pass --build-dir at whatever you burned from.
  * Trust a stale zephyr.confirmed.bin. It re-signs every time, for the reason
    tools/burn.sh:201 spells out at length: zephyr.signed.bin says "boot once",
    and a board with no daemon never becomes healthy, so it reverts 90 s after
    this script says it succeeded. On a kit that looks like a crash loop, and
    the builder has no way to tell it from bad soldering.
"""

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MCUBOOT_OFFSET = "0x1000"
APP_OFFSET = "0x20000"          # agrees with pc/ota.py:142 and tools/burn.sh:272


def _version():
    """The version this tree builds, read from the same place release.sh reads."""
    path = os.path.join(ROOT, "firmware", "src", "version.h")
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#define BLINK_FW_VERSION"):
                return line.split('"')[1]
    raise SystemExit("no BLINK_FW_VERSION in %s" % path)


def _confirmed_app(build_dir, python):
    """Re-sign a confirmed app image and return its path.

    Removed first so a failure cannot leave the previous run's file behind for
    the merge to pick up silently -- the one outcome worse than stopping here
    is shipping an image that reverts in the field.
    """
    out = os.path.join(build_dir, "zephyr.confirmed.bin")
    try:
        os.unlink(out)
    except OSError:
        pass
    cmd = [python, os.path.join(ROOT, "tools", "sign_confirmed.py"),
           "--build-dir", build_dir, "--out", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr or r.stdout or "")
        raise SystemExit("sign_confirmed.py failed; refusing to ship a "
                         "revert-at-90s image")
    if not os.path.exists(out):
        raise SystemExit("sign_confirmed.py reported success but wrote no %s"
                         % out)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build-dir",
                    default=os.path.join(ROOT, "firmware", "build-sb"),
                    help="sysbuild directory to merge (default: firmware/build-sb)")
    ap.add_argument("--out", help="output file (default: dist/overwatch-<ver>.bin)")
    ap.add_argument("--python", default=sys.executable,
                    help="interpreter that has imgtool, for sign_confirmed.py")
    args = ap.parse_args(argv)

    build = os.path.abspath(args.build_dir)
    mcuboot = os.path.join(build, "mcuboot", "zephyr", "zephyr.bin")
    if not os.path.exists(mcuboot):
        raise SystemExit("no bootloader at %s -- build with --sysbuild first"
                         % mcuboot)

    app = _confirmed_app(build, args.python)

    ver = _version()
    out = args.out or os.path.join(ROOT, "dist", "overwatch-%s.bin" % ver)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # esptool 5 accepts `merge_bin` and `merge-bin` both; the hyphen is what
    # 5.x documents. This is a maintainer-side tool run from the project venv,
    # so it can assume 5.x. pc/ota.py cannot -- it runs on customer machines
    # against whatever esptool is there -- which is why it keeps the
    # underscore `write_flash` that 4.x and 5.x agree on.
    cmd = [args.python, "-m", "esptool", "--chip", "esp32", "merge-bin",
           "-o", out, "--flash-mode", "dio", "--flash-size", "4MB",
           MCUBOOT_OFFSET, mcuboot, APP_OFFSET, app]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr or r.stdout or "")
        raise SystemExit("merge-bin failed")

    print("%s  (%.2f MB, flash at 0x0, firmware %s)"
          % (out, os.path.getsize(out) / 1e6, ver))
    return 0


if __name__ == "__main__":
    sys.exit(main())
