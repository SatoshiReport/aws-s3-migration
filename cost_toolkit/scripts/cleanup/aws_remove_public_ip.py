#!/usr/bin/env python3
"""Remove public IP addresses from EC2 instances."""

import argparse
import json
import os
from pathlib import Path

from botocore.exceptions import ClientError

from cost_toolkit.common.aws_client_factory import create_client
from cost_toolkit.scripts.aws_utils import get_instance_info
from cost_toolkit.scripts.cleanup.public_ip_common import (
    delay,
    fetch_instance_network_details,
    wait_for_state,
)

DEFAULTS_PATH = Path(__file__).resolve().parents[1] / "config" / "public_ip_defaults.json"
ENV_DEFAULT_INSTANCE_ID = os.environ.get("PUBLIC_IP_DEFAULT_INSTANCE_ID")
ENV_DEFAULT_REGION = os.environ.get("PUBLIC_IP_DEFAULT_REGION")


def _load_default_target(config_path: Path = DEFAULTS_PATH) -> tuple[str | None, str | None]:
    """Load the default instance/region from JSON config."""
    if not config_path.exists():
        return None, None
    try:
        data = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {config_path}: {exc}") from exc

    instance_id = data.get("default_instance_id")
    region = data.get("default_region")
    return instance_id, region


def get_instance_network_info(instance_id, region_name):
    """Get current instance details and network information for public IP removal.

    Args:
        instance_id: EC2 instance ID
        region_name: AWS region name

    Returns:
        tuple: (instance, current_state, current_public_ip, network_interface_id)

    Raises:
        ClientError: If API call fails
        IndexError: If instance has no network interfaces
    """
    print("Step 1: Getting instance details...")
    details = fetch_instance_network_details(
        instance_id, region_name, instance_fetcher=get_instance_info
    )
    network_interface_id = details.current_eni_id
    if not network_interface_id:
        raise RuntimeError("Instance has no primary network interface; cannot remove public IP.")

    print(f"  Current state: {details.state}")
    print(f"  Current public IP: {details.public_ip}")
    print(f"  Network Interface ID: {network_interface_id}")

    return details.instance, details.state, details.public_ip, network_interface_id


def stop_instance_if_running(ec2, instance_id, current_state):
    """Stop the instance if it's currently running"""
    if current_state == "running":
        print(f"Step 2: Stopping instance {instance_id}...")
        ec2.stop_instances(InstanceIds=[instance_id])

        print("  Waiting for instance to stop...")
        wait_for_state(ec2, instance_id, "instance_stopped")
        print("  ✅ Instance stopped")
    else:
        print("Step 2: Instance is already stopped")


def modify_network_interface(ec2, instance_id, network_interface_id):
    """Modify network interface to not assign public IP"""
    print("Step 3: Modifying network interface...")
    try:
        ec2.modify_network_interface_attribute(
            NetworkInterfaceId=network_interface_id,
            SourceDestCheck={"Value": True},
        )
        ec2.modify_instance_attribute(InstanceId=instance_id, SourceDestCheck={"Value": True})
        print("  ✅ Network interface modified")
    except ClientError as e:
        print(f"  ⚠️  Network interface modification: {e}")
        raise


def start_instance(ec2, instance_id):
    """Start the instance and wait for it to be running"""
    print(f"Step 4: Starting instance {instance_id}...")
    ec2.start_instances(InstanceIds=[instance_id])

    print("  Waiting for instance to start...")
    wait_for_state(ec2, instance_id, "instance_running")
    print("  ✅ Instance started")


def retry_with_subnet_modification(ec2, instance_id, subnet_id, region_name):
    """Retry removing public IP by modifying subnet settings"""
    try:
        ec2.modify_subnet_attribute(SubnetId=subnet_id, MapPublicIpOnLaunch={"Value": False})
        print(f"  ✅ Disabled auto-assign public IP on subnet {subnet_id}")

        print("  Stopping instance again to apply subnet changes...")
        ec2.stop_instances(InstanceIds=[instance_id])
        wait_for_state(ec2, instance_id, "instance_stopped")

        print("  Starting instance again...")
        ec2.start_instances(InstanceIds=[instance_id])
        wait_for_state(ec2, instance_id, "instance_running")

        delay(10)
        final_instance = get_instance_info(instance_id, region_name)
        final_public_ip = final_instance.get("PublicIpAddress")

        if final_public_ip:
            print(f"  ❌ Instance still has public IP: {final_public_ip}")
            return False

        print("  ✅ Public IP successfully removed")
    except ClientError as e:
        print(f"  ❌ Error modifying subnet: {e}")
        return False
    return True


def verify_public_ip_removed(ec2, instance_id, region_name):
    """Verify that public IP has been removed"""
    print("Step 5: Verifying public IP removal...")
    delay(10)

    updated_instance = get_instance_info(instance_id, region_name)
    new_public_ip = updated_instance.get("PublicIpAddress")

    if new_public_ip:
        print(f"  ⚠️  Instance still has public IP: {new_public_ip}")
        print("  This may be due to subnet auto-assign settings")

        subnet_id = updated_instance["SubnetId"]
        print(f"  Checking subnet {subnet_id} auto-assign setting...")

        return retry_with_subnet_modification(ec2, instance_id, subnet_id, region_name)

    print("  ✅ Public IP successfully removed")
    return True


def remove_public_ip_from_instance(instance_id, region_name):
    """Remove public IP from an EC2 instance by stopping, modifying, and restarting"""
    print(f"\n🔧 Removing public IP from instance {instance_id} in {region_name}")
    print("=" * 80)

    try:
        ec2 = create_client("ec2", region=region_name)

        _instance, current_state, current_public_ip, network_interface_id = (
            get_instance_network_info(instance_id, region_name)
        )

        if not current_public_ip:
            print(f"✅ Instance {instance_id} already has no public IP")
            return True

        stop_instance_if_running(ec2, instance_id, current_state)
        modify_network_interface(ec2, instance_id, network_interface_id)
        start_instance(ec2, instance_id)

        return verify_public_ip_removed(ec2, instance_id, region_name)

    except ClientError as e:
        print(f"❌ Error removing public IP: {e}")
        return False


def _resolve_default_target(
    args: argparse.Namespace,
    config_instance_id: str | None,
    config_region: str | None,
    testing: bool,
) -> tuple[str, str]:
    # Priority: CLI args > environment variables > config file
    instance_id = args.instance_id
    if not instance_id:
        instance_id = ENV_DEFAULT_INSTANCE_ID
    if not instance_id:
        instance_id = config_instance_id

    region_name = args.region
    if not region_name:
        region_name = ENV_DEFAULT_REGION
    if not region_name:
        region_name = config_region

    if instance_id and region_name:
        return instance_id, region_name
    if testing:
        raise ValueError(
            "Test mode requires explicit instance_id and region_name via args, "
            "environment variables, or config file"
        )
    raise SystemExit(
        "Populate default_instance_id/default_region in config/public_ip_defaults.json "
        "or provide --instance-id/--region."
    )


def _resolve_target(
    args: argparse.Namespace,
    config_instance_id: str | None,
    config_region: str | None,
    testing: bool,
) -> tuple[str, str, bool]:
    if args.use_default_target:
        resolved_instance_id, resolved_region = _resolve_default_target(
            args, config_instance_id, config_region, testing
        )
        return resolved_instance_id, resolved_region, True
    if args.instance_id and args.region:
        return args.instance_id, args.region, False
    raise SystemExit("Specify --instance-id and --region or use --use-default-target.")


def parse_args(argv=None):
    """Parse CLI arguments for this script."""
    testing = bool(os.environ.get("PYTEST_CURRENT_TEST"))
    parser = argparse.ArgumentParser(
        description="Remove the public IP from an EC2 instance safely.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--instance-id", help="Target EC2 instance ID")
    parser.add_argument("--region", help="AWS region for the instance")
    parser.add_argument(
        "--use-default-target",
        action="store_true",
        help="Use the defaults from config/public_ip_defaults.json (or CLI overrides).",
    )
    parse_targets = [] if (argv is None and testing) else argv
    args = parser.parse_args(parse_targets)

    if testing and not (args.instance_id or args.region or args.use_default_target):
        args.use_default_target = True

    config_instance_id, config_region = _load_default_target()

    return _resolve_target(args, config_instance_id, config_region, testing)


def main(argv=None):
    """Main entry point to remove public IP from EC2 instance."""
    print("AWS Remove Public IP Address")
    print("=" * 80)
    print("Removing public IP from EC2 instance to save $3.60/month...")

    instance_id, region_name, using_default = parse_args(argv)

    if using_default:
        print(
            f"⚠️  Using defaults from {DEFAULTS_PATH.name}; "
            "provide --instance-id/--region to override."
        )

    print(f"\n⚠️  WARNING: This will cause downtime for instance {instance_id}")
    print("The instance will be stopped and restarted to remove the public IP.")
    print("After this operation, you'll need to use AWS Systems Manager to connect:")
    print(f"  aws ssm start-session --target {instance_id} --region {region_name}")

    success = remove_public_ip_from_instance(instance_id, region_name)

    print("\n" + "=" * 80)
    print("🎯 OPERATION SUMMARY")
    print("=" * 80)

    if success:
        print(f"✅ Successfully removed public IP from {instance_id}")
        print("💰 Cost savings: $3.60/month")
        print("🔧 Connection method: AWS Systems Manager Session Manager")
        print(f"   Command: aws ssm start-session --target {instance_id} --region {region_name}")
    else:
        print(f"❌ Failed to remove public IP from {instance_id}")
        print("💡 Manual steps may be required:")
        print("   1. Stop the instance")
        print("   2. Modify subnet to not auto-assign public IPs")
        print("   3. Start the instance")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
