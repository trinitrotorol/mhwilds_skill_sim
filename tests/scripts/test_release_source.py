"""Exercise publication source guards without modifying any real Git checkout."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


@pytest.fixture
def guarded_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    scripts = workspace / "scripts"
    scripts.mkdir(parents=True)
    (workspace / "subprojects/inventory-checker").mkdir(parents=True)
    for name in (
        "check-release-source.sh",
        "cloudflare-publish.sh",
        "build-service-release.sh",
    ):
        shutil.copyfile(SCRIPTS / name, scripts / name)
    # A sentinel proves dirty publication stops before dependency installation.
    (scripts / "bootstrap.sh").write_text(
        '#!/bin/sh\ntouch "$GUARD_TEST_BOOTSTRAP"\nexit 99\n'
    )
    binary = tmp_path / "bin"
    binary.mkdir()
    git = binary / "git"
    git.write_text(
        f"#!{sys.executable}\n"
        + """
import os
import sys
args = sys.argv[1:]
if args[:2] == ['submodule', 'update']:
    raise SystemExit(0)
path = args[1]
checker = path.endswith('/subprojects/inventory-checker')
if '--show-toplevel' in args:
    print(os.environ['GUARD_TEST_ROOT'] if checker and os.environ.get('FAKE_UNINITIALIZED') else path)
elif 'status' in args:
    state = os.environ.get('FAKE_CHECKER_DIRTY' if checker else 'FAKE_PARENT_DIRTY', '')
    if state.startswith('??') and '--untracked-files=all' not in args:
        state = ''
    print(state)
elif 'ls-tree' in args:
    print('160000 commit ' + 'a' * 40 + '\\tsubprojects/inventory-checker')
elif 'rev-parse' in args:
    print(('b' if os.environ.get('FAKE_WRONG_PIN') else 'a') * 40)
else:
    raise SystemExit('Unexpected Git command: ' + repr(args))
"""
    )
    git.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{binary}{os.pathsep}{os.environ['PATH']}",
        "GUARD_TEST_ROOT": str(workspace),
        "GUARD_TEST_BOOTSTRAP": str(tmp_path / "bootstrap-called"),
    }
    return workspace, env


def run_guard(workspace, env, args=()):
    return subprocess.run(
        ["sh", str(workspace / "scripts/check-release-source.sh"), *args],
        env=env,
        capture_output=True,
        text=True,
    )


def test_committed_clean_parent_and_exact_checker_pin_pass(guarded_workspace):
    workspace, env = guarded_workspace
    assert run_guard(workspace, env).returncode == 0


@pytest.mark.parametrize(
    "setting,value",
    [
        ("FAKE_PARENT_DIRTY", " M tracked.py"),
        ("FAKE_PARENT_DIRTY", "?? new-source.py"),
        ("FAKE_CHECKER_DIRTY", " M tracked.ts"),
        ("FAKE_CHECKER_DIRTY", "?? new-source.ts"),
        ("FAKE_WRONG_PIN", "1"),
        ("FAKE_UNINITIALIZED", "1"),
    ],
)
def test_source_changes_uninitialized_child_and_wrong_pin_reject(
    guarded_workspace, setting, value
):
    workspace, env = guarded_workspace
    result = run_guard(workspace, {**env, setting: value})
    assert result.returncode != 0
    assert "Release source check" in result.stderr


def test_uninitialized_mode_only_allows_initialization_not_dirty_sources(
    guarded_workspace,
):
    workspace, env = guarded_workspace
    env = {**env, "FAKE_UNINITIALIZED": "1"}
    assert run_guard(workspace, env, ["--allow-uninitialized"]).returncode == 0
    assert (
        run_guard(
            workspace,
            {**env, "FAKE_PARENT_DIRTY": "?? untracked"},
            ["--allow-uninitialized"],
        ).returncode
        != 0
    )


@pytest.mark.parametrize(
    "script,args",
    [
        ("cloudflare-publish.sh", ["deploy"]),
        ("cloudflare-publish.sh", ["versions", "upload"]),
        ("build-service-release.sh", []),
    ],
)
def test_dirty_publication_stops_before_bootstrap_or_network(
    guarded_workspace, script, args
):
    workspace, env = guarded_workspace
    result = subprocess.run(
        ["sh", str(workspace / "scripts" / script), *args],
        env={**env, "FAKE_PARENT_DIRTY": "?? new-source.py"},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "source changes" in result.stderr
    assert not Path(env["GUARD_TEST_BOOTSTRAP"]).exists()


@pytest.mark.parametrize("trailing_slash", [False, True])
@pytest.mark.parametrize(
    "entrypoint,args",
    [
        ("build-service-release.sh", []),
        ("cloudflare-publish.sh", ["versions", "upload"]),
    ],
)
def test_wrapped_release_discovers_base_python_before_bootstrap(
    guarded_workspace, trailing_slash, entrypoint, args
):
    workspace, env = guarded_workspace
    inherited = []
    for directory in (
        workspace / ".venv/bin",
        workspace / "subprojects/inventory-checker/.venv/bin",
        workspace.parent / "managed-home/.asdf/installs/python/3.13.3/bin",
    ):
        directory.mkdir(parents=True)
        python = directory / "python3"
        python.write_text("#!/bin/sh\nprintf '%s\\n' inherited-virtualenv\n")
        python.chmod(0o755)
        inherited.append(str(directory) + ("/" if trailing_slash else ""))
    bootstrap = workspace / "scripts/bootstrap.sh"
    bootstrap.write_text(
        '#!/bin/sh\npython3 -c "import os, sys; '
        "print(os.path.realpath(sys.executable)); "
        'print(sys.prefix == sys.base_prefix)" > "$GUARD_TEST_BOOTSTRAP"\nexit 99\n'
    )
    bootstrap.chmod(0o755)
    # Match nodew -> Wrangler -> custom build, including a child wrapper PATH.
    result = subprocess.run(
        ["sh", str(workspace / "scripts" / entrypoint), *args],
        env={**env, "PATH": os.pathsep.join([*inherited, env["PATH"]])},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 99, result.stderr
    assert Path(env["GUARD_TEST_BOOTSTRAP"]).read_text().splitlines() == [
        str(Path("/usr/bin/python3").resolve()),
        "True",
    ]
