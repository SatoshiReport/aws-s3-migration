#!/bin/bash

# AWS EBS to S3 Migration Script
# This script transfers user files from EBS volumes to S3 Standard storage

echo "Starting EBS to S3 migration..."
echo "Target bucket: aws-user-files-backup-london"
echo "Region: eu-west-2"
echo ""

# Ensure volumes are mounted
echo "📦 Checking volume mounts..."
sudo mkdir -p /mnt/vol384
sudo mkdir -p /mnt/vol64

# Mount volumes (adjust device names as needed)
sudo mount /dev/nvme1n1 /mnt/vol384 2>/dev/null || echo "Volume 384GB already mounted or not available"
sudo mount /dev/nvme2n1 /mnt/vol64 2>/dev/null || echo "Volume 64GB already mounted or not available"

echo ""
echo "📁 Identifying user directories to migrate..."

# Function to sync directory to S3
sync_to_s3() {
    local source_path="$1"
    local s3_prefix="$2"
    
    if [ -d "$source_path" ]; then
        echo "🔄 Syncing $source_path to s3://aws-user-files-backup-london/$s3_prefix/"
        aws s3 sync "$source_path" "s3://aws-user-files-backup-london/$s3_prefix/" \
            --region eu-west-2 \
            --storage-class STANDARD \
            --exclude "*.tmp" \
            --exclude "*.log" \
            --exclude ".cache/*" \
            --exclude "lost+found/*"
        echo "✅ Completed: $source_path"
        echo ""
    else
        echo "⚠️  Directory not found: $source_path"
    fi
}

# Migrate from 384GB volume
echo "📦 Processing 384GB volume (/mnt/vol384)..."
sync_to_s3 "/mnt/vol384/home" "384gb-volume/home"
sync_to_s3 "/mnt/vol384/opt" "384gb-volume/opt"
sync_to_s3 "/mnt/vol384/var/www" "384gb-volume/var-www"
sync_to_s3 "/mnt/vol384/data" "384gb-volume/data"

# Migrate from 64GB volume (Tars 3)
echo "📦 Processing 64GB volume (/mnt/vol64)..."
sync_to_s3 "/mnt/vol64/home" "64gb-volume/home"
sync_to_s3 "/mnt/vol64/opt" "64gb-volume/opt"
sync_to_s3 "/mnt/vol64/var/www" "64gb-volume/var-www"
sync_to_s3 "/mnt/vol64/data" "64gb-volume/data"

echo ""
echo "📊 Migration summary:"
aws s3 ls s3://aws-user-files-backup-london/ --recursive --human-readable --summarize

echo ""
echo "💰 Cost comparison:"
echo "EBS (current): $35.84/month for 448GB"
echo "S3 Standard: ~$10.30/month for 448GB"
echo "Potential savings: ~$25.54/month"

echo ""
echo "✅ Migration complete!"
echo "Files are now stored in S3 bucket: aws-user-files-backup-london"
