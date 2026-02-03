#!/usr/bin/env python3
"""
Test suite for S3 Image Handler functionality.
Tests AWS S3 integration for Bumble profile image uploads.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv
backend_root = Path(__file__).parent.parent.parent.parent
load_dotenv(backend_root / '.env')


class TestS3ImageHandler(unittest.TestCase):
    """Test S3 Image Handler functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        cls.test_image_url = "https://images.pexels.com/photos/220453/pexels-photo-220453.jpeg?w=100"
        cls.test_profile_name = "TestUser"
        
    def test_handler_initialization(self):
        """Test S3ImageHandler initializes with credentials from environment."""
        try:
            from s3_image_handler import S3ImageHandler
            handler = S3ImageHandler()
            
            self.assertIsNotNone(handler.bucket)
            self.assertIsNotNone(handler.s3_client)
            print(f"✅ Handler initialized with bucket: {handler.bucket}")
        except ImportError as e:
            self.skipTest(f"boto3 not installed: {e}")
        except Exception as e:
            self.fail(f"Failed to initialize handler: {e}")
    
    def test_image_download(self):
        """Test downloading an image from URL."""
        try:
            from s3_image_handler import S3ImageHandler
            handler = S3ImageHandler()
            
            image_data = handler.download_image(self.test_image_url)
            
            self.assertIsNotNone(image_data)
            self.assertGreater(len(image_data), 0)
            print(f"✅ Downloaded image: {len(image_data)} bytes")
        except ImportError:
            self.skipTest("boto3 not installed")
        except Exception as e:
            self.fail(f"Failed to download image: {e}")
    
    def test_s3_key_generation(self):
        """Test S3 key generation format."""
        try:
            from s3_image_handler import S3ImageHandler
            handler = S3ImageHandler()
            
            key = handler._generate_s3_key(self.test_profile_name, 0)
            
            self.assertIn(handler.prefix, key)
            self.assertIn(self.test_profile_name.lower().replace(" ", "_"), key)
            self.assertTrue(key.endswith('.jpg'))
            print(f"✅ Generated S3 key: {key}")
        except ImportError:
            self.skipTest("boto3 not installed")
        except Exception as e:
            self.fail(f"Failed to generate S3 key: {e}")
    
    def test_full_upload_flow(self):
        """Test complete image upload to S3."""
        try:
            from s3_image_handler import S3ImageHandler
            handler = S3ImageHandler()
            
            # Download image
            image_data = handler.download_image(self.test_image_url)
            self.assertIsNotNone(image_data)
            
            # Generate key
            key = handler._generate_s3_key(self.test_profile_name, 0)
            
            # Upload to S3
            s3_url = handler.upload_to_s3(image_data, key)
            
            self.assertIsNotNone(s3_url)
            self.assertIn("s3.amazonaws.com", s3_url)
            print(f"✅ Uploaded to S3: {s3_url}")
            
            return s3_url
        except ImportError:
            self.skipTest("boto3 not installed")
        except Exception as e:
            self.fail(f"Failed to upload image: {e}")
    
    def test_process_profile_images(self):
        """Test processing a complete profile with images."""
        try:
            from s3_image_handler import S3ImageHandler
            handler = S3ImageHandler()
            
            # Create mock profile data
            profile_data = {
                "name": "TestProfile",
                "age": 25,
                "image_urls": [self.test_image_url]
            }
            
            # Process profile images
            result = handler.process_profile_images(profile_data)
            
            self.assertIn("s3_image_urls", result)
            self.assertEqual(len(result["s3_image_urls"]), 1)
            self.assertIn("s3.amazonaws.com", result["s3_image_urls"][0])
            print(f"✅ Profile processed with S3 URLs: {result['s3_image_urls']}")
        except ImportError:
            self.skipTest("boto3 not installed")
        except Exception as e:
            self.fail(f"Failed to process profile: {e}")


class TestS3Integration(unittest.TestCase):
    """Integration tests for S3 with real AWS calls."""
    
    def test_aws_credentials_present(self):
        """Test that AWS credentials are configured."""
        access_key = os.getenv('AWS_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        bucket = os.getenv('S3_BUCKET')
        
        self.assertIsNotNone(access_key, "AWS_ACCESS_KEY_ID not set")
        self.assertIsNotNone(secret_key, "AWS_SECRET_ACCESS_KEY not set")
        self.assertIsNotNone(bucket, "S3_BUCKET not set")
        
        print(f"✅ AWS credentials configured for bucket: {bucket}")
        print(f"   Access Key ID: {access_key[:4]}...{access_key[-4:]}")
    
    def test_s3_bucket_access(self):
        """Test that we can access the S3 bucket."""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            s3 = boto3.client(
                's3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
            )
            
            bucket = os.getenv('S3_BUCKET')
            
            # Try to list objects (limited)
            response = s3.list_objects_v2(
                Bucket=bucket,
                Prefix=os.getenv('S3_PREFIX', 'dealscale/bumble/'),
                MaxKeys=1
            )
            
            print(f"✅ Successfully accessed bucket: {bucket}")
            if 'Contents' in response:
                print(f"   Found {len(response['Contents'])} existing object(s)")
            else:
                print("   Bucket is accessible (empty or no matching prefix)")
                
        except ImportError:
            self.skipTest("boto3 not installed")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                self.fail(f"Access denied to bucket. Check credentials/permissions.")
            elif error_code == 'NoSuchBucket':
                self.fail(f"Bucket does not exist: {bucket}")
            else:
                self.fail(f"S3 error: {e}")


def run_tests():
    """Run all tests and print summary."""
    print("=" * 60)
    print("S3 Image Handler Test Suite")
    print("=" * 60)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestS3Integration))
    suite.addTests(loader.loadTestsFromTestCase(TestS3ImageHandler))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == '__main__':
    sys.exit(run_tests())
