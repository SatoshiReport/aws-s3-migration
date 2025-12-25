"""Tests for cost_toolkit/overview/recommendations.py module."""

from __future__ import annotations

import json
from unittest.mock import mock_open, patch

from cost_toolkit.overview.recommendations import (
    _add_accelerator_recommendations,
    _add_cloudwatch_recommendations,
    _add_database_recommendations,
    _add_ec2_recommendations,
    _add_generic_recommendations,
    _add_lightsail_recommendations,
    _add_service_recommendation,
    _add_storage_recommendations,
    _add_vpc_recommendations,
    _match_service_type,
    _route_to_service_handler,
    get_completed_cleanups,
    get_service_recommendations,
)


def test_get_completed_cleanups_file_exists():
    """Test get_completed_cleanups when cleanup log exists."""
    log_data = {
        "cleanup_actions": [
            {"service": "lightsail", "status": "completed"},
            {"service": "rds", "status": "pending"},
            {"service": "ec2", "status": "completed"},
        ]
    }

    with patch("builtins.open", mock_open(read_data=json.dumps(log_data))):
        with patch("os.path.exists", return_value=True):
            result = get_completed_cleanups()

            assert "lightsail" in result
            assert "ec2" in result
            assert "rds" not in result


def test_get_completed_cleanups_file_not_exists():
    """Test get_completed_cleanups when cleanup log doesn't exist."""
    with patch("os.path.exists", return_value=False):
        result = get_completed_cleanups()

        assert isinstance(result, set)
        assert len(result) == 0


def test_get_completed_cleanups_invalid_json():
    """Test get_completed_cleanups handles invalid JSON."""
    with patch("builtins.open", mock_open(read_data="invalid json")):
        with patch("os.path.exists", return_value=True):
            result = get_completed_cleanups()

            assert isinstance(result, set)


def test_get_completed_cleanups_os_error():
    """Test get_completed_cleanups handles OSError."""
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", side_effect=OSError("File error")):
            result = get_completed_cleanups()

            assert isinstance(result, set)
            assert len(result) == 0


def test_add_storage_recommendations():
    """Test _add_storage_recommendations adds correct messages."""
    recommendations = []
    _add_storage_recommendations(recommendations, "S3", 100.50, 25.5)

    assert len(recommendations) == 3
    assert "S3" in recommendations[0]
    assert "100.50" in recommendations[0]
    assert "lifecycle" in recommendations[1].lower()
    assert "Glacier" in recommendations[2]


def test_add_ec2_recommendations():
    """Test _add_ec2_recommendations adds correct messages."""
    recommendations = []
    _add_ec2_recommendations(recommendations, "EC2", 200.00, 40.0)

    assert len(recommendations) == 3
    assert "EC2" in recommendations[0]
    assert "200.00" in recommendations[0]
    assert "Reserved" in recommendations[1] or "Savings Plans" in recommendations[1]


def test_add_database_recommendations():
    """Test _add_database_recommendations adds correct messages."""
    recommendations = []
    _add_database_recommendations(recommendations, "RDS", 150.75, 30.5)

    assert len(recommendations) == 3
    assert "RDS" in recommendations[0]
    assert "150.75" in recommendations[0]
    assert "Aurora" in recommendations[1] or "Serverless" in recommendations[1]


def test_add_lightsail_recommendations_completed():
    """Test _add_lightsail_recommendations when cleanup is completed."""
    recommendations = []
    completed_cleanups = {"lightsail"}

    _add_lightsail_recommendations(recommendations, "Lightsail", 50.00, 10.0, completed_cleanups)

    assert len(recommendations) == 3
    assert "✅" in recommendations[0]
    assert "previously completed" in recommendations[1].lower()


def test_add_lightsail_recommendations_not_completed():
    """Test _add_lightsail_recommendations when cleanup is not completed."""
    recommendations = []
    completed_cleanups = set()

    _add_lightsail_recommendations(recommendations, "Lightsail", 50.00, 10.0, completed_cleanups)

    assert len(recommendations) == 3
    assert "💡" in recommendations[0]
    assert "cleanup.py" in recommendations[2]


def test_add_accelerator_recommendations():
    """Test _add_accelerator_recommendations adds correct messages."""
    recommendations = []
    _add_accelerator_recommendations(recommendations, "Global Accelerator", 75.00, 15.0)

    assert len(recommendations) == 3
    assert "Global Accelerator" in recommendations[0]
    assert "75.00" in recommendations[0]
    assert "listener" in recommendations[1].lower() or "accelerator" in recommendations[1].lower()


def test_add_vpc_recommendations():
    """Test _add_vpc_recommendations adds correct messages."""
    recommendations = []
    _add_vpc_recommendations(recommendations, "VPC", 30.00, 6.0)

    assert len(recommendations) == 3
    assert "VPC" in recommendations[0]
    assert "30.00" in recommendations[0]
    assert "NAT" in recommendations[1] or "Elastic IP" in recommendations[1]


def test_add_cloudwatch_recommendations():
    """Test _add_cloudwatch_recommendations adds correct messages."""
    recommendations = []
    _add_cloudwatch_recommendations(recommendations, "CloudWatch", 40.00, 8.0)

    assert len(recommendations) == 3
    assert "CloudWatch" in recommendations[0]
    assert "40.00" in recommendations[0]
    assert "retention" in recommendations[1].lower()


def test_add_generic_recommendations():
    """Test _add_generic_recommendations adds correct messages."""
    recommendations = []
    _add_generic_recommendations(recommendations, "SomeService", 25.00, 5.0)

    assert len(recommendations) == 2
    assert "SomeService" in recommendations[0]
    assert "25.00" in recommendations[0]
    assert "optimization" in recommendations[1].lower()


def test_match_service_type_storage():
    """Test _match_service_type identifies storage services."""
    assert _match_service_type("S3") == "storage"
    assert _match_service_type("STORAGE") == "storage"
    assert _match_service_type("Amazon S3") == "storage"


def test_match_service_type_ec2():
    """Test _match_service_type identifies EC2 services."""
    assert _match_service_type("EC2") == "ec2"
    assert _match_service_type("Amazon EC2") == "ec2"


def test_match_service_type_database():
    """Test _match_service_type identifies database services."""
    assert _match_service_type("RDS") == "database"
    assert _match_service_type("DATABASE") == "database"
    assert _match_service_type("Amazon RDS") == "database"


def test_match_service_type_lightsail():
    """Test _match_service_type identifies Lightsail services."""
    assert _match_service_type("LIGHTSAIL") == "lightsail"


def test_match_service_type_accelerator():
    """Test _match_service_type identifies Global Accelerator services."""
    assert _match_service_type("GLOBAL ACCELERATOR") == "accelerator"


def test_match_service_type_vpc():
    """Test _match_service_type identifies VPC services."""
    assert _match_service_type("VPC") == "vpc"
    assert _match_service_type("PRIVATE CLOUD") == "vpc"


def test_match_service_type_cloudwatch():
    """Test _match_service_type identifies CloudWatch services."""
    assert _match_service_type("CLOUDWATCH") == "cloudwatch"


def test_match_service_type_generic():
    """Test _match_service_type returns generic for unknown services."""
    assert _match_service_type("UNKNOWN_SERVICE") == "generic"
    assert _match_service_type("Lambda") == "generic"


def test_route_to_service_handler_storage():
    """Test _route_to_service_handler routes to storage handler."""
    recommendations = []
    _route_to_service_handler("S3", recommendations, "S3", cost=100.0, percentage=20.0, completed_cleanups=set())

    assert len(recommendations) == 3
    assert "Glacier" in recommendations[2]


def test_route_to_service_handler_ec2():
    """Test _route_to_service_handler routes to EC2 handler."""
    recommendations = []
    _route_to_service_handler("EC2", recommendations, "EC2", cost=200.0, percentage=40.0, completed_cleanups=set())

    assert len(recommendations) == 3
    assert "Reserved" in recommendations[1] or "Savings Plans" in recommendations[1]


def test_route_to_service_handler_database():
    """Test _route_to_service_handler routes to database handler."""
    recommendations = []
    _route_to_service_handler("RDS", recommendations, "RDS", cost=150.0, percentage=30.0, completed_cleanups=set())

    assert len(recommendations) == 3


def test_route_to_service_handler_lightsail():
    """Test _route_to_service_handler routes to Lightsail handler."""
    recommendations = []
    _route_to_service_handler(
        "LIGHTSAIL",
        recommendations,
        "Lightsail",
        cost=50.0,
        percentage=10.0,
        completed_cleanups=set(),
    )

    assert len(recommendations) == 3


def test_route_to_service_handler_accelerator():
    """Test _route_to_service_handler routes to accelerator handler."""
    recommendations = []
    _route_to_service_handler(
        "GLOBAL ACCELERATOR",
        recommendations,
        "Global Accelerator",
        cost=75.0,
        percentage=15.0,
        completed_cleanups=set(),
    )

    assert len(recommendations) == 3


def test_route_to_service_handler_vpc():
    """Test _route_to_service_handler routes to VPC handler."""
    recommendations = []
    _route_to_service_handler("VPC", recommendations, "VPC", cost=30.0, percentage=6.0, completed_cleanups=set())

    assert len(recommendations) == 3


def test_route_to_service_handler_cloudwatch():
    """Test _route_to_service_handler routes to CloudWatch handler."""
    recommendations = []
    _route_to_service_handler(
        "CLOUDWATCH",
        recommendations,
        "CloudWatch",
        cost=40.0,
        percentage=8.0,
        completed_cleanups=set(),
    )

    assert len(recommendations) == 3


def test_route_to_service_handler_generic():
    """Test _route_to_service_handler routes to generic handler."""
    recommendations = []
    _route_to_service_handler(
        "LAMBDA",
        recommendations,
        "Lambda",
        cost=25.0,
        percentage=5.0,
        completed_cleanups=set(),
    )

    assert len(recommendations) == 2


def test_add_service_recommendation():
    """Test _add_service_recommendation routes correctly."""
    recommendations = []
    _add_service_recommendation(recommendations, "S3", 100.0, 20.0, set())

    assert len(recommendations) > 0
    assert "S3" in recommendations[0]


def test_get_service_recommendations_with_services():
    """Test get_service_recommendations with service costs."""
    service_costs = {
        "S3": 100.0,
        "EC2": 200.0,
        "RDS": 150.0,
        "Lightsail": 50.0,
        "Global Accelerator": 75.0,
        "VPC": 30.0,
        "CloudWatch": 40.0,
        "Lambda": 25.0,
        "ECS": 10.0,  # This should be included (9th service, top 8 only)
    }

    with patch("cost_toolkit.overview.recommendations.get_completed_cleanups") as mock_cleanups:
        mock_cleanups.return_value = set()

        recommendations = get_service_recommendations(service_costs)

        # Should have recommendations (3 lines per service, top 8 services)
        assert len(recommendations) > 0
        # Verify some services are included
        assert any("EC2" in str(r) for r in recommendations)
        assert any("S3" in str(r) for r in recommendations)


def test_get_service_recommendations_filters_low_cost():
    """Test get_service_recommendations filters out low-cost services."""
    service_costs = {
        "S3": 2.0,  # Below threshold
        "EC2": 3.0,  # Below threshold
        "RDS": 10.0,  # Above threshold
    }

    with patch("cost_toolkit.overview.recommendations.get_completed_cleanups") as mock_cleanups:
        mock_cleanups.return_value = set()

        recommendations = get_service_recommendations(service_costs)

        # Should only have recommendations for RDS
        assert any("RDS" in str(r) for r in recommendations)
        assert not any("S3" in str(r) for r in recommendations)
        assert not any("EC2" in str(r) for r in recommendations)


def test_get_service_recommendations_empty_costs():
    """Test get_service_recommendations with empty service costs."""
    service_costs = {}

    with patch("cost_toolkit.overview.recommendations.get_completed_cleanups") as mock_cleanups:
        mock_cleanups.return_value = set()

        recommendations = get_service_recommendations(service_costs)

        assert len(recommendations) == 0


def test_get_service_recommendations_completed_cleanups():
    """Test get_service_recommendations respects completed cleanups."""
    service_costs = {
        "Lightsail": 50.0,
    }

    with patch("cost_toolkit.overview.recommendations.get_completed_cleanups") as mock_cleanups:
        mock_cleanups.return_value = {"lightsail"}

        recommendations = get_service_recommendations(service_costs)

        # Should have different message for completed cleanup
        assert any("✅" in str(r) for r in recommendations)
