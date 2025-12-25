"""Comprehensive tests for aws_vpc_immediate_cleanup.py - Part 1."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup import (
    _check_vpc_ec2_instances,
    _check_vpc_load_balancers,
    _check_vpc_network_resources,
    release_public_ip_from_instance,
    remove_detached_internet_gateway,
)


class TestReleasePublicIpFromInstance:
    """Tests for release_public_ip_from_instance function."""

    def test_no_public_ip(self, capsys):
        """Test instance with no public IP."""
        with patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup.get_instance_info") as mock_get_info:
            mock_get_info.return_value = {"InstanceId": "i-123"}

            with patch("boto3.client"):
                result = release_public_ip_from_instance("i-123", "us-east-1")

            assert result is True
            captured = capsys.readouterr()
            assert "has no public IP address" in captured.out

    def test_elastic_ip_with_association(self, capsys):
        """Test instance with Elastic IP."""
        with patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup.get_instance_info") as mock_get_info:
            mock_get_info.return_value = {
                "InstanceId": "i-123",
                "PublicIpAddress": "1.2.3.4",
                "NetworkInterfaces": [
                    {
                        "Association": {
                            "AssociationId": "eipassoc-123",
                            "AllocationId": "eipalloc-456",
                        }
                    }
                ],
            }

            with patch("boto3.client") as mock_boto3:
                mock_ec2 = MagicMock()
                mock_boto3.return_value = mock_ec2

                result = release_public_ip_from_instance("i-123", "us-east-1")

                assert result is True
                mock_ec2.disassociate_address.assert_called_once_with(AssociationId="eipassoc-123")
                captured = capsys.readouterr()
                assert "Elastic IP disassociated" in captured.out
                assert "eipalloc-456" in captured.out

    def test_elastic_ip_already_disassociated(self, capsys):
        """Test instance with Elastic IP already disassociated."""
        with patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup.get_instance_info") as mock_get_info:
            mock_get_info.return_value = {
                "InstanceId": "i-123",
                "PublicIpAddress": "1.2.3.4",
                "NetworkInterfaces": [{"Association": {"AllocationId": "eipalloc-456"}}],
            }

            with patch("boto3.client"):
                result = release_public_ip_from_instance("i-123", "us-east-1")

                assert result is True
                captured = capsys.readouterr()
                assert "already disassociated" in captured.out

    def test_auto_assigned_public_ip(self, capsys):
        """Test instance with auto-assigned public IP."""
        with patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup.get_instance_info") as mock_get_info:
            mock_get_info.return_value = {
                "InstanceId": "i-123",
                "PublicIpAddress": "1.2.3.4",
                "NetworkInterfaces": [{"Association": {}}],
            }

            with patch("boto3.client"):
                result = release_public_ip_from_instance("i-123", "us-east-1")

                assert result is False
                captured = capsys.readouterr()
                assert "auto-assigned public IP" in captured.out
                assert "needs to be stopped" in captured.out

    def test_client_error(self, capsys):
        """Test client error handling."""
        with patch("cost_toolkit.scripts.cleanup.aws_vpc_immediate_cleanup.get_instance_info") as mock_get_info:
            mock_get_info.side_effect = ClientError({"Error": {"Code": "InstanceNotFound"}}, "describe_instances")

            result = release_public_ip_from_instance("i-notfound", "us-east-1")

            assert result is False
            captured = capsys.readouterr()
            assert "Error releasing public IP" in captured.out


class TestRemoveDetachedInternetGateway:
    """Tests for remove_detached_internet_gateway function."""

    def test_remove_detached_igw(self, capsys):
        """Test removing a detached IGW."""
        with patch("boto3.client") as mock_boto3:
            mock_ec2 = MagicMock()
            mock_boto3.return_value = mock_ec2
            mock_ec2.describe_internet_gateways.return_value = {"InternetGateways": [{"InternetGatewayId": "igw-123", "Attachments": []}]}

            result = remove_detached_internet_gateway("igw-123", "us-east-1")

            assert result is True
            mock_ec2.delete_internet_gateway.assert_called_once_with(InternetGatewayId="igw-123")
            captured = capsys.readouterr()
            assert "deleted successfully" in captured.out

    def test_remove_attached_igw(self, capsys):
        """Test attempting to remove attached IGW."""
        with patch("boto3.client") as mock_boto3:
            mock_ec2 = MagicMock()
            mock_boto3.return_value = mock_ec2
            mock_ec2.describe_internet_gateways.return_value = {
                "InternetGateways": [
                    {
                        "InternetGatewayId": "igw-123",
                        "Attachments": [{"VpcId": "vpc-123", "State": "available"}],
                    }
                ]
            }

            result = remove_detached_internet_gateway("igw-123", "us-east-1")

            assert result is False
            mock_ec2.delete_internet_gateway.assert_not_called()
            captured = capsys.readouterr()
            assert "still attached to VPCs" in captured.out

    def test_remove_igw_with_unavailable_attachment(self):
        """Test removing IGW with unavailable attachments."""
        with patch("boto3.client") as mock_boto3:
            mock_ec2 = MagicMock()
            mock_boto3.return_value = mock_ec2
            mock_ec2.describe_internet_gateways.return_value = {
                "InternetGateways": [
                    {
                        "InternetGatewayId": "igw-123",
                        "Attachments": [{"VpcId": "vpc-123", "State": "detaching"}],
                    }
                ]
            }

            result = remove_detached_internet_gateway("igw-123", "us-east-1")

            assert result is True
            mock_ec2.delete_internet_gateway.assert_called_once()

    def test_remove_igw_error(self, capsys):
        """Test error when removing IGW."""
        with patch("boto3.client") as mock_boto3:
            mock_ec2 = MagicMock()
            mock_boto3.return_value = mock_ec2
            mock_ec2.describe_internet_gateways.side_effect = ClientError(
                {"Error": {"Code": "InvalidInternetGatewayID.NotFound"}},
                "describe_internet_gateways",
            )

            result = remove_detached_internet_gateway("igw-notfound", "us-east-1")

            assert result is False
            captured = capsys.readouterr()
            assert "Error deleting Internet Gateway" in captured.out


class TestCheckVpcEc2Instances:
    """Tests for _check_vpc_ec2_instances function."""

    def test_check_with_running_instances(self):
        """Test checking VPC with running instances."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {"InstanceId": "i-1", "State": {"Name": "running"}},
                        {"InstanceId": "i-2", "State": {"Name": "stopped"}},
                    ]
                }
            ]
        }

        analysis = {"can_delete": True, "blocking_resources": []}
        _check_vpc_ec2_instances(mock_ec2, "vpc-123", analysis)

        assert analysis["can_delete"] is False
        assert "2 EC2 instances" in analysis["blocking_resources"]

    def test_check_with_no_instances(self):
        """Test checking VPC with no instances."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {"Reservations": []}

        analysis = {"can_delete": True, "blocking_resources": []}
        _check_vpc_ec2_instances(mock_ec2, "vpc-123", analysis)

        assert analysis["can_delete"] is True
        assert len(analysis["blocking_resources"]) == 0

    def test_check_excludes_terminated_instances(self):
        """Test that terminated instances are excluded via filters."""
        mock_ec2 = MagicMock()
        # Terminated instances won't be in the response due to filter
        mock_ec2.describe_instances.return_value = {"Reservations": []}

        analysis = {"can_delete": True, "blocking_resources": []}
        _check_vpc_ec2_instances(mock_ec2, "vpc-123", analysis)

        assert analysis["can_delete"] is True
        # Verify the filter was used
        call_args = mock_ec2.describe_instances.call_args
        filters = call_args[1]["Filters"]
        state_filter = next(f for f in filters if f["Name"] == "instance-state-name")
        assert "terminated" not in state_filter["Values"]


class TestCheckVpcNetworkResources:
    """Tests for _check_vpc_network_resources function."""

    def test_check_with_igw(self):
        """Test checking VPC with Internet Gateway."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_internet_gateways.return_value = {"InternetGateways": [{"InternetGatewayId": "igw-123"}]}
        mock_ec2.describe_nat_gateways.return_value = {"NatGateways": []}
        mock_ec2.describe_vpc_endpoints.return_value = {"VpcEndpoints": []}

        analysis = {"can_delete": True, "blocking_resources": [], "dependencies": []}
        _check_vpc_network_resources(mock_ec2, "vpc-123", analysis)

        assert "1 Internet Gateways" in analysis["dependencies"]

    def test_check_with_nat_gateways(self):
        """Test checking VPC with NAT Gateways."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_internet_gateways.return_value = {"InternetGateways": []}
        mock_ec2.describe_nat_gateways.return_value = {
            "NatGateways": [
                {"NatGatewayId": "nat-1", "State": "available"},
                {"NatGatewayId": "nat-2", "State": "pending"},
            ]
        }
        mock_ec2.describe_vpc_endpoints.return_value = {"VpcEndpoints": []}

        analysis = {"can_delete": True, "blocking_resources": [], "dependencies": []}
        _check_vpc_network_resources(mock_ec2, "vpc-123", analysis)

        assert analysis["can_delete"] is False
        assert "2 NAT Gateways" in analysis["blocking_resources"]

    def test_check_excludes_deleted_nat_gateways(self):
        """Test that deleted NAT Gateways are excluded."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_internet_gateways.return_value = {"InternetGateways": []}
        mock_ec2.describe_nat_gateways.return_value = {"NatGateways": [{"NatGatewayId": "nat-1", "State": "deleted"}]}
        mock_ec2.describe_vpc_endpoints.return_value = {"VpcEndpoints": []}

        analysis = {"can_delete": True, "blocking_resources": [], "dependencies": []}
        _check_vpc_network_resources(mock_ec2, "vpc-123", analysis)

        assert analysis["can_delete"] is True

    def test_check_with_vpc_endpoints(self):
        """Test checking VPC with VPC Endpoints."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_internet_gateways.return_value = {"InternetGateways": []}
        mock_ec2.describe_nat_gateways.return_value = {"NatGateways": []}
        mock_ec2.describe_vpc_endpoints.return_value = {
            "VpcEndpoints": [
                {"VpcEndpointId": "vpce-1", "State": "available"},
                {"VpcEndpointId": "vpce-2", "State": "pending"},
            ]
        }

        analysis = {"can_delete": True, "blocking_resources": [], "dependencies": []}
        _check_vpc_network_resources(mock_ec2, "vpc-123", analysis)

        assert analysis["can_delete"] is False
        assert "2 VPC Endpoints" in analysis["blocking_resources"]

    def test_check_excludes_deleted_endpoints(self):
        """Test that deleted VPC Endpoints are excluded."""
        mock_ec2 = MagicMock()
        mock_ec2.describe_internet_gateways.return_value = {"InternetGateways": []}
        mock_ec2.describe_nat_gateways.return_value = {"NatGateways": []}
        mock_ec2.describe_vpc_endpoints.return_value = {"VpcEndpoints": [{"VpcEndpointId": "vpce-1", "State": "deleted"}]}

        analysis = {"can_delete": True, "blocking_resources": [], "dependencies": []}
        _check_vpc_network_resources(mock_ec2, "vpc-123", analysis)

        assert analysis["can_delete"] is True


class TestCheckVpcLoadBalancers:
    """Tests for _check_vpc_load_balancers function."""

    def test_check_with_load_balancers(self):
        """Test checking VPC with load balancers."""
        with patch("boto3.client") as mock_boto3:
            mock_elbv2 = MagicMock()
            mock_boto3.return_value = mock_elbv2
            mock_elbv2.describe_load_balancers.return_value = {
                "LoadBalancers": [
                    {"LoadBalancerArn": "lb-1", "VpcId": "vpc-123"},
                    {"LoadBalancerArn": "lb-2", "VpcId": "vpc-123"},
                    {"LoadBalancerArn": "lb-3", "VpcId": "vpc-456"},
                ]
            }

            analysis = {"can_delete": True, "blocking_resources": []}
            _check_vpc_load_balancers("us-east-1", "vpc-123", analysis)

            assert analysis["can_delete"] is False
            assert "2 Load Balancers" in analysis["blocking_resources"]

    def test_check_with_no_load_balancers(self):
        """Test checking VPC with no load balancers."""
        with patch("boto3.client") as mock_boto3:
            mock_elbv2 = MagicMock()
            mock_boto3.return_value = mock_elbv2
            mock_elbv2.describe_load_balancers.return_value = {"LoadBalancers": []}

            analysis = {"can_delete": True, "blocking_resources": []}
            _check_vpc_load_balancers("us-east-1", "vpc-123", analysis)

            assert analysis["can_delete"] is True

    def test_check_with_error(self, capsys):
        """Test error handling when checking load balancers."""
        with patch("boto3.client") as mock_boto3:
            mock_elbv2 = MagicMock()
            mock_boto3.return_value = mock_elbv2
            mock_elbv2.describe_load_balancers.side_effect = ClientError({"Error": {"Code": "ServiceError"}}, "describe_load_balancers")

            analysis = {"can_delete": True, "blocking_resources": []}
            _check_vpc_load_balancers("us-east-1", "vpc-123", analysis)

            captured = capsys.readouterr()
            assert "Warning: Could not check load balancers" in captured.out
