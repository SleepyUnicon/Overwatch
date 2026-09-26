# Signing and notarising the macOS build

Everything on this page is wired up and dormant. The scripts exist, CI calls
them, and they exit 0 with an explanation while the credentials are absent —
which is the state today. Adding six repository secrets is the whole of what is
left, and nothing else has to change.

## What it buys, and what it does not

Only one thing: a **browser download** of the macOS build stops being refused.

macOS marks files downloaded by a browser with a quarantine flag. Gatekeeper
reads that flag and refuses to run anything it cannot verify —

> "overwatch" cannot be opened because the developer cannot be verified.

`curl` sets no quarantine flag, so the install line on the setup page is
unaffected and always has been. That is why this has stayed a "not yet" rather
than a "broken": the documented path works, and only somebody who ignores it in
favour of clicking the release page hits the wall.

So this is worth doing when Overwatch goes to people who did not build it, and
is worth nothing before then.

## The cost

The Apple Developer Program, $99/year. There is no free tier that can notarise;
a free Apple ID can only sign for local use, which is what the build already
does for itself.

## Setting it up

### 1. Enrol

<https://developer.apple.com/programs/enroll/> — as an individual is fine.
Approval usually takes a day or two.

### 2. Create a Developer ID Application certificate

In Xcode: **Settings → Accounts → Manage Certificates → + → Developer ID
Application**. Or on the portal under Certificates, Identifiers & Profiles.

There is one other kind, *Developer ID Installer*, which signs `.pkg` files.
This project ships a tarball, so it is not needed — see "No stapling" below for
when it would be.

### 3. Export it as a `.p12`

Keychain Access → My Certificates → the "Developer ID Application" row → right
click → Export. Give it a password; both halves become secrets.

```bash
base64 -i Certificates.p12 | pbcopy      # the value for MACOS_CERT_P12_BASE64
```

The identity's exact name, which is the third secret:

```bash
security find-identity -p codesigning | grep "Developer ID Application"
# 1) A1B2... "Developer ID Application: Your Name (AB12CD34EF)"
```

Copy the quoted string, including the team ID in brackets.

### 4. Create an App Store Connect API key

App Store Connect → **Users and Access → Integrations → App Store Connect API
→ Team Keys → +**. Role **Developer** is enough. Download the `.p8` — Apple
lets you download it once.

An API key rather than an Apple ID and an app-specific password. Both work with
`notarytool`; the key is a credential scoped to this one job that can be
revoked on its own, where the password route puts the account's own login into
CI.

```bash
base64 -i AuthKey_XXXXXXXXXX.p8 | pbcopy   # the value for MACOS_NOTARY_KEY_BASE64
```

### 5. Add the secrets

Repository → Settings → Secrets and variables → Actions:

| Secret | Value |
| --- | --- |
| `MACOS_CERT_P12_BASE64` | base64 of the exported `.p12` |
| `MACOS_CERT_PASSWORD` | the password set during export |
| `MACOS_SIGN_IDENTITY` | `Developer ID Application: Your Name (TEAMID)` |
| `MACOS_NOTARY_KEY_BASE64` | base64 of the `.p8` |
| `MACOS_NOTARY_KEY_ID` | the Key ID, 10 characters, shown beside the key |
| `MACOS_NOTARY_ISSUER` | the Issuer ID, a UUID at the top of the Keys page |

### 6. Cut a release

Nothing to change. `release-binaries.yml` imports the certificate into a
throwaway keychain, runs `tools/macos_sign.sh`, install-tests the signed binary,
runs `tools/macos_notarize.sh`, and deletes the keychain whether or not any of
that worked. Both macOS jobs — arm64 and x86_64 — do it independently.

The first release after this is the one to watch, for the reason in the next
section.

## The hardened runtime, which is where this bites

Notarisation requires the hardened runtime. The hardened runtime enables
**library validation**, which refuses to load any library whose Team ID differs
from the process's own.

A PyInstaller build is an executable plus 52 other Mach-O files — `libssl`,
`libcrypto`, an embedded `Python.framework`, and 49 `.so` extension modules.
All 53 have to agree.

Measured on this project, 2026-09-26: signing all 53 ad-hoc with
`--options runtime` produces a binary that **does not start at all**.

```
Failed to load Python shared library '.../_internal/Python':
  ... not valid for use in process: mapping process and mapped file
  (non-platform) have different Team IDs
```

An ad-hoc signature carries no Team ID, so nothing can match anything. Two
consequences, both already in the scripts:

- The hardened runtime is set **only** in the Developer ID path. On an unsigned
  build it buys nothing and costs a binary that cannot run, so
  `tools/macos_sign.sh` does not set it when there is no identity.
- A real Developer ID gives all 53 files **one** Team ID, which is what library
  validation wants. That is the expectation, and it has **not been observed
  here** — it needs the paid certificate, and it is the one part of this that
  cannot be rehearsed. So the script runs the binary it just signed and refuses
  to pass it on if it does not start.

If that self-test does fail on the first real signing run, the script names the
fix: `tools/macos-library-validation.entitlements`, an entitlement that turns
library validation off. It notarises fine and plenty of Python bundles ship
with it. Read the file before using it — it gives up a real protection, and the
reason it is not the default is that it should not be needed.

## No stapling

`xcrun stapler` attaches a notarisation ticket to a `.app`, a `.dmg`, a `.pkg`
or a `.kext`. This project ships a bare Unix executable inside a `.tar.gz`, and
neither a loose Mach-O nor a tarball can carry a ticket. There is no
`stapler staple` call in `tools/macos_notarize.sh` and its absence is
deliberate.

Unstapled notarisation still works: the first time a quarantined copy runs,
Gatekeeper looks the signature up with Apple online, and a notarised one is
admitted. The cost is that **that first run needs the network**.

Shipping a `.pkg` or `.dmg` instead would fix that, and would also give the
release page something a person can double-click. It is a genuinely better
product for anyone installing on a plane. It is also a much larger change —
a `.pkg` has to place the files and register the login agent itself, which is
today `overwatch install`'s job — so it is noted here rather than done.

## Checking it worked

On any Mac, against a published release:

```bash
curl -fsSLO https://github.com/SleepyUnicon/Overwatch/releases/latest/download/overwatch-macos-arm64.tar.gz
tar xzf overwatch-macos-arm64.tar.gz
codesign -dvv overwatch/overwatch 2>&1 | grep -E 'Authority|TeamIdentifier|flags'
spctl -a -vvv -t exec overwatch/overwatch
```

What you want:

```
Authority=Developer ID Application: Your Name (AB12CD34EF)
TeamIdentifier=AB12CD34EF
flags=0x10000(runtime)
overwatch/overwatch: accepted
source=Notarized Developer ID
```

`source=Notarized Developer ID` is the line that matters. `accepted` on its own
can also mean "no quarantine flag, so nobody asked" — `curl` downloads are not
quarantined, which is the same reason the install line works unsigned. To see
what a browser download would do, set the flag by hand:

```bash
xattr -w com.apple.quarantine "0083;00000000;Safari;" overwatch/overwatch
./overwatch/overwatch --version
```

Unsigned, that is refused. Notarised, it runs.

`tools/macos_notarize.sh` already runs the `spctl` check itself and fails the
release if Gatekeeper disagrees with Apple's acceptance, so a green release job
means this has already been verified once on a real Mac.
