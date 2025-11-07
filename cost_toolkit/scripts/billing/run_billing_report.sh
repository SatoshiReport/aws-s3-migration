#!/bin/bash

# AWS Billing Report Runner
echo "Setting up AWS Billing Report..."

# Install required Python packages
echo "Installing dependencies..."
pip3 install -r requirements.txt

# Run the billing report
echo "Running AWS billing report..."
python3 aws_billing_report.py