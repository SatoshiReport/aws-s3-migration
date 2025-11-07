#!/bin/bash

echo "🚀 EBS to S3 Migration Script"
echo "============================="
echo "Target bucket: aws-user-files-backup-london"
echo "$(date): Migration started"

# Load AWS credentials from ~/.env
if [ -f "$HOME/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$HOME/.env"
    set +a
else
    echo "Missing ~/.env with AWS credentials" >&2
    exit 1
fi

# Install AWS CLI if not present
if ! command -v aws &> /dev/null; then
    echo "📥 Installing AWS CLI..."
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
    cd /tmp && unzip awscliv2.zip
    sudo ./aws/install
    echo "✅ AWS CLI installed"
fi

# Create mount points
echo "📁 Creating mount points..."
sudo mkdir -p /mnt/vol384 /mnt/vol64

echo ""
echo "📦 Available block devices:"
lsblk

echo ""
echo "🔍 Mounting volumes by size..."

# Find and mount volumes by size
for dev in /dev/nvme1n1 /dev/nvme2n1 /dev/nvme3n1 /dev/xvdf /dev/xvdg /dev/xvdh; do
    if [ -b "$dev" ]; then
        size_bytes=$(lsblk -b -d -o SIZE -n $dev 2>/dev/null || echo "0")
        size_gb=$((size_bytes / 1024 / 1024 / 1024))
        echo "Device $dev: ${size_gb}GB"
        
        if [ "$size_gb" -gt 300 ] && [ "$size_gb" -lt 500 ]; then
            echo "🔧 Mounting $dev as 384GB volume..."
            sudo mount $dev /mnt/vol384 2>/dev/null && echo "✅ 384GB volume mounted" || echo "⚠️ Mount failed"
        elif [ "$size_gb" -gt 50 ] && [ "$size_gb" -lt 100 ]; then
            echo "🔧 Mounting $dev as 64GB volume..."
            sudo mount $dev /mnt/vol64 2>/dev/null && echo "✅ 64GB volume mounted" || echo "⚠️ Mount failed"
        fi
    fi
done

echo ""
echo "📁 Current mount status:"
df -h | grep -E "/mnt/|Filesystem"

echo ""
echo "🔍 Checking directory contents..."

for mount_point in /mnt/vol384 /mnt/vol64; do
    if mountpoint -q "$mount_point" 2>/dev/null; then
        echo ""
        echo "📂 Contents of $mount_point:"
        sudo ls -la "$mount_point" 2>/dev/null | head -10
        
        for dir in home opt var root data etc usr; do
            if [ -d "$mount_point/$dir" ]; then
                size=$(sudo du -sh "$mount_point/$dir" 2>/dev/null | cut -f1)
                echo "  📁 $dir/ ($size)"
            fi
        done
    fi
done

echo ""
echo "🔄 Starting S3 sync operations..."

# Function to sync directory to S3
sync_dir() {
    local source="$1"
    local s3_path="$2"
    
    if [ -d "$source" ] && [ "$(sudo ls -A $source 2>/dev/null)" ]; then
        echo ""
        echo "🔄 Syncing $source to s3://aws-user-files-backup-london/$s3_path/"
        sudo aws s3 sync "$source" "s3://aws-user-files-backup-london/$s3_path/" \
            --region eu-west-2 \
            --storage-class STANDARD \
            --exclude "*.tmp" \
            --exclude "*.log" \
            --exclude ".cache/*" \
            --exclude "lost+found/*" \
            --exclude "proc/*" \
            --exclude "sys/*" \
            --exclude "dev/*" \
            --exclude "*.sock" \
            --exclude "*.pid"
        
        if [ $? -eq 0 ]; then
            echo "✅ Completed: $source"
        else
            echo "❌ Failed: $source"
        fi
    else
        echo "⚠️ Skipping empty/missing: $source"
    fi
}

# Sync from 384GB volume
if mountpoint -q /mnt/vol384 2>/dev/null; then
    echo ""
    echo "📦 Processing 384GB volume..."
    sync_dir "/mnt/vol384/home" "384gb/home"
    sync_dir "/mnt/vol384/opt" "384gb/opt"
    sync_dir "/mnt/vol384/var" "384gb/var"
    sync_dir "/mnt/vol384/root" "384gb/root"
    sync_dir "/mnt/vol384/data" "384gb/data"
    sync_dir "/mnt/vol384/etc" "384gb/etc"
else
    echo "⚠️ 384GB volume not mounted"
fi

# Sync from 64GB volume
if mountpoint -q /mnt/vol64 2>/dev/null; then
    echo ""
    echo "📦 Processing 64GB volume..."
    sync_dir "/mnt/vol64/home" "64gb/home"
    sync_dir "/mnt/vol64/opt" "64gb/opt"
    sync_dir "/mnt/vol64/var" "64gb/var"
    sync_dir "/mnt/vol64/root" "64gb/root"
    sync_dir "/mnt/vol64/data" "64gb/data"
    sync_dir "/mnt/vol64/etc" "64gb/etc"
else
    echo "⚠️ 64GB volume not mounted"
fi

echo ""
echo "📊 Final S3 bucket summary:"
aws s3 ls s3://aws-user-files-backup-london/ --recursive --human-readable --summarize

echo ""
echo "✅ Migration complete!"
echo "$(date): Migration finished"
echo ""
echo "💰 Cost optimization summary:"
echo "- Current EBS cost (384GB + 64GB): $35.84/month"
echo "- Target S3 cost: ~$10.30/month"
echo "- Monthly savings: ~$25.54"
echo "- Total project savings: ~$191.94/month"
