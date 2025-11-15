"""Comprehensive tests for aws_network_interface_audit.py - Part 3: Print Functions."""

from __future__ import annotations

from cost_toolkit.scripts.audit.aws_network_interface_audit import (
    _print_attached_interfaces,
    _print_unused_interfaces,
)


class TestPrintUnusedInterfacesSingle:
    """Tests for _print_unused_interfaces function with single region cases."""

    def _assert_unused_output_contains_headers(self, captured_output):
        """Helper to assert presence of standard headers in unused interfaces output."""
        assert "UNUSED NETWORK INTERFACES FOUND" in captured_output
        assert "CLEANUP RECOMMENDATIONS:" in captured_output

    def _assert_unused_interface_details(self, captured_output, interface_data):
        """Helper to assert interface details are present in output."""
        assert f"Interface: {interface_data['interface_id']}" in captured_output
        assert f"Name: {interface_data['name']}" in captured_output
        assert f"Type: {interface_data['type']}" in captured_output
        assert f"VPC: {interface_data['vpc_id']}" in captured_output

    def _assert_unused_interface_network_details(self, captured_output, interface_data):
        """Helper to assert network-related details in output."""
        assert f"Subnet: {interface_data['subnet_id']}" in captured_output
        assert f"Private IP: {interface_data['private_ip']}" in captured_output
        assert f"Description: {interface_data['description']}" in captured_output
        assert f"Status: {interface_data['status']}" in captured_output

    def test_print_no_unused_interfaces(self, capsys):
        """Test printing when no unused interfaces exist."""
        regions_with_interfaces = [
            {
                "region": "us-east-1",
                "unused_interfaces": [],
            }
        ]

        _print_unused_interfaces(regions_with_interfaces)

        captured = capsys.readouterr()
        # Headers are always printed, but no region-specific data should appear
        self._assert_unused_output_contains_headers(captured.out)
        assert "Region: us-east-1" not in captured.out

    def test_print_unused_interfaces_single_region(self, capsys):
        """Test printing unused interfaces for single region."""
        interface_data = {
            "interface_id": "eni-unused1",
            "name": "old-interface",
            "type": "interface",
            "vpc_id": "vpc-123",
            "subnet_id": "subnet-456",
            "private_ip": "10.0.1.5",
            "description": "Leftover from migration",
            "status": "available",
        }
        regions_with_interfaces = [
            {
                "region": "us-east-1",
                "unused_interfaces": [interface_data],
            }
        ]

        _print_unused_interfaces(regions_with_interfaces)

        captured = capsys.readouterr()
        self._assert_unused_output_contains_headers(captured.out)
        assert "Region: us-east-1" in captured.out
        self._assert_unused_interface_details(captured.out, interface_data)
        self._assert_unused_interface_network_details(captured.out, interface_data)

    def test_print_unused_interfaces_recommendations(self, capsys):
        """Test that cleanup recommendations are printed."""
        regions_with_interfaces = [
            {
                "region": "us-east-1",
                "unused_interfaces": [
                    {
                        "interface_id": "eni-test",
                        "name": "test",
                        "type": "interface",
                        "vpc_id": "vpc-123",
                        "subnet_id": "subnet-123",
                        "private_ip": "10.0.0.1",
                        "description": "test",
                        "status": "available",
                    }
                ],
            }
        ]

        _print_unused_interfaces(regions_with_interfaces)

        captured = capsys.readouterr()
        assert "CLEANUP RECOMMENDATIONS:" in captured.out
        assert "Unused network interfaces can be safely deleted" in captured.out
        assert "No cost impact but improves account hygiene" in captured.out


class TestPrintUnusedInterfacesMultiple:
    """Tests for _print_unused_interfaces function with multiple regions."""

    def test_print_unused_interfaces_multiple_regions(self, capsys):
        """Test printing unused interfaces for multiple regions."""
        regions_with_interfaces = [
            {
                "region": "us-east-1",
                "unused_interfaces": [
                    {
                        "interface_id": "eni-unused1",
                        "name": "test-eni-1",
                        "type": "interface",
                        "vpc_id": "vpc-123",
                        "subnet_id": "subnet-456",
                        "private_ip": "10.0.1.1",
                        "description": "Test interface",
                        "status": "available",
                    }
                ],
            },
            {
                "region": "eu-west-1",
                "unused_interfaces": [
                    {
                        "interface_id": "eni-unused2",
                        "name": "test-eni-2",
                        "type": "interface",
                        "vpc_id": "vpc-789",
                        "subnet_id": "subnet-012",
                        "private_ip": "10.1.1.1",
                        "description": "Another test",
                        "status": "available",
                    }
                ],
            },
        ]

        _print_unused_interfaces(regions_with_interfaces)

        captured = capsys.readouterr()
        assert "Region: us-east-1" in captured.out
        assert "eni-unused1" in captured.out
        assert "Region: eu-west-1" in captured.out
        assert "eni-unused2" in captured.out

    def test_print_unused_interfaces_multiple_per_region(self, capsys):
        """Test printing multiple unused interfaces in same region."""
        regions_with_interfaces = [
            {
                "region": "us-west-2",
                "unused_interfaces": [
                    {
                        "interface_id": "eni-1",
                        "name": "interface-1",
                        "type": "interface",
                        "vpc_id": "vpc-111",
                        "subnet_id": "subnet-111",
                        "private_ip": "10.0.0.1",
                        "description": "First",
                        "status": "available",
                    },
                    {
                        "interface_id": "eni-2",
                        "name": "interface-2",
                        "type": "interface",
                        "vpc_id": "vpc-222",
                        "subnet_id": "subnet-222",
                        "private_ip": "10.0.0.2",
                        "description": "Second",
                        "status": "available",
                    },
                ],
            }
        ]

        _print_unused_interfaces(regions_with_interfaces)

        captured = capsys.readouterr()
        assert "eni-1" in captured.out
        assert "eni-2" in captured.out
        assert "interface-1" in captured.out
        assert "interface-2" in captured.out


class TestPrintAttachedInterfacesSingle:
    """Tests for _print_attached_interfaces function with single region cases."""

    def _assert_attached_interface_basic_info(self, captured_output, interface_data):
        """Helper to assert basic attached interface information in output."""
        assert "ATTACHED NETWORK INTERFACES DETAILS" in captured_output
        assert f"Interface: {interface_data['interface_id']}" in captured_output
        assert f"Name: {interface_data['name']}" in captured_output
        assert f"Type: {interface_data['type']}" in captured_output

    def _assert_attached_interface_connection_info(self, captured_output, interface_data):
        """Helper to assert connection-related information in output."""
        assert f"Attached to: {interface_data['attached_to']}" in captured_output
        assert f"Status: {interface_data['status']}" in captured_output
        assert f"VPC: {interface_data['vpc_id']}" in captured_output

    def _assert_attached_interface_ip_info(self, captured_output, interface_data):
        """Helper to assert IP address information in output."""
        assert f"Private IP: {interface_data['private_ip']}" in captured_output
        assert f"Public IP: {interface_data['public_ip']}" in captured_output

    def test_print_no_attached_interfaces(self, capsys):
        """Test printing when no attached interfaces exist."""
        regions_with_interfaces = [
            {
                "region": "us-east-1",
                "attached_interfaces": [],
            }
        ]

        _print_attached_interfaces(regions_with_interfaces)

        captured = capsys.readouterr()
        # Headers are always printed, but no region-specific data should appear
        assert "ATTACHED NETWORK INTERFACES DETAILS" in captured.out
        assert "Region: us-east-1" not in captured.out

    def test_print_attached_interfaces_single_region(self, capsys):
        """Test printing attached interfaces for single region."""
        interface_data = {
            "interface_id": "eni-attached1",
            "name": "web-server-eni",
            "type": "interface",
            "attached_to": "i-1234567890",
            "status": "in-use",
            "vpc_id": "vpc-123",
            "private_ip": "10.0.1.5",
            "public_ip": "54.123.45.67",
        }
        regions_with_interfaces = [
            {
                "region": "us-east-1",
                "attached_interfaces": [interface_data],
            }
        ]

        _print_attached_interfaces(regions_with_interfaces)

        captured = capsys.readouterr()
        assert "Region: us-east-1" in captured.out
        self._assert_attached_interface_basic_info(captured.out, interface_data)
        self._assert_attached_interface_connection_info(captured.out, interface_data)
        self._assert_attached_interface_ip_info(captured.out, interface_data)

    def test_print_attached_interfaces_no_public_ip(self, capsys):
        """Test printing attached interface without public IP."""
        regions_with_interfaces = [
            {
                "region": "us-west-2",
                "attached_interfaces": [
                    {
                        "interface_id": "eni-private",
                        "name": "private-eni",
                        "type": "interface",
                        "attached_to": "i-private",
                        "status": "in-use",
                        "vpc_id": "vpc-123",
                        "private_ip": "10.0.1.10",
                        "public_ip": "None",
                    }
                ],
            }
        ]

        _print_attached_interfaces(regions_with_interfaces)

        captured = capsys.readouterr()
        assert "Public IP: None" in captured.out


class TestPrintAttachedInterfacesMultiple:
    """Tests for _print_attached_interfaces function with multiple regions."""

    def test_print_attached_interfaces_multiple_regions(self, capsys):
        """Test printing attached interfaces for multiple regions."""
        regions_with_interfaces = [
            {
                "region": "us-east-1",
                "attached_interfaces": [
                    {
                        "interface_id": "eni-east",
                        "name": "east-interface",
                        "type": "interface",
                        "attached_to": "i-east",
                        "status": "in-use",
                        "vpc_id": "vpc-east",
                        "private_ip": "10.0.1.1",
                        "public_ip": "1.2.3.4",
                    }
                ],
            },
            {
                "region": "eu-west-1",
                "attached_interfaces": [
                    {
                        "interface_id": "eni-eu",
                        "name": "eu-interface",
                        "type": "interface",
                        "attached_to": "i-eu",
                        "status": "in-use",
                        "vpc_id": "vpc-eu",
                        "private_ip": "10.1.1.1",
                        "public_ip": "None",
                    }
                ],
            },
        ]

        _print_attached_interfaces(regions_with_interfaces)

        captured = capsys.readouterr()
        assert "Region: us-east-1" in captured.out
        assert "eni-east" in captured.out
        assert "Region: eu-west-1" in captured.out
        assert "eni-eu" in captured.out

    def test_print_attached_interfaces_multiple_per_region(self, capsys):
        """Test printing multiple attached interfaces in same region."""
        regions_with_interfaces = [
            {
                "region": "ap-south-1",
                "attached_interfaces": [
                    {
                        "interface_id": "eni-1",
                        "name": "interface-1",
                        "type": "interface",
                        "attached_to": "i-1",
                        "status": "in-use",
                        "vpc_id": "vpc-1",
                        "private_ip": "10.0.0.1",
                        "public_ip": "1.1.1.1",
                    },
                    {
                        "interface_id": "eni-2",
                        "name": "interface-2",
                        "type": "lambda",
                        "attached_to": "Not attached",
                        "status": "in-use",
                        "vpc_id": "vpc-2",
                        "private_ip": "10.0.0.2",
                        "public_ip": "None",
                    },
                ],
            }
        ]

        _print_attached_interfaces(regions_with_interfaces)

        captured = capsys.readouterr()
        assert "eni-1" in captured.out
        assert "eni-2" in captured.out
        assert "interface-1" in captured.out
        assert "interface-2" in captured.out
        assert "Type: lambda" in captured.out
