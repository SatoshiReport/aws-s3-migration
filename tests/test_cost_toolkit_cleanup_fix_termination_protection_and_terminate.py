"""Tests for aws_fix_termination_protection_and_terminate script."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate import (
    disable_termination_protection,
    display_instance_info,
    display_warning_and_confirm,
    load_aws_credentials,
    main,
    print_operation_summary,
    print_success_summary,
    terminate_instance,
)


def test_load_credentials_calls_setup():
    """Test that load_aws_credentials calls setup_aws_credentials."""
    with patch(
        "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
        "setup_aws_credentials"
    ) as mock_setup:
        mock_setup.return_value = ("key_id", "secret_key")
        result = load_aws_credentials()
        assert result == ("key_id", "secret_key")
        mock_setup.assert_called_once()


class TestDisableTerminationProtection:
    """Test disabling termination protection."""

    def test_disable_protection_success(self, capsys):
        """Test successful disabling of termination protection."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
            "create_ec2_client"
        ) as mock_create:
            mock_ec2 = MagicMock()
            mock_ec2.modify_instance_attribute.return_value = {}
            mock_create.return_value = mock_ec2
            result = disable_termination_protection("us-east-1", "i-123", "key", "secret")
            assert result is True
            captured = capsys.readouterr()
            assert "Disabling termination protection: i-123" in captured.out
            assert "Termination protection disabled for i-123" in captured.out
            mock_ec2.modify_instance_attribute.assert_called_once_with(
                InstanceId="i-123", DisableApiTermination={"Value": False}
            )

    def test_disable_protection_client_error(self, capsys):
        """Test handling of ClientError when disabling protection."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
            "create_ec2_client"
        ) as mock_create:
            mock_ec2 = MagicMock()
            error = ClientError(
                {"Error": {"Code": "InvalidInstanceID"}}, "modify_instance_attribute"
            )  # noqa: E501
            mock_ec2.modify_instance_attribute.side_effect = error
            mock_create.return_value = mock_ec2
            result = disable_termination_protection("us-east-1", "i-123", "key", "secret")
            assert result is False
            captured = capsys.readouterr()
            assert "Failed to disable termination protection for i-123" in captured.out

    def test_disable_protection_uses_credentials(self):
        """Test that credentials are passed correctly."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
            "create_ec2_client"
        ) as mock_create:
            mock_ec2 = MagicMock()
            mock_ec2.modify_instance_attribute.return_value = {}
            mock_create.return_value = mock_ec2
            disable_termination_protection("eu-west-2", "i-456", "my_key", "my_secret")
            mock_create.assert_called_once_with("eu-west-2", "my_key", "my_secret")


class TestTerminateInstance:
    """Test instance termination."""

    def test_terminate_instance_success(self, capsys):
        """Test successful instance termination."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
            "create_ec2_client"
        ) as mock_create:
            mock_ec2 = MagicMock()
            mock_ec2.terminate_instances.return_value = {
                "TerminatingInstances": [
                    {
                        "CurrentState": {"Name": "shutting-down"},
                        "PreviousState": {"Name": "running"},
                    }
                ]
            }
            mock_create.return_value = mock_ec2
            result = terminate_instance("us-east-1", "i-123", "key", "secret")
            assert result is True
            captured = capsys.readouterr()
            assert "Terminating instance: i-123" in captured.out
            assert "State change: running → shutting-down" in captured.out
            mock_ec2.terminate_instances.assert_called_once_with(InstanceIds=["i-123"])

    def test_terminate_instance_client_error(self, capsys):
        """Test handling of ClientError during termination."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
            "create_ec2_client"
        ) as mock_create:
            mock_ec2 = MagicMock()
            error = ClientError({"Error": {"Code": "InvalidInstanceID"}}, "terminate_instances")
            mock_ec2.terminate_instances.side_effect = error
            mock_create.return_value = mock_ec2
            result = terminate_instance("us-east-1", "i-123", "key", "secret")
            assert result is False
            captured = capsys.readouterr()
            assert "Failed to terminate i-123" in captured.out

    def test_terminate_instance_uses_credentials(self):
        """Test that credentials are passed correctly."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
            "create_ec2_client"
        ) as mock_create:
            mock_ec2 = MagicMock()
            mock_ec2.terminate_instances.return_value = {
                "TerminatingInstances": [
                    {
                        "CurrentState": {"Name": "shutting-down"},
                        "PreviousState": {"Name": "running"},
                    }
                ]
            }
            mock_create.return_value = mock_ec2
            terminate_instance("ap-south-1", "i-789", "my_key", "my_secret")
            mock_create.assert_called_once_with("ap-south-1", "my_key", "my_secret")


def test_display_instance_info(capsys):
    """Test displaying instance information."""
    instance = {
        "name": "TestInstance",
        "instance_id": "i-123456",
        "region": "us-east-1",
        "type": "t2.micro",
    }
    display_instance_info(instance)
    captured = capsys.readouterr()
    assert "Target: TestInstance (i-123456)" in captured.out
    assert "Region: us-east-1" in captured.out
    assert "Type: t2.micro" in captured.out


class TestDisplayWarningAndConfirm:
    """Test warning display and user confirmation."""

    def test_display_warning_confirm_success(self, capsys):
        """Test successful confirmation."""
        with patch("builtins.input", return_value="DISABLE PROTECTION AND TERMINATE"):
            result = display_warning_and_confirm()
            assert result is True
            captured = capsys.readouterr()
            assert "TERMINATION PROTECTION REMOVAL" in captured.out
            assert "This will disable termination protection" in captured.out
            assert "cannot be undone" in captured.out

    def test_display_warning_confirm_cancel(self, capsys):
        """Test confirmation cancellation."""
        with patch("builtins.input", return_value="NO"):
            result = display_warning_and_confirm()
            assert result is False
            captured = capsys.readouterr()
            assert "Operation cancelled" in captured.out

    def test_display_warning_confirm_wrong_text(self, capsys):
        """Test confirmation with incorrect text."""
        with patch("builtins.input", return_value="DISABLE"):
            result = display_warning_and_confirm()
            assert result is False
            captured = capsys.readouterr()
            assert "Operation cancelled" in captured.out


def test_print_success_summary(capsys):
    """Test printing success summary."""
    print_success_summary("i-123456")
    captured = capsys.readouterr()
    assert "Successfully completed all operations" in captured.out
    assert "Disabled termination protection: i-123456" in captured.out
    assert "Terminated instance: i-123456" in captured.out
    assert "Protected instance termination completed!" in captured.out
    assert "Next steps:" in captured.out


class TestPrintOperationSummary:
    """Test printing operation summary."""

    def test_print_summary_both_success(self, capsys):
        """Test summary when both operations succeed."""
        print_operation_summary(True, True, "i-123")
        captured = capsys.readouterr()
        assert "TERMINATION PROTECTION FIX SUMMARY" in captured.out
        assert "Successfully completed all operations" in captured.out

    def test_print_summary_protection_failed(self, capsys):
        """Test summary when protection disabling failed."""
        print_operation_summary(False, False, "i-123")
        captured = capsys.readouterr()
        assert "Operation partially failed" in captured.out
        assert "Protection disabled: ❌" in captured.out
        assert "Instance terminated: ❌" in captured.out

    def test_print_summary_termination_failed(self, capsys):
        """Test summary when termination failed."""
        print_operation_summary(True, False, "i-123")
        captured = capsys.readouterr()
        assert "Operation partially failed" in captured.out
        assert "Protection disabled: ✅" in captured.out
        assert "Instance terminated: ❌" in captured.out


class TestMainUserCancelsAndSuccess:
    """Test main execution function - success cases."""

    def test_main_user_cancels(self, capsys):
        """Test main when user cancels operation."""
        with patch("builtins.input", return_value="NO"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
                "load_aws_credentials"
            ) as mock_load:
                mock_load.return_value = ("key", "secret")
                main()
                captured = capsys.readouterr()
                assert "Operation cancelled" in captured.out

    def test_main_success(self, capsys):
        """Test successful main execution."""
        with patch("builtins.input", return_value="DISABLE PROTECTION AND TERMINATE"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
                "load_aws_credentials"
            ) as mock_load:
                mock_load.return_value = ("key", "secret")
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
                    "create_ec2_client"
                ) as mock_create:
                    mock_ec2 = MagicMock()
                    mock_ec2.modify_instance_attribute.return_value = {}
                    mock_ec2.terminate_instances.return_value = {
                        "TerminatingInstances": [
                            {
                                "CurrentState": {"Name": "shutting-down"},
                                "PreviousState": {"Name": "running"},
                            }
                        ]
                    }
                    mock_create.return_value = mock_ec2
                    main()
                    captured = capsys.readouterr()
                    assert "Successfully completed all operations" in captured.out


class TestMainFailures:
    """Test main execution function - failure cases."""

    def test_main_protection_disable_fails(self, capsys):
        """Test main when disabling protection fails."""
        with patch("builtins.input", return_value="DISABLE PROTECTION AND TERMINATE"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
                "load_aws_credentials"
            ) as mock_load:
                mock_load.return_value = ("key", "secret")
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
                    "create_ec2_client"
                ) as mock_create:
                    mock_ec2 = MagicMock()
                    error = ClientError(
                        {"Error": {"Code": "InvalidInstanceID"}}, "modify_instance_attribute"
                    )
                    mock_ec2.modify_instance_attribute.side_effect = error
                    mock_create.return_value = mock_ec2
                    main()
                    captured = capsys.readouterr()
                    assert "Failed to disable termination protection" in captured.out
                    assert "cannot proceed with termination" in captured.out

    def test_main_termination_fails(self, capsys):
        """Test main when termination fails."""
        with patch("builtins.input", return_value="DISABLE PROTECTION AND TERMINATE"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
                "load_aws_credentials"
            ) as mock_load:
                mock_load.return_value = ("key", "secret")
                with patch(
                    "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
                    "create_ec2_client"
                ) as mock_create:
                    mock_ec2 = MagicMock()
                    mock_ec2.modify_instance_attribute.return_value = {}
                    error = ClientError(
                        {"Error": {"Code": "InvalidInstanceID"}}, "terminate_instances"
                    )
                    mock_ec2.terminate_instances.side_effect = error
                    mock_create.return_value = mock_ec2
                    main()
                    captured = capsys.readouterr()
                    assert "Operation partially failed" in captured.out

    def test_main_critical_error(self, capsys):
        """Test main with critical error."""
        with patch("builtins.input", return_value="DISABLE PROTECTION AND TERMINATE"):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_fix_termination_protection_and_terminate."
                "load_aws_credentials"
            ) as mock_load:
                error = ClientError({"Error": {"Code": "ServiceUnavailable"}}, "client")
                mock_load.side_effect = error
                try:
                    main()
                    assert False, "Should have raised ClientError"
                except ClientError:
                    captured = capsys.readouterr()
                    assert "Critical error during termination protection fix" in captured.out
