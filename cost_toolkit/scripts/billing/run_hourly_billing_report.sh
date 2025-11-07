#!/bin/bash

# AWS Hourly Billing Report Runner
# Executes the hourly billing analysis script

echo "🕐 AWS Hourly Billing Report"
echo "=========================="
echo "Analyzing current hour costs to identify active services..."
echo ""

# Change to the script directory
cd "$(dirname "$0")"

# Run the hourly billing report
python3 aws_hourly_billing_report.py

echo ""
echo "💡 Tip: Run this hourly to track real-time cost changes"
echo "📊 Compare with monthly report: python3 aws_billing_report.py"