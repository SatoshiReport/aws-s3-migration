"""Comprehensive tests for aws_london_ebs_analysis.py main functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.migration.aws_london_ebs_analysis import (
    analyze_london_ebs,
    main,
)


def test_analyze_running_instance(capsys):
    """Test analyzing a running instance."""
    mod = "cost_toolkit.scripts.migration.aws_london_ebs_analysis"
    with (
        patch(f"{mod}.setup_aws_credentials") as mock_setup_creds,
        patch(f"{mod}.boto3.client") as mock_boto_client,
        patch(f"{mod}._print_volume_details"),
        patch(f"{mod}._check_unattached_volume"),
        patch(f"{mod}._analyze_snapshots"),
        patch(f"{mod}._print_recommendations"),
    ):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        instance_data = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-05ad29f28fc8a8fdc",
                            "State": {"Name": "running"},
                            "InstanceType": "t3.medium",
                            "PublicIpAddress": "203.0.113.1",
                            "PrivateIpAddress": "10.0.0.1",
                        }
                    ]
                }
            ]
        }
        mock_ec2.describe_instances.return_value = instance_data
        analyze_london_ebs()
        mock_setup_creds.assert_called_once()
        mock_boto_client.assert_called_once_with("ec2", region_name="eu-west-2")
        captured = capsys.readouterr()
        assert "AWS London EBS Analysis" in captured.out
        assert "Instance is already running" in captured.out
        assert "Public IP: 203.0.113.1" in captured.out


def test_analyze_stopped_instance(capsys):
    """Test analyzing a stopped instance."""
    with (
        patch("cost_toolkit.scripts.migration.aws_london_ebs_analysis.setup_aws_credentials"),
        patch(
            "cost_toolkit.scripts.migration.aws_london_ebs_analysis.boto3.client"
        ) as mock_boto_client,
        patch("cost_toolkit.scripts.migration.aws_london_ebs_analysis._print_volume_details"),
        patch("cost_toolkit.scripts.migration.aws_london_ebs_analysis._check_unattached_volume"),
        patch(
            "cost_toolkit.scripts.migration.aws_london_ebs_analysis._start_stopped_instance"
        ) as mock_start_instance,
        patch("cost_toolkit.scripts.migration.aws_london_ebs_analysis._analyze_snapshots"),
        patch("cost_toolkit.scripts.migration.aws_london_ebs_analysis._print_recommendations"),
    ):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        instance_data = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-05ad29f28fc8a8fdc",
                            "State": {"Name": "stopped"},
                            "InstanceType": "t3.medium",
                        }
                    ]
                }
            ]
        }
        mock_ec2.describe_instances.return_value = instance_data
        analyze_london_ebs()
        mock_start_instance.assert_called_once_with(mock_ec2, "i-05ad29f28fc8a8fdc")
        captured = capsys.readouterr()
        assert "Current State: stopped" in captured.out


def test_analyze_instance_other_state(capsys):
    """Test analyzing instance in other state (e.g., pending)."""
    mod = "cost_toolkit.scripts.migration.aws_london_ebs_analysis"
    with (
        patch(f"{mod}.setup_aws_credentials"),
        patch(f"{mod}.boto3.client") as mock_boto_client,
        patch(f"{mod}._print_volume_details"),
        patch(f"{mod}._check_unattached_volume"),
        patch(f"{mod}._analyze_snapshots"),
        patch(f"{mod}._print_recommendations"),
    ):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        instance_data = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-05ad29f28fc8a8fdc",
                            "State": {"Name": "pending"},
                            "InstanceType": "t3.medium",
                        }
                    ]
                }
            ]
        }
        mock_ec2.describe_instances.return_value = instance_data
        analyze_london_ebs()
        captured = capsys.readouterr()
        assert "Instance is in 'pending' state" in captured.out


class TestAnalyzeLondonEbsAnalysis:
    """Tests for analyze_london_ebs function analysis and output."""

    def test_analyze_prints_volume_details(self):
        """Test that analyze function prints all volume details."""
        mod = "cost_toolkit.scripts.migration.aws_london_ebs_analysis"
        with (
            patch(f"{mod}.setup_aws_credentials"),
            patch(f"{mod}.boto3.client") as mock_boto_client,
            patch(f"{mod}._print_volume_details") as mock_volume_details,
            patch(f"{mod}._check_unattached_volume") as mock_unattached,
            patch(f"{mod}._analyze_snapshots") as mock_snapshots,
            patch(f"{mod}._print_recommendations") as mock_recommendations,
        ):
            mock_ec2 = MagicMock()
            mock_boto_client.return_value = mock_ec2

            instance_data = {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-05ad29f28fc8a8fdc",
                                "State": {"Name": "running"},
                                "InstanceType": "t3.medium",
                            }
                        ]
                    }
                ]
            }
            mock_ec2.describe_instances.return_value = instance_data

            analyze_london_ebs()

            assert mock_volume_details.call_count == 4
            mock_unattached.assert_called_once()
            mock_snapshots.assert_called_once()
            mock_recommendations.assert_called_once()

    def test_analyze_displays_summary(self, capsys):
        """Test that analyze function displays complete summary."""
        mod = "cost_toolkit.scripts.migration.aws_london_ebs_analysis"
        with (
            patch(f"{mod}.setup_aws_credentials"),
            patch(f"{mod}.boto3.client") as mock_boto_client,
            patch(f"{mod}._print_volume_details"),
            patch(f"{mod}._check_unattached_volume"),
            patch(f"{mod}._analyze_snapshots"),
            patch(f"{mod}._print_recommendations"),
        ):
            mock_ec2 = MagicMock()
            mock_boto_client.return_value = mock_ec2

            instance_data = {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-05ad29f28fc8a8fdc",
                                "State": {"Name": "running"},
                                "InstanceType": "t3.medium",
                            }
                        ]
                    }
                ]
            }
            mock_ec2.describe_instances.return_value = instance_data

            analyze_london_ebs()

            captured = capsys.readouterr()
            assert "London EBS Summary" in captured.out
            assert "Instance: i-05ad29f28fc8a8fdc" in captured.out
            assert "Attached volumes: 4" in captured.out
            assert "Unattached volumes: 1" in captured.out
            assert "Instance Type: t3.medium" in captured.out


def test_analyze_running_instance_no_public_ip(capsys):
    """Test analyzing running instance without public IP."""
    mod = "cost_toolkit.scripts.migration.aws_london_ebs_analysis"
    with (
        patch(f"{mod}.setup_aws_credentials"),
        patch(f"{mod}.boto3.client") as mock_boto_client,
        patch(f"{mod}._print_volume_details"),
        patch(f"{mod}._check_unattached_volume"),
        patch(f"{mod}._analyze_snapshots"),
        patch(f"{mod}._print_recommendations"),
    ):
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2

        instance_data = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-05ad29f28fc8a8fdc",
                            "State": {"Name": "running"},
                            "InstanceType": "t3.medium",
                            "PrivateIpAddress": "10.0.0.1",
                        }
                    ]
                }
            ]
        }
        mock_ec2.describe_instances.return_value = instance_data

        analyze_london_ebs()

        captured = capsys.readouterr()
        assert "Public IP: No public IP" in captured.out
        assert "Private IP: 10.0.0.1" in captured.out


@patch("cost_toolkit.scripts.migration.aws_london_ebs_analysis.setup_aws_credentials")
@patch("cost_toolkit.scripts.migration.aws_london_ebs_analysis.boto3.client")
def test_analyze_client_error(mock_boto_client, _mock_setup_creds, capsys):
    """Test analyzing with ClientError."""
    mock_ec2 = MagicMock()
    mock_boto_client.return_value = mock_ec2

    error = ClientError(
        {"Error": {"Code": "InstanceNotFound", "Message": "Instance not found"}},
        "describe_instances",
    )
    mock_ec2.describe_instances.side_effect = error

    analyze_london_ebs()

    captured = capsys.readouterr()
    assert "Error analyzing instance" in captured.out


@patch("cost_toolkit.scripts.migration.aws_london_ebs_analysis.analyze_london_ebs")
def test_main_calls_analyze(mock_analyze):
    """Test that main function calls analyze_london_ebs."""
    main()

    mock_analyze.assert_called_once()
