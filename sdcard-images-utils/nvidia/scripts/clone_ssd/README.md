# `backup_nvme.sh`

A Bash script to automatically detect an NVMe (or SATA) block device with **15 partitions**, resolve its **persistent symlink** via `/dev/disk/by-id`, and perform a **compressed full-disk backup** using `dd` and `zstd`.

---

## 📦 Features

- Detects the block device (e.g., `/dev/sdX`) with exactly **15 partitions**
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
chmod +x backup_nvme.sh
sudo ./backup_nvme.sh

```
---

## 📂 Output

The backup image is saved in your preset working directory:

```bash
~/jetson_orin_nvme_YYYYMMDD_HHMM.img.zst

```

# restore_nvme_image.sh

A Bash script to safely restore a compressed disk image (zstd-compressed `.img.zst` file) onto a target NVMe or other block device.

---

## Overview

This script wipes the target device, restores a compressed disk image to it, repairs the GPT backup header, and then displays the partition layout to verify the restore.

**Warning:** This will completely erase all data on the target device.

---

##  🚀 Usage

```bash
sudo ./restore_nvme_image.sh <target device> <compressed image (.img.zst)>

sudo ./restore_nvme_image.sh /dev/sda jetson_orin_nvme_20250820_1224.img.zst
```

