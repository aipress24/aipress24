#!/usr/bin/env python3
# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Run the Playwright e2e suite with a fresh, properly-configured
dev server.

Why a wrapper script ?

- The Werkzeug dev server (``flask --debug run --reload``) is only
  marginally threaded. Under sustained Playwright load (many
  parallel sub-resources per page, htmx / Vite / debug-toolbar
  scripts, websockets), it serializes badly enough that
  ``domcontentloaded`` can stall arbitrarily long. Starting a
  fresh server right before the run and tearing it down right
  after eliminates the « long-running dev server accumulating
  state » class of flakiness.
- Coverage tracking needs ``COVERAGE_PROCESS_START`` to point at
  ``pyproject.toml`` so subprocess coverage works (used by
  flask-coverage).
- Pytest needs a stack of CLI flags (`--base-url`, `--browser`,
  rerun policy, …) that are tedious to type each time.

Usage
-----

::

    # Full e2e suite, default browser (firefox).
    uv run scripts/run_e2e.py

    # A specific test file or single test.
    uv run scripts/run_e2e.py e2e_playwright/cross_modules/

    uv run scripts/run_e2e.py \\
        e2e_playwright/regressions/test_resolved_bugs.py::test_bug_0050_pr_card_renders_direct_pricing_link

    # Pass extra pytest args after `--`.
    uv run scripts/run_e2e.py e2e_playwright/wire/ -- -k purchase --tb=long

    # Run on chromium instead.
    uv run scripts/run_e2e.py --browser=chromium

    # Reuse an already-running dev server (no spawn / no teardown).
    uv run scripts/run_e2e.py --no-server

    # Stop on first failure (mirrors `pytest -x`).
    uv run scripts/run_e2e.py -x e2e_playwright/admin/

The script splits args at the first ``--`` : everything before
goes to ``run_e2e.py`` itself (test paths + a few flags below),
everything after is forwarded verbatim to ``pytest``.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import IO

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "http://127.0.0.1:5000"
SERVER_HEALTH_PATH = "/auth/login"  # cheap, always present, returns 200 or 302
SERVER_BOOT_TIMEOUT_S = 20
SERVER_SHUTDOWN_TIMEOUT_S = 10
LOGS_DIR = ROOT / "local-notes" / "e2e-logs"


def main() -> int:
    args, pytest_extra = _parse_args()

    base_url = args.base_url
    run_id = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = LOGS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    server_log = run_dir / "server.log"
    pytest_log = run_dir / "pytest.log"

    print(f"[run_e2e] logs : {run_dir}/", file=sys.stderr)

    server_proc: subprocess.Popen | None = None
    server_tee: _Tee | None = None
    try:
        if not args.no_server:
            if _server_already_up(base_url):
                print(
                    f"[run_e2e] {base_url} already responding ; "
                    "use --no-server to opt-in to reuse, or stop "
                    "the running server first.",
                    file=sys.stderr,
                )
                return 2
            server_proc, server_tee = _spawn_server(server_log)
            if not _wait_for_server(base_url, SERVER_BOOT_TIMEOUT_S):
                print(
                    f"[run_e2e] server didn't come up within "
                    f"{SERVER_BOOT_TIMEOUT_S} s — aborting "
                    f"(server.log : {server_log}).",
                    file=sys.stderr,
                )
                return 3
        elif not _server_already_up(base_url):
            print(
                f"[run_e2e] --no-server but {base_url} is unreachable.",
                file=sys.stderr,
            )
            return 4

        return _run_pytest(
            test_targets=args.tests,
            base_url=base_url,
            browser=args.browser,
            stop_on_first=args.stop_on_first,
            verbose=args.verbose,
            extra=pytest_extra,
            log_path=pytest_log,
        )
    finally:
        if server_proc is not None:
            _shutdown_server(server_proc)
        if server_tee is not None:
            server_tee.close()
        print(
            f"[run_e2e] logs saved to {run_dir}/ "
            f"(server.log, pytest.log)",
            file=sys.stderr,
        )


def _parse_args() -> tuple[argparse.Namespace, list[str]]:
    """Split argv at ``--`` so extra pytest args pass through.

    `argparse.parse_known_args` would also work, but explicit
    splitting documents the convention better and lets us print a
    cleaner help.
    """
    raw = sys.argv[1:]
    if "--" in raw:
        idx = raw.index("--")
        own_args, pytest_extra = raw[:idx], raw[idx + 1 :]
    else:
        own_args, pytest_extra = raw, []

    parser = argparse.ArgumentParser(
        prog="run_e2e.py",
        description=(
            "Spawn the dev server, run the Playwright e2e suite "
            "with sane defaults, then tear the server down."
        ),
    )
    parser.add_argument(
        "tests",
        nargs="*",
        default=["e2e_playwright/"],
        help=(
            "Test paths or nodeids to run. Defaults to the entire "
            "`e2e_playwright/` tree."
        ),
    )
    parser.add_argument(
        "--browser",
        default="firefox",
        choices=("firefox", "chromium", "webkit"),
        help="Playwright browser. Default: firefox.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"App base URL. Default: {DEFAULT_BASE_URL}.",
    )
    parser.add_argument(
        "--no-server",
        action="store_true",
        help=(
            "Don't spawn (or stop) the dev server ; assume one is "
            "already running at --base-url."
        ),
    )
    parser.add_argument(
        "-x",
        "--stop-on-first",
        action="store_true",
        help="Stop pytest after the first failure (forwards `-x`).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbose output (forwards `-v`/`-vv` to pytest).",
    )

    return parser.parse_args(own_args), pytest_extra


def _server_already_up(base_url: str) -> bool:
    try:
        urllib.request.urlopen(  # noqa: S310 — local URL by design
            f"{base_url}{SERVER_HEALTH_PATH}", timeout=2
        )
        return True
    except (urllib.error.URLError, ConnectionError, OSError):
        return False


def _spawn_server(
    log_path: Path,
) -> tuple[subprocess.Popen, _Tee]:
    """Spawn `make run` (which itself runs `honcho -f Procfile-dev
    start`) with `COVERAGE_PROCESS_START` set so subprocess
    coverage tracking works.

    Returns the `Popen` handle and a `_Tee` that drains the
    child's combined stdout/stderr to ``log_path``. Server logs
    are NOT mirrored to the console — they would drown out the
    pytest feed, and the file is right there for postmortem.
    """
    env = os.environ.copy()
    env["COVERAGE_PROCESS_START"] = str(ROOT / "pyproject.toml")
    # Stop Python from buffering child stdout — without this,
    # `make run` output only flushes when the buffer fills, which
    # means the live console feed lags by chunks.
    env.setdefault("PYTHONUNBUFFERED", "1")
    print(
        f"[run_e2e] spawning dev server : "
        f"COVERAGE_PROCESS_START={env['COVERAGE_PROCESS_START']} "
        f"make run",
        file=sys.stderr,
    )
    # `start_new_session=True` puts the child in its own process
    # group so SIGTERM/SIGINT to it (via os.killpg) takes down
    # honcho + the worker(s) it spawned.
    proc = subprocess.Popen(
        ["make", "run"],
        cwd=ROOT,
        env=env,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,  # line-buffered
        text=True,
    )
    assert proc.stdout is not None  # for type checker
    tee = _Tee(proc.stdout, log_path, mirror=None)
    tee.start()
    return proc, tee


def _wait_for_server(base_url: str, timeout_s: int) -> bool:
    """Poll the health URL until the server answers or timeout."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _server_already_up(base_url):
            print(
                f"[run_e2e] dev server up at {base_url}",
                file=sys.stderr,
            )
            return True
        time.sleep(0.5)
    return False


def _shutdown_server(proc: subprocess.Popen) -> None:
    """SIGTERM the whole process group, then SIGKILL fallback."""
    print("[run_e2e] stopping dev server …", file=sys.stderr)
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        proc.wait(timeout=SERVER_SHUTDOWN_TIMEOUT_S)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        return
    proc.wait()


def _run_pytest(
    *,
    test_targets: Iterable[str],
    base_url: str,
    browser: str,
    stop_on_first: bool,
    verbose: int,
    extra: list[str],
    log_path: Path,
) -> int:
    """Build the `uv run pytest …` command and execute it.

    Pytest's combined stdout/stderr is teed to ``log_path`` and
    mirrored to the user's stdout — so the run prints live to the
    console *and* every line is preserved verbatim on disk."""
    cmd: list[str] = [
        "uv",
        "run",
        "pytest",
        f"--base-url={base_url}",
        f"--browser={browser}",
        # Force colored output even when stdout is a pipe (which
        # it is, since we're tee-ing). Without this pytest detects
        # « not a TTY » and strips ANSI codes.
        "--color=yes",
        # Per-test timeout. Belt-and-braces against a hung route
        # — a single test should never block the whole suite for
        # more than 5 min. Requires `pytest-timeout` ; flag is
        # silently dropped if the plugin isn't installed.
        *_optional_plugin_flags(
            "pytest_timeout", ["--timeout=300"]
        ),
        # Retry on transient timeouts only (not assertion errors).
        # Requires `pytest-rerunfailures`. If it's not installed,
        # the flag is silently dropped — see comment below.
        *_rerun_flags(),
        # `-r s` → show skipped reasons in the summary, helpful
        # when a test self-skips on missing seed data.
        "-r", "sx",
        # `--tb=short` is the right default for e2e — full
        # tracebacks rarely add value when the failure is at a
        # `page.goto` line.
        "--tb=short",
    ]
    if stop_on_first:
        cmd.append("-x")
    if verbose >= 2:
        cmd.append("-vv")
    elif verbose == 1:
        cmd.append("-v")
    cmd.extend(extra)
    cmd.extend(test_targets)

    print(
        "[run_e2e] running : " + " ".join(cmd),
        file=sys.stderr,
    )
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        text=True,
    )
    assert proc.stdout is not None
    tee = _Tee(proc.stdout, log_path, mirror=sys.stdout)
    tee.start()
    rc = proc.wait()
    tee.close()
    return rc


def _rerun_flags() -> list[str]:
    """Return rerun flags only if pytest-rerunfailures is
    installed. Avoids hard failure when the user hasn't added the
    dep yet."""
    return _optional_plugin_flags(
        "pytest_rerunfailures",
        [
            "--reruns=1",
            "--reruns-delay=2",
            # Only rerun on transient browser timeouts — never on
            # AssertionError, since that hides real bugs.
            "--only-rerun=TimeoutError",
        ],
    )


class _Tee:
    """Drain a child-process pipe to a log file, optionally
    mirroring to a console stream.

    Why a thread : ``Popen.stdout.readline()`` blocks until the
    child writes a newline. Doing that on the main thread would
    serialize « server is running » with « wait for tests to
    finish » ; one tee per piped child runs in its own thread
    instead.

    The log file gets each line prefixed with an HH:MM:SS.mmm
    timestamp so chronology can be reconstructed even when the
    server's own log lines (which already carry honcho timestamps)
    interleave with pytest output across files. ``mirror=None``
    keeps the line off the console — used for the server, whose
    logs would otherwise drown out the pytest feed."""

    def __init__(
        self, source: IO[str], log_path: Path, *, mirror: IO | None
    ) -> None:
        self._source = source
        self._log = log_path.open("w", encoding="utf-8", buffering=1)
        self._mirror = mirror
        self._thread = threading.Thread(
            target=self._pump, daemon=True, name=f"tee-{log_path.name}"
        )

    def start(self) -> None:
        self._thread.start()

    def _pump(self) -> None:
        for line in self._source:
            ts = _dt.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            try:
                self._log.write(f"{ts} {line}")
            except (OSError, ValueError):
                pass
            if self._mirror is not None:
                try:
                    self._mirror.write(line)
                    self._mirror.flush()
                except (OSError, ValueError):
                    pass

    def close(self) -> None:
        # Wait briefly for the pump to drain (the source pipe will
        # be at EOF once the child exits). Don't block forever ;
        # if the child hung past SIGKILL there's nothing to flush.
        self._thread.join(timeout=2)
        try:
            self._log.close()
        except OSError:
            pass


def _optional_plugin_flags(module: str, flags: list[str]) -> list[str]:
    """Return ``flags`` iff ``import module`` succeeds, else `[]`.

    Lets the wrapper opt into pytest plugins without making them
    hard requirements — the user can `uv add` them when they want
    the extra hardening."""
    if shutil.which("uv") is None:
        return []
    probe = subprocess.run(
        ["uv", "run", "python", "-c", f"import {module}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return flags if probe.returncode == 0 else []


if __name__ == "__main__":
    sys.exit(main())
