"""Comprehensive tests for aws_ec2_compute_detailed_audit.py - Part 3."""

from __future__ import annotations

from unittest.mock import patch

from cost_toolkit.scripts.audit.aws_ec2_compute_detailed_audit import (
    _collect_regional_data,
    _print_cost_breakdown,
    _print_optimization_recommendations,
    main,
)


def test_print_cost_breakdown_print_breakdown(capsys):
    """Test printing cost breakdown."""
    _print_cost_breakdown(100.0, 50.0)

    captured = capsys.readouterr()
    assert "TOTAL EC2 COSTS" in captured.out
    assert "Compute (instances): $100.00/month" in captured.out
    assert "Storage (EBS): $50.00/month" in captured.out
    assert "Total EC2: $150.00/month" in captured.out


def test_print_optimization_recommendations_print_recommendations(capsys):
    """Test printing optimization recommendations."""
    stopped = [{"instance_id": "i-123"}]
    running = [{"instance_id": "i-456"}, {"instance_id": "i-789"}]

    _print_optimization_recommendations(stopped, running, 100.0, 50.0)

    captured = capsys.readouterr()
    assert "COST OPTIMIZATION OPPORTUNITIES" in captured.out
    assert "Stopped instances still incur EBS storage costs" in captured.out
    assert "Multiple running instances detected" in captured.out
    assert "Storage costs exceed compute costs" in captured.out


def test_collect_regional_data_collect_data():
    """Test collecting regional data."""
    with patch("cost_toolkit.scripts.audit.aws_ec2_compute_detailed_audit.analyze_ec2_instances_in_region") as mock_instances:
        with patch("cost_toolkit.scripts.audit.aws_ec2_compute_detailed_audit." "analyze_ebs_volumes_in_region") as mock_volumes:
            mock_instances.return_value = [
                {"state": "running", "monthly_cost": 10.0},
                {"state": "stopped", "monthly_cost": 0.0},
            ]
            mock_volumes.return_value = [{"monthly_cost": 5.0}]

            result = _collect_regional_data(["us-east-1"])

    assert len(result["all_instances"]) == 2
    assert len(result["all_volumes"]) == 1
    assert result["total_compute_cost"] == 10.0
    assert result["total_storage_cost"] == 5.0


def test_main_function_main_execution(capsys):
    """Test main function execution."""
    with patch("cost_toolkit.scripts.audit.aws_ec2_compute_detailed_audit.get_all_regions") as mock_regions:
        with patch("cost_toolkit.scripts.audit.aws_ec2_compute_detailed_audit._collect_regional_data") as mock_collect:
            mock_regions.return_value = ["us-east-1"]
            mock_collect.return_value = {
                "all_instances": [
                    {
                        "instance_id": "i-123",
                        "instance_type": "t3.micro",
                        "state": "running",
                        "monthly_cost": 10.0,
                    },
                ],
                "all_volumes": [{"monthly_cost": 5.0}],
                "total_compute_cost": 10.0,
                "total_storage_cost": 5.0,
            }

            main()

    captured = capsys.readouterr()
    assert "AWS EC2 Compute Detailed Cost Analysis" in captured.out
    assert "OVERALL EC2 COST BREAKDOWN" in captured.out
