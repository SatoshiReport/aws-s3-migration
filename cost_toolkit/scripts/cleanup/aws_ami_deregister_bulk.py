#!/usr/bin/env python3
"""
AWS AMI Bulk Deregistration Script
Deregisters unused AMIs to allow deletion of their associated snapshots.
This script will deregister 7 unused AMIs, preserving only the one currently in use by mufasa.
"""

import os
from datetime import datetime

import boto3
from dotenv import load_dotenv


def load_aws_credentials():
    """Load AWS credentials from .env file"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file")

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def deregister_ami(ec2_client, ami_id, region):
    """Deregister a specific AMI"""
    try:
        print(f"🗑️  Deregistering AMI: {ami_id} in {region}")
        ec2_client.deregister_image(ImageId=ami_id)
        print(f"   ✅ Successfully deregistered {ami_id}")
        return True
    except Exception as e:
        print(f"   ❌ Error deregistering {ami_id}: {e}")
        return False


def bulk_deregister_unused_amis():
    """Deregister all unused AMIs that are preventing snapshot deletion"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    # AMIs to deregister (excluding ami-05d0a30507ebee9d6 which is used by mufasa)
    amis_to_deregister = [
        {
            "ami_id": "ami-0cb04cf30dc50a00e",
            "region": "eu-west-2",
            "name": "Tars Image",
            "snapshot": "snap-09e90c64db692f884",
            "savings": 51.20,
        },
        {
            "ami_id": "ami-0abc073133c9d3e18",
            "region": "us-east-1",
            "name": "SadTalker",
            "snapshot": "snap-07c0d4017e24b3240",
            "savings": 1.60,
        },
        {
            "ami_id": "ami-0b340e8c04ad01f48",
            "region": "us-east-1",
            "name": "GPU",
            "snapshot": "snap-0fbb003580d3dc8ba",
            "savings": 3.20,
        },
        {
            "ami_id": "ami-0833a92e637927528",
            "region": "us-east-1",
            "name": "migration-i-0cfce47f50e3c34ff-20250618-173202",
            "snapshot": "snap-024d718f6d670bff2",
            "savings": 0.40,
        },
        {
            "ami_id": "ami-0cb41e78dab346fb3",
            "region": "us-east-1",
            "name": "migration-i-0cfce47f50e3c34ff-20250618-174214",
            "snapshot": "snap-0ac8b88270ff68d4d",
            "savings": 0.40,
        },
        {
            "ami_id": "ami-07b9b9991f7466e6d",
            "region": "us-east-2",
            "name": "migration-i-0cfce47f50e3c34ff-20250618-173202",
            "snapshot": "snap-0700cdc4cdfaaf8fd",
            "savings": 0.40,
        },
        {
            "ami_id": "ami-0966e8f6fa677382b",
            "region": "us-east-2",
            "name": "mufasa",
            "snapshot": "snap-05a42843f18ba1c5e",
            "savings": 0.40,
        },
    ]

    print("AWS AMI Bulk Deregistration Script")
    print("=" * 80)
    print("Deregistering unused AMIs to enable snapshot deletion...")
    print()
    print(f"🎯 Target: {len(amis_to_deregister)} unused AMIs for deregistration")
    print()

    total_potential_savings = sum(ami["savings"] for ami in amis_to_deregister)

    print("⚠️  FINAL WARNING: This will permanently deregister these AMIs!")
    print("   - AMIs will no longer be available for launching instances")
    print("   - This action cannot be undone")
    print("   - Associated snapshots can then be deleted for cost savings")
    print(f"   - Total potential monthly savings: ${total_potential_savings:.2f}")
    print()

    confirmation = input("Type 'DEREGISTER ALL AMIS' to confirm bulk deregistration: ")

    if confirmation != "DEREGISTER ALL AMIS":
        print("❌ Operation cancelled by user")
        return

    print()
    print("🚨 Proceeding with bulk AMI deregistration...")
    print("=" * 80)

    successful_deregistrations = 0
    failed_deregistrations = 0
    total_savings = 0

    for ami_info in amis_to_deregister:
        ami_id = ami_info["ami_id"]
        region = ami_info["region"]
        name = ami_info["name"]
        snapshot = ami_info["snapshot"]
        savings = ami_info["savings"]

        print(f"🔍 Processing {ami_id} ({name})...")
        print(f"   Region: {region}")
        print(f"   Associated snapshot: {snapshot}")
        print(f"   Potential monthly savings: ${savings:.2f}")

        # Create EC2 client for the specific region
        ec2_client = boto3.client(
            "ec2",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        if deregister_ami(ec2_client, ami_id, region):
            successful_deregistrations += 1
            total_savings += savings
        else:
            failed_deregistrations += 1

        print()

    print("=" * 80)
    print("🎯 BULK DEREGISTRATION SUMMARY")
    print("=" * 80)
    print(f"✅ Successfully deregistered: {successful_deregistrations} AMIs")
    print(f"❌ Failed to deregister: {failed_deregistrations} AMIs")
    print(f"💰 Total potential monthly savings: ${total_savings:.2f}")
    print(f"💰 Annual savings potential: ${total_savings * 12:.2f}")
    print()

    if successful_deregistrations > 0:
        print("🎉 AMI deregistration completed successfully!")
        print("   The associated snapshots can now be deleted for cost savings.")
        print()
        print("📝 Next steps:")
        print("   1. Wait a few minutes for AWS to process the deregistrations")
        print("   2. Run the snapshot deletion script again to remove the freed snapshots")
        print("   3. Verify savings with: python3 scripts/audit/aws_ebs_audit.py")
    else:
        print("❌ No AMIs were successfully deregistered")


if __name__ == "__main__":
    try:
        bulk_deregister_unused_amis()
    except Exception as e:
        print(f"❌ Script failed: {e}")
        exit(1)
