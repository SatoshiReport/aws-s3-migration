"""
Consolidated AWS waiter utilities.

This module provides standardized waiter functions to eliminate duplicate
waiter patterns across scripts. Each function wraps AWS waiters with
sensible default configurations for delays and max attempts.
"""


def wait_instance_stopped(ec2_client, instance_id, delay=15, max_attempts=40):
    """
    Wait for an EC2 instance to reach stopped state.

    Args:
        ec2_client: Boto3 EC2 client
        instance_id: EC2 instance ID to wait for
        delay: Delay between polling attempts in seconds (default: 15)
        max_attempts: Maximum number of attempts (default: 40, ~10 min)

    Raises:
        WaiterError: If waiter times out or encounters an error
    """
    waiter = ec2_client.get_waiter("instance_stopped")
    waiter.wait(
        InstanceIds=[instance_id], WaiterConfig={"Delay": delay, "MaxAttempts": max_attempts}
    )


def wait_instance_running(ec2_client, instance_id, delay=15, max_attempts=40):
    """
    Wait for an EC2 instance to reach running state.

    Args:
        ec2_client: Boto3 EC2 client
        instance_id: EC2 instance ID to wait for
        delay: Delay between polling attempts in seconds (default: 15)
        max_attempts: Maximum number of attempts (default: 40, ~10 min)

    Raises:
        WaiterError: If waiter times out or encounters an error
    """
    waiter = ec2_client.get_waiter("instance_running")
    waiter.wait(
        InstanceIds=[instance_id], WaiterConfig={"Delay": delay, "MaxAttempts": max_attempts}
    )


def wait_instance_terminated(ec2_client, instance_id, delay=15, max_attempts=40):
    """
    Wait for an EC2 instance to reach terminated state.

    Args:
        ec2_client: Boto3 EC2 client
        instance_id: EC2 instance ID to wait for
        delay: Delay between polling attempts in seconds (default: 15)
        max_attempts: Maximum number of attempts (default: 40, ~10 min)

    Raises:
        WaiterError: If waiter times out or encounters an error
    """
    waiter = ec2_client.get_waiter("instance_terminated")
    waiter.wait(
        InstanceIds=[instance_id], WaiterConfig={"Delay": delay, "MaxAttempts": max_attempts}
    )


def wait_volume_available(ec2_client, volume_id, delay=15, max_attempts=40):
    """
    Wait for an EBS volume to reach available state.

    Args:
        ec2_client: Boto3 EC2 client
        volume_id: EBS volume ID to wait for
        delay: Delay between polling attempts in seconds (default: 15)
        max_attempts: Maximum number of attempts (default: 40, ~10 min)

    Raises:
        WaiterError: If waiter times out or encounters an error
    """
    waiter = ec2_client.get_waiter("volume_available")
    waiter.wait(VolumeIds=[volume_id], WaiterConfig={"Delay": delay, "MaxAttempts": max_attempts})


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


def wait_rds_instance_available(rds_client, db_instance_id, delay=30, max_attempts=60):
    """
    Wait for an RDS instance to reach available state.

    Args:
        rds_client: Boto3 RDS client
        db_instance_id: RDS instance identifier to wait for
        delay: Delay between polling attempts in seconds (default: 30)
        max_attempts: Maximum number of attempts (default: 60, ~30 min)

    Raises:
        WaiterError: If waiter times out or encounters an error
    """
    waiter = rds_client.get_waiter("db_instance_available")
    waiter.wait(
        DBInstanceIdentifier=db_instance_id,
        WaiterConfig={"Delay": delay, "MaxAttempts": max_attempts},
    )


def wait_rds_instance_deleted(rds_client, db_instance_id, delay=30, max_attempts=60):
    """
    Wait for an RDS instance to be deleted.

    Args:
        rds_client: Boto3 RDS client
        db_instance_id: RDS instance identifier to wait for
        delay: Delay between polling attempts in seconds (default: 30)
        max_attempts: Maximum number of attempts (default: 60, ~30 min)

    Raises:
        WaiterError: If waiter times out or encounters an error
    """
    waiter = rds_client.get_waiter("db_instance_deleted")
    waiter.wait(
        DBInstanceIdentifier=db_instance_id,
        WaiterConfig={"Delay": delay, "MaxAttempts": max_attempts},
    )


def wait_rds_snapshot_completed(rds_client, snapshot_id, delay=30, max_attempts=60):
    """
    Wait for an RDS snapshot to complete.

    Args:
        rds_client: Boto3 RDS client
        snapshot_id: RDS snapshot identifier to wait for
        delay: Delay between polling attempts in seconds (default: 30)
        max_attempts: Maximum number of attempts (default: 60, ~30 min)

    Raises:
        WaiterError: If waiter times out or encounters an error
    """
    waiter = rds_client.get_waiter("db_snapshot_completed")
    waiter.wait(
        DBSnapshotIdentifier=snapshot_id, WaiterConfig={"Delay": delay, "MaxAttempts": max_attempts}
    )


def wait_rds_cluster_available(rds_client, cluster_id, delay=30, max_attempts=60):
    """
    Wait for an RDS cluster to reach available state.

    Args:
        rds_client: Boto3 RDS client
        cluster_id: RDS cluster identifier to wait for
        delay: Delay between polling attempts in seconds (default: 30)
        max_attempts: Maximum number of attempts (default: 60, ~30 min)

    Raises:
        WaiterError: If waiter times out or encounters an error
    """
    waiter = rds_client.get_waiter("db_cluster_available")
    waiter.wait(
        DBClusterIdentifier=cluster_id, WaiterConfig={"Delay": delay, "MaxAttempts": max_attempts}
    )


def wait_route53_changes(route53_client, change_id, delay=30, max_attempts=60):
    """
    Wait for Route53 resource record set changes to propagate.

    Args:
        route53_client: Boto3 Route53 client
        change_id: Change ID from change_resource_record_sets
        delay: Delay between polling attempts in seconds (default: 30)
        max_attempts: Maximum number of attempts (default: 60, ~30 min)

    Raises:
        WaiterError: If waiter times out or encounters an error
    """
    waiter = route53_client.get_waiter("resource_record_sets_changed")
    waiter.wait(Id=change_id, WaiterConfig={"Delay": delay, "MaxAttempts": max_attempts})
