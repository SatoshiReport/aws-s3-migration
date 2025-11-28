#!/usr/bin/env python3
"""Update RDS instance security group settings."""

from urllib import error as urllib_error
from urllib import request as urllib_request

import boto3
from botocore.exceptions import ClientError

from ..aws_utils import setup_aws_credentials


class PublicIPRetrievalError(RuntimeError):
    """Raised when the current public IP cannot be fetched."""


def _fetch_current_ip(timeout: int = 10) -> str:
    """Retrieve the current public IP address using a simple HTTP GET."""
    try:
        with urllib_request.urlopen("https://ipv4.icanhazip.com/", timeout=timeout) as response:
            ip_text = response.read().decode().strip()
    except (urllib_error.URLError, TimeoutError) as exc:
        raise PublicIPRetrievalError("Could not retrieve current IP address") from exc

    if not ip_text:
        raise PublicIPRetrievalError("Empty response from IP service")

    return ip_text


def update_security_group():
    """Update RDS security group to allow connection from current IP"""

    setup_aws_credentials()
    ec2 = boto3.client("ec2", region_name="us-east-1")

    # Get current public IP
    try:
        print("🌐 Getting your current public IP address...")
        current_ip = _fetch_current_ip()
        print(f"   Your IP: {current_ip}")
    except (ClientError, PublicIPRetrievalError) as e:
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
