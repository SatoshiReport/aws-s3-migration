"""Tests for billing/billing_report/cost_analysis.py (usage and categorization)."""

from __future__ import annotations

from cost_toolkit.scripts.billing.billing_report.cost_analysis import (
    categorize_services,
    process_usage_data,
)


class TestProcessUsageDataBasic:
    """Tests for basic usage data processing scenarios."""

    def test_process_usage_data_single_service(self):
        """Test processing usage data with one service."""
        usage_data = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["Amazon S3", "DataTransfer-In-Bytes"],
                            "Metrics": {"UsageQuantity": {"Amount": "1024.50", "Unit": "GB"}},
                        }
                    ]
                }
            ]
        }

        service_usage = process_usage_data(usage_data)

        assert "Amazon S3" in service_usage
        assert len(service_usage["Amazon S3"]) == 1
        assert service_usage["Amazon S3"][0] == ("DataTransfer-In-Bytes", 1024.50, "GB")

    def test_process_usage_data_multiple_usage_types(self):
        """Test processing usage data with multiple usage types for same service."""
        usage_data = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["Amazon S3", "DataTransfer-In-Bytes"],
                            "Metrics": {"UsageQuantity": {"Amount": "1024.50", "Unit": "GB"}},
                        },
                        {
                            "Keys": ["Amazon S3", "Requests-Tier1"],
                            "Metrics": {"UsageQuantity": {"Amount": "5000.00", "Unit": "N"}},
                        },
                        {
                            "Keys": ["Amazon EC2", "BoxUsage:t3.micro"],
                            "Metrics": {"UsageQuantity": {"Amount": "720.00", "Unit": "Hrs"}},
                        },
                    ]
                }
            ]
        }

        service_usage = process_usage_data(usage_data)

        assert "Amazon S3" in service_usage
        assert len(service_usage["Amazon S3"]) == 2
        assert ("DataTransfer-In-Bytes", 1024.50, "GB") in service_usage["Amazon S3"]
        assert ("Requests-Tier1", 5000.00, "N") in service_usage["Amazon S3"]
        assert "Amazon EC2" in service_usage
        assert len(service_usage["Amazon EC2"]) == 1


class TestProcessUsageDataEdgeCases:
    """Tests for edge cases in usage data processing."""

    def test_process_usage_data_zero_quantity_excluded(self):
        """Test that zero-quantity usage items are excluded."""
        usage_data = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["Amazon S3", "DataTransfer-In-Bytes"],
                            "Metrics": {"UsageQuantity": {"Amount": "0.00", "Unit": "GB"}},
                        },
                        {
                            "Keys": ["Amazon EC2", "BoxUsage:t3.micro"],
                            "Metrics": {"UsageQuantity": {"Amount": "100.00", "Unit": "Hrs"}},
                        },
                    ]
                }
            ]
        }

        service_usage = process_usage_data(usage_data)

        assert "Amazon S3" not in service_usage
        assert "Amazon EC2" in service_usage

    def test_process_usage_data_missing_keys(self):
        """Test processing usage data with missing keys defaults to Unknown."""
        usage_data = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": [],
                            "Metrics": {"UsageQuantity": {"Amount": "50.00", "Unit": "GB"}},
                        },
                        {
                            "Keys": ["Amazon S3"],
                            "Metrics": {"UsageQuantity": {"Amount": "75.00", "Unit": "GB"}},
                        },
                    ]
                }
            ]
        }

        service_usage = process_usage_data(usage_data)

        assert "Unknown Service" in service_usage
        assert ("Unknown Usage Type", 50.00, "GB") in service_usage["Unknown Service"]
        assert "Amazon S3" in service_usage
        assert ("Unknown Usage Type", 75.00, "GB") in service_usage["Amazon S3"]


class TestProcessUsageDataEmptyInputs:
    """Tests for empty or None usage data inputs."""

    def test_process_usage_data_none_input(self):
        """Test processing None usage data returns empty dict."""
        service_usage = process_usage_data(None)

        assert not service_usage

    def test_process_usage_data_empty_results(self):
        """Test processing usage data with no ResultsByTime."""
        usage_data = {"SomeOtherKey": []}

        service_usage = process_usage_data(usage_data)

        assert not service_usage

    def test_process_usage_data_empty_groups(self):
        """Test processing usage data with empty groups."""
        usage_data = {"ResultsByTime": [{"Groups": []}]}

        service_usage = process_usage_data(usage_data)

        assert not service_usage


class TestCategorizeServicesSingleCategory:
    """Tests for categorizing services within a single status category."""

    def test_categorize_services_all_unresolved(self):
        """Test categorization when all services are unresolved."""
        service_costs = {
            "Amazon S3": {"cost": 100.00, "regions": {"us-east-1": 100.00}},
            "Amazon EC2": {"cost": 200.00, "regions": {"us-west-2": 200.00}},
        }
        resolved_services = {}

        result = categorize_services(service_costs, resolved_services)

        assert len(result) == 2
        assert result[0][0] == "Amazon EC2"  # Higher cost first
        assert result[1][0] == "Amazon S3"

    def test_categorize_services_all_resolved(self):
        """Test categorization when all services are resolved."""
        service_costs = {
            "Amazon S3": {"cost": 100.00, "regions": {"us-east-1": 100.00}},
            "Amazon EC2": {"cost": 200.00, "regions": {"us-west-2": 200.00}},
        }
        resolved_services = {
            "AMAZON S3": "✅ RESOLVED - Storage costs optimized",
            "AMAZON EC2": "✅ RESOLVED - Instances right-sized",
        }

        result = categorize_services(service_costs, resolved_services)

        assert len(result) == 2
        # Resolved services come last, sorted by cost descending
        assert result[0][0] == "Amazon EC2"
        assert result[1][0] == "Amazon S3"

    def test_categorize_services_all_noted(self):
        """Test categorization when all services are noted."""
        service_costs = {
            "Amazon S3": {"cost": 100.00, "regions": {"us-east-1": 100.00}},
            "Amazon EC2": {"cost": 200.00, "regions": {"us-west-2": 200.00}},
        }
        resolved_services = {
            "AMAZON S3": "📝 NOTED - Monitoring storage growth",
            "AMAZON EC2": "📝 NOTED - Reviewing instance usage",
        }

        result = categorize_services(service_costs, resolved_services)

        assert len(result) == 2
        # Noted services in middle, sorted by cost descending
        assert result[0][0] == "Amazon EC2"
        assert result[1][0] == "Amazon S3"


class TestCategorizeServicesMixedCategories:
    """Tests for categorizing services with mixed status categories."""

    def test_categorize_services_mixed_statuses(self):
        """Test categorization with mixed service statuses."""
        service_costs = {
            "Amazon S3": {"cost": 100.00, "regions": {"us-east-1": 100.00}},
            "Amazon EC2": {"cost": 200.00, "regions": {"us-west-2": 200.00}},
            "Amazon RDS": {"cost": 150.00, "regions": {"us-east-1": 150.00}},
            "AWS Lambda": {"cost": 50.00, "regions": {"us-west-2": 50.00}},
            "Amazon DynamoDB": {"cost": 75.00, "regions": {"us-east-1": 75.00}},
        }
        resolved_services = {
            "AMAZON S3": "✅ RESOLVED - Storage optimized",
            "AMAZON EC2": "📝 NOTED - Under review",
            "AWS LAMBDA": "✅ RESOLVED - Function optimized",
        }

        result = categorize_services(service_costs, resolved_services)

        assert len(result) == 5
        # Order: unresolved (by cost desc), noted (by cost desc), resolved (by cost desc)
        assert result[0][0] == "Amazon RDS"  # Unresolved, highest cost
        assert result[1][0] == "Amazon DynamoDB"  # Unresolved, lower cost
        assert result[2][0] == "Amazon EC2"  # Noted
        assert result[3][0] == "Amazon S3"  # Resolved, higher cost
        assert result[4][0] == "AWS Lambda"  # Resolved, lower cost

    def test_categorize_services_case_insensitive_matching(self):
        """Test that service matching is case-insensitive."""
        service_costs = {
            "amazon s3": {"cost": 100.00, "regions": {"us-east-1": 100.00}},
            "Amazon EC2": {"cost": 200.00, "regions": {"us-west-2": 200.00}},
        }
        resolved_services = {
            "AMAZON S3": "✅ RESOLVED - Storage optimized",
            "amazon ec2": "📝 NOTED - Under review",
        }

        result = categorize_services(service_costs, resolved_services)

        # Both should be categorized correctly despite case differences
        assert len(result) == 2
        assert result[0][0] == "Amazon EC2"  # Noted
        assert result[1][0] == "amazon s3"  # Resolved


class TestCategorizeServicesEdgeCases:
    """Tests for edge cases in service categorization."""

    def test_categorize_services_empty_input(self):
        """Test categorization with empty service costs."""
        service_costs = {}
        resolved_services = {}

        result = categorize_services(service_costs, resolved_services)

        assert not result

    def test_categorize_services_preserves_data_structure(self):
        """Test that categorization preserves the service data structure."""
        service_costs = {
            "Amazon S3": {
                "cost": 100.00,
                "regions": {"us-east-1": 60.00, "us-west-2": 40.00},
            }
        }
        resolved_services = {}

        result = categorize_services(service_costs, resolved_services)

        assert len(result) == 1
        service_name, service_data = result[0]
        assert service_name == "Amazon S3"
        assert service_data["cost"] == 100.00
        assert service_data["regions"]["us-east-1"] == 60.00
        assert service_data["regions"]["us-west-2"] == 40.00
