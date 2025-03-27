#!/usr/bin/env python
import os
import subprocess

env = dict(**os.environ)
env["TEST_DATABASE_URI"] = "postgresql://localhost/aipress24_test"


def sh(cmd) -> int:
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result.returncode

while True:
    sh(["dropdb", "aipress24_test"])
    sh(["createdb", "aipress24_test"])

    sh(["uv", "sync"])
    status_code = sh(["pytest"])
    print("### Status code:", status_code)
    status_code = sh(["pytest"])
    print("### Status code:", status_code)

    sh(["git", "checkout", "HEAD~1"])
    commit_id = subprocess.check_output(["git", "rev-parse", "HEAD"]).strip()
    print("### Commit ID:", commit_id)
