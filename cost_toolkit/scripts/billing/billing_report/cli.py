"""
Main entry point for AWS billing report CLI.
Contains main function and CLI utilities.
"""

from cost_toolkit.common.credential_utils import check_aws_credentials
from cost_toolkit.common.terminal_utils import clear_screen

from .cost_analysis import get_combined_billing_data
from .formatting import format_combined_billing_report


def main():
    """Main function to run the billing report"""
    clear_screen()

    print("AWS Billing Report Generator")
    print("=" * 80)

    if not check_aws_credentials():
        print("Failed to load AWS credentials. Please check your ~/.env file.")
        return

    cost_data, usage_data = get_combined_billing_data()
    if cost_data:
        format_combined_billing_report(cost_data, usage_data)
    else:
        print("Failed to retrieve billing data. Please check your AWS credentials and permissions.")


if __name__ == "__main__":  # pragma: no cover - script entry point
    pass
