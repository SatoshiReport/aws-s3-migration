#!/usr/bin/env python3

import os
import time

import boto3


def setup_aws_credentials():
    """Load AWS credentials from ~/.env via shared helper."""
    from cost_toolkit.scripts import aws_utils

    aws_utils.setup_aws_credentials()


def analyze_volumes_corrected():
    """Corrected analysis - keep smaller volume if data is the same"""
    setup_aws_credentials()

    print("AWS London EBS Volume Duplicate Analysis - CORRECTED")
    print("=" * 80)
    print("🔍 Re-analyzing to optimize for MAXIMUM cost savings")
    print("⚠️  ANALYSIS ONLY - NO DELETIONS WILL BE PERFORMED")
    print()

    ec2 = boto3.client("ec2", region_name="eu-west-2")

    try:
        # Get volume details
        volume_ids = [
            "vol-0249308257e5fa64d",  # Tars 3 - 64 GB
            "vol-0e07da8b7b7dafa17",  # Tars 2 - 1024 GB
            "vol-089b9ed38099c68f3",  # 384 GB
        ]

        volumes_response = ec2.describe_volumes(VolumeIds=volume_ids)
        volumes = volumes_response["Volumes"]

        print("📊 VOLUME COST ANALYSIS:")
        print("=" * 80)

        volume_data = {}

        for volume in volumes:
            vol_id = volume["VolumeId"]
            size = volume["Size"]
            created = volume["CreateTime"]

            # Get volume name
            name = "No name"
            if "Tags" in volume:
                for tag in volume["Tags"]:
                    if tag["Key"] == "Name":
                        name = tag["Value"]
                        break

            # Calculate monthly cost (London gp3: $0.08/GB/month)
            monthly_cost = size * 0.08

            volume_data[vol_id] = {
                "name": name,
                "size": size,
                "created": created,
                "monthly_cost": monthly_cost,
            }

            print(f"📦 {name} ({vol_id}):")
            print(f"   Size: {size} GB")
            print(f"   Monthly cost: ${monthly_cost:.2f}")
            print(f"   Created: {created.strftime('%Y-%m-%d %H:%M:%S')}")
            print()

        print("🤔 DUPLICATE SCENARIO ANALYSIS:")
        print("=" * 80)

        vol_384_cost = volume_data["vol-089b9ed38099c68f3"]["monthly_cost"]  # $30.72
        tars_2_cost = volume_data["vol-0e07da8b7b7dafa17"]["monthly_cost"]  # $81.92

        print("User's insight: '384 was just a reduced size of Tars2'")
        print()
        print("Two possible interpretations:")
        print()
        print("SCENARIO A: 384 GB is SUBSET of Tars 2 (1024 GB)")
        print("   - 384 GB contains partial data")
        print("   - Tars 2 contains complete data")
        print("   - Must keep Tars 2 (complete)")
        print("   - Remove 384 GB")
        print(f"   - Savings: ${vol_384_cost:.2f}/month")
        print()
        print("SCENARIO B: Both volumes contain SAME data")
        print("   - 384 GB has same data as Tars 2")
        print("   - Tars 2 is just oversized/wasteful")
        print("   - Can keep smaller 384 GB")
        print("   - Remove Tars 2 (1024 GB)")
        print(f"   - Savings: ${tars_2_cost:.2f}/month")
        print()

        print("💡 CRITICAL QUESTION:")
        print("=" * 80)
        print("Does the 384 GB volume contain:")
        print("A) PARTIAL data (subset of Tars 2) → Keep Tars 2")
        print("B) SAME data (just smaller allocation) → Keep 384 GB")
        print()

        print("🎯 COST-OPTIMIZED RECOMMENDATION:")
        print("=" * 80)
        print("IF both volumes contain the SAME complete data:")
        print()
        print("🗑️  REMOVE: Tars 2 (1024 GB) - vol-0e07da8b7b7dafa17")
        print("💰 SAVINGS: $81.92/month")
        print("🔒 KEEP: 384 GB volume - vol-089b9ed38099c68f3")
        print("🔒 KEEP: Tars 3 (64 GB) - Boot volume")
        print()
        print("This would provide MAXIMUM savings of $81.92/month")
        print("vs only $30.72/month if we remove the smaller volume")
        print()
        print("📋 VERIFICATION NEEDED:")
        print("=" * 80)
        print("To determine the correct approach, we need to verify:")
        print("1. Does 384 GB contain complete usable data?")
        print("2. Is Tars 2 just an oversized copy of the same data?")
        print("3. Or does Tars 2 contain additional data not in 384 GB?")
        print()
        print("RECOMMENDATION: Verify data completeness before deciding")
        print("If 384 GB has complete data → Remove Tars 2 (save $81.92)")
        print("If 384 GB has partial data → Remove 384 GB (save $30.72)")

    except Exception as e:
        print(f"❌ Error during analysis: {str(e)}")


if __name__ == "__main__":
    analyze_volumes_corrected()
