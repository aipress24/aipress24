# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

import contextlib
import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, BrowserContext, Error, Page
from slugify import slugify

try:
    from pytest_playwright.pytest_playwright import _build_artifact_test_folder
except ImportError:
    # Fallback for newer versions of pytest-playwright
    def _build_artifact_test_folder(
        pytestconfig: Any, request: pytest.FixtureRequest, suffix: str
    ) -> str:
        output_dir = pytestconfig.getoption("--output")
        return str(Path(output_dir) / slugify(request.node.nodeid) / suffix)


@pytest.fixture(scope="session")
def base_url(request):
    base_url = request.config.getoption("--base-url")
    if not base_url:
        return "http://127.0.0.1:5000"
    else:
        return base_url


@pytest.fixture(scope="session")
def context(  # noqa
    browser: Browser,
    browser_context_args: dict,
    pytestconfig: Any,
    request: pytest.FixtureRequest,
) -> Generator[BrowserContext, None, None]:
    pages: list[Page] = []
    context = browser.new_context(**browser_context_args)
    context.on("page", pages.append)

    tracing_option = pytestconfig.getoption("--tracing")
    capture_trace = tracing_option in ["on", "retain-on-failure"]
    if capture_trace:
        context.tracing.start(
            name=slugify(request.node.nodeid),
            screenshots=True,
            snapshots=True,
            sources=True,
        )

    yield context

    # If requst.node is missing rep_call, then some error happened during execution
    # that prevented teardown, but should still be counted as a failure
    failed = request.node.rep_call.failed if hasattr(request.node, "rep_call") else True

    if capture_trace:
        retain_trace = tracing_option == "on" or (
            failed and tracing_option == "retain-on-failure"
        )
        if retain_trace:
            trace_path = _build_artifact_test_folder(pytestconfig, request, "trace.zip")
            context.tracing.stop(path=trace_path)
        else:
            context.tracing.stop()

    screenshot_option = pytestconfig.getoption("--screenshot")
    capture_screenshot = screenshot_option == "on" or (
        failed and screenshot_option == "only-on-failure"
    )
    if capture_screenshot:
        for index, page in enumerate(pages):
            human_readable_status = "failed" if failed else "finished"
            screenshot_path = _build_artifact_test_folder(
                pytestconfig, request, f"test-{human_readable_status}-{index+1}.png"
            )
            with contextlib.suppress(Error):
                page.screenshot(timeout=5000, path=screenshot_path)

    context.close()

    video_option = pytestconfig.getoption("--video")
    preserve_video = video_option == "on" or (
        failed and video_option == "retain-on-failure"
    )
    if preserve_video:
        for page in pages:
            video = page.video
            if not video:
                continue
            try:
                video_path = video.path()
                file_name = os.path.basename(video_path)
                video.save_as(
                    path=_build_artifact_test_folder(pytestconfig, request, file_name)
                )
            except Error:
                # Silent catch empty videos.
                pass


@pytest.fixture(scope="session")
def page(context: BrowserContext) -> Generator[Page, None, None]:
    page = context.new_page()
    page._current_role = None
    yield page
