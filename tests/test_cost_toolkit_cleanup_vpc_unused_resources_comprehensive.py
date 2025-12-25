"""Comprehensive tests for aws_vpc_cleanup_unused_resources.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.aws_ec2_operations import (
    delete_security_group,
)
from cost_toolkit.scripts.cleanup.aws_vpc_cleanup_unused_resources import (
    EMPTY_VPCS,
    UNUSED_SECURITY_GROUPS,
    clean_security_groups,
    cleanup_unused_vpc_resources,
    main,
    print_cleanup_intro,
    print_cleanup_summary,
    review_empty_vpcs,
)


class TestDeleteSecurityGroup:
    """Tests for delete_security_group function."""

    def test_delete_security_group_success(self, capsys):
        """Test successful security group deletion."""
        mock_client = MagicMock()
        result = delete_security_group(mock_client, "sg-123", "test-sg", "us-east-1")
        assert result is True
        mock_client.delete_security_group.assert_called_once_with(GroupId="sg-123")
        captured = capsys.readouterr()
        assert "Deleted security group" in captured.out

    def test_delete_security_group_error(self, capsys):
        """Test security group deletion with error."""
        mock_client = MagicMock()
        mock_client.delete_security_group.side_effect = ClientError(
            {"Error": {"Code": "DependencyViolation", "Message": "In use"}},
            "delete_security_group",
        )
        result = delete_security_group(mock_client, "sg-123", "test-sg", "us-east-1")
        assert result is False
        captured = capsys.readouterr()
        assert "Failed to delete security group" in captured.out

    def test_delete_security_group_not_found(self, capsys):
        """Test deleting non-existent security group."""
        mock_client = MagicMock()
        mock_client.delete_security_group.side_effect = ClientError({"Error": {"Code": "InvalidGroup.NotFound"}}, "delete_security_group")
        result = delete_security_group(mock_client, "sg-nonexist", "missing-sg", "us-east-1")
        assert result is False
        captured = capsys.readouterr()
        assert "Failed to delete security group" in captured.out


def test_print_cleanup_intro(capsys):
    """Test cleanup introduction printing."""
    print_cleanup_intro()
    captured = capsys.readouterr()
    assert "AWS VPC Unused Resources Cleanup" in captured.out
    assert str(len(UNUSED_SECURITY_GROUPS)) in captured.out
    assert str(len(EMPTY_VPCS)) in captured.out
    assert "IMPORTANT NOTES" in captured.out
    assert "security groups will be permanently deleted" in captured.out


class TestCleanSecurityGroups:
    """Tests for clean_security_groups function."""

    def test_clean_security_groups_all_success(self):
        """Test cleaning all security groups successfully."""
        with patch("boto3.client") as mock_boto_client:
            mock_client = MagicMock()
            mock_boto_client.return_value = mock_client
            with patch(
                "cost_toolkit.scripts.cleanup.aws_vpc_cleanup_unused_resources." "delete_security_group",
                return_value=True,
            ):
                successful, failed = clean_security_groups("key", "secret")
                assert successful == len(UNUSED_SECURITY_GROUPS)
                assert failed == 0

    def test_clean_security_groups_partial_failures(self):
        """Test cleaning security groups with some failures."""
        with patch("boto3.client") as mock_boto_client:
            mock_client = MagicMock()
            mock_boto_client.return_value = mock_client
            # First 5 succeed, next 5 fail
            with patch(
                "cost_toolkit.scripts.cleanup.aws_vpc_cleanup_unused_resources." "delete_security_group",
                side_effect=[True] * 5 + [False] * 5,
            ):
                successful, failed = clean_security_groups("key", "secret")
                assert successful == 5
                assert failed == 5

    def test_clean_security_groups_all_failures(self):
        """Test cleaning security groups when all fail."""
        with patch("boto3.client") as mock_boto_client:
            mock_client = MagicMock()
            mock_boto_client.return_value = mock_client
            with patch(
                "cost_toolkit.scripts.cleanup.aws_vpc_cleanup_unused_resources." "delete_security_group",
                return_value=False,
            ):
                successful, failed = clean_security_groups("key", "secret")
                assert successful == 0
                assert failed == len(UNUSED_SECURITY_GROUPS)

    def test_clean_security_groups_boto_client_calls(self):
        """Test that boto3 clients are created correctly."""
        with patch("boto3.client") as mock_boto_client:
            mock_client = MagicMock()
            mock_boto_client.return_value = mock_client
            with patch(
                "cost_toolkit.scripts.cleanup.aws_vpc_cleanup_unused_resources." "delete_security_group",
                return_value=True,
            ):
                clean_security_groups("test_key", "test_secret")
                # Should create clients for each unique region
                _regions = {sg["region"] for sg in UNUSED_SECURITY_GROUPS}
                assert mock_boto_client.call_count == len(UNUSED_SECURITY_GROUPS)


class TestReviewEmptyVpcs:
    """Tests for review_empty_vpcs function."""

    def test_review_empty_vpcs(self, capsys):
        """Test reviewing empty VPCs."""
        review_empty_vpcs()
        captured = capsys.readouterr()
        assert "Reviewing empty VPCs" in captured.out
        for vpc in EMPTY_VPCS:
            assert vpc["vpc_id"] in captured.out

    def test_review_empty_vpcs_default_handling(self, capsys):
        """Test that default VPCs have different messaging."""
        review_empty_vpcs()
        captured = capsys.readouterr()
        # Should show manual deletion command for non-default VPCs
        assert "Manual command:" in captured.out or "delete-vpc" in captured.out

    def test_review_empty_vpcs_non_default(self, capsys):
        """Test non-default VPC review output."""
        review_empty_vpcs()
        captured = capsys.readouterr()
        # Should mention considering deletion for non-default VPCs
        assert "could be deleted" in captured.out or "Consider" in captured.out


class TestPrintCleanupSummary:
    """Tests for print_cleanup_summary function."""

    def test_print_cleanup_summary_with_successes(self, capsys):
        """Test summary printing with successful deletions."""
        print_cleanup_summary(5, 2)
        captured = capsys.readouterr()
        assert "VPC CLEANUP SUMMARY" in captured.out
        assert "✅ Successfully deleted: 5 security groups" in captured.out
        assert "❌ Failed to delete: 2 security groups" in captured.out
        assert "cleanup completed successfully" in captured.out
        assert "Benefits:" in captured.out

    def test_print_cleanup_summary_no_successes(self, capsys):
        """Test summary printing with no successful deletions."""
        print_cleanup_summary(0, 5)
        captured = capsys.readouterr()
        assert "VPC CLEANUP SUMMARY" in captured.out
        assert "✅ Successfully deleted: 0 security groups" in captured.out
        assert "cleanup completed successfully" not in captured.out

    def test_print_cleanup_summary_with_empty_vpcs(self, capsys):
        """Test summary mentions empty VPCs if present."""
        print_cleanup_summary(3, 1)
        captured = capsys.readouterr()
        if len(EMPTY_VPCS) > 0:
            assert "Next Steps for Empty VPCs" in captured.out


class TestCleanupUnusedVpcResources:
    """Tests for cleanup_unused_vpc_resources function."""

    def test_cleanup_with_user_cancellation(self, capsys, monkeypatch):
        """Test cleanup when user cancels."""
        monkeypatch.setattr("builtins.input", lambda _: "NO")
        with patch(
            "cost_toolkit.common.credential_utils.setup_aws_credentials",
            return_value=("key", "secret"),
        ):
            cleanup_unused_vpc_resources()
        captured = capsys.readouterr()
        assert "Operation cancelled by user" in captured.out

    def test_cleanup_with_user_confirmation(self, capsys, monkeypatch):
        """Test cleanup when user confirms."""
        monkeypatch.setattr("builtins.input", lambda _: "CLEANUP VPC RESOURCES")
        mod = "cost_toolkit.scripts.cleanup.aws_vpc_cleanup_unused_resources"
        with (
            patch(f"{mod}.setup_aws_credentials", return_value=("key", "secret")),
            patch(f"{mod}.clean_security_groups", return_value=(8, 2)),
            patch(f"{mod}.review_empty_vpcs"),
        ):
            cleanup_unused_vpc_resources()
        captured = capsys.readouterr()
        assert "Proceeding with VPC resource cleanup" in captured.out

    def test_cleanup_prints_intro(self, monkeypatch):
        """Test that cleanup prints introduction."""
        monkeypatch.setattr("builtins.input", lambda _: "NO")
        with patch(
            "cost_toolkit.common.credential_utils.setup_aws_credentials",
            return_value=("key", "secret"),
        ):
            with patch("cost_toolkit.scripts.cleanup.aws_vpc_cleanup_unused_resources.print_cleanup_intro") as mock_intro:
                cleanup_unused_vpc_resources()
                mock_intro.assert_called_once()


class TestMain:
    """Tests for main function."""

    def test_main_success(self, monkeypatch):
        """Test main function with successful execution."""
        monkeypatch.setattr("builtins.input", lambda _: "NO")
        mod = "cost_toolkit.scripts.cleanup.aws_vpc_cleanup_unused_resources"
        with patch(f"{mod}.cleanup_unused_vpc_resources"):
            main()

    def test_main_with_client_error(self, capsys, monkeypatch):
        """Test main function with ClientError."""
        monkeypatch.setattr("builtins.input", lambda _: "CLEANUP VPC RESOURCES")
        mod = "cost_toolkit.scripts.cleanup.aws_vpc_cleanup_unused_resources"
        error = ClientError({"Error": {"Code": "ServiceError"}}, "delete")
        with (
            patch(f"{mod}.setup_aws_credentials", return_value=("key", "secret")),
            patch(f"{mod}.clean_security_groups", side_effect=error),
        ):
            try:
                main()
            except SystemExit as e:
                assert e.code == 1
            captured = capsys.readouterr()
            assert "Script failed" in captured.out
