#!/bin/bash

# Function to find the block device with 15 partitions and resolve its symlink
find_device() {
    for dev in /sys/block/sd*; do
        devname=$(basename "$dev") # e.g., sda
        part_count=$(ls "$dev" | grep -c "${devname}[0-9]")

        if [ "$part_count" -eq 15 ]; then
            model=$(lsblk -dn -o MODEL "/dev/$devname" | xargs)
            echo "Device /dev/$devname has 15 partitions. Model: $model"

            symlink=$(ls -1 /dev/disk/by-id/ | grep -i "$model" | grep -Ev -- '-part[0-9]+$' | head -n1)

            if [ -n "$symlink" ]; then
                SRC="/dev/disk/by-id/$symlink"
                DEV="/dev/$devname"  # For dd
                echo "SRC=$SRC"
                return 0
            else
                echo "No base symlink found in /dev/disk/by-id/ for model: $model"
                return 1
            fi
        fi
    done

    echo "No device with 15 partitions found."
    return 1
}

# Function to calculate used space and perform backup
perform_backup() {
    echo "==> Calculating used space on ext4 partitions of $DEV..."

    SRC1="${SRC}-part1"
    SRC2="${SRC}-part2"

    for p in "$SRC1" "$SRC2"; do
        if [[ -b "$p" ]]; then
            sudo dumpe2fs -h "$p" 2>/dev/null | \
              awk -v part="$p" '
                /Block size:/      { bs=$3 }
                /Block count:/     { bc=$3 }
                /Free blocks:/     { fb=$3 }
                END {
                  if (bs) {
                    used = (bc - fb) * bs / 1024 / 1024 / 1024;
                    printf "%s used ≈ %.1f GiB\n", part, used;
                  } else {
                    print part " (not ext4 or unreadable)"
                  }
              }'
        else
            echo "$p does not exist"
        fi
    done

    OUT="$(pwd)/jetson_orin_nvme_$(date +%Y%m%d_%H%M).img.zst"

    echo "==> Reading from: $SRC"
    echo "==> Writing to:   $OUT"

    echo "==> Starting backup and compression..."
    sudo dd if="$DEV" bs=64M status=progress conv=sync,noerror | \
    zstd -T0 -1 -o "$OUT"

    echo "==> Backup completed: $OUT"

}

# Main function
main() {
    if find_device; then
        perform_backup
    else
        echo "Aborting due to device detection failure."
        exit 1
    fi
}

# Execute main
main

