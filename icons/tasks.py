#!/usr/bin/env python3

# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

import os

from invoke import Context, task

REPOS = {
    "lucide": "https://github.com/lucide-icons/lucide.git",
    "heroicons": "https://github.com/tailwindlabs/heroicons.git",
}


def sh(cmd):
    print(cmd)
    status = os.system(cmd)
    if status != 0:
        raise Exception(f"Command failed: {cmd}")


@task
def update_heroicons(c: Context):
    name = "heroicons"

    os.makedirs("svg/outline", exist_ok=True)
    os.makedirs("svg/solid", exist_ok=True)

    checkout_repo(name)

    sh(f"cd git/{name} ; npm i ; npm run build")

    sh("cp -r git/heroicons/24/solid/*.svg svg/solid/")
    sh("cp -r git/heroicons/24/outline/*.svg svg/outline/")


@task
def update_lucide(c: Context):
    name = "lucide"

    os.makedirs("svg/lucide", exist_ok=True)

    checkout_repo(name)

    sh("cp -r git/lucide/icons/*.svg svg/lucide/")


@task
def cleanup(c: Context):
    sh("rm -rf git")


def checkout_repo(name):
    os.makedirs("git", exist_ok=True)
    repo = REPOS[name]
    if not os.path.exists(f"git/{name}"):
        sh(f"cd git ; git clone {repo}")
    else:
        sh(f"cd git/{name} ; git pull")
