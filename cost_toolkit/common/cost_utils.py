"""
AWS Cost Calculation Utilities

Centralized cost calculation functions to eliminate duplication
across audit and optimization scripts.
"""

# Constants for EBS pricing
GP3_DEFAULT_THROUGHPUT_MBS = 125  # Default throughput for gp3 volumes


def calculate_ebs_volume_cost(
    size_gb: int, volume_type: str, iops: int = 0, throughput: int = 0
) -> float:
    """
    Calculate monthly cost for an EBS volume based on type, size, IOPS, and throughput.

    Args:
        size_gb: Volume size in gigabytes
        volume_type: EBS volume type (gp3, gp2, io1, io2, st1, sc1, standard)
        iops: Provisioned IOPS (optional, used for io1/io2 volumes)
        throughput: Provisioned throughput in MB/s (optional, used for gp3 volumes)

    Returns:
        float: Estimated monthly cost in USD

    Note:
        Pricing as of 2024 for us-east-1. May vary by region.
        For accurate pricing, consult AWS Pricing Calculator.

        IOPS pricing:
        - io1/io2: Free for first 3 IOPS per GB, then $0.065 per IOPS/month

        Throughput pricing:
        - gp3: Free for first 125 MB/s, then $0.04 per MB/s/month
    """
    # Pricing per GB-month (us-east-1)
    cost_per_gb = {
        "gp3": 0.08,  # General Purpose SSD (gp3)
        "gp2": 0.10,  # General Purpose SSD (gp2)
        "io1": 0.125,  # Provisioned IOPS SSD (io1)
        "io2": 0.125,  # Provisioned IOPS SSD (io2)
        "st1": 0.045,  # Throughput Optimized HDD
        "sc1": 0.025,  # Cold HDD
        "standard": 0.05,  # Magnetic (legacy)
    }

    # Calculate base storage cost
    if volume_type not in cost_per_gb:
        raise ValueError(
            f"Unknown volume type: {volume_type}. "
            f"Supported types: {', '.join(sorted(cost_per_gb.keys()))}"
        )
    rate = cost_per_gb[volume_type]
    base_cost = size_gb * rate

    # Add IOPS costs for io1/io2 volumes
    # io1/io2 include 3 IOPS per GB for free, additional IOPS charged at $0.065/month
    if volume_type in ["io1", "io2"] and iops > size_gb * 3:
        extra_iops = iops - (size_gb * 3)
        iops_cost = extra_iops * 0.065
        base_cost += iops_cost

    # Add throughput costs for gp3 volumes
    # gp3 includes 125 MB/s for free, additional throughput charged at $0.04/MB/s/month
    if volume_type == "gp3" and throughput > GP3_DEFAULT_THROUGHPUT_MBS:
        extra_throughput = throughput - GP3_DEFAULT_THROUGHPUT_MBS
        throughput_cost = extra_throughput * 0.04
        base_cost += throughput_cost

    return base_cost


def calculate_snapshot_cost(size_gb: int) -> float:
    """
    Calculate monthly cost for an EBS snapshot.

    Args:
        size_gb: Snapshot size in gigabytes

    Returns:
        float: Estimated monthly cost in USD
    """
    # EBS snapshot pricing: $0.05 per GB-month
    return size_gb * 0.05


def calculate_elastic_ip_cost(is_attached: bool = False) -> float:
    """
    Calculate monthly cost for an Elastic IP address.

    Args:
        is_attached: Whether the EIP is attached to a running instance

    Returns:
        float: Estimated monthly cost in USD
    """
    # Unattached EIPs: ~$3.60/month ($0.005/hour)
    # Attached EIPs to running instances: free
    if is_attached:
        return 0.0
    return 0.005 * 24 * 30  # $0.005/hour * 24 hours * 30 days
