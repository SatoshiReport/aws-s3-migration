"""
AWS Cost Audit Functions
Runs quick resource audits and generates cost breakdown reports.
"""

import os
import subprocess
import sys
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def _extract_summary_lines(output):
    """Extract summary lines from audit script output."""
    lines = output.split("\n")
    summary_lines = []
    keywords = ["Total", "Found", "RECOMMENDATIONS", "monthly cost", "snapshots", "volumes"]

    for line in lines:
        if any(keyword in line for keyword in keywords):
            summary_lines.append(line.strip())

    return summary_lines[-5:]


def _run_audit_script(name, script_path):
    """Run a single audit script and display results."""
    if not os.path.exists(script_path):
        print(f"  ⚠️ Script not found: {script_path}")
        return

    print(f"\n📊 {name}:")
    try:
        result = subprocess.run(
            [sys.executable, script_path], capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            summary_lines = _extract_summary_lines(result.stdout)
            for line in summary_lines:
                if line:
                    print(f"  {line}")
        else:
            print(f"  ⚠️ Script failed: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        print(f"  ⚠️ Audit timed out - try running manually: python3 {script_path}")
    except ClientError as e:
        print(f"  ⚠️ Error running audit: {str(e)}")


def run_quick_audit(scripts_dir):
    """Run a quick audit using existing scripts"""
    print("🔍 Running Quick Resource Audit...")
    print("=" * 60)

    audit_scripts = [
        ("EBS Audit", os.path.join(scripts_dir, "audit", "aws_ebs_audit.py")),
        ("VPC Audit", os.path.join(scripts_dir, "audit", "aws_vpc_audit.py")),
    ]

    for name, script_path in audit_scripts:
        _run_audit_script(name, script_path)


def report_lightsail_cost_breakdown():
    """Show the current month's Lightsail spend grouped by usage type."""
    print("\n🔎 LIGHTSAIL COST BREAKDOWN")
    print("=" * 60)
    try:
        ce_client = boto3.client("ce", region_name="us-east-1")
        today = datetime.now(timezone.utc).date()
        start = today.replace(day=1)
        response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start.strftime("%Y-%m-%d"), "End": today.strftime("%Y-%m-%d")},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            Filter={"Dimensions": {"Key": "SERVICE", "Values": ["Amazon Lightsail"]}},
            GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
        )
        rows = []
        total = 0.0
        for result in response.get("ResultsByTime", []):
            for group in result.get("Groups", []):
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                if amount <= 0:
                    continue
                total += amount
                rows.append((group["Keys"][0], amount))
        if not rows:
            print("No Lightsail spend recorded so far this month.")
            return
        print(f"Total month-to-date Lightsail charges: ${total:.2f}")
        for usage, amount in sorted(rows, key=lambda x: x[1], reverse=True):
            print(f"  {usage}: ${amount:.2f}")
    except ClientError as exc:
        print(f"⚠️ Unable to fetch Lightsail cost breakdown: {exc}")
