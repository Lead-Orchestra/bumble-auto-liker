#!/usr/bin/env python3
"""Simple AWS S3 functionality test."""

import os
import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
backend_root = Path(__file__).parent.parent.parent.parent

# Load env
from dotenv import load_dotenv
load_dotenv(backend_root / '.env')

print("=" * 50)
print("AWS S3 Image Handler Test")
print("=" * 50)

# Test 1: Check credentials
print("\n[1] Checking AWS Credentials...")
access_key = os.getenv('AWS_ACCESS_KEY_ID')
secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
bucket = os.getenv('S3_BUCKET')
prefix = os.getenv('S3_PREFIX')

if access_key and secret_key:
    print(f"    Access Key: {access_key[:4]}...{access_key[-4:]}")
    print(f"    Secret Key: SET")
    print(f"    Bucket: {bucket}")
    print(f"    Prefix: {prefix}")
    print("    PASS: Credentials configured")
else:
    print("    FAIL: Missing credentials")
    sys.exit(1)

# Test 2: Handler initialization
print("\n[2] Testing S3 Handler Init...")
try:
    from s3_image_handler import S3ImageHandler
    handler = S3ImageHandler()
    print(f"    Handler bucket: {handler.bucket}")
    print("    PASS: Handler initialized")
except Exception as e:
    print(f"    FAIL: {e}")
    sys.exit(1)

# Test 3: Image download
print("\n[3] Testing Image Download...")
try:
    test_url = "https://images.pexels.com/photos/220453/pexels-photo-220453.jpeg?w=100"
    data = handler.download_image(test_url)
    print(f"    Downloaded: {len(data)} bytes")
    print("    PASS: Image downloaded")
except Exception as e:
    print(f"    FAIL: {e}")
    sys.exit(1)

# Test 4: S3 Upload
print("\n[4] Testing S3 Upload...")
try:
    key = handler._generate_s3_key("test_user", 0)
    print(f"    S3 Key: {key}")
    s3_url = handler.upload_to_s3(data, key)
    print(f"    S3 URL: {s3_url}")
    print("    PASS: Image uploaded to S3")
except Exception as e:
    print(f"    FAIL: {e}")
    sys.exit(1)

# Test 5: Process profile
print("\n[5] Testing Profile Processing...")
try:
    profile = {
        "name": "TestProfile",
        "age": 25,
        "image_urls": [test_url]
    }
    result = handler.process_profile_images(profile)
    print(f"    S3 URLs: {result.get('s3_image_urls', [])}")
    print("    PASS: Profile processed")
except Exception as e:
    print(f"    FAIL: {e}")
    sys.exit(1)

print("\n" + "=" * 50)
print("ALL TESTS PASSED!")
print("=" * 50)
