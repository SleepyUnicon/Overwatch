#!/bin/sh
# Sign a macOS build with a Developer ID, so it can be notarised.
#
#   tools/macos_sign.sh [build-dir]       (default: dist/overwatch)
#
# Credentials come from the environment, and their ABSENCE is a supported
# state, not an error: with no identity this reports what that means and exits
# 0. That is what every build does today, and what CI does on every push --
# which is the point, because a signing script that only ever runs on release
# day is a signing script nobody has tested.
#
#   OVERWATCH_SIGN_IDENTITY      e.g. "Developer ID Application: A Name (TEAMID)"
#   OVERWATCH_SIGN_KEYCHAIN      optional: keychain holding it
#   OVERWATCH_SIGN_ENTITLEMENTS  optional: see "library validation" below
#
# WHY THIS IS NOT PART OF build_binary.sh
#
# Signing needs secrets and applies to one platform. build_binary.sh runs on a
# developer's laptop a dozen times a day and must not want either.
#
# ------------------------------------------------------------------ hardened
#
# Notarisation REQUIRES the hardened runtime (`--options runtime`) and a secure
# timestamp. The hardened runtime turns on library validation, which refuses to
# load any library whose Team ID differs from the process's.
#
# Measured on this project, 2026-09-26: signing all 53 Mach-O files ad-hoc with
# --options runtime produces a binary that does not start at all --
#
#   Failed to load Python shared library '.../_internal/Python': ... not valid
#   for use in process: mapping process and mapped file (non-platform) have
#   different Team IDs
#
# -- because an ad-hoc signature carries NO Team ID, so nothing can match
# anything. That is why the hardened runtime is set only in the signed path
# below and never in the ad-hoc one: on an unsigned build it buys nothing
# (notarisation is the only thing that asks for it) and costs a binary that
# cannot run.
#
# With a real Developer ID every file here is signed by one identity and so
# carries one Team ID, which is what library validation wants. That has NOT
# been observed on this project yet -- it needs a paid Apple account, which is
# the one part of this that cannot be rehearsed -- so the self-test at the
# bottom runs the binary it just signed and refuses to pass it on if it does
# not start, and names the fix if the failure is this one.
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
DIR="${1:-$ROOT/dist/overwatch}"

[ -d "$DIR" ] || { echo "no build at $DIR" >&2; exit 1; }
[ "$(uname -s)" = "Darwin" ] || { echo "not macOS; nothing to sign"; exit 0; }

EXE="$DIR/overwatch"
[ -f "$EXE" ] || { echo "FATAL: no executable at $EXE" >&2; exit 1; }

# ------------------------------------------------------------------ unsigned
#
# Deliberately exit 0. An unsigned build is the shipping build today and the
# curl install line is unaffected by it (curl sets no quarantine flag, so
# Gatekeeper is never consulted -- see docs/notarisation.md). Failing here
# would only mean nobody could build on a machine without the certificate.
if [ -z "${OVERWATCH_SIGN_IDENTITY:-}" ]; then
	echo "OVERWATCH_SIGN_IDENTITY is not set: leaving this build unsigned."
	echo "  Gatekeeper will refuse a browser download of it until it is"
	echo "  notarised. The curl install line is unaffected. See"
	echo "  docs/notarisation.md."
	# PyInstaller ad-hoc signs its own arm64 output, and a build where even
	# that is missing will not run on Apple Silicon at all. Cheap to check,
	# and the only signature assertion available without a certificate.
	if ! codesign --verify --verbose=0 "$EXE" 2>/dev/null; then
		echo "FATAL: not even an ad-hoc signature on $EXE" >&2
		echo "  Apple Silicon refuses to execute an unsigned Mach-O." >&2
		exit 1
	fi
	echo "  ad-hoc signature present and valid."
	exit 0
fi

ID="$OVERWATCH_SIGN_IDENTITY"

# --keychain, as a single argument pair we can leave empty. Not an array:
# this is POSIX sh.
KC=""
[ -n "${OVERWATCH_SIGN_KEYCHAIN:-}" ] && KC="--keychain $OVERWATCH_SIGN_KEYCHAIN"

ENTS=""
if [ -n "${OVERWATCH_SIGN_ENTITLEMENTS:-}" ]; then
	[ -f "$OVERWATCH_SIGN_ENTITLEMENTS" ] || {
		echo "FATAL: no entitlements file at $OVERWATCH_SIGN_ENTITLEMENTS" >&2
		exit 1
	}
	ENTS="--entitlements $OVERWATCH_SIGN_ENTITLEMENTS"
	echo "entitlements: $OVERWATCH_SIGN_ENTITLEMENTS"
fi

# Prove the identity is really there before touching 53 files. codesign's own
# error for a missing identity arrives once per file.
#
# Not `-v`. That filters to identities the machine considers VALID, which
# depends on the trust chain resolving -- and a Developer ID imported into a
# throwaway CI keychain that is not in the search list is reported as no
# identity at all, failing the build for a certificate that is sitting right
# there and signs fine. What actually has to be true of this certificate is
# checked after signing, on the result: a Team ID has to come out of it, and
# the binary has to run. Those are the substantive tests, and an expired or
# malformed certificate fails codesign itself a few lines below.
# shellcheck disable=SC2086
security find-identity -p codesigning ${OVERWATCH_SIGN_KEYCHAIN:-} \
	| grep -Fq "$ID" || {
	echo "FATAL: no code-signing identity matching:" >&2
	echo "  $ID" >&2
	echo "Available:" >&2
	# shellcheck disable=SC2086
	security find-identity -p codesigning ${OVERWATCH_SIGN_KEYCHAIN:-} >&2
	exit 1
}

cd "$DIR"

# --timestamp, not --timestamp=none: notarisation rejects a signature without
# a secure timestamp from Apple's server. It needs the network, and a signing
# run on a machine that cannot reach timestamp.apple.com fails here rather
# than 20 minutes later inside notarytool.
sign() {
	# shellcheck disable=SC2086
	codesign --force --options runtime --timestamp $KC $ENTS -s "$ID" "$1" \
		2>&1 | grep -v 'replacing existing signature' || true
}

# ----------------------------------------------------------- what to sign
#
# Every Mach-O file, because notarisation rejects an archive containing even
# one unsigned executable -- and PyInstaller collects 50-odd .so files that
# nothing else in this repo ever names.
#
# -type f, so the four symlinks in the bundle are skipped: _internal/Python
# points into Python.framework, and signing through it would sign the same
# file twice under two names.
#
# EXCLUDING the framework's own Mach-O. Python.framework is a BUNDLE -- it has
# Versions/3.13/Resources/Info.plist, and PyInstaller signs it as one ("Format
# =bundle with Mach-O thin"). Signing the bare Mach-O inside it instead
# replaces that with a plain Mach-O signature and breaks the bundle's seal.
# It is signed as a bundle, once, below.
#
# The list goes to a FILE and is read back a line at a time, rather than into a
# variable iterated with `for f in $MACHO`. That form depends on the shell
# word-splitting an unquoted expansion, which zsh does not do -- so the same
# loop that works here silently degenerates elsewhere into ONE iteration with
# all 51 paths as a single filename. Seen doing exactly that while this script
# was being written (2026-09-26): codesign answered "File name too long" and
# the verification loop below reported success having checked two files.
LIST="${TMPDIR:-/tmp}/overwatch-macho.txt"
find . -type f \
	! -path './_internal/Python.framework/*' \
	! -name overwatch \
	-exec sh -c 'file -b "$1" | grep -q Mach-O' _ {} \; -print >"$LIST"

n=0
while IFS= read -r f; do
	[ -n "$f" ] || continue
	sign "$f"
	n=$((n + 1))
done <"$LIST"
echo "signed $n inner Mach-O files"

# A bundle whose libraries were not found is a bundle notarisation will reject
# for containing unsigned executables -- and the loop above would have said
# nothing. There are 51 of these in a normal build; the floor is deliberately
# low because the exact count changes with the dependency set.
[ "$n" -ge 20 ] || {
	echo "FATAL: only $n inner Mach-O files found under $DIR." >&2
	echo "  A real build has around 51. Signing the rest would leave" >&2
	echo "  unsigned executables in the archive, which Apple rejects." >&2
	exit 1
}

if [ -d _internal/Python.framework ]; then
	sign _internal/Python.framework
	echo "signed _internal/Python.framework (as a bundle)"
fi

# Last. The main executable's signature has to be the newest thing in the
# directory: sign it first and then rewrite a library underneath it and you
# have shipped a binary whose seal describes files that no longer exist.
sign ./overwatch
echo "signed ./overwatch"

# ------------------------------------------------------------------- verify
#
# Not `--deep`: a one-directory PyInstaller build is not a bundle, so --deep
# has nothing to recurse into and verifying the main executable says nothing
# about the 52 files beside it. Each is checked on its own.
fail=0
checked=0
{ cat "$LIST"; echo ./overwatch; echo _internal/Python.framework; } | {
	while IFS= read -r f; do
		if [ -z "$f" ] || [ ! -e "$f" ]; then continue; fi
		checked=$((checked + 1))
		codesign --verify --strict --verbose=0 "$f" 2>/dev/null || {
			echo "UNSIGNED OR INVALID: $f" >&2
			fail=1
		}
		# The hardened runtime flag, per file. Notarisation checks this
		# on every executable in the archive, not just the entry point,
		# and a rejection names the file -- after a round trip to Apple.
		codesign -d --verbose=2 "$f" 2>&1 | grep -q 'flags=.*runtime' || {
			echo "NO HARDENED RUNTIME: $f" >&2
			fail=1
		}
	done
	# Inside the same subshell as the loop: a pipeline's right-hand side
	# runs in a subshell, so $fail and $checked set by the loop are gone by
	# the line after the closing brace. Checking them out here would have
	# read 0 and 0 and passed no matter what the loop found.
	[ "$checked" -eq $((n + 2)) ] || {
		echo "FATAL: meant to verify $((n + 2)) paths, verified $checked" >&2
		exit 1
	}
	[ "$fail" = 0 ] || {
		echo "FATAL: the signature is not uniform; see above" >&2
		exit 1
	}
	echo "verified $checked signed paths"
} || exit 1

TEAM=$(codesign -dvv ./overwatch 2>&1 | sed -n 's/^TeamIdentifier=//p')
if [ -z "$TEAM" ] || [ "$TEAM" = "not set" ]; then
	echo "FATAL: signed, but the result carries no Team ID." >&2
	echo "  Library validation cannot be satisfied without one, and" >&2
	echo "  notarisation will reject it. Is $ID really a Developer ID" >&2
	echo "  Application certificate, and not a local or self-signed one?" >&2
	exit 1
fi
echo "Team ID: $TEAM (uniform across $((n + 2)) signed paths)"

# ---------------------------------------------------------------- self-test
#
# Run it. Everything above checks what codesign wrote down; only this checks
# that the program still starts, which is the thing the hardened runtime is
# known to be able to take away (see the header).
out=$(./overwatch --version 2>&1) || true
case "$out" in
*overwatch*)
	echo "self-test: $out"
	;;
*"different Team IDs"*)
	echo "FATAL: the signed binary cannot load its own Python." >&2
	echo >&2
	echo "$out" | head -3 >&2
	echo >&2
	echo "This is hardened-runtime library validation. Every file was" >&2
	echo "signed with one identity, so if the Team IDs still disagree the" >&2
	echo "framework is not being sealed the way this script assumes." >&2
	echo "The escape hatch, which notarises fine and is what other Python" >&2
	echo "bundles use:" >&2
	echo >&2
	echo "  OVERWATCH_SIGN_ENTITLEMENTS=tools/macos-library-validation.entitlements \\" >&2
	echo "    tools/macos_sign.sh $DIR" >&2
	echo >&2
	echo "Read that file before using it: it gives up a real protection." >&2
	exit 1
	;;
*)
	echo "FATAL: the signed binary did not report a version." >&2
	echo "$out" | head -10 >&2
	exit 1
	;;
esac
