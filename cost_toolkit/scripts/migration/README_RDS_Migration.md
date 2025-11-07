# RDS to Aurora Serverless v2 Migration Guide

## Overview
This script migrates your existing RDS instances to Aurora Serverless v2 for significant cost savings through automatic scaling.

## Cost Benefits
- **Current RDS**: Fixed monthly cost (~$15/month for db.t3.micro)
- **Aurora Serverless v2**: Pay-per-use, scales to zero during inactivity
- **Typical Savings**: 60-80% for intermittent workloads

## Usage

### 1. List Available Instances
```bash
cd scripts/migration
python3 aws_rds_to_aurora_serverless_migration.py --list-only
```

### 2. Migrate Specific Instance
```bash
# Interactive migration (recommended)
python3 aws_rds_to_aurora_serverless_migration.py

# Or specify instance directly
python3 aws_rds_to_aurora_serverless_migration.py --instance database-1 --region us-east-1
```

## Migration Process

1. **Discovery**: Script finds all standalone RDS instances
2. **Validation**: Checks compatibility with Aurora Serverless v2
3. **Snapshot**: Creates backup snapshot of source database
4. **Migration**: Creates Aurora Serverless v2 cluster from snapshot
5. **Configuration**: Sets up auto-scaling (0.5-4.0 ACU)
6. **Results**: Provides new connection details

## Supported Engines

| Source Engine | Target Aurora Engine |
|---------------|---------------------|
| MySQL | aurora-mysql |
| MariaDB | aurora-mysql |
| PostgreSQL | aurora-postgresql |

## Aurora Serverless v2 Features

- **Auto-scaling**: 0.5 to 4.0 ACU (Aurora Capacity Units)
- **Scale to Zero**: Pauses during inactivity
- **Pay-per-use**: Only charged for active compute time
- **High Availability**: Built-in multi-AZ support
- **Backup**: Automated backups and point-in-time recovery

## Cost Estimation

### Current RDS Instances
- **database-1** (MariaDB, db.t3.micro): ~$15/month
- **simba-db** (PostgreSQL, db.t4g.micro): ~$15/month
- **Total**: ~$30/month

### After Migration to Aurora Serverless v2
- **Low usage** (20% active): ~$6/month per database
- **Medium usage** (50% active): ~$15/month per database
- **High usage** (80% active): ~$24/month per database

## Post-Migration Steps

1. **Update Connection Strings**: Use new Aurora endpoints
2. **Test Application**: Verify functionality with Aurora
3. **Monitor Performance**: Check CloudWatch metrics
4. **Delete Original RDS**: Stop charges once satisfied

## Safety Features

- Original RDS instance remains untouched during migration
- Can rollback by switching connection strings back
- Snapshot created for additional backup
- Deletion protection disabled for cost management

## Example Migration Output

```
🎉 MIGRATION COMPLETED SUCCESSFULLY!
================================================================================

📊 MIGRATION SUMMARY:
Original RDS Instance: database-1 (us-east-1)
New Aurora Cluster: database-1-aurora-serverless
Engine Migration: mariadb → aurora-mysql
Cost Reduction: $15.00/month → $6.00/month
Monthly Savings: $9.00

🔗 NEW CONNECTION DETAILS:
Writer Endpoint: database-1-aurora-serverless.cluster-xxxxx.us-east-1.rds.amazonaws.com
Port: 3306
Engine: aurora-mysql
```

## Troubleshooting

### Common Issues
1. **Instance not available**: Ensure RDS instance is in 'available' state
2. **Engine compatibility**: Only MySQL, MariaDB, and PostgreSQL supported
3. **Permissions**: Ensure AWS credentials have RDS full access
4. **Snapshot timeout**: Large databases may take longer to snapshot

### Rollback Process
1. Update connection strings back to original RDS instance
2. Delete Aurora cluster if no longer needed
3. Original RDS instance continues running unchanged

## Monitoring Aurora Serverless v2

### Key CloudWatch Metrics
- **ServerlessDatabaseCapacity**: Current ACU usage
- **DatabaseConnections**: Active connections
- **CPUUtilization**: CPU usage percentage
- **ReadLatency/WriteLatency**: Performance metrics

### Cost Monitoring
- Check AWS Cost Explorer for Aurora charges
- Monitor ACU-hours in billing details
- Set up billing alerts for unexpected usage

## Support

For issues or questions:
1. Check AWS CloudWatch logs for Aurora cluster
2. Review migration log in `scripts/config/migration_log.json`
3. Consult AWS RDS documentation for Aurora Serverless v2