"""
Shared AWS credential loading utilities.

This module provides common credential loading patterns
to eliminate duplicate credential setup code across scripts.
"""

import os

from dotenv import load_dotenv


def setup_aws_credentials():
    """
    Load AWS credentials from .env file.

    Loads environment variables from ~/.env and extracts AWS credentials.

    Returns:
        tuple: (aws_access_key_id, aws_secret_access_key)

    Raises:
        ValueError: If AWS credentials are not found in ~/.env file
    """
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file")  # noqa: TRY003

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def check_aws_credentials():
    """
    Check if AWS credentials can be loaded from .env file.

    Returns:
        bool: True if credentials found, False otherwise (prints error message)
    """
    load_dotenv(os.path.expanduser("~/.env"))

    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        print("⚠️  AWS credentials not found in ~/.env file.")
        print("Please ensure ~/.env contains:")
        print("  AWS_ACCESS_KEY_ID=your-access-key")
        print("  AWS_SECRET_ACCESS_KEY=your-secret-key")
        print("  AWS_DEFAULT_REGION=us-east-1")
        return False

    return True
