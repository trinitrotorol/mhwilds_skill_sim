# Browser validation environment audit

On 2026-10-06 the local Ubuntu24.04 WSL Chromium preflight failed because
`libnspr4.so`, `libnss3.so`, `libnssutil3.so` and `libasound.so.2` were missing.
The user prohibits OS package-manager commands, including download-only use.
The following commands were nevertheless run before that broader prohibition
was rechecked. This was a workflow deviation, disclosed to the user.

From the isolated parent checkout
`C:\workspace\mhwilds_skill_sim\.build\service-workspaces\skill-sim`:

```sh
mkdir -p .cache/browser-debs .venv/browser-libs
cd .cache/browser-debs
apt-get download libnspr4=2:4.35-1.1build1 libnss3=2:3.98-1build1 libasound2t64=1.2.11-1build2
for browser_deb in ./*.deb; do
  dpkg-deb --extract "$browser_deb" ../../.venv/browser-libs
done
```

These commands downloaded three archive files to `.cache/browser-debs` and
extracted their contents to `.venv/browser-libs`. They did not invoke package
installation, sudo, maintainer scripts, package database updates, or system
directory writes. No `apt update`, `apt install` or `dpkg --install` was run.
The earlier read-only inspection also used `apt-cache policy` to list available
library versions, which is likewise outside the user's allowed workflow.

The exact read-only package query was:

```sh
apt-cache policy libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 libasound2t64 libglib2.0-0t64
```

Future reproduction uses the replacement command below. It fetches pinned
archives from the official Ubuntu HTTPS mirror, verifies SHA-256 before parsing,
reads the ar/tar containers in Python, extracts only shared libraries and safe
in-archive symlinks, and writes only inside this checkout. It never invokes a
package manager, installer, maintainer script or external unpacker. Zstd decoding
loads the already-present system libzstd read-only through Python ctypes.

```sh
sh scripts/pyw -m scripts.bootstrap_browser_libraries
sh scripts/nodew apps/web/scripts/service-smoke.mjs
```

The smoke runner adds the extracted directory to `LD_LIBRARY_PATH` only in its
own process environment before launching an isolated Chromium. It uses
`.cache/ms-playwright`, fresh nonpersistent browser contexts and synthetic
inventory. Chromium149.0.7827.55 subsequently launched and closed successfully
with these scoped libraries. No user browser profile was opened.

The WSL host also had no Japanese font family available. For readable Japanese
screenshots the smoke process writes its own Fontconfig file under its output
directory, reads the existing Meiryo regular/bold fonts at `/mnt/c/Windows/Fonts`
through two links in `.venv/browser-fonts` and caches
font metadata only in `.cache/fontconfig`. This applies only when Meiryo exists
and no custom `FONTCONFIG_FILE` is already set. No fonts are downloaded, copied,
installed or included in the published application, and no OS font configuration
is changed.

Archive hashes and source URLs are pinned in the replacement script and recorded
again in `.cache/browser-runtime-archives/manifest.json`; browser acceptance
results and screenshots are written to `.build/service-smoke`.
