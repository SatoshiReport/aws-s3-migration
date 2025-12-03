"""Security-related AWS helpers split from aws_ec2_operations for reuse."""

from __future__ import annotations

from typing import Optional

import boto3
from botocore.exceptions import ClientError

from cost_toolkit.common.aws_client_factory import create_ec2_client


def delete_security_group(
    region_or_client=None,
    group_id: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    group_name: Optional[str] = None,
    ec2_client=None,
    region: Optional[str] = None,
) -> bool:
    """Delete a security group with flexible client/region inputs."""
    if group_id is None:
        raise ValueError("group_id is required to delete a security group")
    try:
        if not isinstance(region_or_client, str) and region_or_client is not None:
            client = ec2_client or region_or_client
            region_to_use = region or ""
        else:
            region_to_use = region or region_or_client
            client = ec2_client or create_ec2_client(
                region=region_to_use,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
            )

        target_label = f"{group_id} ({group_name})" if group_name else group_id
        print(f"   🗑️  Deleting security group: {target_label}")
        client.delete_security_group(GroupId=group_id)
        print(f"   ✅ Deleted security group: {target_label}")

    except ClientError as e:
        print(f"   ❌ Failed to delete security group {group_id}: {str(e)}")
        return False
    return True
