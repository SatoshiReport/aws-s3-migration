"""Comprehensive tests for aws_vpc_safe_deletion.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.common.vpc_cleanup_utils import (
    delete_internet_gateways as _delete_internet_gateways,
)
from cost_toolkit.common.vpc_cleanup_utils import delete_nat_gateways as _delete_nat_gateways
from cost_toolkit.common.vpc_cleanup_utils import delete_network_acls as _delete_network_acls
from cost_toolkit.common.vpc_cleanup_utils import delete_route_tables as _delete_route_tables
from cost_toolkit.common.vpc_cleanup_utils import delete_security_groups as _delete_security_groups
from cost_toolkit.common.vpc_cleanup_utils import delete_subnets as _delete_subnets
from cost_toolkit.common.vpc_cleanup_utils import delete_vpc_endpoints as _delete_vpc_endpoints


class TestDeleteInternetGateways:
    """Tests for _delete_internet_gateways function."""

    def test_delete_igws_success(self, capsys):
        """Test successful IGW deletion."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_internet_gateways.return_value = {
            "InternetGateways": [
                {"InternetGatewayId": "igw-1"},
                {"InternetGatewayId": "igw-2"},
            ]
        }

        _delete_internet_gateways(mock_ec2, "vpc-123")

        assert mock_ec2.detach_internet_gateway.call_count == 2
        assert mock_ec2.delete_internet_gateway.call_count == 2
        mock_ec2.detach_internet_gateway.assert_any_call(InternetGatewayId="igw-1", VpcId="vpc-123")
        captured = capsys.readouterr()
        assert "IGW igw-1 detached" in captured.out
        assert "IGW igw-1 deleted" in captured.out

    def test_delete_igws_with_error_raises(self):
        """Test IGW deletion with error raises ClientError."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_internet_gateways.return_value = {
            "InternetGateways": [{"InternetGatewayId": "igw-error"}]
        }
        mock_ec2.detach_internet_gateway.side_effect = ClientError(
            {"Error": {"Code": "DependencyViolation"}}, "detach_internet_gateway"
        )

        with pytest.raises(ClientError) as exc_info:
            _delete_internet_gateways(mock_ec2, "vpc-123")

        assert exc_info.value.response["Error"]["Code"] == "DependencyViolation"

    def test_delete_no_igws(self):
        """Test deletion with no IGWs."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_internet_gateways.return_value = {"InternetGateways": []}

        _delete_internet_gateways(mock_ec2, "vpc-123")

        mock_ec2.detach_internet_gateway.assert_not_called()
        mock_ec2.delete_internet_gateway.assert_not_called()


class TestDeleteVpcEndpoints:
    """Tests for _delete_vpc_endpoints function."""

    def test_delete_endpoints_success(self, capsys):
        """Test successful VPC endpoint deletion."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_vpc_endpoints.return_value = {
            "VpcEndpoints": [
                {"VpcEndpointId": "vpce-1", "State": "available"},
                {"VpcEndpointId": "vpce-2", "State": "pending"},
            ]
        }

        _delete_vpc_endpoints(mock_ec2, "vpc-123")

        assert mock_ec2.delete_vpc_endpoint.call_count == 2
        captured = capsys.readouterr()
        assert "VPC Endpoint vpce-1 deleted" in captured.out

    def test_delete_endpoints_skips_deleted(self):
        """Test that deleted endpoints are skipped."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_vpc_endpoints.return_value = {
            "VpcEndpoints": [
                {"VpcEndpointId": "vpce-1", "State": "deleted"},
                {"VpcEndpointId": "vpce-2", "State": "available"},
            ]
        }

        _delete_vpc_endpoints(mock_ec2, "vpc-123")

        assert mock_ec2.delete_vpc_endpoint.call_count == 1
        mock_ec2.delete_vpc_endpoint.assert_called_with(VpcEndpointId="vpce-2")

    def test_delete_endpoints_with_error_raises(self):
        """Test endpoint deletion with error raises ClientError."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_vpc_endpoints.return_value = {
            "VpcEndpoints": [{"VpcEndpointId": "vpce-error", "State": "available"}]
        }
        mock_ec2.delete_vpc_endpoint.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "delete_vpc_endpoint"
        )

        with pytest.raises(ClientError) as exc_info:
            _delete_vpc_endpoints(mock_ec2, "vpc-123")

        assert exc_info.value.response["Error"]["Code"] == "ServiceError"


class TestDeleteNatGateways:
    """Tests for _delete_nat_gateways function."""

    def test_delete_nat_gateways_success(self, capsys):
        """Test successful NAT gateway deletion."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_nat_gateways.return_value = {
            "NatGateways": [
                {"NatGatewayId": "nat-1", "State": "available"},
                {"NatGatewayId": "nat-2", "State": "pending"},
            ]
        }

        _delete_nat_gateways(mock_ec2, "vpc-123")

        assert mock_ec2.delete_nat_gateway.call_count == 2
        captured = capsys.readouterr()
        assert "NAT Gateway nat-1 deletion initiated" in captured.out

    def test_delete_nat_gateways_skips_deleted(self):
        """Test that deleted NAT gateways are skipped."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_nat_gateways.return_value = {
            "NatGateways": [
                {"NatGatewayId": "nat-1", "State": "deleted"},
                {"NatGatewayId": "nat-2", "State": "deleting"},
                {"NatGatewayId": "nat-3", "State": "available"},
            ]
        }

        _delete_nat_gateways(mock_ec2, "vpc-123")

        assert mock_ec2.delete_nat_gateway.call_count == 1
        mock_ec2.delete_nat_gateway.assert_called_with(NatGatewayId="nat-3")

    def test_delete_nat_gateways_with_error_raises(self):
        """Test NAT gateway deletion with error raises ClientError."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_nat_gateways.return_value = {
            "NatGateways": [{"NatGatewayId": "nat-error", "State": "available"}]
        }
        mock_ec2.delete_nat_gateway.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "delete_nat_gateway"
        )

        with pytest.raises(ClientError) as exc_info:
            _delete_nat_gateways(mock_ec2, "vpc-123")

        assert exc_info.value.response["Error"]["Code"] == "ServiceError"


class TestDeleteSecurityGroups:
    """Tests for _delete_security_groups function."""

    def test_delete_sgs_success(self, capsys):
        """Test successful security group deletion."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_security_groups.return_value = {
            "SecurityGroups": [
                {"GroupId": "sg-1", "GroupName": "custom-sg-1"},
                {"GroupId": "sg-2", "GroupName": "custom-sg-2"},
                {"GroupId": "sg-default", "GroupName": "default"},
            ]
        }

        _delete_security_groups(mock_ec2, "vpc-123")

        assert mock_ec2.delete_security_group.call_count == 2
        captured = capsys.readouterr()
        assert "Security Group sg-1 deleted" in captured.out

    def test_delete_sgs_skips_default(self):
        """Test that default security group is skipped."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_security_groups.return_value = {
            "SecurityGroups": [{"GroupId": "sg-default", "GroupName": "default"}]
        }

        _delete_security_groups(mock_ec2, "vpc-123")

        mock_ec2.delete_security_group.assert_not_called()

    def test_delete_sgs_with_error_raises(self):
        """Test security group deletion with error raises ClientError."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_security_groups.return_value = {
            "SecurityGroups": [{"GroupId": "sg-error", "GroupName": "error-sg"}]
        }
        mock_ec2.delete_security_group.side_effect = ClientError(
            {"Error": {"Code": "DependencyViolation"}}, "delete_security_group"
        )

        with pytest.raises(ClientError) as exc_info:
            _delete_security_groups(mock_ec2, "vpc-123")

        assert exc_info.value.response["Error"]["Code"] == "DependencyViolation"


class TestDeleteNetworkAcls:
    """Tests for _delete_network_acls function."""

    def test_delete_nacls_success(self, capsys):
        """Test successful network ACL deletion."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_network_acls.return_value = {
            "NetworkAcls": [
                {"NetworkAclId": "acl-1", "IsDefault": False},
                {"NetworkAclId": "acl-2", "IsDefault": False},
                {"NetworkAclId": "acl-default", "IsDefault": True},
            ]
        }

        _delete_network_acls(mock_ec2, "vpc-123")

        assert mock_ec2.delete_network_acl.call_count == 2
        captured = capsys.readouterr()
        assert "Network ACL acl-1 deleted" in captured.out

    def test_delete_nacls_skips_default(self):
        """Test that default network ACL is skipped."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_network_acls.return_value = {
            "NetworkAcls": [{"NetworkAclId": "acl-default", "IsDefault": True}]
        }

        _delete_network_acls(mock_ec2, "vpc-123")

        mock_ec2.delete_network_acl.assert_not_called()

    def test_delete_nacls_with_error_raises(self):
        """Test network ACL deletion with error raises ClientError."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_network_acls.return_value = {
            "NetworkAcls": [{"NetworkAclId": "acl-error", "IsDefault": False}]
        }
        mock_ec2.delete_network_acl.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "delete_network_acl"
        )

        with pytest.raises(ClientError) as exc_info:
            _delete_network_acls(mock_ec2, "vpc-123")

        assert exc_info.value.response["Error"]["Code"] == "ServiceError"


class TestDeleteRouteTables:
    """Tests for _delete_route_tables function."""

    def test_delete_route_tables_success(self, capsys):
        """Test successful route table deletion."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_route_tables.return_value = {
            "RouteTables": [
                {"RouteTableId": "rtb-1", "Associations": [{"Main": False}]},
                {"RouteTableId": "rtb-2", "Associations": []},
                {"RouteTableId": "rtb-main", "Associations": [{"Main": True}]},
            ]
        }

        _delete_route_tables(mock_ec2, "vpc-123")

        assert mock_ec2.delete_route_table.call_count == 2
        captured = capsys.readouterr()
        assert "Route Table rtb-1 deleted" in captured.out

    def test_delete_route_tables_skips_main(self):
        """Test that main route table is skipped."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_route_tables.return_value = {
            "RouteTables": [{"RouteTableId": "rtb-main", "Associations": [{"Main": True}]}]
        }

        _delete_route_tables(mock_ec2, "vpc-123")

        mock_ec2.delete_route_table.assert_not_called()

    def test_delete_route_tables_with_error_raises(self):
        """Test route table deletion with error raises ClientError."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_route_tables.return_value = {
            "RouteTables": [{"RouteTableId": "rtb-error", "Associations": []}]
        }
        mock_ec2.delete_route_table.side_effect = ClientError(
            {"Error": {"Code": "DependencyViolation"}}, "delete_route_table"
        )

        with pytest.raises(ClientError) as exc_info:
            _delete_route_tables(mock_ec2, "vpc-123")

        assert exc_info.value.response["Error"]["Code"] == "DependencyViolation"


class TestDeleteSubnets:
    """Tests for _delete_subnets function."""

    def test_delete_subnets_success(self, capsys):
        """Test successful subnet deletion."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_subnets.return_value = {
            "Subnets": [{"SubnetId": "subnet-1"}, {"SubnetId": "subnet-2"}]
        }

        _delete_subnets(mock_ec2, "vpc-123")

        assert mock_ec2.delete_subnet.call_count == 2
        captured = capsys.readouterr()
        assert "Subnet subnet-1 deleted" in captured.out

    def test_delete_subnets_with_error_raises(self):
        """Test subnet deletion with error raises ClientError."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_subnets.return_value = {"Subnets": [{"SubnetId": "subnet-error"}]}
        mock_ec2.delete_subnet.side_effect = ClientError(
            {"Error": {"Code": "DependencyViolation"}}, "delete_subnet"
        )

        with pytest.raises(ClientError) as exc_info:
            _delete_subnets(mock_ec2, "vpc-123")

        assert exc_info.value.response["Error"]["Code"] == "DependencyViolation"
