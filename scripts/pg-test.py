#!/usr/bin/env python
import os
import subprocess
import sys

env = dict(**os.environ)
env["TEST_DATABASE_URI"] = "postgresql://localhost/aipress24_test"


def sh(cmd) -> int:
    # print(f"Running: {cmd}")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result.stdout, result.returncode


def test_commit() -> int:
    commit_id = subprocess.check_output(["git", "rev-parse", "HEAD"]).strip()
    print("### Commit ID:", commit_id)
    sh(["dropdb", "aipress24_test"])
    sh(["createdb", "aipress24_test"])
    sh(["uv", "sync", "--frozen"])

    # ignore first test run, just in case
    sh(["pytest", "-x"])

    stdout, status_code = sh(["pytest", "-x"])
    print("### Status code:", status_code)
    if status_code > 0:
        info = [line for line in stdout.splitlines() if line.startswith("FAILED")]
        if info:
            print("###", info[0])
    return status_code


while True:
    if test_commit() == 0:
        sys.exit()
    print()
    sh(["git", "checkout", "HEAD~1"])
