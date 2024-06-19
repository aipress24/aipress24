# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import subprocess
import tempfile
import uuid
from pathlib import Path

import boto3
from flask_super.decorators import service
from loguru import logger
from svcs import Container

from .config import Config

TIMEOUT = 60


class ScreenshotError(Exception):
    pass


@service
class ScreenshotService:
    def __init__(self, svcs_container: Container):
        self.config = svcs_container.get(Config)

    def start_session(self, url):
        session = ScreenshotSession(url, self.config)
        session.run()
        return session


class ScreenshotSession:
    temp_file: str | None = None
    object_id: str | None = None

    def __init__(self, url, config):
        self.url = url
        self.config = config
        self.s3_region_name = config["S3_REGION_NAME"]
        self.s3_access_key_id = config["S3_ACCESS_KEY_ID"]
        self.s3_secret_access_key = config["S3_SECRET_ACCESS_KEY"]
        self.s3_bucket_name = config["S3_BUCKET_NAME"]
        self.s3_url = config["S3_URL"]

        self.temp_file = tempfile.mkstemp(suffix=".png")

    def run(self):
        try:
            self.take_screenshot()
            self.upload_image()
        except ScreenshotError:
            return
        finally:
            self.cleanup()

    def cleanup(self):
        if Path(self.temp_file).exists():
            Path(self.temp_file).unlink()

    def take_screenshot(self):
        args = [
            "shot-scraper",
            "shot",
            self.url,
            f"--output={self.temp_file}",
            "--width",
            "1024",
            "--height",
            "768",
            "--wait",
            "10000",
        ]
        result = subprocess.run(args, capture_output=True, timeout=TIMEOUT, check=False)
        status = result.returncode

        if status != 0:
            logger.info(
                "Error screenshotting",
                url=self.url,
                stdout=result.stdout,
                stderr=result.stderr,
            )
            raise ScreenshotError

        if not Path(self.temp_file).exists():
            raise ScreenshotError

        if Path(self.temp_file).stat().st_size < 10000:
            logger.info("Error screenshotting: size is too small", url=self.url)
            raise ScreenshotError

    def upload_image(self):
        self.object_id = uuid.uuid1().hex + ".png"

        session = boto3.Session(
            region_name=self.s3_region_name,
            aws_access_key_id=self.s3_access_key_id,
            aws_secret_access_key=self.s3_secret_access_key,
        )
        s3 = session.resource("s3", endpoint_url=self.s3_url)
        bucket = s3.Bucket(self.s3_bucket_name)
        with Path(self.temp_file).open("rb") as fd:
            bucket.upload_fileobj(fd, self.object_id, ExtraArgs={"ACL": "public-read"})
