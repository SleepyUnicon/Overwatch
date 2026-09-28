#!/bin/sh
# Assemble the assembly kit: everything needed to build one unit for somebody
# who is not you.
#
#   tools/make_kit.sh
#
# Output is dist/overwatch-<version>/ and a zip beside it. Version comes from
# firmware/src/version.h, the same place tools/release.sh reads it.
#
# WHY THIS SCRIPT EXISTS
#
# The first kit was assembled by hand into dist/. Everything in it that had
# been WRITTEN rather than built -- the four text files that tell a builder
# what to do, and the two documents -- was therefore sitting in a directory
# that .gitignore excludes and that tools/build_binary.sh writes into. One
# `rm -rf dist` and the words were gone, with nothing to restore them from.
#
# So the sources live in docs/print/ and this rebuilds the kit around them.
# The version and the firmware checksum are substituted here rather than typed
# into the text, because those are the two things that go stale between
# releases and a stale checksum is worse than none.
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
SRC="$ROOT/docs/print"
VER=$(sed -n 's/#define OVERWATCH_FW_VERSION "\(.*\)"/\1/p' \
	"$ROOT/firmware/src/version.h")
[ -n "$VER" ] || { echo "FATAL: no version in firmware/src/version.h" >&2; exit 1; }

BIN="$ROOT/dist/overwatch-$VER.bin"
[ -f "$BIN" ] || {
	echo "FATAL: no merged firmware image at $BIN" >&2
	echo "  That file is the whole point of the kit -- it is the one that" >&2
	echo "  works on a blank board, unlike the overwatch-fw.bin a release" >&2
	echo "  publishes. Build it first:" >&2
	echo "    python3 tools/package_firmware.py" >&2
	exit 1
}

KIT="$ROOT/dist/overwatch-kit-$VER"
rm -rf "$KIT"
mkdir -p "$KIT/1-print-the-case/upright-frame" \
	 "$KIT/1-print-the-case/wedge" \
	 "$KIT/2-flash-the-board" \
	 "$KIT/3-hand-it-over"

SHA=$(cd "$(dirname "$BIN")" && shasum -a 256 "$(basename "$BIN")" | cut -d' ' -f1)

# @VERSION@ and @SHA256@ out of the committed sources and into the copy.
fill() {
	sed -e "s/@VERSION@/$VER/g" -e "s/@SHA256@/$SHA/g" "$1" > "$2"
}

# ---------------------------------------------------------------- the parts
cp "$ROOT/case/front_bezel.stl" "$ROOT/case/back_tray.stl" \
	"$KIT/1-print-the-case/upright-frame/"
cp "$ROOT/case/README.md" "$KIT/1-print-the-case/upright-frame/notes.md"
cp "$ROOT/case/v2/v2_shell.stl" "$ROOT/case/v2/v2_base.stl" \
	"$KIT/1-print-the-case/wedge/"
cp "$ROOT/case/v2/README.md" "$KIT/1-print-the-case/wedge/notes.md"

cp "$BIN" "$KIT/2-flash-the-board/"
# Written from inside the directory so the path in it is bare and
# `shasum -c SHA256SUMS` works where a builder actually stands. Generated
# elsewhere and edited down, it lost its hash and checked nothing.
( cd "$KIT/2-flash-the-board" && shasum -a 256 "overwatch-$VER.bin" > SHA256SUMS )
cp "$ROOT/firmware/WIRED.md" "$KIT/2-flash-the-board/wiring-discrete-esp32-only.md"

fill "$SRC/kit/READ-ME-FIRST.txt"     "$KIT/READ-ME-FIRST.txt"
fill "$SRC/kit/WHICH-DESIGN.txt"      "$KIT/1-print-the-case/WHICH-DESIGN.txt"
fill "$SRC/kit/HOW-TO-FLASH.txt"      "$KIT/2-flash-the-board/HOW-TO-FLASH.txt"
fill "$SRC/kit/install-commands.txt"  "$KIT/3-hand-it-over/install-commands.txt"

# ------------------------------------------------------------------- the PDFs
#
# Rendered with headless Chrome, which honours @page but not CSS margin boxes;
# that is why the documents carry no running page numbers. WeasyPrint does both
# and is the better tool, but it needs pango and cairo, which a Mac does not
# have by default -- and a kit that cannot be built on a stock machine is worse
# than one without page numbers.
#
# A machine with no Chrome still gets a complete, usable kit: every instruction
# also exists as plain text beside the PDF it renders. So this warns and
# continues rather than failing.
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
render() {
	src=$1
	out=$2
	tmp="${TMPDIR:-/tmp}/overwatch-kit-render"

	rm -rf "$tmp"
	mkdir -p "$tmp"
	# Flat, so the stylesheet is simply "style.css" from every document and
	# no relative path has to survive being moved into the kit tree.
	fill "$src" "$tmp/doc.html"
	cp "$SRC/style.css" "$tmp/style.css"
	# Chrome writes the PDF and then does not exit. Backgrounded and killed,
	# because there is nothing else to wait for and a release script that
	# hangs is worse than one that is slightly rude.
	"$CHROME" --headless --disable-gpu --no-first-run \
		--user-data-dir="$tmp/profile" --no-pdf-header-footer \
		--print-to-pdf="$tmp/doc.pdf" "file://$tmp/doc.html" \
		>/dev/null 2>&1 &
	pid=$!
	i=0
	while [ $i -lt 40 ]; do
		[ -s "$tmp/doc.pdf" ] && break
		sleep 1
		i=$((i + 1))
	done
	sleep 2
	kill "$pid" 2>/dev/null || true
	# Wait for it to actually go. Chrome keeps writing its profile for a
	# moment after the signal, and removing the directory underneath it
	# printed three "Directory not empty" lines per document.
	wait "$pid" 2>/dev/null || true
	ok=1
	if [ -s "$tmp/doc.pdf" ]; then
		cp "$tmp/doc.pdf" "$out"
		ok=0
	fi
	rm -rf "$tmp" 2>/dev/null || true
	return "$ok"
}

if [ -x "$CHROME" ]; then
	render "$SRC/kit/START-HERE.html"   "$KIT/START-HERE.pdf" \
		|| echo "WARNING: START-HERE.pdf did not render" >&2
	render "$SRC/kit/INSTALL-CARD.html" "$KIT/3-hand-it-over/INSTALL-CARD.pdf" \
		|| echo "WARNING: INSTALL-CARD.pdf did not render" >&2
	render "$SRC/manual.html"           "$KIT/Overwatch-Manual.pdf" \
		|| echo "WARNING: Overwatch-Manual.pdf did not render" >&2
else
	echo "No Chrome at $CHROME -- the kit is complete but has no PDFs." >&2
	echo "  Every instruction in them is also in the .txt files. Set CHROME" >&2
	echo "  to a Chromium binary to render them." >&2
fi

# ------------------------------------------------------------------- the zip
( cd "$ROOT/dist" && rm -f "overwatch-kit-$VER.zip" \
	&& zip -qr "overwatch-kit-$VER.zip" "overwatch-kit-$VER" )

echo "dist/overwatch-kit-$VER/          firmware $VER, sha256 $(echo "$SHA" | cut -c1-8)..."
echo "dist/overwatch-kit-$VER.zip       $(du -h "$ROOT/dist/overwatch-kit-$VER.zip" | cut -f1)"
