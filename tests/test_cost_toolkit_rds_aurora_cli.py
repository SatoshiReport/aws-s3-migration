"""Tests for cost_toolkit/scripts/migration/rds_aurora_migration/cli.py"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cost_toolkit.scripts.migration.rds_aurora_migration.cli import (
    InvalidSelectionError,
    _confirm_migration,
    _print_cost_analysis,
    _select_instance_for_migration,
    _validate_choice,
    main,
    migrate_rds_to_aurora_serverless,
)


# Tests for InvalidSelectionError
def test_invalid_selection_error():
    """Test InvalidSelectionError exception."""
    error = InvalidSelectionError()
    assert str(error) == "Invalid selection"
    assert isinstance(error, ValueError)


# Tests for _validate_choice
def test_validate_choice_valid():
    """Test _validate_choice with valid choice."""
    _validate_choice(0, 5)
    _validate_choice(4, 5)


def test_validate_choice_negative():
    """Test _validate_choice with negative choice."""
    with pytest.raises(InvalidSelectionError):
        _validate_choice(-1, 5)


def test_validate_choice_too_large():
    """Test _validate_choice with choice too large."""
    with pytest.raises(InvalidSelectionError):
        _validate_choice(5, 5)


def test_validate_choice_zero_max():
    """Test _validate_choice with zero max."""
    with pytest.raises(InvalidSelectionError):
        _validate_choice(0, 0)


# Tests for _select_instance_for_migration
@patch("builtins.input", return_value="2")
@patch("builtins.print")
def test_select_instance_interactive_valid(_mock_print, mock_input):
    """Test interactive instance selection with valid choice."""
    instances = [
        {
            "identifier": "db-1",
            "region": "us-east-1",
            "engine": "mysql",
            "instance_class": "db.t3.micro",
        },
        {
            "identifier": "db-2",
            "region": "us-west-2",
            "engine": "postgres",
            "instance_class": "db.t3.small",
        },
    ]

    result = _select_instance_for_migration(instances, None, None)

    assert result == instances[1]
    mock_input.assert_called_once()


@patch("builtins.input", return_value="0")
@patch("builtins.print")
def test_select_instance_interactive_invalid_zero(_mock_print, _mock_input):
    """Test interactive instance selection with invalid zero choice."""
    instances = [
        {
            "identifier": "db-1",
            "region": "us-east-1",
            "engine": "mysql",
            "instance_class": "db.t3.micro",
        },
    ]

    result = _select_instance_for_migration(instances, None, None)

    assert result is None


@patch("builtins.input", return_value="abc")
@patch("builtins.print")
def test_select_instance_interactive_invalid_string(_mock_print, _mock_input2):
    """Test interactive instance selection with invalid string."""
    instances = [
        {
            "identifier": "db-1",
            "region": "us-east-1",
            "engine": "mysql",
            "instance_class": "db.t3.micro",
        },
    ]

    result = _select_instance_for_migration(instances, None, None)

    assert result is None


def test_select_instance_by_identifier():
    """Test instance selection by identifier."""
    instances = [
        {
            "identifier": "db-1",
            "region": "us-east-1",
            "engine": "mysql",
            "instance_class": "db.t3.micro",
        },
        {
            "identifier": "db-2",
            "region": "us-west-2",
            "engine": "postgres",
            "instance_class": "db.t3.small",
        },
    ]

    result = _select_instance_for_migration(instances, "db-2", None)

    assert result == instances[1]


def test_select_instance_by_identifier_with_region():
    """Test instance selection by identifier and region."""
    instances = [
        {
            "identifier": "db-1",
            "region": "us-east-1",
            "engine": "mysql",
            "instance_class": "db.t3.micro",
        },
        {
            "identifier": "db-1",
            "region": "us-west-2",
            "engine": "postgres",
            "instance_class": "db.t3.small",
        },
    ]

    result = _select_instance_for_migration(instances, "db-1", "us-west-2")

    assert result == instances[1]


@patch("builtins.print")
def test_select_instance_not_found(_mock_print):
    """Test instance selection when identifier not found."""
    instances = [
        {
            "identifier": "db-1",
            "region": "us-east-1",
            "engine": "mysql",
            "instance_class": "db.t3.micro",
        },
    ]

    result = _select_instance_for_migration(instances, "db-999", None)

    assert result is None


# Tests for _print_cost_analysis
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.estimate_aurora_serverless_cost")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.estimate_rds_monthly_cost")
@patch("builtins.print")
def test_print_cost_analysis(_mock_print, mock_rds_cost, mock_aurora_cost):
    """Test cost analysis printing."""
    mock_rds_cost.return_value = 120.0
    mock_aurora_cost.return_value = 43.0
    instance = {"instance_class": "db.t3.large"}

    current, estimated = _print_cost_analysis(instance)

    assert current == 120.0
    assert estimated == 43.0
    mock_rds_cost.assert_called_once_with("db.t3.large")
    mock_aurora_cost.assert_called_once()


# Tests for _confirm_migration
@patch("builtins.input", return_value="MIGRATE")
@patch("builtins.print")
def test_confirm_migration_confirmed(_mock_print, mock_input):
    """Test migration confirmation when user confirms."""
    instance = {"identifier": "db-1"}

    result = _confirm_migration(instance)

    assert result is True
    mock_input.assert_called_once()


@patch("builtins.input", return_value="NO")
@patch("builtins.print")
def test_confirm_migration_declined(_mock_print, _mock_input2):
    """Test migration confirmation when user declines."""
    instance = {"identifier": "db-1"}

    result = _confirm_migration(instance)

    assert result is False


@patch("builtins.input", return_value="migrate")
@patch("builtins.print")
def test_confirm_migration_case_sensitive(_mock_print, _mock_input3):
    """Test migration confirmation is case sensitive."""
    instance = {"identifier": "db-1"}

    result = _confirm_migration(instance)

    assert result is False


# Tests for migrate_rds_to_aurora_serverless
def test_migrate_rds_to_aurora_serverless_success():
    """Test successful migration workflow."""
    with (
        patch("builtins.print"),
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli.setup_aws_credentials"
        ) as mock_setup,
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli.discover_rds_instances"
        ) as mock_discover,
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli."
            "_select_instance_for_migration"
        ) as mock_select,
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli."
            "validate_migration_compatibility"
        ) as mock_validate,
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli._print_cost_analysis"
        ) as mock_cost,
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli._confirm_migration"
        ) as mock_confirm,
        patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.boto3"),
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli.create_rds_snapshot"
        ) as mock_snapshot,
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli."
            "create_aurora_serverless_cluster"
        ) as mock_create_cluster,
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli.print_migration_results"
        ) as mock_print_results,
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli.record_migration_action"
        ) as mock_record,
    ):

        mock_discover.return_value = [
            {"identifier": "db-1", "region": "us-east-1", "engine": "mysql"}
        ]
        mock_select.return_value = {"identifier": "db-1", "region": "us-east-1", "engine": "mysql"}
        mock_validate.return_value = (True, "aurora-mysql")
        mock_cost.return_value = (120.0, 43.0)
        mock_confirm.return_value = True
        mock_snapshot.return_value = "snap-12345"
        mock_create_cluster.return_value = {"cluster_identifier": "cluster-1"}

        migrate_rds_to_aurora_serverless()

        mock_setup.assert_called_once()
        mock_discover.assert_called_once()
        mock_snapshot.assert_called_once()
        mock_create_cluster.assert_called_once()
        mock_print_results.assert_called_once()
        mock_record.assert_called_once()


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.discover_rds_instances")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.setup_aws_credentials")
@patch("builtins.print")
def test_migrate_rds_to_aurora_serverless_no_instances(_mock_print, mock_setup, mock_discover):
    """Test migration when no instances found."""
    mock_discover.return_value = []

    migrate_rds_to_aurora_serverless()

    mock_setup.assert_called_once()
    mock_discover.assert_called_once()


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli._select_instance_for_migration")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.discover_rds_instances")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.setup_aws_credentials")
@patch("builtins.print")
def test_migrate_rds_to_aurora_serverless_no_selection(
    _mock_print, _mock_setup, mock_discover, mock_select
):
    """Test migration when no instance selected."""
    mock_discover.return_value = [{"identifier": "db-1"}]
    mock_select.return_value = None

    migrate_rds_to_aurora_serverless()

    mock_select.assert_called_once()


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.validate_migration_compatibility")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli._select_instance_for_migration")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.discover_rds_instances")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.setup_aws_credentials")
@patch("builtins.print")
def test_migrate_rds_to_aurora_serverless_incompatible(
    _mock_print, _mock_setup, mock_discover, mock_select, mock_validate
):
    """Test migration when instance is incompatible."""
    mock_discover.return_value = [{"identifier": "db-1"}]
    mock_select.return_value = {"identifier": "db-1", "region": "us-east-1"}
    mock_validate.return_value = (False, ["Incompatible engine"])

    migrate_rds_to_aurora_serverless()

    mock_validate.assert_called_once()


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli._confirm_migration")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli._print_cost_analysis")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.validate_migration_compatibility")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli._select_instance_for_migration")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.discover_rds_instances")
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.setup_aws_credentials")
@patch("builtins.print")
def test_migrate_rds_to_aurora_serverless_cancelled(
    _mock_print, _mock_setup, mock_discover, mock_select, mock_validate, mock_cost, mock_confirm
):
    """Test migration when user cancels."""
    mock_discover.return_value = [{"identifier": "db-1"}]
    mock_select.return_value = {"identifier": "db-1", "region": "us-east-1"}
    mock_validate.return_value = (True, "aurora-mysql")
    mock_cost.return_value = (120.0, 43.0)
    mock_confirm.return_value = False

    migrate_rds_to_aurora_serverless()

    mock_confirm.assert_called_once()


def test_migrate_rds_to_aurora_serverless_snapshot_error():
    """Test migration when snapshot creation fails."""
    with (
        patch("builtins.print"),
        patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.setup_aws_credentials"),
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli.discover_rds_instances"
        ) as mock_discover,
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli."
            "_select_instance_for_migration"
        ) as mock_select,
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli."
            "validate_migration_compatibility"
        ) as mock_validate,
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli._print_cost_analysis"
        ) as mock_cost,
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli._confirm_migration"
        ) as mock_confirm,
        patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.boto3"),
        patch(
            "cost_toolkit.scripts.migration.rds_aurora_migration.cli.create_rds_snapshot"
        ) as mock_snapshot,
    ):

        mock_discover.return_value = [{"identifier": "db-1"}]
        mock_select.return_value = {"identifier": "db-1", "region": "us-east-1"}
        mock_validate.return_value = (True, "aurora-mysql")
        mock_cost.return_value = (120.0, 43.0)
        mock_confirm.return_value = True
        mock_snapshot.side_effect = Exception("Snapshot failed")

        with pytest.raises(Exception):
            migrate_rds_to_aurora_serverless()


# Tests for main
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.migrate_rds_to_aurora_serverless")
def test_main_default(mock_migrate):
    """Test main with default arguments."""
    with patch("sys.argv", ["cli.py"]):
        main()

    mock_migrate.assert_called_once_with(None, None)


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.migrate_rds_to_aurora_serverless")
def test_main_with_instance(mock_migrate):
    """Test main with instance argument."""
    with patch("sys.argv", ["cli.py", "--instance", "db-1"]):
        main()

    mock_migrate.assert_called_once_with("db-1", None)


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.migrate_rds_to_aurora_serverless")
def test_main_with_region(mock_migrate):
    """Test main with region argument."""
    with patch("sys.argv", ["cli.py", "--region", "us-west-2"]):
        main()

    mock_migrate.assert_called_once_with(None, "us-west-2")


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.discover_rds_instances")
def test_main_list_only(mock_discover):
    """Test main with list-only flag."""
    with patch("sys.argv", ["cli.py", "--list-only"]):
        main()

    mock_discover.assert_called_once()


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.cli.migrate_rds_to_aurora_serverless")
def test_main_with_all_args(mock_migrate):
    """Test main with all arguments."""
    with patch("sys.argv", ["cli.py", "--instance", "db-1", "--region", "us-west-2"]):
        main()

    mock_migrate.assert_called_once_with("db-1", "us-west-2")
