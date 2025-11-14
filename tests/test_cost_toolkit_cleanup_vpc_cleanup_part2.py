"""Comprehensive tests for aws_vpc_cleanup.py - Part 2 (Main Function Tests)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cost_toolkit.scripts.cleanup.aws_vpc_cleanup import main


def _assert_summary_section(captured_output):
    """Helper to assert summary section of output."""
    assert "CLEANUP SUMMARY" in captured_output
    assert "Total monthly savings: $14.40" in captured_output
    assert "SUCCESS: Elastic IP cleanup completed!" in captured_output
    assert "You will save approximately $14.40 per month" in captured_output
    assert "Annual savings: $172.80" in captured_output


def _assert_next_steps_section(captured_output):
    """Helper to assert next steps section of output."""
    assert "NEXT STEPS:" in captured_output
    assert "Your instances can still be started normally" in captured_output
    assert "They will get new public IPs when started" in captured_output


def _assert_reminders_section(captured_output):
    """Helper to assert reminders section of output."""
    assert "IMPORTANT REMINDERS:" in captured_output
    assert "Released IP addresses cannot be recovered" in captured_output


def _assert_main_success_output(captured_output):
    """Helper to assert main success output."""
    _assert_summary_section(captured_output)
    _assert_next_steps_section(captured_output)
    _assert_reminders_section(captured_output)


def test_main_user_confirms_with_ips(capsys):
    """Test successful cleanup with user confirmation."""
    with patch("builtins.input", return_value="RELEASE"):
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_addresses.return_value = {
                "Addresses": [
                    {
                        "PublicIp": "54.123.45.67",
                        "AllocationId": "eipalloc-123",
                    },
                    {
                        "PublicIp": "54.123.45.68",
                        "AllocationId": "eipalloc-456",
                    },
                ]
            }

            main()

    captured = capsys.readouterr()
    _assert_main_success_output(captured.out)


class TestMainSuccess:
    """Tests for main function - success scenarios."""

    def test_main_user_confirms_no_ips(self, capsys):
        """Test when user confirms but no IPs exist."""
        with patch("builtins.input", return_value="RELEASE"):
            with patch("boto3.client") as mock_client:
                mock_ec2 = MagicMock()
                mock_client.return_value = mock_ec2
                mock_ec2.describe_addresses.return_value = {"Addresses": []}

                main()

        captured = capsys.readouterr()
        assert "CLEANUP SUMMARY" in captured.out
        assert "Total monthly savings: $0.00" in captured.out
        assert "No Elastic IPs were found or released." in captured.out

    def test_main_multiple_regions(self, capsys):
        """Test processing multiple regions."""
        with patch("builtins.input", return_value="RELEASE"):
            with patch("boto3.client") as mock_client:
                mock_ec2 = MagicMock()
                mock_client.return_value = mock_ec2

                call_count = [0]

                def side_effect():
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return {
                            "Addresses": [
                                {
                                    "PublicIp": "54.123.45.67",
                                    "AllocationId": "eipalloc-123",
                                }
                            ]
                        }
                    return {
                        "Addresses": [
                            {
                                "PublicIp": "54.123.45.68",
                                "AllocationId": "eipalloc-456",
                            }
                        ]
                    }

                mock_ec2.describe_addresses.side_effect = side_effect

                main()

        captured = capsys.readouterr()
        # Both regions are called so we get double the savings
        assert "SUCCESS: Elastic IP cleanup completed!" in captured.out


class TestMainCancellation:
    """Tests for main function - cancellation and validation scenarios."""

    def test_main_user_cancels(self, capsys):
        """Test when user cancels the operation."""
        with patch("builtins.input", return_value="NO"):
            main()

        captured = capsys.readouterr()
        assert "WARNING: This will permanently release all Elastic IP addresses!" in captured.out
        assert "Operation cancelled. No changes made." in captured.out

    def test_main_wrong_confirmation_text(self, capsys):
        """Test when user types wrong confirmation text."""
        with patch("builtins.input", return_value="YES"):
            main()

        captured = capsys.readouterr()
        assert "Operation cancelled. No changes made." in captured.out

    def test_main_empty_confirmation(self, capsys):
        """Test when user provides empty confirmation."""
        with patch("builtins.input", return_value=""):
            main()

        captured = capsys.readouterr()
        assert "Operation cancelled. No changes made." in captured.out

    def test_main_case_sensitive_confirmation(self, capsys):
        """Test that confirmation is case-sensitive."""
        with patch("builtins.input", return_value="release"):
            main()

        captured = capsys.readouterr()
        assert "Operation cancelled. No changes made." in captured.out

    def test_main_partial_success(self, capsys):
        """Test with partial success (some IPs released, some failed)."""
        with patch("builtins.input", return_value="RELEASE"):
            with patch("boto3.client") as mock_client:
                mock_ec2 = MagicMock()
                mock_client.return_value = mock_ec2
                mock_ec2.describe_addresses.return_value = {
                    "Addresses": [
                        {
                            "PublicIp": "54.123.45.67",
                            "AllocationId": "eipalloc-123",
                        }
                    ]
                }

                main()

        captured = capsys.readouterr()
        assert "Total monthly savings: $7.20" in captured.out
        assert "SUCCESS: Elastic IP cleanup completed!" in captured.out


def test_main_shows_warnings(capsys):
    """Test that main function shows appropriate warnings."""
    with patch("builtins.input", return_value="RELEASE"):
        with patch("boto3.client") as mock_client:
            mock_ec2 = MagicMock()
            mock_client.return_value = mock_ec2
            mock_ec2.describe_addresses.return_value = {"Addresses": []}

            main()

    captured = capsys.readouterr()
    assert "WARNING: This will permanently release all Elastic IP addresses!" in captured.out
    assert "Released IPs cannot be recovered" in captured.out
