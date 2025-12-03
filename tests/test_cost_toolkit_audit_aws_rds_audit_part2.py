"""Comprehensive tests for aws_rds_audit.py - Part 2."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_rds_audit import (
    _audit_region_databases,
    audit_rds_databases,
    main,
)
from tests.rds_audit_test_utils import (
    AURORA_MYSQL_CLUSTER,
    AURORA_POSTGRES_CLUSTER,
    DB_INSTANCE_SUMMARY,
    run_audit_with_mock_clients,
)


class TestAuditRegionDatabasesErrors:
    """Tests for _audit_region_databases function - error scenarios."""

    def test_audit_region_service_unavailable(self, capsys):
        """Test handling service not available in region."""
        mock_rds = MagicMock()
        mock_rds.describe_db_instances.side_effect = ClientError(
            {"Error": {"Code": "InvalidAction", "Message": "Service not available"}},
            "describe_db_instances",
        )

        with patch("boto3.client", return_value=mock_rds):
            instances, clusters, cost = _audit_region_databases("ap-northeast-3")

        assert instances == 0
        assert clusters == 0
        assert cost == 0.0
        captured = capsys.readouterr()
        # Should not print error for unavailable service
        assert "Error accessing region" not in captured.out

    def test_audit_region_access_denied(self, capsys):
        """Test handling access denied error."""
        mock_rds = MagicMock()
        mock_rds.describe_db_instances.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, "describe_db_instances"
        )

        with patch("boto3.client", return_value=mock_rds):
            instances, clusters, cost = _audit_region_databases("us-east-1")

        assert instances == 0
        assert clusters == 0
        assert cost == 0.0
        captured = capsys.readouterr()
        assert "Error accessing region us-east-1" in captured.out

    def test_audit_region_other_error(self, capsys):
        """Test handling other client errors."""
        mock_rds = MagicMock()
        mock_rds.describe_db_instances.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "describe_db_instances",
        )

        with patch("boto3.client", return_value=mock_rds):
            instances, clusters, cost = _audit_region_databases("us-east-1")

        assert instances == 0
        assert clusters == 0
        assert cost == 0.0
        captured = capsys.readouterr()
        assert "Error accessing region us-east-1" in captured.out


class TestAuditRegionDatabasesBasic:
    """Tests for _audit_region_databases function - basic scenarios."""

    def test_audit_region_no_databases(self, capsys):
        """Test auditing region with no databases."""
        mock_rds = MagicMock()
        mock_rds.describe_db_instances.return_value = {"DBInstances": []}
        mock_rds.describe_db_clusters.return_value = {"DBClusters": []}

        with patch("boto3.client", return_value=mock_rds):
            instances, clusters, cost = _audit_region_databases("us-west-2")

        assert instances == 0
        assert clusters == 0
        assert cost == 0.0
        captured = capsys.readouterr()
        assert "Region: us-west-2" not in captured.out

    def test_audit_region_with_clusters(self, capsys):
        """Test auditing region with Aurora clusters."""
        mock_rds = MagicMock()
        mock_rds.describe_db_instances.return_value = {"DBInstances": []}
        mock_rds.describe_db_clusters.return_value = {
            "DBClusters": [{**AURORA_POSTGRES_CLUSTER, "DBClusterIdentifier": "aurora-1"}]
        }

        with patch("boto3.client", return_value=mock_rds):
            instances, clusters, cost = _audit_region_databases("eu-west-1")

        assert instances == 0
        assert clusters == 1
        assert cost == 0.0
        captured = capsys.readouterr()
        assert "Region: eu-west-1" in captured.out
        assert "AURORA CLUSTERS:" in captured.out
        assert "Cluster ID: aurora-1" in captured.out


class TestAuditRegionDatabasesInstances:
    """Tests for _audit_region_databases function - instance scenarios."""

    def test_audit_region_with_instances(self, capsys):
        """Test auditing region with RDS instances."""
        mock_rds = MagicMock()
        mock_rds.describe_db_instances.return_value = {
            "DBInstances": [
                {"DBInstanceIdentifier": "db-1", **DB_INSTANCE_SUMMARY},
                {
                    "DBInstanceIdentifier": "db-2",
                    **DB_INSTANCE_SUMMARY,
                    "Engine": "mysql",
                    "EngineVersion": "8.0",
                    "DBInstanceClass": "db.t3.small",
                    "AllocatedStorage": 50,
                    "StorageType": "gp2",
                    "MultiAZ": True,
                    "PubliclyAccessible": True,
                },
            ]
        }
        mock_rds.describe_db_clusters.return_value = {"DBClusters": []}

        with patch("boto3.client", return_value=mock_rds):
            instances, clusters, cost = _audit_region_databases("us-east-1")

        assert instances == 2
        assert clusters == 0
        assert cost == 20.0
        captured = capsys.readouterr()
        assert "Region: us-east-1" in captured.out
        assert "RDS INSTANCES:" in captured.out
        assert "Instance ID: db-1" in captured.out
        assert "Instance ID: db-2" in captured.out

    def test_audit_region_with_both(self, capsys):
        """Test auditing region with both instances and clusters."""
        mock_rds = MagicMock()
        mock_rds.describe_db_instances.return_value = {
            "DBInstances": [{"DBInstanceIdentifier": "standalone-db", **DB_INSTANCE_SUMMARY}]
        }
        mock_rds.describe_db_clusters.return_value = {"DBClusters": [AURORA_MYSQL_CLUSTER]}

        with patch("boto3.client", return_value=mock_rds):
            instances, clusters, cost = _audit_region_databases("us-west-1")

        assert instances == 1
        assert clusters == 1
        assert cost == 20.0
        captured = capsys.readouterr()
        assert "Region: us-west-1" in captured.out
        assert "RDS INSTANCES:" in captured.out
        assert "AURORA CLUSTERS:" in captured.out


class TestAuditRdsDatabasesBasic:
    """Tests for audit_rds_databases function - basic scenarios."""

    def test_audit_rds_databases_no_resources(self, capsys):
        """Test auditing with no RDS resources."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_regions.return_value = {
            "Regions": [{"RegionName": "us-east-1"}, {"RegionName": "us-west-2"}]
        }

        mock_rds = MagicMock()
        mock_rds.describe_db_instances.return_value = {"DBInstances": []}
        mock_rds.describe_db_clusters.return_value = {"DBClusters": []}

        with patch("boto3.client") as mock_client:
            mock_client.side_effect = lambda service, **kwargs: (
                mock_ec2 if service == "ec2" else mock_rds
            )
            audit_rds_databases()

        captured = capsys.readouterr()
        assert "AWS RDS Database Audit" in captured.out
        assert "=" * 80 in captured.out
        assert "DATABASE SUMMARY:" in captured.out
        assert "Total RDS Instances: 0" in captured.out
        assert "Total Aurora Clusters: 0" in captured.out
        assert "Estimated Monthly Cost: $0.00" in captured.out
        assert "BILLING DATA ANALYSIS:" in captured.out

    def test_audit_rds_databases_multiple_t3_micro(self, capsys):
        """Test auditing with multiple t3.micro instances for cost calculation."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}

        mock_rds = MagicMock()
        mock_rds.describe_db_instances.return_value = {
            "DBInstances": [
                {"DBInstanceIdentifier": "db-1", **DB_INSTANCE_SUMMARY},
                {"DBInstanceIdentifier": "db-2", **DB_INSTANCE_SUMMARY, "Engine": "mysql"},
            ]
        }
        mock_rds.describe_db_clusters.return_value = {"DBClusters": []}

        with patch("boto3.client") as mock_client:
            mock_client.side_effect = lambda service, **kwargs: (
                mock_ec2 if service == "ec2" else mock_rds
            )
            audit_rds_databases()

        captured = capsys.readouterr()
        assert "Total RDS Instances: 2" in captured.out
        assert "Estimated Monthly Cost: $40.00" in captured.out


class TestAuditRdsDatabasesMultiRegion:  # pylint: disable=too-few-public-methods
    """Tests for audit_rds_databases function - multi-region scenarios."""

    def test_audit_rds_databases_with_resources(self, capsys):
        """Test auditing with multiple RDS resources across regions."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_regions.return_value = {
            "Regions": [{"RegionName": "us-east-1"}, {"RegionName": "eu-west-2"}]
        }

        def create_rds_client(region):
            mock_rds = MagicMock()
            if region == "us-east-1":
                mock_rds.describe_db_instances.return_value = {
                    "DBInstances": [{"DBInstanceIdentifier": "prod-db", **DB_INSTANCE_SUMMARY}]
                }
                mock_rds.describe_db_clusters.return_value = {"DBClusters": []}
            else:
                mock_rds.describe_db_instances.return_value = {"DBInstances": []}
                mock_rds.describe_db_clusters.return_value = {
                    "DBClusters": [AURORA_POSTGRES_CLUSTER]
                }
            return mock_rds

        run_audit_with_mock_clients(mock_ec2, create_rds_client)

        captured = capsys.readouterr()
        assert "AWS RDS Database Audit" in captured.out
        assert "Total RDS Instances: 1" in captured.out
        assert "Total Aurora Clusters: 1" in captured.out
        assert "Estimated Monthly Cost: $20.00" in captured.out
        assert "Region: us-east-1" in captured.out
        assert "Region: eu-west-2" in captured.out


class TestMain:
    """Tests for main function."""

    def test_main_calls_audit_rds_databases(self):
        """Test main function calls audit_rds_databases."""
        with patch("cost_toolkit.scripts.audit.aws_rds_audit.audit_rds_databases") as mock_audit:
            main()
            mock_audit.assert_called_once()

    def test_main_executes_successfully(self, capsys):
        """Test main function executes audit successfully."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}

        mock_rds = MagicMock()
        mock_rds.describe_db_instances.return_value = {"DBInstances": []}
        mock_rds.describe_db_clusters.return_value = {"DBClusters": []}

        with patch("boto3.client") as mock_client:
            mock_client.side_effect = lambda service, **kwargs: (
                mock_ec2 if service == "ec2" else mock_rds
            )
            main()

        captured = capsys.readouterr()
        assert "AWS RDS Database Audit" in captured.out
        assert "DATABASE SUMMARY:" in captured.out
