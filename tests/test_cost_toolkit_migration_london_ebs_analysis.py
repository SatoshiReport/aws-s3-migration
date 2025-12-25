"""Comprehensive tests for aws_london_ebs_analysis.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.migration.aws_london_ebs_analysis import (
    _analyze_snapshots,
    _check_unattached_volume,
    _print_recommendations,
    _print_volume_details,
    _start_stopped_instance,
    analyze_london_ebs,
)


@patch("cost_toolkit.scripts.migration.aws_london_ebs_analysis._print_recommendations")
@patch("cost_toolkit.scripts.migration.aws_london_ebs_analysis._analyze_snapshots")
@patch("cost_toolkit.scripts.migration.aws_london_ebs_analysis._check_unattached_volume")
@patch("cost_toolkit.scripts.migration.aws_london_ebs_analysis._start_stopped_instance")
@patch("cost_toolkit.scripts.migration.aws_london_ebs_analysis.aws_utils.setup_aws_credentials")
@patch("cost_toolkit.scripts.migration.aws_london_ebs_analysis.boto3.client")
def test_analyze_london_ebs_calls_setup(
    mock_boto_client,
    mock_setup_creds,
    _mock_start_instance,
    _mock_check_unattached,
    _mock_analyze_snapshots,
    _mock_print_recommendations,
):
    """analyze_london_ebs should initialize credentials before running."""
    mock_ec2 = MagicMock()
    mock_boto_client.return_value = mock_ec2

    analyze_london_ebs()

    mock_setup_creds.assert_called_once()


class TestPrintVolumeDetails:
    """Tests for _print_volume_details function."""

    def test_print_volume_details_success(self, capsys):
        """Test printing volume details successfully."""
        mock_ec2 = MagicMock()

        volume_data = {
            "Volumes": [
                {
                    "VolumeId": "vol-12345",
                    "Size": 100,
                    "Attachments": [{"Device": "/dev/sda1"}],
                    "CreateTime": "2024-01-15T12:00:00.000Z",
                    "Tags": [
                        {"Key": "Name", "Value": "TestVolume"},
                        {"Key": "Environment", "Value": "Production"},
                    ],
                }
            ]
        }
        mock_ec2.describe_volumes.return_value = volume_data

        vol = {"id": "vol-12345", "size": "100 GB"}

        _print_volume_details(mock_ec2, vol)

        captured = capsys.readouterr()
        assert "Volume: vol-12345" in captured.out
        assert "Size: 100 GB" in captured.out
        assert "Device: /dev/sda1" in captured.out
        assert "Name: TestVolume" in captured.out

    def test_print_volume_details_no_attachments(self, capsys):
        """Test printing volume details without attachments."""
        mock_ec2 = MagicMock()

        volume_data = {
            "Volumes": [
                {
                    "VolumeId": "vol-12345",
                    "Size": 100,
                    "Attachments": [],
                    "CreateTime": "2024-01-15T12:00:00.000Z",
                    "Tags": [],
                }
            ]
        }
        mock_ec2.describe_volumes.return_value = volume_data

        vol = {"id": "vol-12345", "size": "100 GB"}

        _print_volume_details(mock_ec2, vol)

        captured = capsys.readouterr()
        assert "Device: Unknown" in captured.out
        assert "Name: No name" in captured.out

    def test_print_volume_details_client_error(self, capsys):
        """Test printing volume details with ClientError."""
        mock_ec2 = MagicMock()

        error = ClientError(
            {"Error": {"Code": "VolumeNotFound", "Message": "Volume not found"}},
            "describe_volumes",
        )
        mock_ec2.describe_volumes.side_effect = error

        vol = {"id": "vol-12345", "size": "100 GB"}

        _print_volume_details(mock_ec2, vol)

        captured = capsys.readouterr()
        assert "Error getting details for vol-12345" in captured.out


class TestCheckUnattachedVolume:
    """Tests for _check_unattached_volume function."""

    def test_check_unattached_volume_success(self, capsys):
        """Test checking unattached volume successfully."""
        mock_ec2 = MagicMock()

        volume_data = {
            "Volumes": [
                {
                    "VolumeId": "vol-unattached",
                    "Size": 32,
                    "CreateTime": "2024-01-10T12:00:00.000Z",
                    "Tags": [{"Key": "Name", "Value": "OldVolume"}],
                }
            ]
        }
        mock_ec2.describe_volumes.return_value = volume_data

        unattached_vol = {"id": "vol-unattached", "size": "32 GB"}

        _check_unattached_volume(mock_ec2, unattached_vol)

        captured = capsys.readouterr()
        assert "Unattached Volume Details" in captured.out
        assert "Volume: vol-unattached" in captured.out
        assert "Size: 32 GB" in captured.out
        assert "Name: OldVolume" in captured.out

    def test_check_unattached_volume_client_error(self, capsys):
        """Test checking unattached volume with ClientError."""
        mock_ec2 = MagicMock()

        error = ClientError(
            {"Error": {"Code": "VolumeNotFound", "Message": "Volume not found"}},
            "describe_volumes",
        )
        mock_ec2.describe_volumes.side_effect = error

        unattached_vol = {"id": "vol-unattached", "size": "32 GB"}

        _check_unattached_volume(mock_ec2, unattached_vol)

        captured = capsys.readouterr()
        assert "Error getting details for vol-unattached" in captured.out


class TestStartStoppedInstance:
    """Tests for _start_stopped_instance function."""

    def test_start_instance_success(self, capsys):
        """Test starting instance successfully."""
        mock_ec2 = MagicMock()

        mock_waiter = MagicMock()
        mock_ec2.get_waiter.return_value = mock_waiter

        instance_data = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-12345",
                            "PublicIpAddress": "203.0.113.1",
                            "PrivateIpAddress": "10.0.0.1",
                        }
                    ]
                }
            ]
        }
        mock_ec2.describe_instances.return_value = instance_data

        _start_stopped_instance(mock_ec2, "i-12345")

        mock_ec2.start_instances.assert_called_once_with(InstanceIds=["i-12345"])
        mock_waiter.wait.assert_called_once_with(InstanceIds=["i-12345"], WaiterConfig={"Delay": 15, "MaxAttempts": 20})
        captured = capsys.readouterr()
        assert "Instance is now running" in captured.out
        assert "Public IP: 203.0.113.1" in captured.out
        assert "Private IP: 10.0.0.1" in captured.out

    def test_start_instance_no_public_ip(self, capsys):
        """Test starting instance without public IP."""
        mock_ec2 = MagicMock()

        mock_waiter = MagicMock()
        mock_ec2.get_waiter.return_value = mock_waiter

        instance_data = {"Reservations": [{"Instances": [{"InstanceId": "i-12345", "PrivateIpAddress": "10.0.0.1"}]}]}
        mock_ec2.describe_instances.return_value = instance_data

        _start_stopped_instance(mock_ec2, "i-12345")

        captured = capsys.readouterr()
        assert "Public IP: No public IP" in captured.out
        assert "Private IP: 10.0.0.1" in captured.out

    def test_start_instance_client_error(self, capsys):
        """Test starting instance with ClientError."""
        mock_ec2 = MagicMock()

        error = ClientError(
            {"Error": {"Code": "InstanceNotFound", "Message": "Instance not found"}},
            "start_instances",
        )
        mock_ec2.start_instances.side_effect = error

        _start_stopped_instance(mock_ec2, "i-12345")

        captured = capsys.readouterr()
        assert "Error starting instance" in captured.out


class TestAnalyzeSnapshots:
    """Tests for _analyze_snapshots function."""

    def test_analyze_snapshots_with_related(self, capsys):
        """Test analyzing snapshots with related snapshots."""
        mock_ec2 = MagicMock()

        snapshots_data = {
            "Snapshots": [
                {
                    "SnapshotId": "snap-12345",
                    "VolumeSize": 100,
                    "StartTime": "2024-01-15T12:00:00.000Z",
                    "Description": "Snapshot for vol-abc123",
                },
                {
                    "SnapshotId": "snap-67890",
                    "VolumeSize": 50,
                    "StartTime": "2024-01-14T12:00:00.000Z",
                    "Description": "Snapshot for i-instance123",
                },
            ]
        }
        mock_ec2.describe_snapshots.return_value = snapshots_data

        instance_id = "i-instance123"
        attached_volumes = [{"id": "vol-abc123", "size": "100 GB"}]

        _analyze_snapshots(mock_ec2, instance_id, attached_volumes)

        captured = capsys.readouterr()
        assert "Related Snapshots Analysis" in captured.out
        assert "Found 2 snapshots" in captured.out
        assert "snap-12345" in captured.out
        assert "snap-67890" in captured.out

    def test_analyze_snapshots_no_related(self, capsys):
        """Test analyzing snapshots with no related snapshots."""
        mock_ec2 = MagicMock()

        snapshots_data = {
            "Snapshots": [
                {
                    "SnapshotId": "snap-other",
                    "VolumeSize": 10,
                    "StartTime": "2024-01-15T12:00:00.000Z",
                    "Description": "Unrelated snapshot",
                }
            ]
        }
        mock_ec2.describe_snapshots.return_value = snapshots_data

        instance_id = "i-instance123"
        attached_volumes = [{"id": "vol-abc123", "size": "100 GB"}]

        _analyze_snapshots(mock_ec2, instance_id, attached_volumes)

        captured = capsys.readouterr()
        assert "No snapshots directly related to this instance found" in captured.out

    def test_analyze_snapshots_client_error(self, capsys):
        """Test analyzing snapshots with ClientError."""
        mock_ec2 = MagicMock()

        error = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "describe_snapshots",
        )
        mock_ec2.describe_snapshots.side_effect = error

        instance_id = "i-instance123"
        attached_volumes = []

        _analyze_snapshots(mock_ec2, instance_id, attached_volumes)

        captured = capsys.readouterr()
        assert "Error analyzing snapshots" in captured.out


class TestPrintRecommendations:
    """Tests for _print_recommendations function."""

    def test_print_recommendations_with_duplicates(self, capsys):
        """Test printing recommendations with duplicate volume sizes."""
        attached_volumes = [
            {"id": "vol-1", "size": "1024 GB"},
            {"id": "vol-2", "size": "1024 GB"},
            {"id": "vol-3", "size": "384 GB"},
        ]
        unattached_volume = {"id": "vol-unattached", "size": "32 GB"}

        _print_recommendations(attached_volumes, unattached_volume, "running")

        captured = capsys.readouterr()
        assert "ANALYSIS & RECOMMENDATIONS" in captured.out
        assert "Found volumes with duplicate sizes" in captured.out
        assert "1024 GB" in captured.out
        assert "Unattached volume vol-unattached" in captured.out
        assert "NEXT STEPS" in captured.out

    def test_print_recommendations_no_duplicates(self, capsys):
        """Test printing recommendations without duplicate sizes."""
        attached_volumes = [
            {"id": "vol-1", "size": "1024 GB"},
            {"id": "vol-2", "size": "384 GB"},
            {"id": "vol-3", "size": "64 GB"},
        ]
        unattached_volume = {"id": "vol-unattached", "size": "32 GB"}

        _print_recommendations(attached_volumes, unattached_volume, "running")

        captured = capsys.readouterr()
        assert "ANALYSIS & RECOMMENDATIONS" in captured.out
        assert "Found volumes with duplicate sizes" not in captured.out

    def test_print_recommendations_stopped_instance(self, capsys):
        """Test printing recommendations for stopped instance."""
        attached_volumes = [{"id": "vol-1", "size": "100 GB"}]
        unattached_volume = {"id": "vol-unattached", "size": "32 GB"}

        _print_recommendations(attached_volumes, unattached_volume, "stopped")

        captured = capsys.readouterr()
        assert "IMPORTANT: Instance was started for analysis" in captured.out
        assert "Remember to stop it after analysis" in captured.out
