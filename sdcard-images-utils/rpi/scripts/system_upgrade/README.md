# Raspberry Pi 5 — ADI ToF System Upgrade

This directory contains scripts to apply and validate the ADI ToF ADSD3500 software
patch on a **Raspberry Pi 5** running Ubuntu.

---

## Scripts

| Script | Description |
|--------|-------------|
| `apply_patch.sh` | Applies kernel, device tree, modules, and boot configuration for ADI ToF integration |
| `patch_validation.sh` | Validates that all patch components were applied correctly and hardware is detected |

---

## Requirements

- Raspberry Pi 5 (4 GB or 8 GB)
- Ubuntu (64-bit, aarch64)
- Root / sudo privileges
- Software update package archive extracted in the same directory as `apply_patch.sh`

### Required archive contents

| File | Description |
|------|-------------|
| `Image.gz` | ADI kernel image (`6.12.47-adi+`) |
| `bcm2712-rpi-5-b.dtb` | Device tree blob for Raspberry Pi 5 |
| `adsd3500-adsd3100.dtbo` | Device tree overlay |
| `modules.tar.gz` | Kernel modules archive |
| `sw-versions` | Software version manifest |
| `ubuntu_overlay/` | (Optional) systemd services, scripts, and Tools directory |

---

## Usage

### Step 1 — Transfer the update package

Using WinSCP (or `scp`) upload the software update package `.zip` to the Raspberry Pi
and extract it:

```bash
unzip <package>.zip
cd <extracted-folder>
```

### Step 2 — Apply the patch

```bash
sudo ./apply_patch.sh
```

The script will:
1. Validate required files are present
2. Back up the current kernel, DTB, and boot config to `/root/adi_tof_backup_<timestamp>/`
3. Install the ADI kernel image, device tree blob, overlay, and kernel modules
4. Update `/boot/firmware/config.txt` with `kernel=kernel_adi.img` and `dtoverlay=adsd3500-adsd3100`
5. Enable the `adi-tof` systemd service
6. Reboot automatically after 10 seconds (press **Ctrl+C** to cancel)

> **Note:** If the script is copied from Windows, convert line endings before running:
> ```bash
> sed -i 's/\r$//' apply_patch.sh
> sudo ./apply_patch.sh
> ```

### Step 3 — Validate the patch (after reboot)

```bash
sudo ./patch_validation.sh
```

---

## Patch Validation

`patch_validation.sh` performs the following checks:

### Software Checks

| Check | Description |
|-------|-------------|
| System Information | Kernel version (`6.12.47-adi+`), platform, OS, root filesystem |
| Boot Configuration | `kernel_adi.img` and `dtoverlay=adsd3500-adsd3100` present in `/boot/firmware/config.txt` |
| Kernel & DT Files | `kernel_adi.img`, `bcm2712-rpi-5-b.dtb`, `sw-versions` |
| Device Tree Overlay | `/boot/firmware/overlays/adsd3500-adsd3100.dtbo` |
| Kernel Modules (disk) | `/lib/modules/6.12.47-adi+/` directory and `.ko` files |
| Loaded Kernel Modules | `adsd3500` module loaded and in use (`lsmod`) |
| Ubuntu Overlay | `/opt/adi/Tools`, `/usr/share/systemd/*.sh` |
| Systemd Services | `adi-tof`, `systemd-networkd` enabled and running |
| Camera Devices | V4L2 video devices present (`/dev/video*`) |
| ADSD3500 Subdevice | ADSD3500 found in media graph via `media-ctl` |

### Hardware Checks

| Check | Description |
|-------|-------------|
| I2C Device Detection | I2C bus 10 scanned; devices at `0x38`, `0x58`, `0x68` |
| GPIO Label Detection | MAX7327 GPIO expander signals mapped (ISP_RST via GPIO34; all others by label) |
| ToF Service Execution | `adi-tof.service` journal checked for power-sequence checkpoints |

### Output

- **Console**: colour-coded `[PASS]` / `[FAIL]` / `[WARN]` per check
- **Log file**: `/var/log/adi-patch-validation-<timestamp>.log`
- **Report**: `/boot/firmware/adi-patch-validation-report.txt`

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | All critical checks passed |
| `1` | One or more critical checks failed |

---

## Backup & Recovery

A timestamped backup of the original kernel and boot config is created automatically
at `/root/adi_tof_backup_<timestamp>/` before any files are modified.

To restore manually:

```bash
cp /root/adi_tof_backup_<timestamp>/kernel_adi.img /boot/firmware/
cp /root/adi_tof_backup_<timestamp>/config.txt.bak /boot/firmware/config.txt
sudo reboot
```
