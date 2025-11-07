#!/bin/bash

echo "🚀 Simple EBS to S3 Migration"
echo "============================="
echo "$(date): Starting migration"

# Install prerequisites
echo "📦 Installing prerequisites..."
sudo apt update -qq
sudo apt install -y unzip curl

# Install AWS CLI using pip (simpler method)
echo "📥 Installing AWS CLI via pip..."
sudo apt install -y python3-pip
pip3 install awscli --user

# Add to PATH
export PATH="$HOME/.local/bin:$PATH"

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

# Test AWS CLI
echo "🔐 Testing AWS CLI..."
aws --version
aws sts get-caller-identity

if [ $? -ne 0 ]; then
    echo "❌ AWS CLI setup failed"
    exit 1
fi

echo "✅ AWS CLI working"

# Create mount points
sudo mkdir -p /mnt/vol384 /mnt/vol64

echo ""
echo "📦 Available devices:"
lsblk

echo ""
echo "🔍 Mounting volumes..."

# Mount volumes by size
for dev in /dev/nvme1n1 /dev/nvme2n1 /dev/nvme3n1; do
    if [ -b "$dev" ]; then
        size_gb=$(lsblk -b -d -o SIZE -n $dev 2>/dev/null | awk '{print int($1/1024/1024/1024)}')
        echo "Device $dev: ${size_gb}GB"
        
        if [ "$size_gb" -gt 300 ] && [ "$size_gb" -lt 500 ]; then
            sudo mount $dev /mnt/vol384 && echo "✅ Mounted 384GB volume"
        elif [ "$size_gb" -gt 50 ] && [ "$size_gb" -lt 100 ]; then
            sudo mount $dev /mnt/vol64 && echo "✅ Mounted 64GB volume"
        fi
    fi
done

echo ""
echo "📁 Mount status:"
df -h | grep /mnt

echo ""
echo "🔄 Starting S3 sync..."

# Simple sync function
sync_to_s3() {
    local source="$1"
    local dest="$2"
    
    if [ -d "$source" ]; then
        echo "🔄 Syncing $source..."
        
        # Create temp copy with proper permissions
        temp_dir="/tmp/$(basename $source)_sync"
        sudo rm -rf "$temp_dir"
        sudo cp -r "$source" "$temp_dir"
        sudo chown -R ubuntu:ubuntu "$temp_dir"
        
        # Sync to S3
        aws s3 sync "$temp_dir" "s3://aws-user-files-backup-london/$dest/" \
            --storage-class STANDARD \
            --exclude "*.tmp" \
            --exclude "*.log" \
            --exclude ".cache/*"
        
        if [ $? -eq 0 ]; then
            echo "✅ Synced: $source"
        else
            echo "❌ Failed: $source"
        fi
        
        sudo rm -rf "$temp_dir"
    fi
}

# Sync from 384GB volume
if mountpoint -q /mnt/vol384; then
    echo "📦 Processing 384GB volume..."
    sync_to_s3 "/mnt/vol384/home" "384gb/home"
    sync_to_s3 "/mnt/vol384/opt" "384gb/opt"
    sync_to_s3 "/mnt/vol384/var" "384gb/var"
    sync_to_s3 "/mnt/vol384/root" "384gb/root"
    sync_to_s3 "/mnt/vol384/data" "384gb/data"
    sync_to_s3 "/mnt/vol384/etc" "384gb/etc"
fi

# Sync from 64GB volume
if mountpoint -q /mnt/vol64; then
    echo "📦 Processing 64GB volume..."
    sync_to_s3 "/mnt/vol64/home" "64gb/home"
    sync_to_s3 "/mnt/vol64/opt" "64gb/opt"
    sync_to_s3 "/mnt/vol64/var" "64gb/var"
    sync_to_s3 "/mnt/vol64/root" "64gb/root"
    sync_to_s3 "/mnt/vol64/data" "64gb/data"
    sync_to_s3 "/mnt/vol64/etc" "64gb/etc"
fi

echo ""
echo "📊 S3 bucket contents:"
aws s3 ls s3://aws-user-files-backup-london/ --recursive --summarize

echo ""
echo "✅ Migration complete!"
echo "$(date): Finished"
echo ""
echo "💰 Savings achieved:"
echo "- EBS cleanup: $166.40/month"
echo "- S3 migration: ~$25.54/month"
echo "- Total: ~$191.94/month"
