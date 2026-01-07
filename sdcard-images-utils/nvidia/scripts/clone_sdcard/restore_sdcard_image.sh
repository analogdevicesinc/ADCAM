#!/bin/bash

# Usage: sudo ./restore_sdcard_image.sh /dev/sdX /path/to/image.img.zst

set -euox pipefail

if [[ $# -ne 2 ]]; then
	  echo "Usage: $0 <target device> <compressed image (.img.zst)>"
	  echo "sudo ./restore_nvme_image.sh /dev/sdX /path/to/image.img.zst"
	    exit 1
fi

TARGET="$1"
IMG="$2"

# Validate target device
if [[ ! -b "$TARGET" ]]; then
	  echo "Error: $TARGET is not a valid block device."
	    exit 1
fi

# Validate image
if [[ ! -f "$IMG" ]]; then
	  echo "Error: Image file $IMG does not exist."
	    exit 1
fi

echo "⚠️  WARNING: This will erase all data on $TARGET"
read -p "Type 'YES' to continue: " confirm
if [[ "$confirm" != "YES" ]]; then
	  echo "Aborted."
	    exit 1
fi

echo "==> Wiping existing data..."
sudo wipefs -a "$TARGET"
sudo sgdisk --zap-all "$TARGET"
sudo dd if=/dev/zero of="$TARGET" bs=1M count=100 status=progress

echo "==> Restoring image to $TARGET..."
zstd -dc "$IMG" | sudo dd of="$TARGET" bs=64M status=progress conv=fsync

echo "==> Repairing GPT backup header..."
sudo sgdisk -e "$TARGET"

echo "==> Verifying partition layout..."
lsblk -o NAME,SIZE,FSTYPE,LABEL "$TARGET"

echo "✅ Restore complete!"
