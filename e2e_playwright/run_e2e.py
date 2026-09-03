#!/usr/bin/env python3
"""Boot a server, run the Playwright suite against it, tear it down.

The server's output goes to a log file rather than the terminal, so what
you see is pytest and nothing else — colours, progress line and all,
because pytest runs in the foreground on the real tty.

Knobs, all optional, read from the environment:

    MOD=kyc                  one module instead of the whole suite
    E2E_ALL=1                drop the marker filter: run everything
    E2E_MARKERS='not slow'   use this filter instead of the default
    E2E_BASE_URL=<url>       run against a server that is already up
                             (no server is started, nothing is stopped)
    E2E_PORT=8899            port for the throwaway server
    E2E_BROWSER=chromium     firefox / webkit (webkit hangs, see README)
    E2E_SERVER_LOG=<path>    where the server writes
    E2E_PYTEST_ARGS='-q'     replaces the default '-v'

`mutates_db` is excluded by default: those tests write to whatever
database the app is configured against, and the KYC signup ones create
real members. Running them is opt-in through `E2E_ALL`, and deliberately
not through an empty `E2E_MARKERS` — `export` in the Makefile hands
undefined variables down as empty, so empty has to keep meaning "use the
default".

Exits with pytest's status, so a failed suite fails `make` and CI.
"""

from __future__ import annotations

import contextlib
import os
import shlex
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_MARKERS = "not slow and not mutates_db"
DEFAULT_PORT = 8899
#: Chromium: about twice as quick as Firefox on this suite (kyc 14 s
#: vs 29 s, wire 43 s vs 72 s), and it does not stall on the aborted
#: Vite module graph the way Firefox does. WebKit hangs — see README.
DEFAULT_BROWSER = "chromium"
#: `/kyc/` is public, cheap and always 200 — this app has no health route.
DEFAULT_PROBE = "/kyc/"
STARTUP_TIMEOUT = 90
SHUTDOWN_GRACE = 5

#: FLASK_ACCEPT_ANY_PASSWORD lets the suite sign in whatever the database
#: holds: the CSV passwords do not match a restored production dump, and
#: the session-wide login probe in `conftest.py` skips *every* test when
#: the first one fails. FLASK_UNSECURE is required alongside it — the
#: flag on its own stops the app from starting rather than being ignored
#: — and it also opens the `/backdoor/` routes some tests use.
SERVER_ENV = {"FLASK_UNSECURE": "true", "FLASK_ACCEPT_ANY_PASSWORD": "true"}

#: `SERVER_NAME` is pinned to `127.0.0.1:5000` in the settings, and Flask
#: builds every absolute URL from it — so on any other port a redirect
#: sends the browser to a port where nothing is listening, and the test
#: dies on NS_ERROR_CONNECTION_REFUSED rather than on anything real. The
#: harness therefore tells the app which host it is actually answering on.


def stop_on_sigterm() -> None:
    """Turn SIGTERM into an exception so the server still gets stopped.

    Python runs no `finally` on the default SIGTERM disposition, so a
    `timeout`, a CI cancellation or a `kill` would leave the app holding
    the port. SIGINT already arrives as KeyboardInterrupt.
    """

    def raise_it(signum: int, _frame: object) -> None:
        raise KeyboardInterrupt(f"signal {signum}")

    signal.signal(signal.SIGTERM, raise_it)


def main() -> int:
    stop_on_sigterm()

    # pytest writes to the same file descriptor from a subprocess. Without
    # line buffering, our own prints sit in Python's buffer and surface
    # after its output whenever stdout is a pipe rather than a terminal.
    sys.stdout.reconfigure(line_buffering=True)

    browser = os.environ.get("E2E_BROWSER") or DEFAULT_BROWSER
    external = os.environ.get("E2E_BASE_URL")

    if external:
        print(f"Running against {external} (no server started).")
        return run_pytest(external, browser)

    port = int(os.environ.get("E2E_PORT") or DEFAULT_PORT)
    base_url = f"http://127.0.0.1:{port}"
    log_path = Path(
        os.environ.get("E2E_SERVER_LOG") or ROOT / "e2e_playwright" / "server.log"
    )

    if is_listening(port):
        print(
            f"Port {port} is already in use — stop what is on it, or set "
            f"E2E_PORT (or E2E_BASE_URL to use it as-is).",
            file=sys.stderr,
        )
        return 1

    with AppServer(port, log_path) as proc:
        if not wait_until_up(base_url, proc, log_path):
            return 1
        install_browser(browser)
        print()
        return run_pytest(base_url, browser)


class AppServer:
    """The throwaway app server, stopped whatever happens.

    Started in its own process group: `uv run` spawns flask as a child,
    so signalling the group is what actually stops the server rather
    than orphaning it on the port.
    """

    def __init__(self, port: int, log_path: Path) -> None:
        self.port = port
        self.log_path = log_path
        self.proc: subprocess.Popen | None = None

    def __enter__(self) -> subprocess.Popen:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log = self.log_path.open("w")
        self.proc = subprocess.Popen(
            [
                "uv",
                "run",
                "flask",
                "run",
                # `--debug` because `/debug/stripe` — the in-tree Stripe mock
                # the stripe tests drive — only mounts under `app.debug` or
                # behind an HTTP-Basic password the tests do not send. This is
                # what `make run` uses, and the suite is written for it.
                # `--no-reload` because the reloader would watch the tree,
                # including the server log written here, and restart mid-run.
                "--debug",
                "--no-reload",
                "--port",
                str(self.port),
                "--host",
                "127.0.0.1",
            ],
            cwd=ROOT,
            env={
                **os.environ,
                **SERVER_ENV,
                "FLASK_SERVER_NAME": f"127.0.0.1:{self.port}",
            },
            stdout=self.log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        return self.proc

    def __exit__(self, *exc_info: object) -> None:
        proc = self.proc
        if proc is not None and proc.poll() is None:
            signal_group(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=SHUTDOWN_GRACE)
            except subprocess.TimeoutExpired:
                signal_group(proc.pid, signal.SIGKILL)
        self.log.close()


def signal_group(pid: int, sig: int) -> None:
    """Signal the whole group: `uv run` spawns flask as a child."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(pid), sig)


def is_listening(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_until_up(base_url: str, proc: subprocess.Popen, log_path: Path) -> bool:
    """Poll the probe URL until it answers, or explain why it never did."""
    probe = base_url + (os.environ.get("E2E_PROBE") or DEFAULT_PROBE)
    print(f"Starting server on {base_url} (log: {log_path})", end="", flush=True)

    for _ in range(STARTUP_TIMEOUT):
        try:
            with urllib.request.urlopen(probe, timeout=2) as response:
                if response.status < 400:
                    print(" — up.")
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            pass
        if proc.poll() is not None:
            print()
            return complain("The server exited before answering.", log_path)
        print(".", end="", flush=True)
        time.sleep(1)

    print()
    return complain(f"The server never answered on {probe}.", log_path)


def complain(message: str, log_path: Path) -> bool:
    """Say what went wrong, with the end of the log nobody else will read."""
    print(f"{message} Last lines of {log_path}:", file=sys.stderr)
    try:
        tail = log_path.read_text().splitlines()[-20:]
    except OSError:
        tail = ["(the log could not be read)"]
    print("\n".join(tail), file=sys.stderr)
    return False


def install_browser(browser: str) -> None:
    """pytest-playwright is a dependency; its browser binary may not be.

    A browser that is already there is a no-op, and a failure here is not
    fatal: the run may still work with what is installed.
    """
    subprocess.run(
        ["uv", "run", "playwright", "install", browser],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def markers() -> str:
    if os.environ.get("E2E_ALL"):
        return ""
    return os.environ.get("E2E_MARKERS") or DEFAULT_MARKERS


def run_pytest(base_url: str, browser: str) -> int:
    """Run the suite in the foreground, so its output is the only output."""
    target = "e2e_playwright"
    if module := os.environ.get("MOD"):
        target = f"{target}/{module}"

    extra = os.environ.get("E2E_PYTEST_ARGS")
    args = shlex.split(extra) if extra else ["-v"]
    args += [target, "--browser", browser, "--base-url", base_url]
    if selected := markers():
        args += ["-m", selected]

    return subprocess.run(
        ["uv", "run", "pytest", *args], cwd=ROOT, check=False
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
