#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPOSITORY_ROOT=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd -P)
cd "${REPOSITORY_ROOT}"
test -f subprojects/inventory-checker/contracts/search-inventory.v1.schema.json || {
  echo 'Initialize the pinned checker submodule: git submodule update --init' >&2
  exit 1
}
make test
make lint
make data-check
./scripts/npmw --prefix apps/web test
./scripts/npmw --prefix apps/web run lint
./scripts/npmw --prefix apps/web run build
./scripts/nodew --test cloudflare/mhwilds-skill-sim/src/index.test.mjs
./scripts/nodew --test cloudflare/mhwilds-skill-sim-api/src/handler.test.mjs cloudflare/mhwilds-skill-sim-api/src/config.test.mjs
(cd subprojects/inventory-checker && ./scripts/npmw run verify)
