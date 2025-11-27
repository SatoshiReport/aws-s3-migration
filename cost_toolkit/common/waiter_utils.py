"""
Consolidated AWS waiter utilities.

This module provides standardized waiter functions to eliminate duplicate
waiter patterns across scripts. Each function wraps AWS waiters with
sensible default configurations for delays and max attempts.
"""


def wait_ami_available(ec2_client, ami_id, delay=15, max_attempts=40):
    """
    Wait for an AMI to reach available state.

    Args:
        ec2_client: Boto3 EC2 client
        ami_id: AMI ID to wait for
        delay: Delay between polling attempts in seconds (default: 15)
        max_attempts: Maximum number of attempts (default: 40, ~10 min)

    Raises:
        WaiterError: If waiter times out or encounters an error
    """
    waiter = ec2_client.get_waiter("image_available")
    waiter.wait(ImageIds=[ami_id], WaiterConfig={"Delay": delay, "MaxAttempts": max_attempts})
