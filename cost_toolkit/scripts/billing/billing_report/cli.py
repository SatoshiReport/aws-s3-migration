"""
Main entry point for AWS billing report CLI.
Contains main function and CLI utilities.
"""

import os

from dotenv import load_dotenv

from cost_toolkit.common.terminal_utils import clear_screen

from .cost_analysis import get_combined_billing_data
from .formatting import format_combined_billing_report


def setup_aws_credentials():
    """Load AWS credentials from .env file"""
    load_dotenv(os.path.expanduser("~/.env"))

    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        print("⚠️  AWS credentials not found in ~/.env file.")
        print("Please ensure ~/.env contains:")
        print("  AWS_ACCESS_KEY_ID=your-access-key")
        print("  AWS_SECRET_ACCESS_KEY=your-secret-key")
        print("  AWS_DEFAULT_REGION=us-east-1")
        return False

    return True


def main():
    """Main function to run the billing report"""
    clear_screen()

    print("AWS Billing Report Generator")
    print("=" * 80)

    if not setup_aws_credentials():
        print("Failed to load AWS credentials. Please check your ~/.env file.")
        return

    cost_data, usage_data = get_combined_billing_data()
    if cost_data:
        format_combined_billing_report(cost_data, usage_data)
    else:
        print("Failed to retrieve billing data. Please check your AWS credentials and permissions.")
