# `backup_sdcard.sh`

A Bash script to automatically detect micro sd card with **15 partitions**, resolve its **persistent symlink** via `/dev/disk/by-id`, and perform a **compressed full-disk backup** using `dd` and `zstd`.

---

## 📦 Features

- Detects the block device (e.g., `/dev/mmcblk0*`) with exactly **15 partitions**
- Resolves a stable symlink path from `/dev/disk/by-id/`
- Estimates **used space** on the first two partitions (assumed to be `ext4`)
- Backs up the entire device using `dd`, compresses with `zstd`
- Outputs a timestamped backup image (`.img.zst`)

---

## 🔧 Requirements

- Bash (Linux)
- `dd`
- `lsblk`
- `dumpe2fs` (from `e2fsprogs`)
- `zstd`
- `sudo` privileges

---

## 🚀 Usage

```bash
chmod +x backup_sdcard.sh
sudo ./backup_sdcard.sh

```
---

## 📂 Output

The backup image is saved in your preset working directory:

```bash
~/jetson_orin_nano_sdcard_YYYYMMDD_HHMM.img.zst

```

# restore_sdcard_image.sh

A Bash script to safely restore a compressed disk image (zstd-compressed `.img.zst` file) onto a target NVMe or other block device.

---

## Overview

This script wipes the target device, restores a compressed disk image to it, repairs the GPT backup header, and then displays the partition layout to verify the restore.

**Warning:** This will completely erase all data on the target device.

---

##  🚀 Usage

```bash
sudo ./restore_sdcard_image.sh <target device> <compressed image (.img.zst)>

sudo ./restore_sdcard_image.sh /dev/sda /jetson_orin_nano_sdcard_20251120_1224.img.zst
```

