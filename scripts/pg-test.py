#!/usr/bin/env python
import os
import subprocess

env = dict(**os.environ)
env["TEST_DATABASE_URI"] = "postgresql://localhost/aipress24_test"


def sh(cmd):
    print(f"Running: {cmd}")
    subprocess.check_call(cmd, env=env)


sh(["dropdb", "aipress24_test"])
sh(["createdb", "aipress24_test"])

sh(["pytest"])
sh(["pytest"])
