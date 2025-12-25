"""Comprehensive tests for aws_stopped_instance_cleanup.py - main function."""

from __future__ import annotations

from unittest.mock import patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup import main


class TestMainSuccessful:
    """Tests for successful main function flows."""

    def test_main_successful_termination_with_confirmation(self, capsys, monkeypatch):
        """Test main function with successful termination flow."""
        monkeypatch.setattr("builtins.input", lambda _: "TERMINATE STOPPED INSTANCES")

        mock_instance_details = {
            "instance_id": "i-123",
            "name": "test-instance",
            "instance_type": "t2.micro",
            "state": "stopped",
            "vpc_id": "vpc-123",
            "launch_time": "2024-01-01",
            "volumes": [],
            "network_interfaces": [],
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.load_credentials_from_env",
            return_value=("access_key", "secret_key"),
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup._get_stopped_instances",
                return_value=[{"region": "us-east-1", "instance_id": "i-123", "type": "t2.micro"}],
            ):
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.get_instance_cleanup_details",
                    return_value=mock_instance_details,
                ):
                    with patch("cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup._print_instance_details"):
                        with patch(
                            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.terminate_instance",
                            return_value=True,
                        ):
                            main()

        captured = capsys.readouterr()
        assert "AWS Stopped Instance Cleanup" in captured.out
        assert "Target: 1 stopped instances" in captured.out
        assert "TERMINATION IMPACT" in captured.out
        assert "Instance termination completed" in captured.out

    def test_main_cancelled_confirmation(self, capsys, monkeypatch):
        """Test main function with cancelled confirmation."""
        monkeypatch.setattr("builtins.input", lambda _: "WRONG TEXT")

        mock_instance_details = {
            "instance_id": "i-123",
            "name": "test-instance",
            "instance_type": "t2.micro",
            "state": "stopped",
            "vpc_id": "vpc-123",
            "launch_time": "2024-01-01",
            "volumes": [],
            "network_interfaces": [],
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.load_credentials_from_env",
            return_value=("access_key", "secret_key"),
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup._get_stopped_instances",
                return_value=[{"region": "us-east-1", "instance_id": "i-123", "type": "t2.micro"}],
            ):
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.get_instance_cleanup_details",
                    return_value=mock_instance_details,
                ):
                    with patch("cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup._print_instance_details"):
                        main()

        captured = capsys.readouterr()
        assert "Operation cancelled" in captured.out


class TestMainEdgeCases:
    """Tests for main function edge cases."""

    def test_main_no_valid_instances(self, capsys):
        """Test main function when no valid instances found."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.load_credentials_from_env",
            return_value=("access_key", "secret_key"),
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup._get_stopped_instances",
                return_value=[{"region": "us-east-1", "instance_id": "i-123", "type": "t2.micro"}],
            ):
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.get_instance_cleanup_details",
                    return_value=None,
                ):
                    main()

        captured = capsys.readouterr()
        assert "No valid instances found to terminate" in captured.out

    def test_main_with_client_error(self, capsys):
        """Test main function with ClientError."""
        with patch("cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.load_credentials_from_env") as mock_creds:
            mock_creds.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
                "GetCredentials",
            )

            try:
                main()
            except ClientError:
                pass

        captured = capsys.readouterr()
        assert "Critical error during instance cleanup" in captured.out


class TestMainPartialResults:
    """Tests for partial termination results."""

    def test_main_with_partial_termination_success(self, capsys, monkeypatch):
        """Test main function with partial termination success."""
        monkeypatch.setattr("builtins.input", lambda _: "TERMINATE STOPPED INSTANCES")

        mock_instance_details = {
            "instance_id": "i-123",
            "name": "test-instance",
            "instance_type": "t2.micro",
            "state": "stopped",
            "vpc_id": "vpc-123",
            "launch_time": "2024-01-01",
            "volumes": [],
            "network_interfaces": [],
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.load_credentials_from_env",
            return_value=("access_key", "secret_key"),
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup._get_stopped_instances",
                return_value=[
                    {"region": "us-east-1", "instance_id": "i-1", "type": "t2.micro"},
                    {"region": "us-east-2", "instance_id": "i-2", "type": "t2.small"},
                ],
            ):
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.get_instance_cleanup_details",
                    return_value=mock_instance_details,
                ):
                    with patch("cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup._print_instance_details"):
                        with patch(
                            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.terminate_instance",
                            side_effect=[True, False],
                        ):
                            main()

        captured = capsys.readouterr()
        assert "Successfully terminated: 1" in captured.out
        assert "Failed terminations: 1" in captured.out

    def test_main_no_successful_terminations(self, capsys, monkeypatch):
        """Test main function when all terminations fail."""
        monkeypatch.setattr("builtins.input", lambda _: "TERMINATE STOPPED INSTANCES")

        mock_instance_details = {
            "instance_id": "i-123",
            "name": "test-instance",
            "instance_type": "t2.micro",
            "state": "stopped",
            "vpc_id": "vpc-123",
            "launch_time": "2024-01-01",
            "volumes": [],
            "network_interfaces": [],
        }

        with patch(
            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.load_credentials_from_env",
            return_value=("access_key", "secret_key"),
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup._get_stopped_instances",
                return_value=[{"region": "us-east-1", "instance_id": "i-123", "type": "t2.micro"}],
            ):
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.get_instance_cleanup_details",
                    return_value=mock_instance_details,
                ):
                    with patch("cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup._print_instance_details"):
                        with patch(
                            "cost_toolkit.scripts.cleanup.aws_stopped_instance_cleanup.terminate_instance",
                            return_value=False,
                        ):
                            main()

        captured = capsys.readouterr()
        assert "Successfully terminated: 0" in captured.out
        assert "Failed terminations: 1" in captured.out
