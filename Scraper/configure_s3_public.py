import boto3
import os
import sys
import json
from botocore.exceptions import ClientError
from pathlib import Path
from dotenv import load_dotenv

def configure_public_access():
    # Load env from backend root
    backend_root = Path(__file__).resolve().parent.parent.parent.parent
    env_path = backend_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    bucket = os.getenv('S3_BUCKET')
    
    if not all([access_key, secret_key, bucket]):
        print("Error: Missing AWS credentials or bucket in .env")
        return

    # Initialize S3 client (try to detect region or default)
    # Most buckets work with generic s3 client, but BPA/Policy often need regional client
    # Let's try to get location first
    s3_simple = boto3.client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_key)
    try:
        location = s3_simple.get_bucket_location(Bucket=bucket)['LocationConstraint']
        region = location if location else 'us-east-1'
    except:
        region = 'us-east-1'
        
    print(f"[*] Target Region: {region}")
    s3 = boto3.client(
        's3',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )

    print(f"[*] Attempting to disable 'Block Public Access' for bucket: {bucket}")
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                'BlockPublicAcls': False,
                'IgnorePublicAcls': False,
                'BlockPublicPolicy': False,
                'RestrictPublicBuckets': False
            }
        )
        print("✅ SUCCESS: Block Public Access disabled.")
    except ClientError as e:
        print(f"❌ FAILED to disable Block Public Access: {e}")
        print("   (This usually means your credentials don't have 's3:PutBucketPublicAccessBlock' permission)")

    print(f"\n[*] Attempting to apply Public Read bucket policy...")
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket}/*"
            }
        ]
    }
    try:
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        print("✅ SUCCESS: Bucket policy updated to ALLOW PUBLIC READ.")
    except ClientError as e:
        print(f"❌ FAILED to update bucket policy: {e}")
        print("   (This usually means your credentials don't have 's3:PutBucketPolicy' permission)")

if __name__ == "__main__":
    configure_public_access()
