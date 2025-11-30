"""Comprehensive tests for aws_security_group_circular_cleanup.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup import (
    _check_inbound_rules,
    _check_outbound_rules,
    _delete_security_groups,
    _get_circular_security_groups,
    _print_final_summary,
    _process_regions,
    _remove_cross_references,
    cleanup_circular_security_groups,
    get_security_group_rules_referencing_group,
    remove_security_group_rule,
)


class TestRemoveSecurityGroupRule:
    """Tests for remove_security_group_rule function."""

    def test_remove_inbound_rule(self):
        """Test removing inbound rule."""
        mock_client = MagicMock()
        rule_data = {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22}
        result = remove_security_group_rule(mock_client, "sg-123", "inbound", rule_data)
        assert result is True
        mock_client.revoke_security_group_ingress.assert_called_once_with(
            GroupId="sg-123", IpPermissions=[rule_data]
        )

    def test_remove_outbound_rule(self):
        """Test removing outbound rule."""
        mock_client = MagicMock()
        rule_data = {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80}
        result = remove_security_group_rule(mock_client, "sg-123", "outbound", rule_data)
        assert result is True
        mock_client.revoke_security_group_egress.assert_called_once_with(
            GroupId="sg-123", IpPermissions=[rule_data]
        )

    def test_remove_rule_error(self, capsys):
        """Test error when removing rule."""
        mock_client = MagicMock()
        mock_client.revoke_security_group_ingress.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "revoke_security_group_ingress"
        )
        result = remove_security_group_rule(mock_client, "sg-123", "inbound", {})
        assert result is False
        captured = capsys.readouterr()
        assert "Error removing rule" in captured.out


class TestCheckInboundRules:
    """Tests for _check_inbound_rules function."""

    def test_check_rules_with_reference(self):
        """Test checking rules that reference target group."""
        sg = {
            "GroupId": "sg-source",
            "GroupName": "source-sg",
            "IpPermissions": [
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "UserIdGroupPairs": [{"GroupId": "sg-target"}],
                }
            ],
        }
        rules = _check_inbound_rules(sg, "sg-target")
        assert len(rules) == 1
        assert rules[0]["source_sg_id"] == "sg-source"
        assert rules[0]["rule_type"] == "inbound"
        assert rules[0]["target_group_id"] == "sg-target"

    def test_check_rules_no_reference(self):
        """Test checking rules without target reference."""
        sg = {
            "GroupId": "sg-source",
            "GroupName": "source-sg",
            "IpPermissions": [
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "UserIdGroupPairs": [{"GroupId": "sg-other"}],
                }
            ],
        }
        rules = _check_inbound_rules(sg, "sg-target")
        assert len(rules) == 0

    def test_check_rules_no_user_id_pairs(self):
        """Test checking rules without UserIdGroupPairs."""
        sg = {
            "GroupId": "sg-source",
            "GroupName": "source-sg",
            "IpPermissions": [
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                }
            ],
        }
        rules = _check_inbound_rules(sg, "sg-target")
        assert len(rules) == 0


def test_check_outbound_rules_check_outbound_rules_with_reference():
    """Test checking outbound rules that reference target group."""
    sg = {
        "GroupId": "sg-source",
        "GroupName": "source-sg",
        "IpPermissionsEgress": [
            {
                "IpProtocol": "tcp",
                "FromPort": 80,
                "ToPort": 80,
                "UserIdGroupPairs": [{"GroupId": "sg-target"}],
            }
        ],
    }
    rules = _check_outbound_rules(sg, "sg-target")
    assert len(rules) == 1
    assert rules[0]["rule_type"] == "outbound"


class TestGetSecurityGroupRulesReferencingGroup:
    """Tests for get_security_group_rules_referencing_group function."""

    def test_get_rules_success(self):
        """Test successful retrieval of rules."""
        mock_client = MagicMock()
        mock_client.describe_security_groups.return_value = {
            "SecurityGroups": [
                {
                    "GroupId": "sg-source",
                    "GroupName": "source-sg",
                    "IpPermissions": [
                        {
                            "IpProtocol": "tcp",
                            "FromPort": 22,
                            "ToPort": 22,
                            "UserIdGroupPairs": [{"GroupId": "sg-target"}],
                        }
                    ],
                    "IpPermissionsEgress": [],
                }
            ]
        }
        rules = get_security_group_rules_referencing_group(mock_client, "sg-target")
        assert len(rules) == 1

    def test_get_rules_error(self, capsys):
        """Test error when getting rules."""
        mock_client = MagicMock()
        mock_client.describe_security_groups.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "describe_security_groups"
        )
        rules = get_security_group_rules_referencing_group(mock_client, "sg-target")
        assert not rules
        captured = capsys.readouterr()
        assert "Error getting security group rules" in captured.out


class TestDeleteSecurityGroup:
    """Tests for delete_security_group function."""

    def test_delete_group_success(self, capsys):
        """Test successful security group deletion."""
        mock_client = MagicMock()
        result = delete_security_group(mock_client, "sg-123", "test-sg")
        assert result is True
        mock_client.delete_security_group.assert_called_once_with(GroupId="sg-123")
        captured = capsys.readouterr()
        assert "Deleted security group" in captured.out

    def test_delete_group_error(self, capsys):
        """Test error when deleting security group."""
        mock_client = MagicMock()
        mock_client.delete_security_group.side_effect = ClientError(
            {"Error": {"Code": "ServiceError"}}, "delete_security_group"
        )
        result = delete_security_group(mock_client, "sg-123", "test-sg")
        assert result is False
        captured = capsys.readouterr()
        assert "Failed to delete security group" in captured.out


def test_get_circular_security_groups_returns_list():
    """Test that function returns a list."""
    groups = _get_circular_security_groups()
    assert isinstance(groups, list)


def test_remove_cross_references_remove_references(capsys):
    """Test removing cross-references."""
    mock_client = MagicMock()
    sgs = [
        {"group_id": "sg-1", "name": "test-sg-1"},
        {"group_id": "sg-2", "name": "test-sg-2"},
    ]
    with patch(
        "cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup."
        "get_security_group_rules_referencing_group"
    ) as mock_get:
        with patch(
            "cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup."
            "remove_security_group_rule",
            return_value=True,
        ):
            mock_get.return_value = [
                {
                    "source_sg_id": "sg-other",
                    "source_sg_name": "other-sg",
                    "rule_type": "inbound",
                    "rule_data": {},
                }
            ]
            count = _remove_cross_references(mock_client, sgs)
    assert count == 2  # 1 rule per group
    captured = capsys.readouterr()
    assert "Removing cross-references" in captured.out


class TestDeleteSecurityGroups:
    """Tests for _delete_security_groups function."""

    def test_delete_groups_all_successful(self, capsys):
        """Test deleting all groups successfully."""
        mock_client = MagicMock()
        sgs = [
            {"group_id": "sg-1", "name": "test-sg-1"},
            {"group_id": "sg-2", "name": "test-sg-2"},
        ]
        with patch(
            "cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup."
            "delete_security_group",
            return_value=True,
        ):
            count = _delete_security_groups(mock_client, sgs)
        assert count == 2
        captured = capsys.readouterr()
        assert "Deleting security groups" in captured.out

    def test_delete_groups_partial_failures(self):
        """Test deleting with some failures."""
        mock_client = MagicMock()
        sgs = [
            {"group_id": "sg-1", "name": "test-sg-1"},
            {"group_id": "sg-2", "name": "test-sg-2"},
        ]
        with patch(
            "cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup."
            "delete_security_group",
            side_effect=[True, False],
        ):
            count = _delete_security_groups(mock_client, sgs)
        assert count == 1


def test_process_regions_process_multiple_regions():
    """Test processing multiple regions."""
    regions = {
        "us-east-1": [{"group_id": "sg-1", "name": "sg-1"}],
        "us-west-2": [{"group_id": "sg-2", "name": "sg-2"}],
    }
    with patch("boto3.client"):
        with patch(
            "cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup."
            "_remove_cross_references",
            return_value=2,
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup."
                "_delete_security_groups",
                return_value=2,
            ):
                rules_removed, groups_deleted = _process_regions(regions, "key", "secret")
    assert rules_removed == 4  # 2 per region
    assert groups_deleted == 4  # 2 per region


class TestPrintFinalSummary:
    """Tests for _print_final_summary function."""

    def test_print_summary_with_deletions(self, capsys):
        """Test summary with successful deletions."""
        _print_final_summary(10, 5, 8)
        captured = capsys.readouterr()
        assert "CIRCULAR DEPENDENCY CLEANUP SUMMARY" in captured.out
        assert "Security group rules removed: 10" in captured.out
        assert "Security groups deleted: 5" in captured.out
        assert "Success rate: 5/8" in captured.out
        assert "cleanup completed" in captured.out

    def test_print_summary_no_deletions(self, capsys):
        """Test summary with no deletions."""
        _print_final_summary(0, 0, 5)
        captured = capsys.readouterr()
        assert "No security groups were successfully deleted" in captured.out


class TestCleanupCircularSecurityGroups:
    """Tests for cleanup_circular_security_groups function."""

    def test_cleanup_with_user_cancellation(self, capsys):
        """Test when user cancels operation."""
        with patch(
            "cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup."
            "setup_aws_credentials",
            return_value=("key", "secret"),
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup."
                "_get_circular_security_groups",
                return_value=[],
            ):
                with patch("builtins.input", return_value="NO"):
                    cleanup_circular_security_groups()
        captured = capsys.readouterr()
        assert "Operation cancelled by user" in captured.out

    def test_cleanup_with_user_confirmation(self, capsys):
        """Test when user confirms operation."""
        mock_groups = [
            {"group_id": "sg-1", "name": "sg-1", "region": "us-east-1"},
            {"group_id": "sg-2", "name": "sg-2", "region": "us-east-1"},
        ]
        with patch(
            "cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup."
            "setup_aws_credentials",
            return_value=("key", "secret"),
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup."
                "_get_circular_security_groups",
                return_value=mock_groups,
            ):
                with patch("builtins.input", return_value="RESOLVE CIRCULAR DEPENDENCIES"):
                    with patch(
                        "cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup."
                        "_process_regions",
                        return_value=(5, 2),
                    ):
                        with patch(
                            "cost_toolkit.scripts.cleanup."
                            "aws_security_group_circular_cleanup._print_final_summary"
                        ):
                            cleanup_circular_security_groups()
        captured = capsys.readouterr()
        assert "Proceeding with circular dependency resolution" in captured.out
        assert "Target: 2 security groups" in captured.out

    def test_cleanup_region_grouping(self):
        """Test that regions are grouped correctly."""
        mock_groups = [
            {"group_id": "sg-1", "name": "sg-1", "region": "us-east-1"},
            {"group_id": "sg-2", "name": "sg-2", "region": "us-west-2"},
            {"group_id": "sg-3", "name": "sg-3", "region": "us-east-1"},
        ]
        with patch(
            "cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup."
            "setup_aws_credentials",
            return_value=("key", "secret"),
        ):
            with patch(
                "cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup."
                "_get_circular_security_groups",
                return_value=mock_groups,
            ):
                with patch("builtins.input", return_value="RESOLVE CIRCULAR DEPENDENCIES"):
                    with patch(
                        "cost_toolkit.scripts.cleanup.aws_security_group_circular_cleanup."
                        "_process_regions"
                    ) as mock_process:
                        with patch(
                            "cost_toolkit.scripts.cleanup."
                            "aws_security_group_circular_cleanup._print_final_summary"
                        ):
                            mock_process.return_value = (0, 0)
                            cleanup_circular_security_groups()
                            # Verify regions were grouped correctly
                            call_args = mock_process.call_args[0][0]
                            assert "us-east-1" in call_args
                            assert "us-west-2" in call_args
                            assert len(call_args["us-east-1"]) == 2
                            assert len(call_args["us-west-2"]) == 1
