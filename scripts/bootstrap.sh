#!/usr/bin/env sh

set -eu
umask 077

NODE_VERSION="24.18.0"
EXPECTED_NODE_VERSION="v${NODE_VERSION}"
NPM_VERSION="11.16.0"
PIP_VERSION="26.1.2"
NODEENV_VERSION="1.10.0"
PIP_WHEEL_NAME="pip-${PIP_VERSION}-py3-none-any.whl"
PIP_WHEEL_URL="https://files.pythonhosted.org/packages/5d/95/6b5cb3461ea5673ba0995989746db58eb18b91b54dbf331e72f569540946/${PIP_WHEEL_NAME}"
PIP_WHEEL_SHA256="382ff9f685ee3bc25864f820aa50505825f10f5458ffff07e30a6d96e5715cab"

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPOSITORY_ROOT=$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd -P)
VENV_DIR="${REPOSITORY_ROOT}/.venv"
CACHE_DIR="${REPOSITORY_ROOT}/.cache"
PIP_CACHE_DIR="${CACHE_DIR}/pip"
PIP_BOOTSTRAP_DIR="${PIP_CACHE_DIR}/bootstrap"
PIP_WHEEL_PATH="${PIP_BOOTSTRAP_DIR}/${PIP_WHEEL_NAME}"
NODE_MIRROR_ROOT="${CACHE_DIR}/node-mirror"
NODE_MIRROR_VERSION_DIR="${NODE_MIRROR_ROOT}/v${NODE_VERSION}"
TEMP_DIR="${CACHE_DIR}/tmp"
XDG_ROOT="${CACHE_DIR}/xdg"
NPM_CACHE_DIR="${CACHE_DIR}/npm"
INSTALL_LOCK_DIR="${CACHE_DIR}/bootstrap.lock"
NODE_VERSION_FILE="${REPOSITORY_ROOT}/.node-version"
TOOLCHAIN_REQUIREMENTS="${REPOSITORY_ROOT}/requirements-toolchain.txt"

fail() {
  printf '%s\n' "bootstrap: $*" >&2
  exit 1
}

assert_directory_in_repository() {
  DIRECTORY_PATH=$1
  DIRECTORY_LABEL=$2

  DIRECTORY_REAL=$(CDPATH= cd -P -- "${DIRECTORY_PATH}" 2>/dev/null && pwd -P) ||
    fail "${DIRECTORY_LABEL} is not an accessible directory: ${DIRECTORY_PATH}"
  case "${DIRECTORY_REAL}/" in
    "${REPOSITORY_ROOT}/"*) ;;
    *) fail "${DIRECTORY_LABEL} resolves outside the repository: ${DIRECTORY_REAL}" ;;
  esac
}

ensure_repository_directory() {
  LOCAL_DIRECTORY=$1
  LOCAL_LABEL=$2

  [ ! -L "${LOCAL_DIRECTORY}" ] ||
    fail "refusing to use symlinked ${LOCAL_LABEL}: ${LOCAL_DIRECTORY}"
  if [ -e "${LOCAL_DIRECTORY}" ]; then
    [ -d "${LOCAL_DIRECTORY}" ] ||
      fail "${LOCAL_LABEL} is not a directory: ${LOCAL_DIRECTORY}"
  else
    mkdir -p "${LOCAL_DIRECTORY}" ||
      fail "could not create ${LOCAL_LABEL}: ${LOCAL_DIRECTORY}"
  fi
  assert_directory_in_repository "${LOCAL_DIRECTORY}" "${LOCAL_LABEL}"
}

assert_repository_file() {
  LOCAL_FILE=$1
  LOCAL_LABEL=$2

  [ -f "${LOCAL_FILE}" ] && [ ! -L "${LOCAL_FILE}" ] ||
    fail "${LOCAL_LABEL} must be a regular non-symlink file: ${LOCAL_FILE}"
  FILE_PARENT_REAL=$(CDPATH= cd -P -- "$(dirname -- "${LOCAL_FILE}")" 2>/dev/null && pwd -P) ||
    fail "could not resolve the parent directory for ${LOCAL_FILE}"
  case "${FILE_PARENT_REAL}/" in
    "${REPOSITORY_ROOT}/"*) ;;
    *) fail "${LOCAL_LABEL} resolves outside the repository: ${LOCAL_FILE}" ;;
  esac
}

assert_venv_executable() {
  LOCAL_EXECUTABLE=$1
  LOCAL_LABEL=$2

  [ -x "${LOCAL_EXECUTABLE}" ] ||
    fail "${LOCAL_LABEL} is missing or not executable: ${LOCAL_EXECUTABLE}"
  RESOLVED_EXECUTABLE=$(readlink -f -- "${LOCAL_EXECUTABLE}" 2>/dev/null) ||
    fail "could not resolve ${LOCAL_LABEL}"
  case "${RESOLVED_EXECUTABLE}" in
    "${VENV_DIR}/"*) ;;
    *) fail "${LOCAL_LABEL} resolves outside .venv: ${RESOLVED_EXECUTABLE}" ;;
  esac
}

verify_venv_python() {
  [ -x "${VENV_DIR}/bin/python" ] ||
    fail ".venv does not use the required POSIX bin layout"
  VENV_PYTHON_REAL=$(readlink -f -- "${VENV_DIR}/bin/python" 2>/dev/null) ||
    fail "could not resolve the virtualenv Python"
  [ "${VENV_PYTHON_REAL}" = "${SYSTEM_PYTHON_REAL}" ] ||
    fail ".venv Python does not resolve to the selected system Python"

  "${VENV_DIR}/bin/python" -c '
import os
import sys

expected_prefix = os.path.realpath(sys.argv[1])
expected_base_executable = os.path.realpath(sys.argv[2])
actual_base_executable = os.path.realpath(getattr(sys, "_base_executable", ""))

valid = (
    os.name == "posix"
    and sys.version_info >= (3, 10)
    and os.path.realpath(sys.prefix) == expected_prefix
    and sys.prefix != sys.base_prefix
    and actual_base_executable == expected_base_executable
)
raise SystemExit(0 if valid else 1)
' "${VENV_DIR}" "${SYSTEM_PYTHON_REAL}" ||
    fail ".venv Python metadata does not match the selected POSIX system Python"
}

verify_existing_toolchain() {
  [ -f "${VENV_DIR}/pyvenv.cfg" ] ||
    fail ".venv exists but is not a Python virtual environment"
  verify_venv_python
  assert_venv_executable "${VENV_DIR}/bin/nodeenv" "nodeenv executable"
  assert_venv_executable "${VENV_DIR}/bin/node" "Node.js executable"
  assert_venv_executable "${VENV_DIR}/bin/npm" "npm executable"

  ACTUAL_PIP_VERSION=$("${VENV_DIR}/bin/python" -c \
    'import pip; print(pip.__version__)' 2>/dev/null || true)
  [ "${ACTUAL_PIP_VERSION}" = "${PIP_VERSION}" ] ||
    fail ".venv pip is ${ACTUAL_PIP_VERSION:-unknown}; expected ${PIP_VERSION}"

  ACTUAL_NODEENV_VERSION=$("${VENV_DIR}/bin/nodeenv" --version 2>/dev/null || true)
  [ "${ACTUAL_NODEENV_VERSION}" = "${NODEENV_VERSION}" ] ||
    fail ".venv nodeenv is ${ACTUAL_NODEENV_VERSION:-unknown}; expected ${NODEENV_VERSION}"

  ACTUAL_NODE_VERSION=$("${VENV_DIR}/bin/node" --version 2>/dev/null || true)
  [ "${ACTUAL_NODE_VERSION}" = "${EXPECTED_NODE_VERSION}" ] ||
    fail ".venv Node.js is ${ACTUAL_NODE_VERSION:-unknown}; expected ${EXPECTED_NODE_VERSION}"
  ACTUAL_NODE_PLATFORM=$("${VENV_DIR}/bin/node" -p 'process.platform' 2>/dev/null || true)
  ACTUAL_NODE_ARCH=$("${VENV_DIR}/bin/node" -p 'process.arch' 2>/dev/null || true)
  [ "${ACTUAL_NODE_PLATFORM}" = "linux" ] && [ "${ACTUAL_NODE_ARCH}" = "${NODE_ARCH}" ] ||
    fail ".venv Node.js platform/architecture is incompatible"

  ACTUAL_NPM_VERSION=$(PATH="${VENV_DIR}/bin${PATH:+:${PATH}}" \
    "${VENV_DIR}/bin/npm" --version 2>/dev/null || true)
  [ "${ACTUAL_NPM_VERSION}" = "${NPM_VERSION}" ] ||
    fail ".venv npm is ${ACTUAL_NPM_VERSION:-unknown}; expected ${NPM_VERSION}"
}

assert_repository_file "${NODE_VERSION_FILE}" ".node-version"
assert_repository_file "${TOOLCHAIN_REQUIREMENTS}" "toolchain requirements"

PINNED_NODE_VERSION=$(awk 'NR == 1 { sub(/\r$/, ""); print }' "${NODE_VERSION_FILE}")
PINNED_NODE_LINE_COUNT=$(awk 'END { print NR }' "${NODE_VERSION_FILE}")
[ "${PINNED_NODE_LINE_COUNT}" = "1" ] &&
  [ "${PINNED_NODE_VERSION}" = "${NODE_VERSION}" ] ||
  fail ".node-version must contain exactly ${NODE_VERSION}"

EXPECTED_NODEENV_REQUIREMENT="nodeenv==${NODEENV_VERSION} --hash=sha256:5bb13e3eed2923615535339b3c620e76779af4cb4c6a90deccc9e36b274d3827"
ACTUAL_NODEENV_REQUIREMENT=$(awk 'NR == 1 { sub(/\r$/, ""); print }' "${TOOLCHAIN_REQUIREMENTS}")
TOOLCHAIN_REQUIREMENT_LINE_COUNT=$(awk 'END { print NR }' "${TOOLCHAIN_REQUIREMENTS}")
[ "${TOOLCHAIN_REQUIREMENT_LINE_COUNT}" = "1" ] &&
  [ "${ACTUAL_NODEENV_REQUIREMENT}" = "${EXPECTED_NODEENV_REQUIREMENT}" ] ||
  fail "requirements-toolchain.txt does not contain the expected hash-pinned nodeenv requirement"

OS_NAME=$(uname -s 2>/dev/null || true)
ARCH_NAME=$(uname -m 2>/dev/null || true)
[ "${OS_NAME}" = "Linux" ] ||
  fail "only Linux and WSL are supported; detected ${OS_NAME:-unknown}"
case "${ARCH_NAME}" in
  x86_64 | amd64)
    NODE_ARCH="x64"
    NODE_ARCHIVE_SHA256="783130984963db7ba9cbd01089eaf2c2efb055c7c1693c943174b967b3050cb8"
    ;;
  aarch64 | arm64)
    NODE_ARCH="arm64"
    NODE_ARCHIVE_SHA256="6b4484c2190274175df9aa8f28e2d758a819cb1c1fe6ab481e2f95b463ab8508"
    ;;
  *)
    fail "unsupported Linux architecture: ${ARCH_NAME:-unknown}"
    ;;
esac
NODE_ARCHIVE_NAME="node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.gz"
NODE_ARCHIVE_URL="https://nodejs.org/dist/v${NODE_VERSION}/${NODE_ARCHIVE_NAME}"
NODE_ARCHIVE_PATH="${NODE_MIRROR_VERSION_DIR}/${NODE_ARCHIVE_NAME}"

command -v readlink >/dev/null 2>&1 ||
  fail "GNU readlink is required to validate repository-local executables"
command -v python3 >/dev/null 2>&1 ||
  fail "a POSIX system python3 is required; on Windows run this script through WSL"
SYSTEM_PYTHON=$(command -v python3)
SYSTEM_PYTHON_REAL=$("${SYSTEM_PYTHON}" -c \
  'import os, sys; print(os.path.realpath(sys.executable))' 2>/dev/null) ||
  fail "could not inspect system python3"

"${SYSTEM_PYTHON}" -c \
  'import os, sys; raise SystemExit(0 if os.name == "posix" and sys.prefix == sys.base_prefix and sys.version_info >= (3, 10) else 1)' ||
  fail "python3 must be a POSIX system Python 3.10 or newer, not an active virtualenv"

case "${SYSTEM_PYTHON_REAL}" in
  "${REPOSITORY_ROOT}/"*) fail "system python3 must not come from the repository" ;;
esac
if [ -n "${HOME:-}" ]; then
  HOME_REAL=$(readlink -f -- "${HOME}" 2>/dev/null || printf '%s\n' "${HOME%/}")
  case "${SYSTEM_PYTHON_REAL}" in
    "${HOME_REAL%/}/"*) fail "system python3 must not come from HOME" ;;
  esac
fi
"${SYSTEM_PYTHON}" -c 'import venv' ||
  fail "system python3 does not provide venv; OS package installation is not permitted"

ensure_repository_directory "${CACHE_DIR}" "cache directory"
ensure_repository_directory "${PIP_CACHE_DIR}" "pip cache directory"
ensure_repository_directory "${PIP_BOOTSTRAP_DIR}" "pip bootstrap directory"
ensure_repository_directory "${NODE_MIRROR_ROOT}" "Node.js mirror directory"
ensure_repository_directory "${NODE_MIRROR_VERSION_DIR}" "Node.js mirror version directory"
ensure_repository_directory "${TEMP_DIR}" "temporary directory"
ensure_repository_directory "${XDG_ROOT}" "XDG directory"
ensure_repository_directory "${XDG_ROOT}/cache" "XDG cache directory"
ensure_repository_directory "${XDG_ROOT}/config" "XDG config directory"
ensure_repository_directory "${XDG_ROOT}/data" "XDG data directory"
ensure_repository_directory "${XDG_ROOT}/state" "XDG state directory"
ensure_repository_directory "${NPM_CACHE_DIR}" "npm cache directory"
ensure_repository_directory "${CACHE_DIR}/corepack" "Corepack cache directory"
ensure_repository_directory "${CACHE_DIR}/ms-playwright" "Playwright cache directory"

unset \
  NODE_OPTIONS \
  NODE_PATH \
  PYTHONHOME \
  PYTHONPATH \
  PIP_TARGET \
  PIP_PREFIX \
  PIP_USER \
  PIP_EXTRA_INDEX_URL \
  PIP_FIND_LINKS \
  PIP_TRUSTED_HOST

export PYTHONNOUSERSITE="1"
export PIP_CACHE_DIR
export PIP_CONFIG_FILE="/dev/null"
export PIP_DISABLE_PIP_VERSION_CHECK="1"
export PIP_INDEX_URL="https://pypi.org/simple"
export PIP_NO_INPUT="1"
export PIP_REQUIRE_VIRTUALENV="true"
export TMPDIR="${TEMP_DIR}"
export TMP="${TEMP_DIR}"
export TEMP="${TEMP_DIR}"
export XDG_CACHE_HOME="${XDG_ROOT}/cache"
export XDG_CONFIG_HOME="${XDG_ROOT}/config"
export XDG_DATA_HOME="${XDG_ROOT}/data"
export XDG_STATE_HOME="${XDG_ROOT}/state"
export npm_config_cache="${NPM_CACHE_DIR}"
export npm_config_prefix="${VENV_DIR}"
export npm_config_userconfig="${REPOSITORY_ROOT}/.npmrc"
export npm_config_registry="https://registry.npmjs.org/"
export npm_config_audit="false"
export npm_config_fund="false"
export npm_config_update_notifier="false"
export COREPACK_HOME="${CACHE_DIR}/corepack"
export PLAYWRIGHT_BROWSERS_PATH="${CACHE_DIR}/ms-playwright"

[ ! -L "${INSTALL_LOCK_DIR}" ] ||
  fail "refusing to use a symlinked bootstrap lock"
if ! mkdir "${INSTALL_LOCK_DIR}" 2>/dev/null; then
  fail "another bootstrap may be running, or a stale lock exists at ${INSTALL_LOCK_DIR}"
fi
assert_directory_in_repository "${INSTALL_LOCK_DIR}" "bootstrap lock"

VENV_CREATED="0"
ACTIVE_DOWNLOAD_PART=""
cleanup() {
  EXIT_STATUS=$?
  trap - EXIT HUP INT TERM

  if [ -n "${ACTIVE_DOWNLOAD_PART}" ] && [ -f "${ACTIVE_DOWNLOAD_PART}" ] &&
    [ ! -L "${ACTIVE_DOWNLOAD_PART}" ]; then
    case "${ACTIVE_DOWNLOAD_PART}" in
      "${CACHE_DIR}/"*.part) rm -f -- "${ACTIVE_DOWNLOAD_PART}" ;;
    esac
  fi

  if [ "${EXIT_STATUS}" -ne 0 ] && [ "${VENV_CREATED}" = "1" ] &&
    [ -d "${VENV_DIR}" ] && [ ! -L "${VENV_DIR}" ]; then
    VENV_REAL=$(CDPATH= cd -P -- "${VENV_DIR}" 2>/dev/null && pwd -P || true)
    if [ "${VENV_REAL}" = "${VENV_DIR}" ]; then
      rm -rf -- "${VENV_DIR}"
    fi
  fi

  if [ -d "${INSTALL_LOCK_DIR}" ] && [ ! -L "${INSTALL_LOCK_DIR}" ]; then
    rmdir "${INSTALL_LOCK_DIR}" 2>/dev/null || true
  fi
  exit "${EXIT_STATUS}"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

[ ! -L "${VENV_DIR}" ] ||
  fail "refusing to use symlinked .venv: ${VENV_DIR}"
if [ -e "${VENV_DIR}" ]; then
  [ -d "${VENV_DIR}" ] || fail ".venv exists but is not a directory"
  assert_directory_in_repository "${VENV_DIR}" "virtual environment"
  verify_existing_toolchain
  printf '%s\n' \
    "Node.js ${EXPECTED_NODE_VERSION}, npm ${NPM_VERSION}, and nodeenv ${NODEENV_VERSION} are already available in .venv."
  exit 0
fi

sha256_file() {
  "${SYSTEM_PYTHON}" -c '
import hashlib
import pathlib
import sys

digest = hashlib.sha256()
with pathlib.Path(sys.argv[1]).open("rb") as source:
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(chunk)
print(digest.hexdigest())
' "$1"
}

download_verified_file() {
  DOWNLOAD_URL=$1
  DOWNLOAD_TARGET=$2
  EXPECTED_SHA256=$3
  DOWNLOAD_LABEL=$4

  if [ -e "${DOWNLOAD_TARGET}" ]; then
    [ -f "${DOWNLOAD_TARGET}" ] && [ ! -L "${DOWNLOAD_TARGET}" ] ||
      fail "cached ${DOWNLOAD_LABEL} must be a regular non-symlink file"
    CACHED_SHA256=$(sha256_file "${DOWNLOAD_TARGET}")
    [ "${CACHED_SHA256}" = "${EXPECTED_SHA256}" ] ||
      fail "cached ${DOWNLOAD_LABEL} checksum mismatch; remove ${DOWNLOAD_TARGET} before retrying"
    return 0
  fi

  DOWNLOAD_PART="${DOWNLOAD_TARGET}.part"
  ACTIVE_DOWNLOAD_PART="${DOWNLOAD_PART}"
  [ ! -e "${DOWNLOAD_PART}" ] ||
    fail "partial ${DOWNLOAD_LABEL} already exists; remove ${DOWNLOAD_PART} before retrying"

  printf '%s\n' "Downloading ${DOWNLOAD_LABEL}."
  if ! "${SYSTEM_PYTHON}" - "${DOWNLOAD_URL}" "${DOWNLOAD_PART}" <<'PY'
import pathlib
import shutil
import sys
import urllib.request

request = urllib.request.Request(
    sys.argv[1],
    headers={"User-Agent": "mhwilds-inventory-checker-bootstrap"},
)
with urllib.request.urlopen(request, timeout=60) as response:
    with pathlib.Path(sys.argv[2]).open("xb") as destination:
        shutil.copyfileobj(response, destination)
PY
  then
    rm -f -- "${DOWNLOAD_PART}"
    ACTIVE_DOWNLOAD_PART=""
    fail "could not download ${DOWNLOAD_LABEL}"
  fi

  DOWNLOADED_SHA256=$(sha256_file "${DOWNLOAD_PART}")
  if [ "${DOWNLOADED_SHA256}" != "${EXPECTED_SHA256}" ]; then
    rm -f -- "${DOWNLOAD_PART}"
    ACTIVE_DOWNLOAD_PART=""
    fail "downloaded ${DOWNLOAD_LABEL} checksum mismatch"
  fi
  mv "${DOWNLOAD_PART}" "${DOWNLOAD_TARGET}"
  ACTIVE_DOWNLOAD_PART=""
}

download_verified_file \
  "${PIP_WHEEL_URL}" \
  "${PIP_WHEEL_PATH}" \
  "${PIP_WHEEL_SHA256}" \
  "hash-pinned pip ${PIP_VERSION} bootstrap wheel"
download_verified_file \
  "${NODE_ARCHIVE_URL}" \
  "${NODE_ARCHIVE_PATH}" \
  "${NODE_ARCHIVE_SHA256}" \
  "official Node.js ${NODE_VERSION} ${NODE_ARCH} archive"

NODE_MIRROR_URI=$("${SYSTEM_PYTHON}" -c \
  'import pathlib, sys; print(pathlib.Path(sys.argv[1]).resolve().as_uri())' \
  "${NODE_MIRROR_ROOT}") ||
  fail "could not construct the verified local Node.js mirror URI"

printf '%s\n' "Creating repository-local Python virtual environment."
VENV_CREATED="1"
"${SYSTEM_PYTHON}" -m venv --without-pip "${VENV_DIR}" ||
  fail "could not create .venv with the system Python"
assert_directory_in_repository "${VENV_DIR}" "virtual environment"
verify_venv_python

VENV_PYTHON="${VENV_DIR}/bin/python"
PYTHONPATH="${PIP_WHEEL_PATH}" "${VENV_PYTHON}" -m pip install \
  --disable-pip-version-check \
  --force-reinstall \
  --no-deps \
  --no-index \
  --no-input \
  "${PIP_WHEEL_PATH}" ||
  fail "could not bootstrap pip inside .venv"
unset PYTHONPATH

ACTUAL_PIP_VERSION=$("${VENV_PYTHON}" -c 'import pip; print(pip.__version__)' 2>/dev/null || true)
[ "${ACTUAL_PIP_VERSION}" = "${PIP_VERSION}" ] ||
  fail "bootstrapped pip is ${ACTUAL_PIP_VERSION:-unknown}; expected ${PIP_VERSION}"

"${VENV_PYTHON}" -m pip install \
  --disable-pip-version-check \
  --index-url "${PIP_INDEX_URL}" \
  --no-deps \
  --no-input \
  --only-binary=:all: \
  --require-hashes \
  --requirement "${TOOLCHAIN_REQUIREMENTS}" ||
  fail "could not install hash-pinned nodeenv inside .venv"

assert_venv_executable "${VENV_DIR}/bin/nodeenv" "nodeenv executable"
ACTUAL_NODEENV_VERSION=$("${VENV_DIR}/bin/nodeenv" --version 2>/dev/null || true)
[ "${ACTUAL_NODEENV_VERSION}" = "${NODEENV_VERSION}" ] ||
  fail "installed nodeenv is ${ACTUAL_NODEENV_VERSION:-unknown}; expected ${NODEENV_VERSION}"

printf '%s\n' "Installing verified Node.js ${NODE_VERSION} and bundled npm ${NPM_VERSION} inside .venv."
# Node.js 24.18.0's verified official prebuilt includes npm 11.16.0.
# Avoid nodeenv's --with-npm path because it performs an npm global install;
# the mandatory post-install version check below fails closed if npm drifts.
"${VENV_DIR}/bin/nodeenv" \
  --python-virtualenv \
  --node="${NODE_VERSION}" \
  --npm="${NPM_VERSION}" \
  --prebuilt \
  --clean-src \
  --mirror="${NODE_MIRROR_URI}" \
  --config-file="" ||
  fail "nodeenv could not install the verified pinned Node.js toolchain"

verify_existing_toolchain
printf '%s\n' \
  "Installed Node.js ${EXPECTED_NODE_VERSION}, npm ${NPM_VERSION}, pip ${PIP_VERSION}, and nodeenv ${NODEENV_VERSION} in .venv."
