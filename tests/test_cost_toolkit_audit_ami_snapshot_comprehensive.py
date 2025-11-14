"""Comprehensive tests for aws_ami_snapshot_analysis.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.audit.aws_ami_snapshot_analysis import (
    _analyze_single_snapshot,
    _analyze_snapshot_cost,
    _print_ami_details,
    _print_ami_tags,
    _print_ami_usage,
    analyze_snapshot_ami_relationships,
    check_ami_usage,
    get_ami_details,
    load_aws_credentials,
)


def test_load_aws_credentials_calls_setup_credentials():
    """Test that function calls setup utility."""
    with patch(
        "cost_toolkit.scripts.audit.aws_ami_snapshot_analysis.setup_aws_credentials"
    ) as mock_setup:
        mock_setup.return_value = ("key", "secret")

        result = load_aws_credentials()

        mock_setup.assert_called_once()
        assert result == ("key", "secret")


class TestGetAmiDetails:
    """Tests for get_ami_details function."""

    def test_get_ami_details_success(self):
        """Test successful retrieval of AMI details."""
        mock_client = MagicMock()
        mock_client.describe_images.return_value = {
            "Images": [
                {
                    "ImageId": "ami-123",
                    "Name": "test-ami",
                    "Description": "Test AMI",
                    "State": "available",
                    "CreationDate": "2024-01-01",
                    "OwnerId": "123456789",
                    "Public": False,
                    "Platform": "Linux",
                    "Architecture": "x86_64",
                    "VirtualizationType": "hvm",
                    "RootDeviceType": "ebs",
                    "BlockDeviceMappings": [],
                    "Tags": [],
                }
            ]
        }

        result = get_ami_details(mock_client, "ami-123")

        assert result is not None
        assert result["ami_id"] == "ami-123"
        assert result["name"] == "test-ami"
        assert result["description"] == "Test AMI"
        assert result["state"] == "available"
        assert result["public"] is False

    def test_get_ami_details_no_images(self):
        """Test when no images returned."""
        mock_client = MagicMock()
        mock_client.describe_images.return_value = {"Images": []}

        result = get_ami_details(mock_client, "ami-123")

        assert result is None

    def test_get_ami_details_error(self):
        """Test error when retrieving AMI details."""
        mock_client = MagicMock()
        mock_client.describe_images.side_effect = ClientError(
            {"Error": {"Code": "InvalidAMIID.NotFound"}}, "describe_images"
        )

        result = get_ami_details(mock_client, "ami-notfound")

        assert result is not None
        assert "error" in result
        assert result["accessible"] is False


class TestCheckAmiUsage:
    """Tests for check_ami_usage function."""

    def test_check_usage_with_instances(self):
        """Test checking AMI usage when instances exist."""
        mock_client = MagicMock()
        mock_client.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-123",
                            "State": {"Name": "running"},
                            "LaunchTime": "2024-01-01",
                            "InstanceType": "t2.micro",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }

        instances = check_ami_usage(mock_client, "ami-123")

        assert len(instances) == 1
        assert instances[0]["instance_id"] == "i-123"
        assert instances[0]["state"] == "running"

    def test_check_usage_no_instances(self):
        """Test checking AMI usage when no instances."""
        mock_client = MagicMock()
        mock_client.describe_instances.return_value = {"Reservations": []}

        instances = check_ami_usage(mock_client, "ami-123")

        assert not instances

    def test_check_usage_error(self, capsys):
        """Test error when checking AMI usage."""
        mock_client = MagicMock()
        mock_client.describe_instances.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "describe_instances"
        )

        instances = check_ami_usage(mock_client, "ami-123")

        assert not instances
        captured = capsys.readouterr()
        assert "Error checking AMI usage" in captured.out


def test_print_ami_details_print_details(capsys):
    """Test printing AMI details."""
    ami_details = {
        "name": "test-ami",
        "description": "Test AMI",
        "creation_date": "2024-01-01",
        "architecture": "x86_64",
        "platform": "Linux",
        "state": "available",
        "public": False,
    }

    _print_ami_details(ami_details)

    captured = capsys.readouterr()
    assert "test-ami" in captured.out
    assert "Test AMI" in captured.out
    assert "2024-01-01" in captured.out
    assert "x86_64" in captured.out
    assert "Linux" in captured.out


class TestPrintAmiTags:
    """Tests for _print_ami_tags function."""

    def test_print_tags_with_tags(self, capsys):
        """Test printing when tags exist."""
        ami_details = {
            "tags": [
                {"Key": "Environment", "Value": "prod"},
                {"Key": "Owner", "Value": "team"},
            ]
        }

        _print_ami_tags(ami_details)

        captured = capsys.readouterr()
        assert "Tags:" in captured.out
        assert "Environment: prod" in captured.out
        assert "Owner: team" in captured.out

    def test_print_tags_no_tags(self, capsys):
        """Test printing when no tags."""
        ami_details = {"tags": []}

        _print_ami_tags(ami_details)

        captured = capsys.readouterr()
        assert "Tags: None" in captured.out


class TestPrintAmiUsage:
    """Tests for _print_ami_usage function."""

    def test_print_usage_with_instances(self, capsys):
        """Test printing when instances exist."""
        instances = [
            {
                "instance_id": "i-123",
                "state": "running",
                "tags": [{"Key": "Name", "Value": "web-server"}],
            },
            {
                "instance_id": "i-456",
                "state": "stopped",
                "tags": [],
            },
        ]

        _print_ami_usage(instances)

        captured = capsys.readouterr()
        assert "Currently used by 2 instance(s)" in captured.out
        assert "i-123 (web-server)" in captured.out
        assert "i-456 (Unnamed)" in captured.out

    def test_print_usage_no_instances(self, capsys):
        """Test printing when no instances."""
        _print_ami_usage([])

        captured = capsys.readouterr()
        assert "Not currently used" in captured.out


class TestAnalyzeSnapshotCost:
    """Tests for _analyze_snapshot_cost function."""

    def test_analyze_cost_unused_ami(self, capsys):
        """Test analyzing cost for unused AMI."""
        mock_client = MagicMock()
        mock_client.describe_snapshots.return_value = {
            "Snapshots": [
                {
                    "SnapshotId": "snap-123",
                    "VolumeSize": 100,
                }
            ]
        }

        cost = _analyze_snapshot_cost(mock_client, "snap-123", [])

        assert cost == 5.0  # 100 * 0.05
        captured = capsys.readouterr()
        assert "Monthly cost: $5.00" in captured.out
        assert "RECOMMENDATION" in captured.out

    def test_analyze_cost_used_ami(self, capsys):
        """Test analyzing cost for AMI in use."""
        mock_client = MagicMock()
        mock_client.describe_snapshots.return_value = {
            "Snapshots": [{"SnapshotId": "snap-123", "VolumeSize": 200}]
        }

        instances = [{"instance_id": "i-123"}]
        cost = _analyze_snapshot_cost(mock_client, "snap-123", instances)

        assert cost == 10.0  # 200 * 0.05
        captured = capsys.readouterr()
        assert "CAUTION: AMI is in use" in captured.out

    def test_analyze_cost_error(self, capsys):
        """Test error when analyzing cost."""
        mock_client = MagicMock()
        mock_client.describe_snapshots.side_effect = ClientError(
            {"Error": {"Code": "InvalidSnapshot.NotFound"}}, "describe_snapshots"
        )

        cost = _analyze_snapshot_cost(mock_client, "snap-notfound", [])

        assert cost == 0
        captured = capsys.readouterr()
        assert "Error getting snapshot details" in captured.out


class TestAnalyzeSingleSnapshot:
    """Tests for _analyze_single_snapshot function."""

    def test_analyze_snapshot_success(self, capsys):
        """Test successful snapshot analysis."""
        mock_client = MagicMock()

        ami_details = {
            "ami_id": "ami-123",
            "name": "test-ami",
            "description": "Test",
            "creation_date": "2024-01-01",
            "architecture": "x86_64",
            "platform": "Linux",
            "state": "available",
            "public": False,
            "tags": [],
        }

        with patch(
            "cost_toolkit.scripts.audit.aws_ami_snapshot_analysis.get_ami_details",
            return_value=ami_details,
        ):
            with patch(
                "cost_toolkit.scripts.audit.aws_ami_snapshot_analysis.check_ami_usage",
                return_value=[],
            ):
                with patch(
                    "cost_toolkit.scripts.audit.aws_ami_snapshot_analysis._analyze_snapshot_cost",
                    return_value=5.0,
                ):
                    cost = _analyze_single_snapshot(mock_client, "snap-123", "ami-123", "us-east-1")

        assert cost == 5.0
        captured = capsys.readouterr()
        assert "Analyzing snap-123" in captured.out

    def test_analyze_snapshot_ami_error(self, capsys):
        """Test analysis when AMI has error."""
        mock_client = MagicMock()

        ami_details = {
            "ami_id": "ami-123",
            "error": "Not found",
            "accessible": False,
        }

        with patch(
            "cost_toolkit.scripts.audit.aws_ami_snapshot_analysis.get_ami_details",
            return_value=ami_details,
        ):
            cost = _analyze_single_snapshot(mock_client, "snap-123", "ami-123", "us-east-1")

        assert cost == 0
        captured = capsys.readouterr()
        assert "Error accessing AMI" in captured.out

    def test_analyze_snapshot_ami_not_found(self, capsys):
        """Test analysis when AMI not found."""
        mock_client = MagicMock()

        with patch(
            "cost_toolkit.scripts.audit.aws_ami_snapshot_analysis.get_ami_details",
            return_value=None,
        ):
            cost = _analyze_single_snapshot(mock_client, "snap-123", "ami-123", "us-east-1")

        assert cost == 0
        captured = capsys.readouterr()
        assert "AMI not found or inaccessible" in captured.out


class TestAnalyzeSnapshotAmiRelationships:
    """Tests for analyze_snapshot_ami_relationships function."""

    def test_analyze_relationships_success(self, capsys):
        """Test successful analysis of relationships."""
        with patch(
            "cost_toolkit.scripts.audit.aws_ami_snapshot_analysis.load_aws_credentials",
            return_value=("key", "secret"),
        ):
            with patch("boto3.client") as mock_client:
                mock_ec2 = MagicMock()
                mock_client.return_value = mock_ec2

                with patch(
                    "cost_toolkit.scripts.audit.aws_ami_snapshot_analysis._analyze_single_snapshot",
                    return_value=5.0,
                ):
                    analyze_snapshot_ami_relationships()

        captured = capsys.readouterr()
        assert "AWS AMI and Snapshot Analysis" in captured.out
        assert "SUMMARY" in captured.out
        assert "Total snapshots analyzed:" in captured.out
        assert "Total potential monthly savings" in captured.out
        assert "NEXT STEPS" in captured.out

    def test_analyze_relationships_with_zero_savings(self, capsys):
        """Test analysis with no potential savings."""
        with patch(
            "cost_toolkit.scripts.audit.aws_ami_snapshot_analysis.load_aws_credentials",
            return_value=("key", "secret"),
        ):
            with patch("boto3.client"):
                with patch(
                    "cost_toolkit.scripts.audit.aws_ami_snapshot_analysis._analyze_single_snapshot",
                    return_value=0,
                ):
                    analyze_snapshot_ami_relationships()

        captured = capsys.readouterr()
        assert "$0.00" in captured.out or "$0" in captured.out
