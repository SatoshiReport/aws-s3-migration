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
