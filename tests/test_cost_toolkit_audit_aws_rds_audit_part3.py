"""Comprehensive tests for aws_rds_audit.py - Part 3."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.audit.aws_rds_audit import (
    _process_aurora_cluster,
    _process_rds_instance,
    audit_rds_databases,
)


class TestEdgeCasesInstances:
    """Tests for edge cases and special scenarios - instance processing."""

    def test_instance_with_zero_allocated_storage(self, capsys):
        """Test processing instance with zero allocated storage."""
        instance = {
            "DBInstanceIdentifier": "aurora-member",
            "Engine": "aurora-mysql",
            "EngineVersion": "8.0",
            "DBInstanceClass": "db.r5.large",
            "DBInstanceStatus": "available",
            "AllocatedStorage": 0,
            "StorageType": "aurora",
            "MultiAZ": False,
            "PubliclyAccessible": False,
            "InstanceCreateTime": datetime(2024, 1, 15, 10, 30),
        }

        cost = _process_rds_instance(instance)

        assert cost == 0.0
        captured = capsys.readouterr()
        assert "Storage: 0 GB" in captured.out

    def test_instance_status_variations(self, capsys):
        """Test processing instances with different statuses."""
        statuses = ["creating", "available", "modifying", "stopping", "stopped", "deleting"]

        for status in statuses:
            instance = {
                "DBInstanceIdentifier": f"db-{status}",
                "Engine": "postgres",
                "DBInstanceClass": "db.t3.small",
                "DBInstanceStatus": status,
            }

            _process_rds_instance(instance)
            captured = capsys.readouterr()
            assert f"Status: {status}" in captured.out


class TestEdgeCasesClusters:
    """Tests for edge cases and special scenarios - cluster processing."""

    def test_cluster_with_no_members(self, capsys):
        """Test processing cluster with empty member list."""
        cluster = {
            "DBClusterIdentifier": "empty-cluster",
            "Engine": "aurora-postgresql",
            "EngineVersion": "14.6",
            "Status": "available",
            "DatabaseName": "mydb",
            "MasterUsername": "admin",
            "MultiAZ": False,
            "StorageEncrypted": True,
            "ClusterCreateTime": datetime(2024, 1, 15, 10, 30),
            "DBClusterMembers": [],
        }

        _process_aurora_cluster(cluster)

        captured = capsys.readouterr()
        # Empty member list is not printed (truthy check in code)
        assert "Cluster ID: empty-cluster" in captured.out
        assert "Cluster Members" not in captured.out

    def test_serverless_cluster_missing_scaling_info(self, capsys):
        """Test serverless cluster without scaling configuration."""
        cluster = {
            "DBClusterIdentifier": "serverless-no-config",
            "Engine": "aurora-mysql",
            "EngineVersion": "5.7",
            "Status": "available",
            "DatabaseName": "testdb",
            "MasterUsername": "admin",
            "MultiAZ": False,
            "StorageEncrypted": True,
            "ClusterCreateTime": datetime(2024, 1, 15, 10, 30),
            "EngineMode": "serverless",
        }

        _process_aurora_cluster(cluster)

        captured = capsys.readouterr()
        assert "Engine Mode: Serverless" in captured.out
        # Should not crash even without ScalingConfigurationInfo

    def test_audit_all_regions_integration(self, capsys):
        """Test auditing across all AWS regions."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_regions.return_value = {
            "Regions": [
                {"RegionName": "us-east-1"},
                {"RegionName": "us-west-2"},
                {"RegionName": "eu-west-1"},
                {"RegionName": "ap-southeast-1"},
            ]
        }

        def create_rds_client(region):
            mock_rds = MagicMock()
            if region == "us-east-1":
                mock_rds.describe_db_instances.return_value = {
                    "DBInstances": [
                        {
                            "DBInstanceIdentifier": "db-east",
                            "Engine": "postgres",
                            "EngineVersion": "14.5",
                            "DBInstanceClass": "db.t3.micro",
                            "DBInstanceStatus": "available",
                            "AllocatedStorage": 20,
                            "StorageType": "gp3",
                            "MultiAZ": False,
                            "PubliclyAccessible": False,
                            "InstanceCreateTime": datetime(2024, 1, 15, 10, 30),
                        }
                    ]
                }
                mock_rds.describe_db_clusters.return_value = {"DBClusters": []}
            else:
                mock_rds.describe_db_instances.return_value = {"DBInstances": []}
                mock_rds.describe_db_clusters.return_value = {"DBClusters": []}
            return mock_rds

        with patch("boto3.client") as mock_client:

            def client_side_effect(service, **kwargs):
                if service == "ec2":
                    return mock_ec2
                return create_rds_client(kwargs.get("region_name"))

            mock_client.side_effect = client_side_effect
            audit_rds_databases()

        captured = capsys.readouterr()
        assert "Total RDS Instances: 1" in captured.out
        assert "Region: us-east-1" in captured.out
