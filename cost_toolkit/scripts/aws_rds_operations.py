#!/usr/bin/env python3
"""
AWS RDS Operations Module
Common RDS API operations extracted to reduce code duplication.
"""

from typing import Optional

from botocore.exceptions import ClientError

from cost_toolkit.scripts.aws_client_factory import create_rds_client


def describe_db_instances(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    db_instance_identifier: Optional[str] = None,
) -> list[dict]:
    """
    Get RDS database instances in a region.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key
        db_instance_identifier: Optional specific DB instance to describe

    Returns:
        list: List of DB instance dictionaries

    Raises:
        ClientError: If API call fails
    """
    rds_client = create_rds_client(
        region=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    params = {}
    if db_instance_identifier:
        params["DBInstanceIdentifier"] = db_instance_identifier

    response = rds_client.describe_db_instances(**params)
    return response.get("DBInstances", [])


def describe_db_clusters(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    db_cluster_identifier: Optional[str] = None,
) -> list[dict]:
    """
    Get RDS database clusters (Aurora) in a region.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key
        db_cluster_identifier: Optional specific cluster to describe

    Returns:
        list: List of DB cluster dictionaries

    Raises:
        ClientError: If API call fails
    """
    rds_client = create_rds_client(
        region=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    params = {}
    if db_cluster_identifier:
        params["DBClusterIdentifier"] = db_cluster_identifier

    response = rds_client.describe_db_clusters(**params)
    return response.get("DBClusters", [])


def describe_db_snapshots(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    db_instance_identifier: Optional[str] = None,
    db_snapshot_identifier: Optional[str] = None,
) -> list[dict]:
    """
    Get RDS database snapshots in a region.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key
        db_instance_identifier: Optional DB instance to filter snapshots
        db_snapshot_identifier: Optional specific snapshot to describe

    Returns:
        list: List of DB snapshot dictionaries

    Raises:
        ClientError: If API call fails
    """
    rds_client = create_rds_client(
        region=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    params = {}
    if db_instance_identifier:
        params["DBInstanceIdentifier"] = db_instance_identifier
    if db_snapshot_identifier:
        params["DBSnapshotIdentifier"] = db_snapshot_identifier

    response = rds_client.describe_db_snapshots(**params)
    return response.get("DBSnapshots", [])


def describe_db_subnet_groups(
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    db_subnet_group_name: Optional[str] = None,
) -> list[dict]:
    """
    Get RDS database subnet groups in a region.

    Args:
        region: AWS region name
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key
        db_subnet_group_name: Optional specific subnet group to describe

    Returns:
        list: List of DB subnet group dictionaries

    Raises:
        ClientError: If API call fails
    """
    rds_client = create_rds_client(
        region=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    params = {}
    if db_subnet_group_name:
        params["DBSubnetGroupName"] = db_subnet_group_name

    response = rds_client.describe_db_subnet_groups(**params)
    return response.get("DBSubnetGroups", [])


def create_db_subnet_group(
    region: str,
    db_subnet_group_name: str,
    subnet_ids: list[str],
    description: str,
    tags: Optional[list[dict]] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> dict:
    """
    Create an RDS database subnet group.

    Args:
        region: AWS region name
        db_subnet_group_name: Name for the subnet group
        subnet_ids: List of subnet IDs to include
        description: Description of the subnet group
        tags: Optional list of tag dictionaries
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        dict: Created DB subnet group data

    Raises:
        ClientError: If API call fails
    """
    rds_client = create_rds_client(
        region=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    params = {
        "DBSubnetGroupName": db_subnet_group_name,
        "DBSubnetGroupDescription": description,
        "SubnetIds": subnet_ids,
    }

    if tags:
        params["Tags"] = tags

    response = rds_client.create_db_subnet_group(**params)
    return response.get("DBSubnetGroup", {})


def modify_db_instance(
    region: str,
    db_instance_identifier: str,
    apply_immediately: bool = False,
    publicly_accessible: Optional[bool] = None,
    vpc_security_group_ids: Optional[list[str]] = None,
    db_subnet_group_name: Optional[str] = None,
    credentials: Optional[tuple[str, str]] = None,
) -> dict:
    """
    Modify an RDS database instance.

    Args:
        region: AWS region name
        db_instance_identifier: DB instance identifier
        apply_immediately: Whether to apply changes immediately
        publicly_accessible: Optional boolean to set public accessibility
        vpc_security_group_ids: Optional list of security group IDs
        db_subnet_group_name: Optional subnet group name
        credentials: Optional tuple of (aws_access_key_id, aws_secret_access_key)

    Returns:
        dict: Modified DB instance data

    Raises:
        ClientError: If API call fails
    """
    aws_access_key_id = credentials[0] if credentials else None
    aws_secret_access_key = credentials[1] if credentials else None

    rds_client = create_rds_client(
        region=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    params = {
        "DBInstanceIdentifier": db_instance_identifier,
        "ApplyImmediately": apply_immediately,
    }

    if publicly_accessible is not None:
        params["PubliclyAccessible"] = publicly_accessible

    if vpc_security_group_ids is not None:
        params["VpcSecurityGroupIds"] = vpc_security_group_ids

    if db_subnet_group_name is not None:
        params["DBSubnetGroupName"] = db_subnet_group_name

    response = rds_client.modify_db_instance(**params)
    return response.get("DBInstance", {})


def delete_db_instance(
    region: str,
    db_instance_identifier: str,
    skip_final_snapshot: bool = False,
    final_snapshot_identifier: Optional[str] = None,
    delete_automated_backups: bool = True,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> bool:
    """
    Delete an RDS database instance.

    Args:
        region: AWS region name
        db_instance_identifier: DB instance identifier to delete
        skip_final_snapshot: Whether to skip final snapshot
        final_snapshot_identifier: Optional name for final snapshot
        delete_automated_backups: Whether to delete automated backups
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        rds_client = create_rds_client(
            region=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        params = {
            "DBInstanceIdentifier": db_instance_identifier,
            "SkipFinalSnapshot": skip_final_snapshot,
            "DeleteAutomatedBackups": delete_automated_backups,
        }

        if not skip_final_snapshot and final_snapshot_identifier:
            params["FinalDBSnapshotIdentifier"] = final_snapshot_identifier

        rds_client.delete_db_instance(**params)
        print(f"✅ Deleted RDS instance: {db_instance_identifier}")

    except ClientError as e:
        print(f"❌ Failed to delete RDS instance {db_instance_identifier}: {str(e)}")
        return False
    return True


def delete_db_cluster(
    region: str,
    db_cluster_identifier: str,
    skip_final_snapshot: bool = False,
    final_snapshot_identifier: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> bool:
    """
    Delete an RDS database cluster (Aurora).

    Args:
        region: AWS region name
        db_cluster_identifier: DB cluster identifier to delete
        skip_final_snapshot: Whether to skip final snapshot
        final_snapshot_identifier: Optional name for final snapshot
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        rds_client = create_rds_client(
            region=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        params = {
            "DBClusterIdentifier": db_cluster_identifier,
            "SkipFinalSnapshot": skip_final_snapshot,
        }

        if not skip_final_snapshot and final_snapshot_identifier:
            params["FinalDBSnapshotIdentifier"] = final_snapshot_identifier

        rds_client.delete_db_cluster(**params)
        print(f"✅ Deleted RDS cluster: {db_cluster_identifier}")

    except ClientError as e:
        print(f"❌ Failed to delete RDS cluster {db_cluster_identifier}: {str(e)}")
        return False
    return True


def stop_db_instance(
    region: str,
    db_instance_identifier: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> bool:
    """
    Stop an RDS database instance.

    Args:
        region: AWS region name
        db_instance_identifier: DB instance identifier to stop
        aws_access_key_id: Optional AWS access key
        aws_secret_access_key: Optional AWS secret key

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        rds_client = create_rds_client(
            region=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        rds_client.stop_db_instance(DBInstanceIdentifier=db_instance_identifier)
        print(f"✅ Stopped RDS instance: {db_instance_identifier}")

    except ClientError as e:
        print(f"❌ Failed to stop RDS instance {db_instance_identifier}: {str(e)}")
        return False
    return True
