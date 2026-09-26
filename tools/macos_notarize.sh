#!/bin/sh
# Send a signed macOS build to Apple for notarisation.
#
#   tools/macos_notarize.sh [build-dir]       (default: dist/overwatch)
#
# Run AFTER tools/macos_sign.sh. Apple notarises code signatures, so an
# unsigned or ad-hoc build has nothing for this to do -- and, like the signing
# script, missing credentials are a supported state that exits 0 rather than
# failing a build on a machine that has none.
#
#   OVERWATCH_NOTARY_KEY      path to the App Store Connect .p8 private key
#   OVERWATCH_NOTARY_KEY_ID   its Key ID (10 characters)
#   OVERWATCH_NOTARY_ISSUER   the issuer UUID for the account
#
# An App Store Connect API key, not an Apple ID and app-specific password.
# Both work; the key is a credential scoped to this one job that can be
# revoked on its own, where the password route puts the account's own
# credentials into CI.
#
# ------------------------------------------------------------ no stapling
#
# There is deliberately no `xcrun stapler staple` here, and it is not an
# omission. stapler attaches a ticket to a .app bundle, a .dmg, a .pkg or a
# .kext. What this project ships is a bare Unix executable inside a .tar.gz,
# and neither a loose Mach-O nor a tarball can carry a ticket.
#
# Unstapled notarisation still works: Gatekeeper looks the signature up with
# Apple online the first time a quarantined copy is run, and a notarised one
# is admitted. The cost is that the check needs the network on that first run.
#
# The way to get a stapled ticket would be to ship a .pkg or .dmg instead of a
# tarball -- a real improvement for anyone who downloads from the releases page
# on a plane, and a much larger change than this. See docs/notarisation.md.
set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
DIR="${1:-$ROOT/dist/overwatch}"

[ -d "$DIR" ] || { echo "no build at $DIR" >&2; exit 1; }
[ "$(uname -s)" = "Darwin" ] || { echo "not macOS; nothing to notarise"; exit 0; }

if [ -z "${OVERWATCH_NOTARY_KEY:-}" ] || [ -z "${OVERWATCH_NOTARY_KEY_ID:-}" ] \
	|| [ -z "${OVERWATCH_NOTARY_ISSUER:-}" ]; then
	echo "no notary credentials: skipping notarisation."
	echo "  A browser download of this build will be refused by Gatekeeper."
	echo "  The curl install line is unaffected. See docs/notarisation.md."
	exit 0
fi

[ -f "$OVERWATCH_NOTARY_KEY" ] || {
	echo "FATAL: no key file at $OVERWATCH_NOTARY_KEY" >&2
	exit 1
}

EXE="$DIR/overwatch"

# Refuse to spend a round trip on something that cannot pass. Apple rejects an
# ad-hoc signature, and its rejection takes minutes to come back and names
# every file in the archive.
codesign -dvv "$EXE" 2>&1 | grep -q 'flags=.*runtime' || {
	echo "FATAL: $EXE is not signed with the hardened runtime." >&2
	echo "  Run tools/macos_sign.sh with OVERWATCH_SIGN_IDENTITY set first." >&2
	exit 1
}
TEAM=$(codesign -dvv "$EXE" 2>&1 | sed -n 's/^TeamIdentifier=//p')
if [ -z "$TEAM" ] || [ "$TEAM" = "not set" ]; then
	echo "FATAL: $EXE carries no Team ID, so it is not Developer ID signed." >&2
	exit 1
fi

WORK="${TMPDIR:-/tmp}/overwatch-notarize"
rm -rf "$WORK"
mkdir -p "$WORK"
ZIP="$WORK/overwatch.zip"

# ditto, not zip(1). The bundle contains four symlinks -- including
# Python.framework/Versions/Current -- and `zip` stores what they point at,
# which both doubles the archive and presents notarytool with duplicate
# executables. ditto is also what Apple's own documentation uses here.
ditto -c -k --sequesterRsrc --keepParent "$DIR" "$ZIP"
echo "submitting $(du -h "$ZIP" | cut -f1) to Apple; this usually takes a few minutes"

# --wait, because the whole point is to know the answer before the release is
# published. Without it this returns a submission id and a green tick that
# means "Apple received it".
set +e
OUT=$(xcrun notarytool submit "$ZIP" \
	--key "$OVERWATCH_NOTARY_KEY" \
	--key-id "$OVERWATCH_NOTARY_KEY_ID" \
	--issuer "$OVERWATCH_NOTARY_ISSUER" \
	--wait --timeout 30m 2>&1)
RC=$?
set -e
echo "$OUT"

# The id of THIS submission, for the log fetch below. First match: notarytool
# prints "id: <uuid>" for the submission and again inside the status block.
SUB=$(echo "$OUT" | sed -n 's/^ *id: *//p' | head -1)

if [ "$RC" != 0 ] || ! echo "$OUT" | grep -q 'status: Accepted'; then
	echo >&2
	echo "FATAL: notarisation did not succeed." >&2
	if [ -n "$SUB" ]; then
		echo "Apple's reasons:" >&2
		xcrun notarytool log "$SUB" \
			--key "$OVERWATCH_NOTARY_KEY" \
			--key-id "$OVERWATCH_NOTARY_KEY_ID" \
			--issuer "$OVERWATCH_NOTARY_ISSUER" >&2 2>&1 || true
	fi
	exit 1
fi

echo "notarised (submission $SUB)"

# ------------------------------------------------------------------- verify
#
# Ask the machine, not the transcript. "status: Accepted" says Apple accepted
# the submission; this says Gatekeeper on a real Mac now admits this exact
# binary, which is the thing being bought. It needs the network, because there
# is no stapled ticket to read offline -- see the header.
echo "checking what Gatekeeper makes of it"
if spctl -a -vvv -t exec "$EXE" 2>&1 | tee "$WORK/spctl.txt" \
	| grep -q 'source=Notarized Developer ID'; then
	echo "Gatekeeper: accepted, notarised."
else
	echo >&2
	echo "FATAL: notarisation was accepted but Gatekeeper does not agree:" >&2
	cat "$WORK/spctl.txt" >&2
	echo >&2
	echo "Apple's lookup can lag a few minutes behind an acceptance. If this" >&2
	echo "machine is online and it still says this, do not publish: a" >&2
	echo "customer's Mac is running the same check." >&2
	exit 1
fi
