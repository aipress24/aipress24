#!/usr/bin/env python3
# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Run the Playwright e2e suite against a foreground dev server.

Server lifecycle
----------------

- **First run** — spawns ``make run`` (honcho + Procfile-dev),
  waits for ``/auth/login`` to answer, runs pytest, then **blocks
  in foreground** holding the server. The user can re-run pytest
  in another terminal (``run_e2e.py --no-server <args>``), tail
  the server log, etc. Ctrl-C in this terminal triggers a clean
  SIGTERM to the whole honcho/vite/backend process group.
- **Subsequent runs** (server already up) — detects the running
  server and reuses it, skipping the ~30 s cold boot. The script
  exits as soon as pytest finishes ; ownership stays with the
  process that spawned the server.
- **--no-server** — refuses to start if the server isn't already
  up. Useful for iterating with a server kept up by another
  ``run_e2e.py`` instance, or by ``make run`` in another tab.

Why foreground supervision ? The `make run` ergonomic — one
script holds the server, you Ctrl-C to stop everything, no leaked
processes. But you also want tests to run automatically up front,
without a second window.

Why this script and not raw ``pytest`` ?

- Coverage tracking needs ``COVERAGE_PROCESS_START`` to point at
  ``pyproject.toml`` so subprocess coverage works (used by
  flask-coverage).
- Pytest needs a stack of CLI flags (``--base-url``,
  ``--browser``, rerun policy, …) that are tedious to type each
  time.
- Server logs go to a timestamped file
  (``local-notes/e2e-logs/<run_id>/server.log``) so the live
  pytest feed doesn't mix with backend output.

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

    # Force « no spawn » mode (errors if no server is up).
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
    spawned_now = False
    if args.no_server:
        if not _server_already_up(base_url):
            print(
                f"[run_e2e] --no-server but {base_url} is unreachable.",
                file=sys.stderr,
            )
            return 4
    elif _server_already_up(base_url):
        # Reuse a server already running on this port — first run
        # spawns it, subsequent runs skip the ~30 s cold boot.
        print(
            f"[run_e2e] reusing existing server at {base_url}",
            file=sys.stderr,
        )
    else:
        server_proc = _spawn_server(server_log)
        spawned_now = True
        if not _wait_for_server(base_url, SERVER_BOOT_TIMEOUT_S):
            print(
                f"[run_e2e] server didn't come up within "
                f"{SERVER_BOOT_TIMEOUT_S} s — aborting "
                f"(server.log : {server_log}).",
                file=sys.stderr,
            )
            return 3

    rc = _run_pytest(
        test_targets=args.tests,
        base_url=base_url,
        browser=args.browser,
        stop_on_first=args.stop_on_first,
        verbose=args.verbose,
        extra=pytest_extra,
        log_path=pytest_log,
    )

    print(
        f"[run_e2e] logs saved to {run_dir}/ "
        f"(server.log, pytest.log)",
        file=sys.stderr,
    )

    # If we spawned the server, this script owns it — block in
    # foreground so the user can keep iterating (re-run pytest in
    # another terminal with --no-server, watch the server log,
    # etc.). Ctrl-C / SIGTERM triggers a clean shutdown of the
    # whole honcho/vite/backend process group via explicit signal
    # handlers (relying on Python's default `KeyboardInterrupt`
    # is unreliable under `uv run` and similar wrappers — they
    # may swallow or delay the signal).
    #
    # If we reused an existing server, we don't own it ; exit
    # immediately and let whoever started it keep ownership.
    # Same when --no-server was passed.
    if spawned_now and server_proc is not None:
        _install_shutdown_handlers(server_proc)
        print(
            f"[run_e2e] tests done (rc={rc}). Server still up "
            f"(pid {server_proc.pid}). Press Ctrl-C to stop the "
            "server and exit.",
            file=sys.stderr,
        )
        print(
            f"[run_e2e] tail server log : tail -f {server_log}",
            file=sys.stderr,
        )
        # Block until the server exits or a signal handler calls
        # `sys.exit()`. `proc.wait()` is interruptible by signals
        # delivered to the main thread.
        try:
            server_proc.wait()
        except KeyboardInterrupt:
            # Belt-and-braces : if KeyboardInterrupt did escape
            # the signal handler somehow, still shut down.
            _shutdown_server(server_proc)
            return 130
        print(
            f"[run_e2e] server exited on its own "
            f"(rc={server_proc.returncode}).",
            file=sys.stderr,
        )
    return rc


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
            "Run the Playwright e2e suite against a dev server. "
            "Spawns the server on first run, reuses it on "
            "subsequent runs (the server is left running between "
            "invocations — stop it manually with `pkill -f "
            "'flask --debug run'`)."
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
            "Don't spawn the dev server (require one to be "
            "running at --base-url already). Without this flag, "
            "the script auto-detects an existing server and "
            "reuses it ; this flag turns the missing-server "
            "case into an error instead."
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


def _spawn_server(log_path: Path) -> subprocess.Popen:
    """Spawn `make run` (which itself runs `honcho -f Procfile-dev
    start`) with `COVERAGE_PROCESS_START` set so subprocess
    coverage tracking works.

    The server's combined stdout+stderr is redirected DIRECTLY to
    ``log_path`` (no pipe through this process). Two consequences :

    1. The server keeps writing to the file even after this
       script exits — which is what we want, since we leave the
       server running between runs.
    2. We can't add per-line timestamps to the log ourselves ; we
       rely on honcho's built-in `HH:MM:SS process |` prefix.
    """
    env = os.environ.copy()
    env["COVERAGE_PROCESS_START"] = str(ROOT / "pyproject.toml")
    # Stop Python from buffering child stdout — without this the
    # server log file only flushes when the buffer fills.
    env.setdefault("PYTHONUNBUFFERED", "1")
    print(
        f"[run_e2e] spawning dev server : "
        f"COVERAGE_PROCESS_START={env['COVERAGE_PROCESS_START']} "
        f"make run",
        file=sys.stderr,
    )
    log_fp = log_path.open("w", encoding="utf-8", buffering=1)
    # `start_new_session=True` decouples the child from this
    # process group so it survives our exit cleanly.
    return subprocess.Popen(
        ["make", "run"],
        cwd=ROOT,
        env=env,
        start_new_session=True,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
    )


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


def _install_shutdown_handlers(server_proc: subprocess.Popen) -> None:
    """Install SIGINT/SIGTERM handlers that shut the server down
    and exit cleanly.

    Why explicit handlers and not Python's default Ctrl-C →
    KeyboardInterrupt machinery ? Wrappers like ``uv run`` can
    swallow or delay SIGINT delivery to the child Python process ;
    a registered handler bypasses that. The handler is registered
    AFTER pytest finishes so it doesn't interfere with pytest's
    own Ctrl-C handling during the test run.

    The exit code on signal is 128 + signum (the conventional
    shell convention) — preserves visibility into « was this a
    clean run that finished, or a Ctrl-C kill ? ».
    """

    def _handler(signum: int, _frame: object) -> None:
        sig_name = signal.Signals(signum).name
        print(
            f"\n[run_e2e] {sig_name} received, stopping dev server …",
            file=sys.stderr,
        )
        _shutdown_server(server_proc)
        # Use `os._exit` to bypass any cleanup that might re-raise
        # a different signal — we've already done the cleanup we
        # care about (server shutdown).
        os._exit(128 + signum)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def _shutdown_server(proc: subprocess.Popen) -> None:
    """SIGTERM the whole process group, then SIGKILL fallback."""
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
