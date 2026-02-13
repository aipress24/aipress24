#!/usr/bin/env python
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Check S3 bucket access by uploading and downloading a test file.

Usage:
    flask run-script scripts/check_s3.py
    # or
    python scripts/check_s3.py
"""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

from app.flask.main import create_app


def check_s3_access() -> bool:
    """Test S3 bucket access by uploading and downloading a test file."""
    app = create_app()

    with app.app_context():
        config = app.config

        endpoint_url = config.get("S3_ENDPOINT_URL")
        access_key = config.get("S3_ACCESS_KEY_ID")
        secret_key = config.get("S3_SECRET_ACCESS_KEY")
        bucket_name = config.get("S3_BUCKET_NAME")

        # Check configuration
        missing = []
        if not endpoint_url:
            missing.append("S3_ENDPOINT_URL")
        if not access_key:
            missing.append("S3_ACCESS_KEY_ID")
        if not secret_key:
            missing.append("S3_SECRET_ACCESS_KEY")
        if not bucket_name:
            missing.append("S3_BUCKET_NAME")

        if missing:
            print(f"ERROR: Missing configuration: {', '.join(missing)}")
            return False

        print(f"S3 Endpoint: {endpoint_url}")
        print(f"S3 Bucket:   {bucket_name}")
        print(f"Access Key:  {access_key[:8]}...")
        print()

        # Create S3 client
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

        # Generate test file
        test_key = f"_test/{uuid.uuid4().hex}.txt"
        test_content = f"S3 access test - {datetime.now(UTC).isoformat()}"

        try:
            # Test 1: Upload
            print(f"[1/4] Uploading test file: {test_key}")
            s3.put_object(
                Bucket=bucket_name,
                Key=test_key,
                Body=test_content.encode("utf-8"),
                ContentType="text/plain",
            )
            print("      OK")

            # Test 2: Check existence
            print(f"[2/4] Checking file exists...")
            s3.head_object(Bucket=bucket_name, Key=test_key)
            print("      OK")

            # Test 3: Download and verify
            print(f"[3/4] Downloading and verifying content...")
            response = s3.get_object(Bucket=bucket_name, Key=test_key)
            downloaded_content = response["Body"].read().decode("utf-8")
            if downloaded_content != test_content:
                print("      ERROR: Content mismatch!")
                return False
            print("      OK")

            # Test 4: Delete
            print(f"[4/4] Deleting test file...")
            s3.delete_object(Bucket=bucket_name, Key=test_key)
            print("      OK")

            print()
            print("SUCCESS: All S3 operations completed successfully!")
            return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            print(f"      ERROR: {error_code} - {error_msg}")
            return False
        except Exception as e:
            print(f"      ERROR: {e}")
            return False


if __name__ == "__main__":
    success = check_s3_access()
    sys.exit(0 if success else 1)
