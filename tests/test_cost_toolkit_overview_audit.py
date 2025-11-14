"""Tests for cost_toolkit/overview/audit.py module."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from cost_toolkit.overview.audit import (
    _extract_summary_lines,
    _run_audit_script,
    report_lightsail_cost_breakdown,
    run_quick_audit,
)


def test_extract_summary_lines_with_keywords():
    """Test _extract_summary_lines extracts lines with keywords."""
    output = """
Line 1
Total: 10 items
Line 3
Found 5 volumes
Line 5
RECOMMENDATIONS:
Line 7
"""
    result = _extract_summary_lines(output)
    assert len(result) <= 5
    assert any("Total" in line for line in result)
    assert any("Found" in line for line in result)


def test_extract_summary_lines_returns_last_five():
    """Test that _extract_summary_lines returns at most 5 lines."""
    output = "\n".join([f"Total: {i}" for i in range(20)])
    result = _extract_summary_lines(output)
    assert len(result) == 5


def test_run_audit_script_not_found(capsys, tmp_path):
    """Test _run_audit_script when script doesn't exist."""
    script_path = tmp_path / "nonexistent.py"
    _run_audit_script("Test Audit", str(script_path))

    captured = capsys.readouterr()
    assert "Script not found" in captured.out


def test_run_audit_script_success(capsys, tmp_path):
    """Test _run_audit_script with successful execution."""
    script_path = tmp_path / "test_script.py"
    script_path.write_text("print('Total: 10 items')")

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Total: 10 items\nFound 5 volumes"
        mock_run.return_value = mock_result

        _run_audit_script("Test Audit", str(script_path))

        captured = capsys.readouterr()
        assert "Test Audit" in captured.out


def test_run_audit_script_failure(capsys, tmp_path):
    """Test _run_audit_script when script fails."""
    script_path = tmp_path / "test_script.py"
    script_path.write_text("import sys; sys.exit(1)")

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error occurred"
        mock_run.return_value = mock_result

        _run_audit_script("Test Audit", str(script_path))

        captured = capsys.readouterr()
        assert "Script failed" in captured.out


def test_run_audit_script_timeout(capsys, tmp_path):
    """Test _run_audit_script handles timeout."""
    script_path = tmp_path / "test_script.py"
    script_path.write_text("print('test')")

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 60)):
        _run_audit_script("Test Audit", str(script_path))

        captured = capsys.readouterr()
        assert "timed out" in captured.out


def test_run_audit_script_client_error(capsys, tmp_path):
    """Test _run_audit_script handles ClientError."""
    script_path = tmp_path / "test_script.py"
    script_path.write_text("print('test')")

    with patch("subprocess.run", side_effect=ClientError({"Error": {"Code": "TestError"}}, "test")):
        _run_audit_script("Test Audit", str(script_path))

        captured = capsys.readouterr()
        assert "Error running audit" in captured.out


def test_run_quick_audit(capsys, tmp_path):
    """Test run_quick_audit executes audit scripts."""
    scripts_dir = tmp_path
    audit_dir = scripts_dir / "audit"
    audit_dir.mkdir()

    ebs_script = audit_dir / "aws_ebs_audit.py"
    vpc_script = audit_dir / "aws_vpc_audit.py"
    ebs_script.write_text("print('EBS test')")
    vpc_script.write_text("print('VPC test')")

    with patch("cost_toolkit.overview.audit._run_audit_script") as mock_run:
        run_quick_audit(str(scripts_dir))

        assert mock_run.call_count == 2
        captured = capsys.readouterr()
        assert "Quick Resource Audit" in captured.out


def test_report_lightsail_cost_breakdown_with_data(capsys):
    """Test report_lightsail_cost_breakdown with cost data."""
    with patch("boto3.client") as mock_client:
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["USW2-BoxUsage:1"],
                            "Metrics": {"UnblendedCost": {"Amount": "10.50"}},
                        },
                        {
                            "Keys": ["USW2-LoadBalancer"],
                            "Metrics": {"UnblendedCost": {"Amount": "5.25"}},
                        },
                    ]
                }
            ]
        }
        mock_client.return_value = mock_ce

        report_lightsail_cost_breakdown()

        captured = capsys.readouterr()
        assert "LIGHTSAIL COST BREAKDOWN" in captured.out
        assert "10.50" in captured.out or "5.25" in captured.out


def test_report_lightsail_cost_breakdown_no_data(capsys):
    """Test report_lightsail_cost_breakdown with no cost data."""
    with patch("boto3.client") as mock_client:
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.return_value = {"ResultsByTime": [{"Groups": []}]}
        mock_client.return_value = mock_ce

        report_lightsail_cost_breakdown()

        captured = capsys.readouterr()
        assert "No Lightsail spend" in captured.out


def test_report_lightsail_cost_breakdown_error(capsys):
    """Test report_lightsail_cost_breakdown handles errors."""
    with patch("boto3.client") as mock_client:
        mock_ce = MagicMock()
        mock_ce.get_cost_and_usage.side_effect = ClientError(
            {"Error": {"Code": "TestError"}}, "test"
        )
        mock_client.return_value = mock_ce

        report_lightsail_cost_breakdown()

        captured = capsys.readouterr()
        assert "Unable to fetch" in captured.out
