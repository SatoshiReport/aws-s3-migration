"""Comprehensive tests for aws_rds_network_interface_audit.py - Part 2."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_rds_network_interface_audit import (
    audit_rds_instances_in_region,
)


class TestAuditRdsInstancesInRegion:
    """Tests for audit_rds_instances_in_region function."""

    def test_audit_with_instances_and_clusters(self):
        """Test auditing region with both instances and clusters."""
        with patch("boto3.client") as mock_client:
            mock_rds = MagicMock()
            mock_rds.describe_db_instances.return_value = {
                "DBInstances": [
                    {
                        "DBInstanceIdentifier": "db-1",
                        "Engine": "postgres",
                        "EngineVersion": "14.7",
                        "DBInstanceClass": "db.t3.micro",
                        "DBInstanceStatus": "available",
                    }
                ]
            }
            mock_rds.describe_db_clusters.return_value = {
                "DBClusters": [
                    {
                        "DBClusterIdentifier": "cluster-1",
                        "Engine": "aurora-postgresql",
                        "EngineVersion": "14.6",
                        "Status": "available",
                        "Endpoint": "cluster-1.xyz.us-east-1.rds.amazonaws.com",
                        "Port": 5432,
                        "ClusterCreateTime": "2024-01-01T00:00:00Z",
                    }
                ]
            }
            mock_client.return_value = mock_rds

            result = audit_rds_instances_in_region("us-east-1", "test-key", "test-secret")

        assert result is not None
        assert result["region"] == "us-east-1"
        assert result["total_instances"] == 1
        assert result["total_clusters"] == 1
        assert len(result["instances"]) == 1
        assert len(result["clusters"]) == 1
        assert result["instances"][0]["identifier"] == "db-1"
        assert result["clusters"][0]["identifier"] == "cluster-1"

    def test_audit_no_rds_resources(self):
        """Test auditing region with no RDS resources."""
        with patch("boto3.client") as mock_client:
            mock_rds = MagicMock()
            mock_rds.describe_db_instances.return_value = {"DBInstances": []}
            mock_rds.describe_db_clusters.return_value = {"DBClusters": []}
            mock_client.return_value = mock_rds

            result = audit_rds_instances_in_region("us-west-2", "test-key", "test-secret")

        assert result is None

    def test_audit_client_error(self, capsys):
        """Test error handling when auditing fails."""
        with patch("boto3.client") as mock_client:
            mock_rds = MagicMock()
            mock_rds.describe_db_instances.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied"}}, "describe_db_instances"
            )
            mock_client.return_value = mock_rds

            result = audit_rds_instances_in_region("eu-west-1", "test-key", "test-secret")

        assert result is None
        captured = capsys.readouterr()
        assert "Error auditing RDS in eu-west-1" in captured.out
