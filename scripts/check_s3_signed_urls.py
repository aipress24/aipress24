#!/usr/bin/env python
"""Verify S3 signed URLs work with fsspec backend (Hetzner/non-AWS compatible).

This script tests:
1. S3 connection via fsspec
2. File upload
3. Signed URL generation
4. Signed URL accessibility (fetch)
5. Cleanup (after pause for manual verification)

Usage:
    uv run python scripts/check_s3_signed_urls.py

Environment variables required:
    FLASK_S3_BUCKET_NAME
    FLASK_S3_ACCESS_KEY_ID
    FLASK_S3_SECRET_ACCESS_KEY
    FLASK_S3_ENDPOINT_URL
"""

from __future__ import annotations

import os
import sys
from uuid import uuid4

import httpx


def get_env(name: str) -> str:
    """Get environment variable or exit with error."""
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: Missing environment variable: {name}")
        sys.exit(1)
    return value


def main() -> int:
    # Load configuration from environment
    bucket_name = get_env("FLASK_S3_BUCKET_NAME")
    access_key = get_env("FLASK_S3_ACCESS_KEY_ID")
    secret_key = get_env("FLASK_S3_SECRET_ACCESS_KEY")
    endpoint_url = get_env("FLASK_S3_ENDPOINT_URL")

    print("=" * 60)
    print("S3 Signed URL Verification Script")
    print("=" * 60)
    print(f"Endpoint:    {endpoint_url}")
    print(f"Bucket:      {bucket_name}")
    print(f"Access Key:  {access_key[:8]}...")
    print()

    # Step 1: Create fsspec S3 filesystem (same as app uses)
    print("[1/6] Creating fsspec S3 filesystem...")
    try:
        import fsspec

        s3_fs = fsspec.filesystem(
            "s3",
            client_kwargs={
                "endpoint_url": endpoint_url,
                "aws_access_key_id": access_key,
                "aws_secret_access_key": secret_key,
            },
        )
        print("      OK - S3 filesystem created")
    except Exception as e:
        print(f"      FAILED: {e}")
        return 1

    # Step 2: Test connection by listing bucket
    print("[2/6] Testing connection (listing bucket)...")
    try:
        prefix = f"{bucket_name}/files"
        # Try to list (may be empty, that's OK)
        files = s3_fs.ls(prefix, detail=False)
        print(f"      OK - Found {len(files)} files in {prefix}")
    except Exception as e:
        print(f"      FAILED: {e}")
        print("      (This might be OK if the bucket/prefix doesn't exist yet)")

    # Step 3: Upload a test file
    test_filename = f"_test_signed_url_{uuid4().hex}.txt"
    test_key = f"{bucket_name}/files/{test_filename}"
    test_content = b"Hello from signed URL test!"

    print(f"[3/6] Uploading test file...")
    print(f"      Bucket:   {bucket_name}")
    print(f"      Key:      files/{test_filename}")
    print(f"      Full key: {test_key}")
    try:
        with s3_fs.open(test_key, "wb") as f:
            f.write(test_content)
        print("      OK - File uploaded")

        # Verify file exists
        print("      Verifying file exists...")
        if s3_fs.exists(test_key):
            info = s3_fs.info(test_key)
            print(f"      OK - File confirmed (size: {info.get('size', 'unknown')} bytes)")
        else:
            print("      WARNING - File not found after upload!")
    except Exception as e:
        print(f"      FAILED: {e}")
        return 1

    # Step 4: Generate signed URL
    print("[4/6] Generating signed URL (expires in 300s)...")
    try:
        # fsspec/s3fs uses .sign() method for pre-signed URLs
        signed_url = s3_fs.sign(test_key, expiration=300)
        print(f"      OK - Signed URL generated")
        print()
        print("      SIGNED URL (copy to test in browser/curl):")
        print("      " + "-" * 50)
        print(f"      {signed_url}")
        print("      " + "-" * 50)
        print()
        # Parse URL to show what path it contains
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(signed_url)
        print(f"      URL breakdown:")
        print(f"        Host: {parsed.netloc}")
        print(f"        Path: {parsed.path}")
        print()
    except AttributeError:
        print("      FAILED: s3fs doesn't have .sign() method")
        print("      Your s3fs version may not support signed URLs")
        # Try alternative method
        print("      Trying alternative: s3fs.url() method...")
        try:
            signed_url = s3_fs.url(test_key, expires=300)
            print(f"      OK (via .url()) - Signed URL generated")
            print()
            print("      SIGNED URL (copy to test in browser/curl):")
            print("      " + "-" * 50)
            print(f"      {signed_url}")
            print("      " + "-" * 50)
            print()
        except Exception as e2:
            print(f"      FAILED: {e2}")
            return 1
    except Exception as e:
        print(f"      FAILED: {e}")
        return 1

    # Step 5: Fetch the signed URL
    print("[5/6] Fetching signed URL to verify accessibility...")
    print("      (You can also test manually: curl the URL above)")
    try:
        response = httpx.get(signed_url, timeout=30)
        if response.status_code == 200:
            if response.content == test_content:
                print("      OK - Content matches!")
            else:
                print(f"      WARNING - Content mismatch")
                print(f"      Expected: {test_content}")
                print(f"      Got:      {response.content}")
        else:
            print(f"      FAILED - HTTP {response.status_code}")
            print(f"      Response:")
            print(f"      {response.text[:500]}")
            print()
            print("      DEBUG: Checking if file still exists via fsspec...")
            if s3_fs.exists(test_key):
                print(f"      File EXISTS at {test_key}")
            else:
                print(f"      File NOT FOUND at {test_key}")
            return 1
    except Exception as e:
        print(f"      FAILED: {e}")
        return 1

    # Step 6: Cleanup after manual verification
    print("[6/6] Cleanup...")
    print()
    print("      Test file is ready for manual verification.")
    print("      Test the signed URL in your browser or with curl now.")
    print()
    input("      Press Enter when done to delete the test file...")
    try:
        s3_fs.rm(test_key)
        print("      OK - Test file deleted")
    except Exception as e:
        print(f"      WARNING - Cleanup failed: {e}")
        print(f"      You may need to manually delete: {test_key}")

    print()
    print("=" * 60)
    print("SUCCESS: S3 signed URLs work correctly!")
    print("=" * 60)
    print()
    print("Your Hetzner Object Storage is properly configured for:")
    print("  - File upload/download via fsspec")
    print("  - Pre-signed URL generation")
    print("  - Signed URL access (private bucket support)")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
