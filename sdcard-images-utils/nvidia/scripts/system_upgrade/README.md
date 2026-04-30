# NVIDIA Jetson Orin Nano — ADI ToF System Upgrade

This directory contains scripts to apply and validate the ADI ToF ADSD3500 software
patch on an **NVIDIA Jetson Orin Nano** running JetPack 6.2.1.

---

## Scripts

| Script | Description |
|--------|-------------|
| `apply_patch.sh` | Applies kernel, device tree overlays, modules, and boot configuration for ADI ToF integration |
| `patch_validation.sh` | Validates that all patch components were applied correctly and hardware is detected |

---

## Requirements

- NVIDIA Jetson Orin Nano (JetPack 6.2.1)
- Root / sudo privileges
- Boot device: microSD card (`/dev/mmcblk0p1`) or NVMe SSD (PARTUUID-based)
- Software update package archive extracted in the same directory as `apply_patch.sh`

### Required archive contents

| File | Description |
|------|-------------|
| `Image` | ADI kernel image (`5.15.148-adi-tegra`) |
| `kernel_supplements.tbz2` | Kernel modules and firmware supplement archive |
| `tegra234-p3767-camera-p3768-*.dtbo` | Device tree overlay(s) |
| `sw-versions` | Software version manifest |
| `ubuntu_overlay/` | (Optional) systemd services, scripts, and Tools directory |

---

## Usage

### Step 1 — Transfer the update package

Using WinSCP (or `scp`) upload the software update package `.zip` to the Jetson
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
1. Detect the boot device type (microSD or NVMe SSD)
2. Back up the current kernel, DTBOs, and extlinux config to `/root/adi_tof_backup_<timestamp>/`
3. Install the ADI kernel image to `/boot/adi/Image`
4. Install device tree overlays to `/boot/adi/`
5. Extract kernel modules from `kernel_supplements.tbz2`
6. Update `/boot/extlinux/extlinux.conf` with ADI boot labels
7. Enable the `adi-tof` systemd service
8. Reboot automatically after 10 seconds (press **Ctrl+C** to cancel)

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
| System Information | Kernel version, Tegra platform, root filesystem |
| Boot Device Detection | microSD (`/dev/mmcblk0p1`) or NVMe SSD (PARTUUID) |
| Extlinux Configuration | Default label `ADSD3500-DUAL+ADSD3100`, required boot labels, correct root device |
| Kernel Files | `/boot/adi/Image`, backup kernel, `sw-versions` |
| Device Tree Overlays | All three ADSD3500/ADSD3100/AR0234 `.dtbo` files |
| Kernel Modules (disk) | `/lib/modules/5.15.148-adi-tegra/` directory and `.ko` files |
| Firmware Directory | `/lib/firmware/adi/` |
| Network Configuration | NetworkManager, systemd-network MTU 15000, DHCP lease time |
| Systemd Services | `adi-tof`, `jetson-performance`, `systemd-networkd` |
| Udev Rules | `/etc/udev/rules.d/99-gpio.rules` |
| Shell Scripts | `/usr/share/systemd/*.sh` |
| Camera Devices | V4L2 video devices present (`/dev/video*`) |
| Loaded Kernel Modules | `adsd3500` module loaded and in use (`lsmod`) |
| ADSD3500 Subdevice | ADSD3500 found in media graph via `media-ctl` |

### Hardware Checks

| Check | Description |
|-------|-------------|
| I2C Device Detection | I2C bus 2 scanned; devices at `0x38`, `0x58`, `0x68` |
| GPIO Label Detection | All ADSD3500 camera board GPIO signals found in debugfs |
| ToF Service Execution | `adi-tof.service` journal checked for power-sequence checkpoints |

### Output

- **Console**: colour-coded `[PASS]` / `[FAIL]` / `[WARN]` per check
- **Log file**: `/var/log/adi-patch-validation-<timestamp>.log`
- **Report**: `/boot/adi-patch-validation-report.txt`

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | All critical checks passed |
| `1` | One or more critical checks failed |

---

## Backup & Recovery

A timestamped backup of the original kernel, DTBOs, and extlinux config is created
automatically at `/root/adi_tof_backup_<timestamp>/` before any files are modified.

To restore manually:

```bash
cp /root/adi_tof_backup_<timestamp>/Image /boot/
cp /root/adi_tof_backup_<timestamp>/extlinux.conf.bak /boot/extlinux/extlinux.conf
sudo reboot
```
