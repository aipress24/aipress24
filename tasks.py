# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
from pathlib import Path

import abilian_devtools.invoke
import toml
from invoke import Context, task

abilian_devtools.invoke.import_tasks(locals())

NUA_HOST = "c17.abilian.com"
NUA_DOMAIN = "aipress24.c17.abilian.com"
NUA_ENV = "/home/nua/env"

DIM = "\033[2m"
RESET = "\033[0m"
BRIGHT = "\033[1m"

EXCLUDES = [
    ".git",
    ".env",
    ".venv",
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".nox",
    ".tox",
    ".coverage",
    ".idea",
    "dist",
    "build",
    "data",
    "doc",
    "vite/node_modules/",
    "front-old",
    "tmp",
    "sandbox",
]


@task
def nua_deploy(c: Context, host=NUA_HOST, domain=NUA_DOMAIN) -> None:
    nua_build_(c, host=host)
    nua_deploy_(c, host=host, domain=domain)


@task
def nua_build_(c: Context, host=NUA_HOST) -> None:
    c.run("make -s clean")

    config = get_config()
    app_id = config["metadata"]["id"]

    build_dir = tempfile.mkdtemp(prefix=f"nua-build-{app_id}-", dir="/tmp")
    # build_dir = f"/tmp/nua-build/{app_id}"

    print(f"{BRIGHT}Building app {app_id}...{RESET}")

    excludes_args = " ".join([f"--exclude={e}" for e in EXCLUDES])
    ssh(f"mkdir -p {build_dir}", host=host)
    sh(f"rsync -e ssh --delete-after -az {excludes_args} ./ nua@{host}:{build_dir}")

    ssh(f"{NUA_ENV}/bin/nua-build {build_dir}", host)

    # sh(f"nua-build .", cwd=cwd)
    print()


@task
def nua_deploy_(c: Context, host=NUA_HOST, domain=NUA_DOMAIN) -> None:
    """Deploy all apps."""
    config = get_config()
    app_id = config["metadata"]["id"]
    deploy_config = {
        "site": [
            {
                "image": app_id,
                "domain": domain,
            }
        ],
    }

    temp_dir = tempfile.mkdtemp(prefix=f"nua-deploy-{app_id}-", dir="/tmp")
    config_file = Path(temp_dir) / "deploy.json"
    Path(config_file).write_text(json.dumps(deploy_config, indent=2))

    sh(f"rsync -az --mkpath {config_file} root@{host}:{config_file}")
    ssh(f"{NUA_ENV}/bin/nua-orchestrator deploy {config_file}", host)


# helpers
def sh(cmd: str, cwd: str = ".") -> None:
    """Run a shell command."""
    print(f'{DIM}Running "{cmd}" locally in "{cwd}"...{RESET}')
    args = shlex.split(cmd)
    try:
        subprocess.run(args, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e.cmd}")


def ssh(cmd: str, host: str) -> None:
    """Run a ssh command."""
    print(f'{DIM}Running "{cmd}" on server...{RESET}')
    args = shlex.split(cmd)
    cmd = ["ssh", f"nua@{host}", f"{shlex.join(args)}"]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e.cmd}")


def get_config() -> dict:
    config_file = Path("nua/nua-config.toml")
    config_data = config_file.read_text()
    return toml.loads(config_data)
