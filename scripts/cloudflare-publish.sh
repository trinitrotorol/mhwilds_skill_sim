#!/usr/bin/env sh
# Keep the pinned Cloudflare CLI and every installation cache inside this checkout.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPOSITORY_ROOT=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd -P)
cd "${REPOSITORY_ROOT}"
case "$*" in
  deploy|"versions upload"|"deploy --dry-run") ;;
  *) printf '%s\n' 'Expected deploy, versions upload, or deploy --dry-run' >&2; exit 2 ;;
esac
sh ./scripts/check-release-source.sh --allow-uninitialized
git submodule update --init
sh ./scripts/check-release-source.sh
# Cloudflare's language shims can live under HOME. Bootstrap requires the
# existing distro interpreter; nodew/npmw still select the pinned local Node.
export PATH="/usr/bin:/bin:${PATH:-}"
sh ./scripts/bootstrap.sh
sh ./scripts/npmw --prefix cloudflare/mhwilds-skill-sim-api ci
export WRANGLER_LOG_PATH="${REPOSITORY_ROOT}/.cache/wrangler/logs"
export WRANGLER_SEND_METRICS=false
sh ./scripts/check-release-source.sh
exec sh ./scripts/nodew ./cloudflare/mhwilds-skill-sim-api/node_modules/wrangler/bin/wrangler.js "$@"
