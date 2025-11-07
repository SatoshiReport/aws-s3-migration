# AWS EBS Snapshot to S3 Export Guide

## Overview

This guide explains how to export EBS snapshots to S3 for significant cost savings while maintaining data accessibility for disaster recovery.

## Cost Savings Analysis

### Current EBS Snapshot Costs
- **Standard EBS Snapshots**: $0.05 per GB/month
- **Your current 3 snapshots (456 GB total)**: $22.80/month

### S3 Storage Cost Analysis
| Storage Class | Cost per GB/month | Monthly Cost (456 GB) | Savings vs EBS |
|---------------|-------------------|----------------------|----------------|
| EBS Snapshots | $0.050 | $22.80 | - |
| **S3 Standard** | **$0.023** | **$10.49** | **54%** |

### Savings Potential with S3 Standard
- **Current monthly cost**: $22.80
- **S3 Standard cost**: $10.49
- **Monthly savings**: $12.31 (54% reduction)
- **Annual savings**: $147.72

## Export Process

### 1. Automated Export Script
```bash
python3 scripts/optimization/aws_snapshot_to_s3_export.py
```

**What the script does:**
1. Creates temporary AMIs from EBS snapshots
2. Exports AMIs to S3 buckets in VMDK format
3. Sets up S3 lifecycle policies for automatic cost optimization
4. Provides cleanup commands for temporary resources

### 2. S3 Storage Configuration
The script stores snapshots in S3 Standard storage with:
- **Immediate access**: No retrieval delays
- **High durability**: 99.999999999% (11 9's) durability
- **Versioning enabled**: Protection against accidental deletion
- **Simple pricing**: $0.023 per GB/month

## Restore Process

### 1. Automated Restore Script
```bash
python3 scripts/optimization/aws_s3_to_snapshot_restore.py
```

**What the script does:**
1. Lists available exports in S3 buckets
2. Imports AMIs from S3 exports
3. Creates new EBS snapshots from imported AMIs
4. Tags restored snapshots for identification

### 2. Restore Times by Storage Class
| Storage Class | Restore Time | Use Case |
|---------------|--------------|----------|
| S3 Standard | Immediate | Frequent access |
| S3 Standard-IA | Immediate | Infrequent access |
| S3 Glacier Flexible | 1-5 minutes | Archive with occasional access |
| S3 Glacier Deep Archive | 12 hours | Long-term archive |

## Implementation Strategy

### Phase 1: Export Current Snapshots
1. Run the export script for all 3 current snapshots
2. Verify successful exports in S3
3. Test restore process with one snapshot

### Phase 2: Cleanup and Savings Realization
1. Delete original EBS snapshots after successful export
2. Clean up temporary AMIs
3. Monitor S3 costs and lifecycle transitions

### Phase 3: Ongoing Management
1. Set up automated exports for new snapshots
2. Regular testing of restore procedures
3. Cost monitoring and optimization

## Current Snapshots to Export

| Snapshot ID | Region | Size | Description | Monthly Cost |
|-------------|--------|------|-------------|--------------|
| snap-0f68820355c25e73e | eu-west-2 | 384 GB | vol-089b9ed38099c68f3 backup | $19.20 |
| snap-046b7eace8694913b | eu-west-2 | 64 GB | Tars 3 backup | $3.20 |
| snap-036eee4a7c291fd26 | us-east-2 | 8 GB | mufasa AMI snapshot | $0.40 |

## Security Considerations

### S3 Bucket Security
- Buckets are created with private access by default
- Enable versioning for additional protection
- Consider cross-region replication for disaster recovery
- Use S3 bucket policies to restrict access

### Data Encryption
- S3 server-side encryption is enabled by default
- Consider using AWS KMS for additional key management
- Exported AMIs maintain original encryption settings

## Monitoring and Alerts

### Cost Monitoring
- Set up AWS Cost Explorer alerts for S3 spending
- Monitor lifecycle policy effectiveness
- Track storage class transitions

### Operational Monitoring
- Set up CloudWatch alarms for failed exports/imports
- Monitor S3 bucket access patterns
- Regular testing of restore procedures

## Troubleshooting

### Common Export Issues
1. **AMI creation timeout**: Increase waiter timeout in script
2. **S3 permissions**: Ensure proper IAM permissions for S3 operations
3. **Export task failures**: Check CloudTrail logs for detailed error messages

### Common Restore Issues
1. **Import format errors**: Verify VMDK format compatibility
2. **Storage class delays**: Account for restore times from archived storage
3. **Region mismatches**: Ensure consistent region usage

## Cost Comparison Example

### Before S3 Export (Current State)
```
3 EBS snapshots (456 GB total)
Monthly cost: $22.80
Annual cost: $273.60
```

### After S3 Export (S3 Standard)
```
3 S3 exports (456 GB total)
Monthly cost: $10.49
Annual cost: $125.88
Savings: $147.72/year (54% reduction)
```

## Next Steps

1. **Immediate**: Run export script to move snapshots to S3
2. **Short-term**: Verify exports and test restore process
3. **Long-term**: Implement automated snapshot lifecycle management

## Commands Summary

### Export to S3
```bash
cd /Users/mahrens917/aws_cost
python3 scripts/optimization/aws_snapshot_to_s3_export.py
```

### Restore from S3
```bash
cd /Users/mahrens917/aws_cost
python3 scripts/optimization/aws_s3_to_snapshot_restore.py
```

### Manual Cleanup (after successful export)
```bash
# Delete original snapshots
aws ec2 delete-snapshot --snapshot-id snap-0f68820355c25e73e --region eu-west-2
aws ec2 delete-snapshot --snapshot-id snap-046b7eace8694913b --region eu-west-2
aws ec2 delete-snapshot --snapshot-id snap-036eee4a7c291fd26 --region us-east-2

# Clean up temporary AMIs (IDs provided by export script)
aws ec2 deregister-image --image-id ami-xxxxxxxxx --region eu-west-2
```

This S3 export strategy provides the maximum possible cost savings while maintaining data accessibility for disaster recovery scenarios.