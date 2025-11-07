#!/usr/bin/env python3
"""
AWS VM Import Service Role Setup Script
Creates the required 'vmimport' IAM service role needed for AMI export operations.
This role is required by AWS to export AMIs to S3.
"""

import json
import os

import boto3
from dotenv import load_dotenv


def load_aws_credentials():
    """Load AWS credentials from .env file"""
    load_dotenv(os.path.expanduser("~/.env"))

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key_id or not aws_secret_access_key:
        raise ValueError("AWS credentials not found in ~/.env file")

    print("✅ AWS credentials loaded from ~/.env")
    return aws_access_key_id, aws_secret_access_key


def create_vmimport_role():
    """Create the vmimport service role required for AMI exports"""
    aws_access_key_id, aws_secret_access_key = load_aws_credentials()

    # Create IAM client
    iam_client = boto3.client(
        "iam", aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key
    )

    print("AWS VM Import Service Role Setup")
    print("=" * 50)
    print("Setting up the required 'vmimport' IAM service role for AMI exports...")
    print()

    # Trust policy for the vmimport role
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "vmie.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {"StringEquals": {"sts:Externalid": "vmimport"}},
            }
        ],
    }

    # Policy for vmimport role permissions
    vmimport_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetBucketLocation",
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:PutObject",
                    "s3:GetBucketAcl",
                ],
                "Resource": ["arn:aws:s3:::*"],
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ec2:ModifySnapshotAttribute",
                    "ec2:CopySnapshot",
                    "ec2:RegisterImage",
                    "ec2:Describe*",
                ],
                "Resource": "*",
            },
        ],
    }

    try:
        # Check if role already exists
        try:
            role = iam_client.get_role(RoleName="vmimport")
            print("✅ vmimport role already exists")
            print(f"   Role ARN: {role['Role']['Arn']}")
            print(f"   Created: {role['Role']['CreateDate']}")
            return True
        except iam_client.exceptions.NoSuchEntityException:
            print("🔄 Creating vmimport service role...")

            # Create the role
            role_response = iam_client.create_role(
                RoleName="vmimport",
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description="Service role for VM Import/Export operations",
            )

            print(f"✅ Created vmimport role: {role_response['Role']['Arn']}")

            # Create and attach the policy
            print("🔄 Creating vmimport policy...")

            policy_response = iam_client.create_policy(
                PolicyName="vmimport-policy",
                PolicyDocument=json.dumps(vmimport_policy),
                Description="Policy for VM Import/Export operations",
            )

            print(f"✅ Created vmimport policy: {policy_response['Policy']['Arn']}")

            # Attach policy to role
            print("🔄 Attaching policy to role...")

            iam_client.attach_role_policy(
                RoleName="vmimport", PolicyArn=policy_response["Policy"]["Arn"]
            )

            print("✅ Successfully attached policy to vmimport role")
            print()
            print("🎉 VM Import service role setup completed!")
            print("   You can now run the S3 export script successfully.")

            return True

    except Exception as e:
        print(f"❌ Error setting up vmimport role: {e}")
        print()
        print("💡 Alternative setup using AWS CLI:")
        print("1. Create trust policy file:")
        print(
            '   echo \'{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"vmie.amazonaws.com"},"Action":"sts:AssumeRole","Condition":{"StringEquals":{"sts:Externalid":"vmimport"}}}]}\' > trust-policy.json'
        )
        print()
        print("2. Create the role:")
        print(
            "   aws iam create-role --role-name vmimport --assume-role-policy-document file://trust-policy.json"
        )
        print()
        print("3. Create policy file:")
        print(
            '   echo \'{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:GetBucketLocation","s3:GetObject","s3:ListBucket","s3:PutObject","s3:GetBucketAcl"],"Resource":["arn:aws:s3:::*"]},{"Effect":"Allow","Action":["ec2:ModifySnapshotAttribute","ec2:CopySnapshot","ec2:RegisterImage","ec2:Describe*"],"Resource":"*"}]}\' > role-policy.json'
        )
        print()
        print("4. Attach policy:")
        print(
            "   aws iam put-role-policy --role-name vmimport --policy-name vmimport --policy-document file://role-policy.json"
        )

        return False


if __name__ == "__main__":
    try:
        create_vmimport_role()
    except Exception as e:
        print(f"❌ Script failed: {e}")
        exit(1)
