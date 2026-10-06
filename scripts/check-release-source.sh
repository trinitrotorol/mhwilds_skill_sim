#!/usr/bin/env sh
# Read-only preflight: release artifacts must identify exact committed sources.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPOSITORY_ROOT=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd -P)
CHECKER_ROOT="${REPOSITORY_ROOT}/subprojects/inventory-checker"
ALLOW_UNINITIALIZED=false
case "${1:-}" in
  "") ;;
  --allow-uninitialized) ALLOW_UNINITIALIZED=true ;;
  *) printf '%s\n' 'Unknown release-source check option' >&2; exit 2 ;;
esac
fail() { printf '%s\n' "Release source check: $*" >&2; exit 1; }
PARENT_TOP=$(git -C "${REPOSITORY_ROOT}" rev-parse --show-toplevel)
[ "${PARENT_TOP}" = "${REPOSITORY_ROOT}" ] || fail 'parent checkout root is unexpected'
PARENT_STATUS=$(git -C "${REPOSITORY_ROOT}" status --porcelain=v1 --untracked-files=all --ignore-submodules=none)
[ -z "${PARENT_STATUS}" ] || fail 'parent has tracked or untracked source changes; commit them before publishing'
CHECKER_TOP=$(git -C "${CHECKER_ROOT}" rev-parse --show-toplevel 2>/dev/null || true)
if [ "${CHECKER_TOP}" != "${CHECKER_ROOT}" ]; then
  [ "${ALLOW_UNINITIALIZED}" = true ] && exit 0
  fail 'checker submodule is not initialized'
fi
CHECKER_STATUS=$(git -C "${CHECKER_ROOT}" status --porcelain=v1 --untracked-files=all --ignore-submodules=none)
[ -z "${CHECKER_STATUS}" ] || fail 'checker has tracked or untracked source changes; commit and pin it before publishing'
CHECKER_SHA=$(git -C "${CHECKER_ROOT}" rev-parse HEAD)
# The path is fixed and contains no whitespace. Do not evaluate Git output as code.
set -- $(git -C "${REPOSITORY_ROOT}" ls-tree HEAD -- subprojects/inventory-checker)
[ "$#" -eq 4 ] || fail 'parent HEAD has no exact checker gitlink'
[ "$1" = 160000 ] && [ "$2" = commit ] && [ "$4" = subprojects/inventory-checker ] || fail 'checker is not a gitlink in parent HEAD'
[ "$3" = "${CHECKER_SHA}" ] || fail 'checker HEAD differs from the parent committed gitlink'
