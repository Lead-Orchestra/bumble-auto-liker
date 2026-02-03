#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S3 Image Handler for Bumble Profile Scraper
Downloads profile images from Bumble CDN and uploads to S3 for permanent storage.
"""

import os
import re
import time
import hashlib
import requests
from typing import Dict, List, Optional
from pathlib import Path

# Try to import boto3, provide helpful error if missing
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception

# Load environment variables from .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Load .env from backend root
    backend_root = Path(__file__).resolve().parent.parent.parent.parent
    env_path = backend_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass


class S3ImageHandler:
    """Handles downloading images from URLs and uploading them to S3."""
    
    def __init__(
        self,
        bucket: str = None,
        prefix: str = None,
        access_key_id: str = None,
        secret_access_key: str = None,
        region: str = 'us-east-1'
    ):
        """
        Initialize the S3 handler.
        
        Args:
            bucket: S3 bucket name (defaults to S3_BUCKET env var)
            prefix: S3 key prefix (defaults to S3_PREFIX env var)
            access_key_id: AWS access key (defaults to AWS_ACCESS_KEY_ID env var)
            secret_access_key: AWS secret key (defaults to AWS_SECRET_ACCESS_KEY env var)
            region: AWS region (defaults to us-east-1)
        """
        if boto3 is None:
            raise ImportError(
                "boto3 is required for S3 uploads. Install with: pip install boto3"
            )
        
        self.bucket = bucket or os.getenv('S3_BUCKET', 'peridot-partner-ingress')
        self.prefix = prefix or os.getenv('S3_PREFIX', 'dealscale/bumble/')
        self.region = region
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key_id or os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=secret_access_key or os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=region
        )
        
    def download_image(self, url: str, timeout: int = 30) -> Optional[bytes]:
        """
        Download an image from a URL.
        
        Args:
            url: Image URL to download
            timeout: Request timeout in seconds
            
        Returns:
            Image bytes if successful, None otherwise
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': 'https://bumble.com/'
            }
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            print(f"[!] Failed to download image from {url[:50]}...: {e}")
            return None
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string to be safe for use in S3 keys."""
        # Remove or replace unsafe characters
        sanitized = re.sub(r'[^\w\s-]', '', name)
        sanitized = re.sub(r'[\s]+', '_', sanitized)
        return sanitized.lower()[:50]  # Limit length
    
    def _generate_s3_key(self, profile_name: str, image_index: int, extension: str = 'jpg') -> str:
        """
        Generate a unique S3 key for an image.
        
        Args:
            profile_name: Name of the profile
            image_index: Index of the image (0-based)
            extension: File extension
            
        Returns:
            S3 key string
        """
        sanitized_name = self._sanitize_filename(profile_name)
        timestamp = int(time.time())
        # Create unique folder per profile session
        folder = f"{sanitized_name}_{timestamp}"
        return f"{self.prefix}{folder}/{image_index}.{extension}"
    
    def upload_to_s3(self, image_data: bytes, key: str, content_type: str = 'image/jpeg') -> Optional[str]:
        """
        Upload image data to S3.
        
        Args:
            image_data: Raw image bytes
            key: S3 object key
            content_type: MIME type of the image
            
        Returns:
            Public URL of the uploaded image, or None on failure
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=image_data,
                ContentType=content_type
            )
            # Generate public URL (assumes bucket allows public access)
            url = f"https://{self.bucket}.s3.amazonaws.com/{key}"
            return url
        except (ClientError, NoCredentialsError) as e:
            print(f"[X] Failed to upload to S3: {e}")
            return None
    
    def process_profile_images(self, profile_data: Dict) -> Dict:
        """
        Download all profile images and upload to S3.
        Adds 's3_image_urls' field to the profile data.
        
        Args:
            profile_data: Profile dictionary containing 'image_urls' field
            
        Returns:
            Updated profile data with 's3_image_urls' field
        """
        image_urls = profile_data.get('image_urls', [])
        if not image_urls:
            profile_data['s3_image_urls'] = []
            return profile_data
        
        profile_name = profile_data.get('name', 'unknown')
        s3_urls = []
        
        print(f"[*] Uploading {len(image_urls)} images for {profile_name} to S3...")
        
        for idx, url in enumerate(image_urls):
            # Skip if already an S3 URL
            if 's3.amazonaws.com' in url:
                s3_urls.append(url)
                continue
            
            # Download image
            image_data = self.download_image(url)
            if not image_data:
                # Keep original URL as fallback
                s3_urls.append(url)
                continue
            
            # Detect content type from URL or default to JPEG
            content_type = 'image/jpeg'
            if '.png' in url.lower():
                content_type = 'image/png'
                ext = 'png'
            elif '.webp' in url.lower():
                content_type = 'image/webp'
                ext = 'webp'
            else:
                ext = 'jpg'
            
            # Generate S3 key and upload
            key = self._generate_s3_key(profile_name, idx, ext)
            s3_url = self.upload_to_s3(image_data, key, content_type)
            
            if s3_url:
                s3_urls.append(s3_url)
                print(f"[OK] Uploaded image {idx + 1}/{len(image_urls)}: {key}")
            else:
                # Keep original URL as fallback
                s3_urls.append(url)
        
        profile_data['s3_image_urls'] = s3_urls
        print(f"[OK] Uploaded {len([u for u in s3_urls if 's3.amazonaws.com' in u])}/{len(image_urls)} images to S3")
        
        return profile_data


# Convenience function for simple usage
def upload_profile_images(profile_data: Dict) -> Dict:
    """
    Convenience function to upload profile images to S3.
    Uses environment variables for configuration.
    
    Args:
        profile_data: Profile dictionary with 'image_urls' field
        
    Returns:
        Updated profile data with 's3_image_urls' field
    """
    try:
        handler = S3ImageHandler()
        return handler.process_profile_images(profile_data)
    except ImportError as e:
        print(f"[!] S3 upload skipped: {e}")
        profile_data['s3_image_urls'] = profile_data.get('image_urls', [])
        return profile_data
    except Exception as e:
        print(f"[X] S3 upload failed: {e}")
        profile_data['s3_image_urls'] = profile_data.get('image_urls', [])
        return profile_data


if __name__ == '__main__':
    # Quick test
    import sys
    
    print("[*] Testing S3 Image Handler...")
    
    # Test with a sample profile
    test_profile = {
        'name': 'Test User',
        'image_urls': ['https://example.com/image1.jpg']
    }
    
    try:
        handler = S3ImageHandler()
        print(f"[OK] S3 client initialized for bucket: {handler.bucket}")
        print(f"[OK] Prefix: {handler.prefix}")
        
        # Don't actually upload in test mode
        print("[*] To test full upload, run with actual Bumble image URLs")
    except Exception as e:
        print(f"[X] Initialization failed: {e}")
        sys.exit(1)
