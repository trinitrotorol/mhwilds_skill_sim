#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPOSITORY_ROOT=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd -P)
cd "${REPOSITORY_ROOT}"
sh scripts/check-release-source.sh --allow-uninitialized
git submodule update --init
sh scripts/check-release-source.sh
# Prefer the existing Ubuntu/WSL base Python over inherited virtualenvs or
# HOME-managed Cloudflare shims. Pinned wrappers restore their own Node/Python.
export PATH="/usr/bin:/bin:${PATH:-}"
./scripts/bootstrap.sh
sh scripts/pyw -m pip install -r requirements-service.txt
sh scripts/pyw -m pip install --no-deps -e .
./scripts/npmw --prefix apps/web ci
(cd subprojects/inventory-checker && ./scripts/bootstrap.sh && ./scripts/npmw ci)
sh scripts/verify-service.sh
sh scripts/pyw -m scripts.build_service --require-clean
sh scripts/check-release-source.sh
