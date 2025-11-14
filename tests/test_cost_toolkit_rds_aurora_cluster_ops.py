"""Tests for cost_toolkit/scripts/migration/rds_aurora_migration/cluster_ops.py"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops import (
    _build_cluster_params,
    _get_cluster_endpoint_info,
    create_aurora_serverless_cluster,
    create_rds_snapshot,
    discover_rds_instances,
    validate_migration_compatibility,
)


# Tests for discover_rds_instances
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.get_aws_regions")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.boto3")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.setup_aws_credentials")
@patch("builtins.print")
def test_discover_rds_instances_success(mock_print, mock_setup, mock_boto3, mock_regions):
    """Test discovering RDS instances."""
    mock_regions.return_value = ["us-east-1"]
    mock_rds = MagicMock()
    mock_boto3.client.return_value = mock_rds
    mock_rds.describe_db_instances.return_value = {
        "DBInstances": [
            {
                "DBInstanceIdentifier": "db-1",
                "Engine": "mysql",
                "EngineVersion": "8.0",
                "DBInstanceClass": "db.t3.micro",
                "DBInstanceStatus": "available",
                "AllocatedStorage": 100,
                "StorageType": "gp2",
                "MultiAZ": False,
                "PubliclyAccessible": False,
                "VpcSecurityGroups": [{"VpcSecurityGroupId": "sg-123"}],
                "DBSubnetGroup": {"DBSubnetGroupName": "default"},
                "DBParameterGroups": [{"DBParameterGroupName": "default.mysql8.0"}],
                "BackupRetentionPeriod": 7,
                "PreferredBackupWindow": "03:00-04:00",
                "PreferredMaintenanceWindow": "sun:04:00-sun:05:00",
                "StorageEncrypted": True,
                "KmsKeyId": "arn:aws:kms:us-east-1:123456789012:key/12345678",
                "DeletionProtection": False,
            }
        ]
    }

    result = discover_rds_instances()

    assert len(result) == 1
    assert result[0]["identifier"] == "db-1"
    assert result[0]["region"] == "us-east-1"
    assert result[0]["engine"] == "mysql"
    mock_setup.assert_called_once()


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.get_aws_regions")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.boto3")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.setup_aws_credentials")
@patch("builtins.print")
def test_discover_rds_instances_skip_cluster_member(
    mock_print, mock_setup, mock_boto3, mock_regions
):
    """Test discovering RDS instances skips cluster members."""
    mock_regions.return_value = ["us-east-1"]
    mock_rds = MagicMock()
    mock_boto3.client.return_value = mock_rds
    mock_rds.describe_db_instances.return_value = {
        "DBInstances": [
            {
                "DBInstanceIdentifier": "aurora-instance",
                "DBClusterIdentifier": "aurora-cluster-1",
                "Engine": "aurora-mysql",
                "DBInstanceClass": "db.t3.medium",
                "DBInstanceStatus": "available",
            }
        ]
    }

    result = discover_rds_instances()

    assert len(result) == 0


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.get_aws_regions")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.boto3")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.setup_aws_credentials")
@patch("builtins.print")
def test_discover_rds_instances_no_instances(mock_print, mock_setup, mock_boto3, mock_regions):
    """Test discovering RDS instances when none exist."""
    mock_regions.return_value = ["us-east-1"]
    mock_rds = MagicMock()
    mock_boto3.client.return_value = mock_rds
    mock_rds.describe_db_instances.return_value = {"DBInstances": []}

    result = discover_rds_instances()

    assert result == []


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.get_aws_regions")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.boto3")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.setup_aws_credentials")
@patch("builtins.print")
def test_discover_rds_instances_client_error(mock_print, mock_setup, mock_boto3, mock_regions):
    """Test discovering RDS instances with client error."""
    mock_regions.return_value = ["us-east-1"]
    mock_rds = MagicMock()
    mock_boto3.client.return_value = mock_rds
    mock_rds.describe_db_instances.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedOperation"}}, "DescribeDBInstances"
    )

    result = discover_rds_instances()

    assert result == []


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.get_aws_regions")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.boto3")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops.setup_aws_credentials")
@patch("builtins.print")
def test_discover_rds_instances_region_not_available(
    mock_print, mock_setup, mock_boto3, mock_regions
):
    """Test discovering RDS instances when region not available."""
    mock_regions.return_value = ["us-east-1"]
    mock_rds = MagicMock()
    mock_boto3.client.return_value = mock_rds
    mock_rds.describe_db_instances.side_effect = ClientError(
        {"Error": {"Code": "NotAvailable", "Message": "not available"}}, "DescribeDBInstances"
    )

    result = discover_rds_instances()

    assert result == []


# Tests for validate_migration_compatibility
@patch("builtins.print")
def test_validate_migration_compatibility_mysql(mock_print):
    """Test validating MySQL instance compatibility."""
    instance = {
        "identifier": "db-1",
        "engine": "mysql",
        "status": "available",
        "allocated_storage": 100,
    }

    is_compatible, target = validate_migration_compatibility(instance)

    assert is_compatible is True
    assert target == "aurora-mysql"


@patch("builtins.print")
def test_validate_migration_compatibility_postgres(mock_print):
    """Test validating PostgreSQL instance compatibility."""
    instance = {
        "identifier": "db-1",
        "engine": "postgres",
        "status": "available",
        "allocated_storage": 100,
    }

    is_compatible, target = validate_migration_compatibility(instance)

    assert is_compatible is True
    assert target == "aurora-postgresql"


@patch("builtins.print")
def test_validate_migration_compatibility_mariadb(mock_print):
    """Test validating MariaDB instance compatibility."""
    instance = {
        "identifier": "db-1",
        "engine": "mariadb",
        "status": "available",
        "allocated_storage": 100,
    }

    is_compatible, target = validate_migration_compatibility(instance)

    assert is_compatible is True
    assert target == "aurora-mysql"


@patch("builtins.print")
def test_validate_migration_compatibility_incompatible_engine(mock_print):
    """Test validating incompatible engine."""
    instance = {
        "identifier": "db-1",
        "engine": "oracle-ee",
        "status": "available",
        "allocated_storage": 100,
    }

    is_compatible, issues = validate_migration_compatibility(instance)

    assert is_compatible is False
    assert len(issues) == 1
    assert "oracle-ee" in issues[0]


@patch("builtins.print")
def test_validate_migration_compatibility_wrong_status(mock_print):
    """Test validating instance with wrong status."""
    instance = {
        "identifier": "db-1",
        "engine": "mysql",
        "status": "modifying",
        "allocated_storage": 100,
    }

    is_compatible, issues = validate_migration_compatibility(instance)

    assert is_compatible is False
    assert any("modifying" in issue for issue in issues)


@patch("builtins.print")
def test_validate_migration_compatibility_storage_too_small(mock_print):
    """Test validating instance with storage too small."""
    instance = {
        "identifier": "db-1",
        "engine": "mysql",
        "status": "available",
        "allocated_storage": 0,
    }

    is_compatible, issues = validate_migration_compatibility(instance)

    assert is_compatible is False
    assert any("too small" in issue for issue in issues)


@patch("builtins.print")
def test_validate_migration_compatibility_multiple_issues(mock_print):
    """Test validating instance with multiple issues."""
    instance = {
        "identifier": "db-1",
        "engine": "sqlserver-se",
        "status": "stopped",
        "allocated_storage": 0,
    }

    is_compatible, issues = validate_migration_compatibility(instance)

    assert is_compatible is False
    assert len(issues) == 3


# Tests for create_rds_snapshot
@patch("builtins.print")
def test_create_rds_snapshot_success(mock_print):
    """Test creating RDS snapshot."""
    mock_rds = MagicMock()
    mock_waiter = MagicMock()
    mock_rds.get_waiter.return_value = mock_waiter

    result = create_rds_snapshot(mock_rds, "db-1", "us-east-1")

    assert result.startswith("db-1-migration-")
    mock_rds.create_db_snapshot.assert_called_once()
    mock_waiter.wait.assert_called_once()


@patch("builtins.print")
def test_create_rds_snapshot_client_error(mock_print):
    """Test creating RDS snapshot with client error."""
    mock_rds = MagicMock()
    mock_rds.create_db_snapshot.side_effect = ClientError(
        {"Error": {"Code": "SnapshotQuotaExceeded"}}, "CreateDBSnapshot"
    )

    with pytest.raises(ClientError):
        create_rds_snapshot(mock_rds, "db-1", "us-east-1")


# Tests for _build_cluster_params
def test_build_cluster_params_mysql():
    """Test building cluster params for MySQL."""
    instance = {
        "identifier": "db-1",
        "backup_retention": 7,
        "storage_encrypted": True,
        "kms_key_id": "arn:aws:kms:us-east-1:123:key/456",
        "vpc_security_groups": ["sg-123"],
        "db_subnet_group": "default",
        "preferred_backup_window": "03:00-04:00",
        "preferred_maintenance_window": "sun:04:00-sun:05:00",
    }

    params = _build_cluster_params(instance, "aurora-mysql", "cluster-1")

    assert params["DBClusterIdentifier"] == "cluster-1"
    assert params["Engine"] == "aurora-mysql"
    assert params["MasterUsername"] == "admin"
    assert params["BackupRetentionPeriod"] == 7
    assert params["StorageEncrypted"] is True
    assert params["KmsKeyId"] == "arn:aws:kms:us-east-1:123:key/456"
    assert params["VpcSecurityGroupIds"] == ["sg-123"]
    assert params["EnableCloudwatchLogsExports"] == ["error", "general", "slowquery"]


def test_build_cluster_params_postgresql():
    """Test building cluster params for PostgreSQL."""
    instance = {
        "identifier": "db-1",
        "backup_retention": 0,
        "storage_encrypted": False,
        "kms_key_id": None,
        "vpc_security_groups": [],
        "db_subnet_group": None,
        "preferred_backup_window": None,
        "preferred_maintenance_window": None,
    }

    params = _build_cluster_params(instance, "aurora-postgresql", "cluster-1")

    assert params["Engine"] == "aurora-postgresql"
    assert params["MasterUsername"] == "postgres"
    assert params["BackupRetentionPeriod"] == 1
    assert params["StorageEncrypted"] is False
    assert "KmsKeyId" not in params
    assert "VpcSecurityGroupIds" not in params
    assert params["EnableCloudwatchLogsExports"] == ["postgresql"]


def test_build_cluster_params_min_backup_retention():
    """Test building cluster params with minimum backup retention."""
    instance = {
        "identifier": "db-1",
        "backup_retention": 0,
        "storage_encrypted": False,
        "kms_key_id": None,
        "vpc_security_groups": [],
        "db_subnet_group": None,
        "preferred_backup_window": None,
        "preferred_maintenance_window": None,
    }

    params = _build_cluster_params(instance, "aurora-mysql", "cluster-1")

    assert params["BackupRetentionPeriod"] == 1


# Tests for _get_cluster_endpoint_info
def test_get_cluster_endpoint_info():
    """Test getting cluster endpoint info."""
    mock_rds = MagicMock()
    mock_rds.describe_db_clusters.return_value = {
        "DBClusters": [
            {
                "DBClusterIdentifier": "cluster-1",
                "Endpoint": "cluster-1.us-east-1.rds.amazonaws.com",
                "ReaderEndpoint": "cluster-1-ro.us-east-1.rds.amazonaws.com",
                "Port": 3306,
                "Engine": "aurora-mysql",
                "Status": "available",
            }
        ]
    }

    result = _get_cluster_endpoint_info(mock_rds, "cluster-1")

    assert result["cluster_identifier"] == "cluster-1"
    assert result["writer_endpoint"] == "cluster-1.us-east-1.rds.amazonaws.com"
    assert result["reader_endpoint"] == "cluster-1-ro.us-east-1.rds.amazonaws.com"
    assert result["port"] == 3306
    assert result["engine"] == "aurora-mysql"
    assert result["status"] == "available"


def test_get_cluster_endpoint_info_no_reader():
    """Test getting cluster endpoint info without reader endpoint."""
    mock_rds = MagicMock()
    mock_rds.describe_db_clusters.return_value = {
        "DBClusters": [
            {
                "DBClusterIdentifier": "cluster-1",
                "Endpoint": "cluster-1.us-east-1.rds.amazonaws.com",
                "Port": 5432,
                "Engine": "aurora-postgresql",
                "Status": "available",
            }
        ]
    }

    result = _get_cluster_endpoint_info(mock_rds, "cluster-1")

    assert result["reader_endpoint"] is None


# Tests for create_aurora_serverless_cluster
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops._get_cluster_endpoint_info")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops._build_cluster_params")
@patch("builtins.print")
def test_create_aurora_serverless_cluster_success(mock_print, mock_build, mock_get_info):
    """Test creating Aurora Serverless cluster."""
    mock_rds = MagicMock()
    mock_waiter = MagicMock()
    mock_rds.get_waiter.return_value = mock_waiter
    mock_build.return_value = {
        "DBClusterIdentifier": "cluster-1",
        "Engine": "aurora-mysql",
    }
    mock_get_info.return_value = {
        "cluster_identifier": "cluster-1",
        "writer_endpoint": "cluster-1.us-east-1.rds.amazonaws.com",
    }

    instance = {"identifier": "db-1"}

    result = create_aurora_serverless_cluster(mock_rds, instance, "aurora-mysql", "snap-123")

    assert result["cluster_identifier"] == "cluster-1"
    mock_rds.create_db_cluster.assert_called_once()
    mock_waiter.wait.assert_called_once()


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cluster_ops._build_cluster_params")
@patch("builtins.print")
def test_create_aurora_serverless_cluster_error(mock_print, mock_build):
    """Test creating Aurora Serverless cluster with error."""
    mock_rds = MagicMock()
    mock_build.return_value = {"DBClusterIdentifier": "cluster-1"}
    mock_rds.create_db_cluster.side_effect = ClientError(
        {"Error": {"Code": "ClusterAlreadyExists"}}, "CreateDBCluster"
    )

    instance = {"identifier": "db-1"}

    with pytest.raises(ClientError):
        create_aurora_serverless_cluster(mock_rds, instance, "aurora-mysql", "snap-123")
