"""Comprehensive tests for aws_security_group_dependencies.py - Part 2: RDS Dependencies."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_security_group_dependencies import (
    _collect_rds_deps,
)


class TestCollectRdsDeps:
    """Tests for _collect_rds_deps function."""

    def test_collect_rds_instances(self):
        """Test collecting RDS instances."""
        with patch("boto3.client") as mock_client_factory:
            mock_rds_client = MagicMock()
            mock_client_factory.return_value = mock_rds_client
            mock_rds_client.describe_db_instances.return_value = {
                "DBInstances": [
                    {
                        "DBInstanceIdentifier": "db-123",
                        "DBInstanceStatus": "available",
                        "Engine": "postgres",
                        "VpcSecurityGroups": [{"VpcSecurityGroupId": "sg-123", "Status": "active"}],
                        "DbSubnetGroup": {"VpcId": "vpc-123"},
                    }
                ]
            }

            result = _collect_rds_deps("sg-123", "us-east-1", "key", "secret")

        assert len(result) == 1
        assert result[0]["db_instance_id"] == "db-123"
        assert result[0]["db_instance_status"] == "available"
        assert result[0]["engine"] == "postgres"
        assert result[0]["vpc_id"] == "vpc-123"

    def test_collect_rds_instances_client_error(self, capsys):
        """Test error handling when RDS API fails."""
        with patch("boto3.client") as mock_client_factory:
            mock_rds_client = MagicMock()
            mock_client_factory.return_value = mock_rds_client
            mock_rds_client.describe_db_instances.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "describe_db_instances")

            result = _collect_rds_deps("sg-123", "us-east-1", "key", "secret")

        assert len(result) == 0
        captured = capsys.readouterr()
        assert "Could not check RDS dependencies" in captured.out

    def test_collect_rds_instances_no_match(self):
        """Test collecting RDS instances with no matching security group."""
        with patch("boto3.client") as mock_client_factory:
            mock_rds_client = MagicMock()
            mock_client_factory.return_value = mock_rds_client
            mock_rds_client.describe_db_instances.return_value = {
                "DBInstances": [
                    {
                        "DBInstanceIdentifier": "db-456",
                        "DBInstanceStatus": "available",
                        "Engine": "mysql",
                        "VpcSecurityGroups": [{"VpcSecurityGroupId": "sg-other", "Status": "active"}],
                    }
                ]
            }

            result = _collect_rds_deps("sg-123", "us-east-1", "key", "secret")

        assert len(result) == 0
