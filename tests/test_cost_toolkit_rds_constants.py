"""Comprehensive tests for cost_toolkit/scripts/rds/constants.py."""

from __future__ import annotations

from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from cost_toolkit.scripts.rds.constants import PUBLIC_SUBNETS, create_public_subnet_group


class TestPublicSubnets:
    """Tests for PUBLIC_SUBNETS constant."""

    def test_public_subnets_defined(self):
        """Test that PUBLIC_SUBNETS is defined and contains expected subnets."""
        assert PUBLIC_SUBNETS is not None
        assert isinstance(PUBLIC_SUBNETS, list)
        assert len(PUBLIC_SUBNETS) == 6

    def test_public_subnets_format(self):
        """Test that subnet IDs have correct format."""
        for subnet in PUBLIC_SUBNETS:
            assert subnet.startswith("subnet-")
            assert len(subnet) > 7  # subnet- + at least one char


class TestCreatePublicSubnetGroup:
    """Tests for create_public_subnet_group function."""

    def test_create_subnet_group_success(self, capsys):
        """Test creating subnet group successfully."""
        mock_rds = MagicMock()
        mock_rds.create_db_subnet_group.return_value = {}

        create_public_subnet_group(mock_rds, "test-subnet-group")

        mock_rds.create_db_subnet_group.assert_called_once()
        call_args = mock_rds.create_db_subnet_group.call_args[1]
        assert call_args["DBSubnetGroupName"] == "test-subnet-group"
        assert call_args["DBSubnetGroupDescription"] == "Public subnets only for RDS internet access"
        assert call_args["SubnetIds"] == PUBLIC_SUBNETS
        assert call_args["Tags"] == [{"Key": "Purpose", "Value": "Public RDS access"}]

        captured = capsys.readouterr()
        assert "Creating public subnet group: test-subnet-group" in captured.out
        assert "Created new subnet group: test-subnet-group" in captured.out

    def test_create_subnet_group_with_custom_description(self, capsys):
        """Test creating subnet group with custom description."""
        mock_rds = MagicMock()
        mock_rds.create_db_subnet_group.return_value = {}

        create_public_subnet_group(mock_rds, "custom-group", description="Custom description for testing")

        call_args = mock_rds.create_db_subnet_group.call_args[1]
        assert call_args["DBSubnetGroupDescription"] == "Custom description for testing"

        captured = capsys.readouterr()
        assert "Creating public subnet group: custom-group" in captured.out

    def test_create_subnet_group_already_exists(self, capsys):
        """Test handling when subnet group already exists."""
        mock_rds = MagicMock()
        mock_rds.create_db_subnet_group.side_effect = ClientError(
            {"Error": {"Code": "DBSubnetGroupAlreadyExists", "Message": "already exists"}},
            "CreateDBSubnetGroup",
        )

        create_public_subnet_group(mock_rds, "existing-group")

        captured = capsys.readouterr()
        assert "Subnet group existing-group already exists" in captured.out

    def test_create_subnet_group_other_error(self):
        """Test handling other errors during creation."""
        mock_rds = MagicMock()
        mock_rds.create_db_subnet_group.side_effect = ClientError(
            {"Error": {"Code": "InvalidSubnet", "Message": "Invalid subnet"}},
            "CreateDBSubnetGroup",
        )

        try:
            create_public_subnet_group(mock_rds, "error-group")
            assert False, "Expected ClientError to be raised"
        except ClientError as e:
            assert e.response["Error"]["Code"] == "InvalidSubnet"

    def test_create_subnet_group_none_description(self):
        """Test that None description uses default."""
        mock_rds = MagicMock()
        mock_rds.create_db_subnet_group.return_value = {}

        create_public_subnet_group(mock_rds, "test-group", description=None)

        call_args = mock_rds.create_db_subnet_group.call_args[1]
        assert call_args["DBSubnetGroupDescription"] == "Public subnets only for RDS internet access"

    def test_create_subnet_group_empty_description(self):
        """Test creating subnet group with empty description."""
        mock_rds = MagicMock()
        mock_rds.create_db_subnet_group.return_value = {}

        create_public_subnet_group(mock_rds, "test-group", description="")

        call_args = mock_rds.create_db_subnet_group.call_args[1]
        assert call_args["DBSubnetGroupDescription"] == ""
