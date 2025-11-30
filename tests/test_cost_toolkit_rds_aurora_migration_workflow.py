"""Tests for cost_toolkit/scripts/migration/rds_aurora_migration/migration_workflow.py"""

from __future__ import annotations

from unittest.mock import mock_open, patch

import pytest

from cost_toolkit.scripts.migration.rds_aurora_migration.migration_workflow import (
    estimate_aurora_serverless_cost,
    estimate_rds_monthly_cost,
    print_migration_results,
    record_migration_action,
)


# Tests for estimate_rds_monthly_cost
def test_estimate_rds_monthly_cost_t3_micro():
    """Test RDS cost estimation for t3.micro."""
    result = estimate_rds_monthly_cost("db.t3.micro")
    assert result == 15.0


def test_estimate_rds_monthly_cost_t3_small():
    """Test RDS cost estimation for t3.small."""
    result = estimate_rds_monthly_cost("db.t3.small")
    assert result == 30.0


def test_estimate_rds_monthly_cost_t3_medium():
    """Test RDS cost estimation for t3.medium."""
    result = estimate_rds_monthly_cost("db.t3.medium")
    assert result == 60.0


def test_estimate_rds_monthly_cost_t3_large():
    """Test RDS cost estimation for t3.large."""
    result = estimate_rds_monthly_cost("db.t3.large")
    assert result == 120.0


def test_estimate_rds_monthly_cost_m5_large():
    """Test RDS cost estimation for m5.large."""
    result = estimate_rds_monthly_cost("db.m5.large")
    assert result == 180.0


def test_estimate_rds_monthly_cost_r5_xlarge():
    """Test RDS cost estimation for r5.xlarge."""
    result = estimate_rds_monthly_cost("db.r5.xlarge")
    assert result == 440.0


def test_estimate_rds_monthly_cost_unknown():
    """Test RDS cost estimation for unknown instance class."""
    result = estimate_rds_monthly_cost("db.unknown.type")
    assert result == 100.0


def test_estimate_rds_monthly_cost_empty():
    """Test RDS cost estimation for empty instance class."""
    result = estimate_rds_monthly_cost("")
    assert result == 100.0


# Tests for estimate_aurora_serverless_cost
def test_estimate_aurora_serverless_cost():
    """Test Aurora Serverless cost estimation."""
    result = estimate_aurora_serverless_cost()

    # Expected: 720 hours * 0.5 ACU * 0.2 utilization * $0.12 per ACU-hour
    expected = 720 * 0.5 * 0.2 * 0.12
    assert result == expected


# Tests for print_migration_results
@patch("builtins.print")
def test_print_migration_results_with_reader(_mock_print):
    """Test printing migration results with reader endpoint."""
    original = {
        "identifier": "db-1",
        "region": "us-east-1",
        "engine": "mysql",
    }
    endpoint = {
        "cluster_identifier": "db-1-aurora-serverless",
        "writer_endpoint": "cluster.us-east-1.rds.amazonaws.com",
        "reader_endpoint": "cluster-ro.us-east-1.rds.amazonaws.com",
        "port": 3306,
        "engine": "aurora-mysql",
    }

    print_migration_results(original, endpoint, 120.0, 43.0)

    _mock_print.assert_called()
    call_args = [str(call) for call in _mock_print.call_args_list]
    combined = " ".join(call_args)

    assert "db-1" in combined
    assert "cluster.us-east-1.rds.amazonaws.com" in combined
    assert "cluster-ro.us-east-1.rds.amazonaws.com" in combined
    assert "3306" in combined


@patch("builtins.print")
def test_print_migration_results_without_reader(_mock_print):
    """Test printing migration results without reader endpoint."""
    original = {
        "identifier": "db-1",
        "region": "us-east-1",
        "engine": "postgres",
    }
    endpoint = {
        "cluster_identifier": "db-1-aurora-serverless",
        "writer_endpoint": "cluster.us-east-1.rds.amazonaws.com",
        "reader_endpoint": None,
        "port": 5432,
        "engine": "aurora-postgresql",
    }

    print_migration_results(original, endpoint, 180.0, 43.0)

    _mock_print.assert_called()


@patch("builtins.print")
def test_print_migration_results_cost_calculations(_mock_print):
    """Test printing migration results with cost calculations."""
    original = {
        "identifier": "db-1",
        "region": "us-east-1",
        "engine": "mysql",
    }
    endpoint = {
        "cluster_identifier": "cluster-1",
        "writer_endpoint": "cluster.rds.amazonaws.com",
        "reader_endpoint": None,
        "port": 3306,
        "engine": "aurora-mysql",
    }

    print_migration_results(original, endpoint, 240.0, 60.0)

    call_args = [str(call) for call in _mock_print.call_args_list]
    combined = " ".join(call_args)

    assert "240.00" in combined
    assert "60.00" in combined
    assert "180.00" in combined


# Tests for record_migration_action
@patch("cost_toolkit.scripts.migration.rds_aurora_migration.migration_workflow.datetime")
@patch("builtins.open", new_callable=mock_open)
@patch("builtins.print")
def test_record_migration_action_new_file(_mock_print, mock_file, mock_datetime):
    """Test recording migration action when log file doesn't exist."""
    mock_datetime.now.return_value.isoformat.return_value = "2025-01-14T12:00:00"

    original = {
        "identifier": "db-1",
        "region": "us-east-1",
        "engine": "mysql",
        "instance_class": "db.t3.large",
    }
    endpoint = {
        "cluster_identifier": "cluster-1",
        "engine": "aurora-mysql",
        "writer_endpoint": "cluster.rds.amazonaws.com",
    }

    with patch("os.path.exists", return_value=False):
        with patch("os.makedirs"):
            record_migration_action(original, endpoint, 77.0)

    mock_file.assert_called()
    write_calls = list(mock_file().write.call_args_list)
    written_data = "".join([str(call[0][0]) for call in write_calls])

    assert "db-1" in written_data
    assert "cluster-1" in written_data
    assert "77" in written_data or "77.0" in written_data


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.migration_workflow.datetime")
@patch("builtins.open", new_callable=mock_open, read_data='{"migrations": []}')
@patch("builtins.print")
def test_record_migration_action_existing_file(_mock_print, mock_file, mock_datetime):
    """Test recording migration action when log file exists."""
    mock_datetime.now.return_value.isoformat.return_value = "2025-01-14T12:00:00"

    original = {
        "identifier": "db-2",
        "region": "us-west-2",
        "engine": "postgres",
        "instance_class": "db.t3.medium",
    }
    endpoint = {
        "cluster_identifier": "cluster-2",
        "engine": "aurora-postgresql",
        "writer_endpoint": "cluster2.rds.amazonaws.com",
    }

    with patch("os.path.exists", return_value=True):
        with patch("os.makedirs"):
            record_migration_action(original, endpoint, 17.0)

    mock_file.assert_called()


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.migration_workflow.datetime")
@patch("builtins.open", new_callable=mock_open)
def test_record_migration_action_write_error(mock_file, mock_datetime):
    """Test recording migration action with write error."""
    mock_datetime.now.return_value.isoformat.return_value = "2025-01-14T12:00:00"
    mock_file.side_effect = IOError("Permission denied")

    original = {
        "identifier": "db-1",
        "region": "us-east-1",
        "engine": "mysql",
        "instance_class": "db.t3.large",
    }
    endpoint = {
        "cluster_identifier": "cluster-1",
        "engine": "aurora-mysql",
        "writer_endpoint": "cluster.rds.amazonaws.com",
    }

    with patch("os.path.exists", return_value=False):
        with patch("os.makedirs"):
            with pytest.raises(IOError, match="Permission denied"):
                record_migration_action(original, endpoint, 77.0)


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.migration_workflow.datetime")
@patch("builtins.open", new_callable=mock_open, read_data='{"migrations": [{"old": "data"}]}')
@patch("builtins.print")
def test_record_migration_action_appends_to_existing(_mock_print, mock_file, mock_datetime):
    """Test recording migration action appends to existing migrations."""
    mock_datetime.now.return_value.isoformat.return_value = "2025-01-14T12:00:00"

    original = {
        "identifier": "db-3",
        "region": "eu-west-1",
        "engine": "mariadb",
        "instance_class": "db.t3.small",
    }
    endpoint = {
        "cluster_identifier": "cluster-3",
        "engine": "aurora-mysql",
        "writer_endpoint": "cluster3.rds.amazonaws.com",
    }

    with patch("os.path.exists", return_value=True):
        with patch("os.makedirs"):
            record_migration_action(original, endpoint, 13.0)

    mock_file.assert_called()


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.migration_workflow.datetime")
@patch("builtins.open", new_callable=mock_open)
@patch("builtins.print")
def test_record_migration_action_creates_directory(_mock_print, _mock_file, mock_datetime):
    """Test recording migration action creates directory if needed."""
    mock_datetime.now.return_value.isoformat.return_value = "2025-01-14T12:00:00"

    original = {
        "identifier": "db-1",
        "region": "us-east-1",
        "engine": "mysql",
        "instance_class": "db.t3.large",
    }
    endpoint = {
        "cluster_identifier": "cluster-1",
        "engine": "aurora-mysql",
        "writer_endpoint": "cluster.rds.amazonaws.com",
    }

    with patch("os.path.exists", return_value=False):
        with patch("os.makedirs") as mock_makedirs:
            record_migration_action(original, endpoint, 77.0)
            mock_makedirs.assert_called()


@patch("cost_toolkit.scripts.migration.rds_aurora_migration.migration_workflow.datetime")
@patch("builtins.open", new_callable=mock_open)
@patch("builtins.print")
def test_record_migration_action_complete_log_entry(_mock_print, mock_file, mock_datetime):
    """Test recording migration action creates complete log entry."""
    mock_datetime.now.return_value.isoformat.return_value = "2025-01-14T12:00:00"

    original = {
        "identifier": "production-db",
        "region": "us-east-1",
        "engine": "mysql",
        "instance_class": "db.r5.xlarge",
    }
    endpoint = {
        "cluster_identifier": "production-aurora",
        "engine": "aurora-mysql",
        "writer_endpoint": "production.rds.amazonaws.com",
    }

    with patch("os.path.exists", return_value=False):
        with patch("os.makedirs"):
            record_migration_action(original, endpoint, 397.0)

    write_calls = list(mock_file().write.call_args_list)
    written_data = "".join([str(call[0][0]) for call in write_calls])

    assert "production-db" in written_data
    assert "production-aurora" in written_data
    assert "us-east-1" in written_data
    assert "aurora-mysql" in written_data
    assert "397" in written_data or "397.0" in written_data
    assert "completed" in written_data
