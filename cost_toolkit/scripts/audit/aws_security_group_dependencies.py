#!/usr/bin/env python3
"""
AWS Security Group Dependencies Audit Script
Investigates why security groups cannot be deleted by finding their dependencies:
- Network interfaces using the security groups
- Other security groups referencing them
- Load balancers or other services using them
- RDS instances or other database services

This helps understand what's preventing cleanup and provides targeted solutions.
"""

import os
import sys

import boto3
from dotenv import load_dotenv


def load_aws_credentials():
    """Load AWS credentials from .env file"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file")  # noqa: TRY003

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def check_security_group_dependencies(ec2_client, group_id, region):  # noqa: C901, PLR0912
    """Check what's preventing a security group from being deleted"""
    dependencies = {
        "network_interfaces": [],
        "instances": [],
        "load_balancers": [],
        "rds_instances": [],
        "security_group_rules": [],
        "other_dependencies": [],
    }

    try:
        # Check network interfaces
        eni_response = ec2_client.describe_network_interfaces(
            Filters=[{"Name": "group-id", "Values": [group_id]}]
        )
        for eni in eni_response.get("NetworkInterfaces", []):
            dependencies["network_interfaces"].append(
                {
                    "interface_id": eni["NetworkInterfaceId"],
                    "status": eni["Status"],
                    "description": eni.get("Description", "N/A"),
                    "attachment": eni.get("Attachment", {}),
                    "vpc_id": eni["VpcId"],
                    "subnet_id": eni["SubnetId"],
                }
            )

        # Check instances using this security group
        instances_response = ec2_client.describe_instances(
            Filters=[{"Name": "instance.group-id", "Values": [group_id]}]
        )
        for reservation in instances_response["Reservations"]:
            for instance in reservation["Instances"]:
                dependencies["instances"].append(
                    {
                        "instance_id": instance["InstanceId"],
                        "state": instance["State"]["Name"],
                        "instance_type": instance["InstanceType"],
                        "vpc_id": instance.get("VpcId"),
                        "name": next(
                            (
                                tag["Value"]
                                for tag in instance.get("Tags", [])
                                if tag["Key"] == "Name"
                            ),
                            "Unnamed",
                        ),
                    }
                )

        # Check if other security groups reference this one
        all_sgs_response = ec2_client.describe_security_groups()
        for sg in all_sgs_response.get("SecurityGroups", []):
            if sg["GroupId"] != group_id:
                # Check inbound rules
                for rule in sg.get("IpPermissions", []):
                    for group_pair in rule.get("UserIdGroupPairs", []):
                        if group_pair.get("GroupId") == group_id:
                            dependencies["security_group_rules"].append(
                                {
                                    "referencing_sg": sg["GroupId"],
                                    "referencing_sg_name": sg["GroupName"],
                                    "rule_type": "inbound",
                                    "protocol": rule.get("IpProtocol"),
                                    "port_range": f"{rule.get('FromPort', 'N/A')}-{rule.get('ToPort', 'N/A')}",
                                }
                            )

                # Check outbound rules
                for rule in sg.get("IpPermissionsEgress", []):
                    for group_pair in rule.get("UserIdGroupPairs", []):
                        if group_pair.get("GroupId") == group_id:
                            dependencies["security_group_rules"].append(
                                {
                                    "referencing_sg": sg["GroupId"],
                                    "referencing_sg_name": sg["GroupName"],
                                    "rule_type": "outbound",
                                    "protocol": rule.get("IpProtocol"),
                                    "port_range": f"{rule.get('FromPort', 'N/A')}-{rule.get('ToPort', 'N/A')}",
                                }
                            )

        # Check RDS instances (requires RDS client)
        try:
            rds_client = boto3.client(
                "rds",
                region_name=region,
                aws_access_key_id=ec2_client._client_config.__dict__["_user_provided_options"][
                    "aws_access_key_id"
                ],
                aws_secret_access_key=ec2_client._client_config.__dict__["_user_provided_options"][
                    "aws_secret_access_key"
                ],
            )

            rds_response = rds_client.describe_db_instances()
            for db in rds_response.get("DBInstances", []):
                for sg in db.get("VpcSecurityGroups", []):
                    if sg["VpcSecurityGroupId"] == group_id:
                        dependencies["rds_instances"].append(
                            {
                                "db_instance_id": db["DBInstanceIdentifier"],
                                "db_instance_status": db["DBInstanceStatus"],
                                "engine": db["Engine"],
                                "vpc_id": db.get("DbSubnetGroup", {}).get("VpcId"),
                            }
                        )
        except Exception as e:
            print(f"   ⚠️  Could not check RDS dependencies: {e}")

    except Exception as e:
        print(f"   ❌ Error checking dependencies for {group_id}: {e}")
        return dependencies

    else:
        return dependencies


def audit_security_group_dependencies():  # noqa: C901, PLR0912
    """Audit dependencies for security groups that couldn't be deleted"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    # Security groups that failed to delete
    failed_security_groups = [
        {
            "group_id": "sg-0423403672ae41d94",
            "name": "security-group-for-outbound-nfs-d-jbqwgqwiy4df",
            "region": "us-east-1",
        },
        {"group_id": "sg-0bf8a0d06a121f4a0", "name": "rds-ec2-1", "region": "us-east-1"},
        {
            "group_id": "sg-049977ce080d9ab0f",
            "name": "security-group-for-inbound-nfs-d-ujcvqjdoyu70",
            "region": "us-east-1",
        },
        {"group_id": "sg-044777fbbcdee8f28", "name": "ec2-rds-1", "region": "us-east-1"},
        {
            "group_id": "sg-0dfa7bedc21d91798",
            "name": "security-group-for-inbound-nfs-d-jbqwgqwiy4df",
            "region": "us-east-1",
        },
        {
            "group_id": "sg-05ec40d14e0fb6fed",
            "name": "security-group-for-outbound-nfs-d-ujcvqjdoyu70",
            "region": "us-east-1",
        },
        {
            "group_id": "sg-09e291dc61da97af1",
            "name": "security-group-for-outbound-nfs-d-ki8zr9k0yt95",
            "region": "us-east-2",
        },
        {
            "group_id": "sg-0dba11de0f5b92f40",
            "name": "security-group-for-inbound-nfs-d-ki8zr9k0yt95",
            "region": "us-east-2",
        },
    ]

    print("AWS Security Group Dependencies Audit")
    print("=" * 60)
    print("Investigating why security groups cannot be deleted...")
    print()

    for sg_info in failed_security_groups:
        group_id = sg_info["group_id"]
        group_name = sg_info["name"]
        region = sg_info["region"]

        print(f"🔍 Analyzing {group_id} ({group_name}) in {region}")
        print("-" * 50)

        # Create EC2 client for the specific region
        ec2_client = boto3.client(
            "ec2",
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        dependencies = check_security_group_dependencies(ec2_client, group_id, region)

        # Report findings
        has_dependencies = False

        if dependencies["network_interfaces"]:
            has_dependencies = True
            print(f"🔗 Network Interfaces ({len(dependencies['network_interfaces'])}):")
            for eni in dependencies["network_interfaces"]:
                attachment_info = "Unattached"
                if eni["attachment"]:
                    attachment_info = (
                        f"Attached to {eni['attachment'].get('InstanceId', 'Unknown')}"
                    )
                print(f"   • {eni['interface_id']} - {eni['status']} - {attachment_info}")
                print(f"     Description: {eni['description']}")

        if dependencies["instances"]:
            has_dependencies = True
            print(f"🖥️  Instances ({len(dependencies['instances'])}):")
            for instance in dependencies["instances"]:
                print(f"   • {instance['instance_id']} ({instance['name']}) - {instance['state']}")

        if dependencies["rds_instances"]:
            has_dependencies = True
            print(f"🗄️  RDS Instances ({len(dependencies['rds_instances'])}):")
            for rds in dependencies["rds_instances"]:
                print(
                    f"   • {rds['db_instance_id']} - {rds['engine']} - {rds['db_instance_status']}"
                )

        if dependencies["security_group_rules"]:
            has_dependencies = True
            print(
                f"🔒 Referenced by Security Group Rules ({len(dependencies['security_group_rules'])}):"
            )
            for rule in dependencies["security_group_rules"]:
                print(
                    f"   • {rule['referencing_sg']} ({rule['referencing_sg_name']}) - {rule['rule_type']} rule"
                )
                print(f"     Protocol: {rule['protocol']}, Ports: {rule['port_range']}")

        if not has_dependencies:
            print("❓ No obvious dependencies found - may be a transient issue")

        print()

    print("=" * 60)
    print("💡 CLEANUP RECOMMENDATIONS")
    print("=" * 60)
    print("1. Remove security group references from other security groups")
    print("2. Detach or delete unused network interfaces")
    print("3. Remove security groups from RDS instances if no longer needed")
    print("4. Terminate or modify instances using these security groups")
    print()
    print("🔧 After resolving dependencies, retry security group deletion")


if __name__ == "__main__":
    try:
        audit_security_group_dependencies()
    except Exception as e:
        print(f"❌ Script failed: {e}")
        sys.exit(1)
