#!/usr/bin/env python3
"""Clean up unused KMS encryption keys."""

import boto3
from botocore.exceptions import ClientError


def get_keys_to_remove():
    """Return list of KMS keys to remove based on audit"""
    return [
        {
            "region": "us-west-1",
            "key_id": "09e32e6e-12cf-4dd1-ad49-b651bf81e152",
            "description": "WorkMail encryption key",
        },
        {
            "region": "eu-west-1",
            "key_id": "36eabc4d-f9ec-4c48-a44c-0a3e267f096d",
            "description": "WorkMail encryption key",
        },
        {
            "region": "eu-west-1",
            "key_id": "fd385fc7-d349-4dfa-87a5-aa032d47e5bb",
            "description": "WorkMail encryption key",
        },
        {
            "region": "us-east-1",
            "key_id": "6e4195b1-7e5d-4b9c-863b-0d33bbb8f71b",
            "description": "S3 encryption key (already disabled)",
        },
    ]


def schedule_key_deletion(kms_client, key_id, current_state):
    """Schedule a KMS key for deletion based on its current state"""
    if current_state in ["Enabled", "Disabled"]:
        try:
            # Schedule deletion with minimum waiting period (7 days)
            response = kms_client.schedule_key_deletion(KeyId=key_id, PendingWindowInDays=7)

            deletion_date = response["DeletionDate"]
            print(f"  ✅ Scheduled for deletion on: {deletion_date}")
            print("  💰 Will save: $1.00/month after deletion")

        except ClientError as e:
            if "already scheduled" in str(e).lower():
                print("  ⚠️  Already scheduled for deletion")
                return True

            print(f"  ❌ Error scheduling deletion: {e}")
            return False

        return True

    if current_state == "PendingDeletion":
        print("  ⚠️  Already pending deletion")
        return True

    print(f"  ⚠️  Key state '{current_state}' - cannot delete")
    return False


def process_single_key(key_info):
    """Process a single KMS key for deletion"""
    region = key_info["region"]
    key_id = key_info["key_id"]
    description = key_info["description"]

    print(f"\nProcessing {description} in {region}...")

    try:
        kms = boto3.client("kms", region_name=region)

        # Check current key state
        key_details = kms.describe_key(KeyId=key_id)
        current_state = key_details["KeyMetadata"]["KeyState"]

        print(f"  Current state: {current_state}")

        # Schedule key for deletion (7-30 day waiting period)
        return schedule_key_deletion(kms, key_id, current_state)

    except ClientError as e:
        print(f"  ❌ Error accessing key: {e}")
        return False


def cleanup_kms_keys():
    """Remove customer-managed KMS keys to eliminate costs"""

    print("AWS KMS Key Cleanup")
    print("=" * 50)

    keys_to_remove = get_keys_to_remove()
    total_savings = 0

    for key_info in keys_to_remove:
        if process_single_key(key_info):
            total_savings += 1

    print("\n" + "=" * 50)
    print("KMS CLEANUP SUMMARY:")
    print(f"Keys scheduled for deletion: {total_savings}")
    print(f"Estimated monthly savings: ${total_savings}.00")
    print("Note: Keys will be deleted after 7-day waiting period")
    print("Billing will stop once keys are fully deleted")


if __name__ == "__main__":
    cleanup_kms_keys()
