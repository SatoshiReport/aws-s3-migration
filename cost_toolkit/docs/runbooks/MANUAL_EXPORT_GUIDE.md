# AWS EBS Snapshot to S3 Manual Export Guide

## Overview
This guide provides a semi-automated approach to export EBS snapshots to S3 for cost savings. The automated script handles the reliable parts (creating AMIs and S3 buckets), while you manually run the problematic export commands.

## Cost Savings
- **Current EBS cost**: $0.05/GB/month
- **S3 Standard cost**: $0.023/GB/month  
- **Savings**: 54% reduction in storage costs
- **Your snapshots**: 456 GB total = ~$12.31/month savings

## Step-by-Step Process

### Step 1: Run the Preparation Script
```bash
cd /Users/mahrens917/aws_cost
python3 scripts/optimization/aws_snapshot_to_s3_semi_manual.py
```

This will:
- ✅ Create AMIs from your snapshots
- ✅ Set up S3 buckets with versioning
- 📋 Generate exact manual commands
- 📄 Save commands to a text file

### Step 2: Run Manual Export Commands
The script will provide commands like:
```bash
aws ec2 export-image \
    --image-id ami-xxxxxxxxx \
    --disk-image-format VMDK \
    --s3-export-location S3Bucket=bucket-name,S3Prefix=ebs-snapshots/ami-id/ \
    --description "Manual export of snap-xxxxxxxxx" \
    --region us-east-2
```

### Step 3: Monitor Progress
Use the monitoring script:
```bash
# Check all regions
python3 scripts/optimization/monitor_manual_exports.py

# Check specific AMI
python3 scripts/optimization/monitor_manual_exports.py --region us-east-2 --ami ami-xxxxxxxxx

# Continuous monitoring
python3 scripts/optimization/monitor_manual_exports.py --watch
```

### Step 4: Handle Common Issues

**If export gets stuck at 80%:**
1. Wait 2-3 hours
2. Check S3 directly:
   ```bash
   aws s3 ls s3://bucket-name/ebs-snapshots/ami-id/ --recursive --human-readable
   ```
3. If file exists and size is stable, consider export complete

**If export gets deleted immediately:**
1. Wait 10-15 minutes
2. Try again
3. Consider using eu-west-2 region (more reliable)

**If export fails repeatedly:**
1. Try different region (eu-west-2 works better)
2. Try smaller snapshots first
3. Contact AWS support

### Step 5: Verify and Cleanup
Once S3 file exists and is stable:

1. **Verify S3 file:**
   ```bash
   aws s3api head-object --bucket bucket-name --key ebs-snapshots/ami-id/export-task-id.vmdk
   ```

2. **Clean up temporary AMI:**
   ```bash
   aws ec2 deregister-image --image-id ami-xxxxxxxxx --region region-name
   ```

3. **Optional - Delete original snapshot** (after verifying S3 export):
   ```bash
   aws ec2 delete-snapshot --snapshot-id snap-xxxxxxxxx --region region-name
   ```

## Your Specific Snapshots

| Snapshot ID | Region | Size | Expected Monthly Savings |
|-------------|--------|------|-------------------------|
| snap-036eee4a7c291fd26 | us-east-2 | 8 GB | $0.22 |
| snap-046b7eace8694913b | eu-west-2 | 64 GB | $1.73 |
| snap-0f68820355c25e73e | eu-west-2 | 384 GB | $10.37 |

## Troubleshooting

### Export Task Gets Deleted
- **Cause**: AWS resource allocation failure
- **Solution**: Retry in 10-15 minutes, try different region

### Export Stuck at 80%
- **Cause**: Known AWS service issue
- **Solution**: Check S3 directly, file might be complete

### No S3 File After "Completed" Status
- **Cause**: AWS status inconsistency
- **Solution**: Wait 30 minutes, check S3 again

## Success Indicators
- ✅ S3 file exists
- ✅ File size is reasonable (10%-120% of original snapshot size)
- ✅ File size hasn't changed for 10+ minutes
- ✅ AWS export status shows "completed" OR S3 file is stable

## Files Created
- `aws_snapshot_to_s3_semi_manual.py` - Preparation script
- `monitor_manual_exports.py` - Monitoring script  
- `manual_export_commands_YYYYMMDD_HHMMSS.txt` - Generated commands

## Expected Timeline
- **Preparation**: 5-10 minutes per snapshot
- **Manual export**: 1-6 hours per snapshot (varies by size)
- **Total time**: Plan for 1 day to complete all exports

## Support
If you encounter issues:
1. Check the monitoring script output
2. Verify AWS CLI is configured correctly
3. Try the eu-west-2 region (more reliable)
4. Contact AWS support for persistent export service issues