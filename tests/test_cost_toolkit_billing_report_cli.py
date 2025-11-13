"""Tests for cost_toolkit/scripts/billing/billing_report/cli.py"""

from __future__ import annotations

from unittest.mock import patch

from cost_toolkit.scripts.billing.billing_report.cli import main


@patch("cost_toolkit.scripts.billing.billing_report.cli.format_combined_billing_report")
@patch("cost_toolkit.scripts.billing.billing_report.cli.get_combined_billing_data")
@patch("cost_toolkit.scripts.billing.billing_report.cli.check_aws_credentials")
@patch("cost_toolkit.scripts.billing.billing_report.cli.clear_screen")
def test_main_success(mock_clear, mock_check_creds, mock_get_data, mock_format_report):
    """Test main function with successful billing data retrieval."""
    mock_check_creds.return_value = True
    mock_get_data.return_value = ({"service1": 100.50}, {"service1": 1000})

    main()

    mock_clear.assert_called_once()
    mock_check_creds.assert_called_once()
    mock_get_data.assert_called_once()
    mock_format_report.assert_called_once_with({"service1": 100.50}, {"service1": 1000})


@patch("cost_toolkit.scripts.billing.billing_report.cli.check_aws_credentials")
@patch("cost_toolkit.scripts.billing.billing_report.cli.clear_screen")
def test_main_no_credentials(mock_clear, mock_check_creds, capsys):
    """Test main function when credentials check fails."""
    mock_check_creds.return_value = False

    main()

    mock_clear.assert_called_once()
    mock_check_creds.assert_called_once()

    captured = capsys.readouterr()
    assert "Failed to load AWS credentials" in captured.out


@patch("cost_toolkit.scripts.billing.billing_report.cli.get_combined_billing_data")
@patch("cost_toolkit.scripts.billing.billing_report.cli.check_aws_credentials")
@patch("cost_toolkit.scripts.billing.billing_report.cli.clear_screen")
def test_main_no_cost_data(mock_clear, mock_check_creds, mock_get_data, capsys):
    """Test main function when billing data retrieval fails."""
    mock_check_creds.return_value = True
    mock_get_data.return_value = (None, None)

    main()

    mock_clear.assert_called_once()
    mock_check_creds.assert_called_once()
    mock_get_data.assert_called_once()

    captured = capsys.readouterr()
    assert "Failed to retrieve billing data" in captured.out
