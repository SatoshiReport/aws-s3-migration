"""Comprehensive tests for aws_ami_deregister_bulk.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_ami_deregister_bulk import (
    confirm_deregistration,
    deregister_ami,
    get_amis_to_deregister,
    load_aws_credentials,
    print_deregistration_summary,
    print_deregistration_warning,
    process_ami_deregistrations,
)


class TestLoadAwsCredentials:
    """Tests for load_aws_credentials function."""

    def test_calls_setup_credentials(self):
        """Test that function calls setup utility."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_ami_deregister_bulk.setup_aws_credentials"
        ) as mock_setup:
            mock_setup.return_value = ("key", "secret")

            result = load_aws_credentials()

            mock_setup.assert_called_once()
            assert result == ("key", "secret")


class TestDeregisterAmi:
    """Tests for deregister_ami function."""

    def test_deregister_ami_success(self, capsys):
        """Test successful AMI deregistration."""
        mock_client = MagicMock()

        result = deregister_ami(mock_client, "ami-123", "us-east-1")

        assert result is True
        mock_client.deregister_image.assert_called_once_with(ImageId="ami-123")
        captured = capsys.readouterr()
        assert "Successfully deregistered" in captured.out

    def test_deregister_ami_error(self, capsys):
        """Test error when deregistering AMI."""
        mock_client = MagicMock()
        mock_client.deregister_image.side_effect = ClientError(
            {"Error": {"Code": "InvalidAMIID.NotFound"}}, "deregister_image"
        )

        result = deregister_ami(mock_client, "ami-notfound", "us-east-1")

        assert result is False
        captured = capsys.readouterr()
        assert "Error deregistering" in captured.out


class TestGetAmisToDeregister:
    """Tests for get_amis_to_deregister function."""

    def test_returns_list_of_amis(self):
        """Test that function returns expected list."""
        amis = get_amis_to_deregister()

        assert isinstance(amis, list)
        assert len(amis) > 0
        for ami in amis:
            assert "ami_id" in ami
            assert "region" in ami
            assert "name" in ami
            assert "snapshot" in ami
            assert "savings" in ami


class TestPrintDeregistrationWarning:
    """Tests for print_deregistration_warning function."""

    def test_print_warning(self, capsys):
        """Test printing deregistration warning."""
        amis = [
            {
                "ami_id": "ami-1",
                "region": "us-east-1",
                "name": "test-ami-1",
                "snapshot": "snap-1",
                "savings": 10.0,
            },
            {
                "ami_id": "ami-2",
                "region": "us-east-2",
                "name": "test-ami-2",
                "snapshot": "snap-2",
                "savings": 5.0,
            },
        ]

        print_deregistration_warning(amis)

        captured = capsys.readouterr()
        assert "AMI Bulk Deregistration" in captured.out
        assert "2 unused AMIs" in captured.out
        assert "$15.00" in captured.out
        assert "FINAL WARNING" in captured.out


class TestConfirmDeregistration:
    """Tests for confirm_deregistration function."""

    def test_confirm_with_correct_input(self):
        """Test confirmation with correct input."""
        with patch("builtins.input", return_value="DEREGISTER ALL AMIS"):
            result = confirm_deregistration()

            assert result is True

    def test_confirm_with_wrong_input(self):
        """Test confirmation with wrong input."""
        with patch("builtins.input", return_value="deregister"):
            result = confirm_deregistration()

            assert result is False


class TestProcessAmiDeregistrations:
    """Tests for process_ami_deregistrations function."""

    def test_process_all_successful(self, capsys):
        """Test processing with all deregistrations successful."""
        amis = [
            {
                "ami_id": "ami-1",
                "region": "us-east-1",
                "name": "test-1",
                "snapshot": "snap-1",
                "savings": 10.0,
            },
            {
                "ami_id": "ami-2",
                "region": "us-east-2",
                "name": "test-2",
                "snapshot": "snap-2",
                "savings": 5.0,
            },
        ]

        with patch("boto3.client") as mock_client:
            with patch(
                "cost_toolkit.scripts.cleanup.aws_ami_deregister_bulk.deregister_ami",
                return_value=True,
            ):
                successful, failed, savings = process_ami_deregistrations(amis, "key", "secret")

        assert successful == 2
        assert failed == 0
        assert savings == 15.0
        captured = capsys.readouterr()
        assert "Processing ami-1" in captured.out

    def test_process_partial_failures(self, capsys):
        """Test processing with some failures."""
        amis = [
            {
                "ami_id": "ami-1",
                "region": "us-east-1",
                "name": "test-1",
                "snapshot": "snap-1",
                "savings": 10.0,
            },
            {
                "ami_id": "ami-2",
                "region": "us-east-2",
                "name": "test-2",
                "snapshot": "snap-2",
                "savings": 5.0,
            },
        ]

        with patch("boto3.client"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_ami_deregister_bulk.deregister_ami",
                side_effect=[True, False],
            ):
                successful, failed, savings = process_ami_deregistrations(amis, "key", "secret")

        assert successful == 1
        assert failed == 1
        assert savings == 10.0

    def test_process_displays_info(self, capsys):
        """Test that processing displays AMI info."""
        amis = [
            {
                "ami_id": "ami-test",
                "region": "us-west-2",
                "name": "MyAMI",
                "snapshot": "snap-test",
                "savings": 7.5,
            },
        ]

        with patch("boto3.client"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_ami_deregister_bulk.deregister_ami",
                return_value=True,
            ):
                process_ami_deregistrations(amis, "key", "secret")

        captured = capsys.readouterr()
        assert "ami-test" in captured.out
        assert "MyAMI" in captured.out
        assert "us-west-2" in captured.out
        assert "snap-test" in captured.out
        assert "$7.50" in captured.out


class TestPrintDeregistrationSummary:
    """Tests for print_deregistration_summary function."""

    def test_print_summary_with_success(self, capsys):
        """Test summary with successful deregistrations."""
        print_deregistration_summary(5, 1, 50.0)

        captured = capsys.readouterr()
        assert "BULK DEREGISTRATION SUMMARY" in captured.out
        assert "Successfully deregistered: 5" in captured.out
        assert "Failed to deregister: 1" in captured.out
        assert "$50.00" in captured.out
        assert "completed successfully" in captured.out
        assert "Next steps:" in captured.out

    def test_print_summary_all_successful(self, capsys):
        """Test summary with all successful."""
        print_deregistration_summary(10, 0, 100.0)

        captured = capsys.readouterr()
        assert "Successfully deregistered: 10" in captured.out
        assert "Failed to deregister: 0" in captured.out
        assert "$100.00" in captured.out

    def test_print_summary_no_success(self, capsys):
        """Test summary with no successful deregistrations."""
        print_deregistration_summary(0, 5, 0.0)

        captured = capsys.readouterr()
        assert "Successfully deregistered: 0" in captured.out
        assert "No AMIs were successfully deregistered" in captured.out
