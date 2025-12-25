"""Tests for aws_fix_termination_protection script."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_fix_termination_protection import (
    disable_termination_protection_and_terminate,
    main,
)


class TestDisableTerminationProtectionAndTerminate:
    """Test disabling termination protection and terminating instance."""

    def test_disable_and_terminate_success(self, capsys):
        """Test successful disable and terminate operation."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.modify_instance_attribute.return_value = {}
            mock_ec2.terminate_instances.return_value = {}
            mock_client.return_value = mock_ec2
            result = disable_termination_protection_and_terminate("i-123", "us-east-1")
            assert result is True
            captured = capsys.readouterr()
            assert "Disabling termination protection for i-123 in us-east-1" in captured.out
            assert "Disabling termination protection..." in captured.out
            assert "Termination protection disabled" in captured.out
            assert "Terminating instance..." in captured.out
            assert "Instance i-123 termination initiated" in captured.out
            assert "This will stop EBS storage charges" in captured.out
            mock_ec2.modify_instance_attribute.assert_called_once_with(InstanceId="i-123", DisableApiTermination={"Value": False})
            mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=["i-123"])

    def test_disable_and_terminate_modify_error(self, capsys):
        """Test handling of error during modify_instance_attribute."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            error = ClientError(
                {"Error": {"Code": "InvalidInstanceID.NotFound", "Message": "Instance not found"}},
                "modify_instance_attribute",
            )
            mock_ec2.modify_instance_attribute.side_effect = error
            mock_client.return_value = mock_ec2
            result = disable_termination_protection_and_terminate("i-123", "us-east-1")
            assert result is False
            captured = capsys.readouterr()
            assert "Error:" in captured.out
            assert mock_ec2.terminate_instances.call_count == 0

    def test_disable_and_terminate_terminate_error(self, capsys):
        """Test handling of error during terminate_instances."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.modify_instance_attribute.return_value = {}
            error = ClientError(
                {"Error": {"Code": "OperationNotPermitted", "Message": "Cannot terminate"}},
                "terminate_instances",
            )
            mock_ec2.terminate_instances.side_effect = error
            mock_client.return_value = mock_ec2
            result = disable_termination_protection_and_terminate("i-123", "us-east-1")
            assert result is False
            captured = capsys.readouterr()
            assert "Termination protection disabled" in captured.out
            assert "Error:" in captured.out

    def test_disable_and_terminate_uses_region(self):
        """Test that correct region is used."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.modify_instance_attribute.return_value = {}
            mock_ec2.terminate_instances.return_value = {}
            mock_client.return_value = mock_ec2
            disable_termination_protection_and_terminate("i-456", "eu-west-2")
            mock_client.assert_called_once_with("ec2", region_name="eu-west-2")

    def test_disable_and_terminate_different_instances(self, capsys):
        """Test with different instance IDs."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_ec2.modify_instance_attribute.return_value = {}
            mock_ec2.terminate_instances.return_value = {}
            mock_client.return_value = mock_ec2
            result = disable_termination_protection_and_terminate("i-abc123", "ap-south-1")
            assert result is True
            captured = capsys.readouterr()
            assert "i-abc123" in captured.out
            assert "ap-south-1" in captured.out

    def test_disable_and_terminate_generic_client_error(self, capsys):
        """Test handling of generic ClientError."""
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            error = ClientError(
                {"Error": {"Code": "ServiceUnavailable", "Message": "Service unavailable"}},
                "modify_instance_attribute",
            )
            mock_ec2.modify_instance_attribute.side_effect = error
            mock_client.return_value = mock_ec2
            result = disable_termination_protection_and_terminate("i-123", "us-east-1")
            assert result is False
            captured = capsys.readouterr()
            assert "Error:" in captured.out


class TestMain:
    """Test main execution function."""

    def test_main_success(self, capsys):
        """Test successful main execution."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_fix_termination_protection." "disable_termination_protection_and_terminate"
        ) as mock_disable:
            mock_disable.return_value = True
            main()
            captured = capsys.readouterr()
            assert "AWS Fix Termination Protection" in captured.out
            assert "Fixing termination protection for mufasa instance" in captured.out
            assert "RESULT:" in captured.out
            assert "Successfully disabled protection and terminated i-0cfce47f50e3c34f" in captured.out
            assert "Additional monthly savings: $0.64 (8GB EBS volume)" in captured.out
            mock_disable.assert_called_once_with("i-0cfce47f50e3c34f", "us-east-1")

    def test_main_failure(self, capsys):
        """Test main execution with failure."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_fix_termination_protection." "disable_termination_protection_and_terminate"
        ) as mock_disable:
            mock_disable.return_value = False
            main()
            captured = capsys.readouterr()
            assert "AWS Fix Termination Protection" in captured.out
            assert "RESULT:" in captured.out
            assert "Failed to terminate i-0cfce47f50e3c34f" in captured.out

    def test_main_hardcoded_values(self):
        """Test that main uses correct hardcoded instance ID and region."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_fix_termination_protection." "disable_termination_protection_and_terminate"
        ) as mock_disable:
            mock_disable.return_value = True
            main()
            mock_disable.assert_called_once_with("i-0cfce47f50e3c34f", "us-east-1")

    def test_main_prints_header(self, capsys):
        """Test that main prints proper header."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_fix_termination_protection." "disable_termination_protection_and_terminate"
        ) as mock_disable:
            mock_disable.return_value = True
            main()
            captured = capsys.readouterr()
            assert "AWS Fix Termination Protection" in captured.out
            assert "=" * 80 in captured.out

    def test_main_displays_savings(self, capsys):
        """Test that main displays cost savings information."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_fix_termination_protection." "disable_termination_protection_and_terminate"
        ) as mock_disable:
            mock_disable.return_value = True
            main()
            captured = capsys.readouterr()
            assert "$0.64" in captured.out
            assert "8GB EBS volume" in captured.out
