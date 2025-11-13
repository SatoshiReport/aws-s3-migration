#!/usr/bin/env python3
"""Update RDS instance security group settings."""

import boto3
import requests
from botocore.exceptions import ClientError

from ..aws_utils import setup_aws_credentials


def update_security_group():
    """Update RDS security group to allow connection from current IP"""

    setup_aws_credentials()
    ec2 = boto3.client("ec2", region_name="us-east-1")

    # Get current public IP
    try:
        print("🌐 Getting your current public IP address...")
        response = requests.get("https://ipv4.icanhazip.com/", timeout=10)
        current_ip = response.text.strip()
        print(f"   Your IP: {current_ip}")
    except ClientError as e:
        print(f"❌ Could not get current IP: {e}")
        print("Please provide your public IP address manually")
        return

    security_group_id = "sg-265aa043"  # From the previous analysis

    try:
        print(f"🔒 Adding rule to security group {security_group_id}...")

        # Add inbound rule for PostgreSQL (port 5432) from current IP
        ec2.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 5432,
                    "ToPort": 5432,
                    "IpRanges": [
                        {
                            "CidrIp": f"{current_ip}/32",
                            "Description": "Temporary access for data migration",
                        }
                    ],
                }
            ],
        )

        print("✅ Security group updated!")
        print(f"   Added rule: Port 5432 from {current_ip}/32")
        print("⚠️  This is temporary - we'll remove it after data migration")

    except ClientError as e:
        if "already exists" in str(e).lower():
            print("✅ Rule already exists for your IP")
        else:
            print(f"❌ Error updating security group: {e}")


def main():
    """Main function."""
    update_security_group()


if __name__ == "__main__":
    main()
