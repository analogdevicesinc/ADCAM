# MAX96793 / MAX96792A GMSL3 Tunnel-Mode Init — `config_1_max96793_max96792a_init.py`

Python translation of [config_1.cpp](config_1.cpp) (a Maxim/ADI **CSIConfigurationTool**
export) that brings up a GMSL3 link between a **MAX96793** serializer and a
**MAX96792A** deserializer for single-VC RAW8 tunnel-mode MIPI CSI-2 passthrough
(Serializer Port B → Deserializer Pipe Y → Port A, 2-lane D-PHY @ 1500 Mbps/lane —
comfortably covers the ADSD3500's MIPI output rate, see "MIPI output frequency
macros" below), plus a MAX7320-driven MFP0 GPIO tunnel for camera sensor reset
control (see "Camera sensor reset / MFP0 GPIO tunnel" below).

## Table of contents

1. [Physical hardware setup](#1-physical-hardware-setup)
   1. [Required items](#11-required-items)
   2. [Hardware changes on the ADCAM REV A](#12-hardware-changes-on-the-adcam-rev-a)
   3. [Hardware changes on the AD-GMSL793MIPI-EVK](#13-hardware-changes-on-the-ad-gmsl793mipi-evk)
2. [Prerequisites](#2-prerequisites)
3. [Running sequence](#3-running-sequence)
4. [CLI usage reference](#4-cli-usage-reference)
5. [Script structure](#5-script-structure)
6. [What the script does, in order](#6-what-the-script-does-in-order)
7. [Device addressing](#7-device-addressing)
8. [Chip ID / revision readback](#8-chip-id--revision-readback-added-beyond-config_1cpp)
9. [Configuration functions](#9-configuration-functions-gmsl_conf_max96793_max96792a)
10. [Camera sensor reset / MFP0 GPIO tunnel (MAX7320)](#10-camera-sensor-reset--mfp0-gpio-tunnel-max7320)
11. [Lane-configuration debug tracing](#11-lane-configuration-debug-tracing)
12. [MIPI output frequency macros](#12-mipi-output-frequency-macros)
13. [I2C pass-through channel (serializer REG1)](#13-i2c-pass-through-channel-serializer-reg1)
14. [MIPI D-PHY configuration summary](#14-mipi-d-phy-configuration-summary)
15. [Delay markers](#15-delay-markers)
16. [Masked-write rows (`0x55` address)](#16-masked-write-rows-0x55-address)
17. [Deserializer (MAX96792A) register reference](#17-deserializer-max96792a-register-reference)
18. [Serializer (MAX96793) register reference](#18-serializer-max96793-register-reference)
19. [Serializer errata workarounds (`max96793-errata.pdf`)](#19-serializer-errata-workarounds-max96793-errata-pdf)
20. [Eye-opening monitor (EOM) threshold tuning (Link A)](#20-eye-opening-monitor-eom-threshold-tuning-link-a)
21. [Experimental tuning (deskew tunnel offset / DT filter / TUN_PKT_START_ADDR)](#21-experimental-tuning-deskew-tunnel-offset--dt-filter--tun_pkt_start_addr)
22. [Known issues / limitations](#22-known-issues--limitations)

## 1. Physical hardware setup

### 1.1. Required items

1. Jetson Orin Nano Developer Kit
2. [AD-GMSL793MIPI-EVK Evaluation Board](https://www.analog.com/en/resources/evaluation-hardware-and-software/evaluation-boards-kits/ad-gmsl793mipi-evk.html#eb-overview) (serializer, camera-side board)
3. [AD-GMSL792MIPI-EVK Evaluation Board](https://www.analog.com/en/resources/evaluation-hardware-and-software/evaluation-boards-kits/ad-gmsl792mipi-evk.html#eb-overview) (deserializer, host-side board)
4. ADSD3500 sensor module
5. 22-22 pin opposite side contacts FFC cable and 15-15 pin same side contacts FFC cable
6. [AD-GMSLCAMRPI-ADP# Evaluation Board](https://www.analog.com/en/resources/evaluation-hardware-and-software/evaluation-boards-kits/ad-gmslcamrpi-adp.html#eb-documentation) — serializer to sensor module converter board
7. FAKRA cable (GMSL3 link between deserializer and serializer)

```mermaid
flowchart LR
    A["Jetson Orin Nano\n(CAM0 MIPI CSI-2)"] -- "22<->22 pin FFC" --> B["MAX96792A Deserializer\n(host-side board, addr 0x2A)"]
    B -- "GMSL3 link\n(FAKRA/coax cable)" --> C["MAX96793 Serializer\n(camera-side board, addr 0x40/0x41)"]
    C -- "15<->15 pin FFC\n(same-side contacts)" --> E["AD-GMSLCAMRPI-ADP#\nconverter board"]
    E -- "22<->22 pin FFC\n(opposite-side contacts)" --> D["ADSD3500 sensor module\n(addr 0x38)"]
```

The ADSD3500 sits **behind the GMSL3 link** — its I2C address is only
reachable once the deserializer/serializer link trains and locks and the
serializer's I2C pass-through channel is enabled. This means this script
must run successfully **before** the ADSD3500's kernel driver can probe or
before any `nvarguscamerasrc`/GStreamer pipeline can stream.

### 1.2. Hardware changes on the ADCAM REV A

Removed R15. U6 pin 18 (previously connected to one side of R15) is now
connected directly to the TP4 (1.8V) power rail.

### 1.3. Hardware changes on the AD-GMSL793MIPI-EVK

The board ships with 4.7kΩ resistors populated at R9 and R11. These were
replaced with 32.4kΩ and 68.1kΩ, 0402 package, respectively.

## 2. Prerequisites

- Jetson Orin Nano running **NVIDIA JetPack SDK 7.2** (or a compatible
  L4T/JetPack release) with the `nv_adsd3500` kernel module available (built
  from the sensor vendor's BSP, not stock JetPack).
- Set the default boot label in `/boot/extlinux/extlinux.conf` to
  `ADSD3500+ADSD3100` so the Jetson boots with the correct ToF device tree
  overlay selected.
- Build the `tegra234-p3767-camera-p3768-adsd3500.dts` device tree source into
  a `.dtbo` and copy it to `/boot/adi` (see `dts_adsd3500_2500/` for the
  pre-built overlay used on this board).
- Python 3 and the `smbus2` package (see "Running sequence" below).
- Read/write access to the target I2C bus device node (`/dev/i2c-<bus>`,
  default bus `2`) — either run as `root`/`sudo` or add the invoking user to
  the `i2c` group.
- `i2c-tools` (`i2cdetect`, `i2cget`, `i2ctransfer`) installed, useful for
  independently confirming device addresses if this script reports a
  detection failure.
- [GMSL SerDes Public GUI Software](https://www.analog.com/en/resources/evaluation-hardware-and-software/embedded-development-software/software-download.html?swpart=SFW0019760J)
  (Maxim/ADI **CSIConfigurationTool**) — used to generate [config_1.cpp](config_1.cpp),
  the register-sequence export this script is translated from.

## 3. Running sequence

1. **Run this script** (as root, for raw I2C bus access), with the MIPI
   output speed set to 1500 Mbps/lane:
   ```bash
   sudo python3 config_1_max96793_max96792a_init.py --mipi-freq 1500
   ```
   It must complete with `GMSL configuration succeeded` (GMSL3 link trained
   and locked, serializer I2C pass-through channel enabled) before the
   sensor's I2C address is reachable at all.

   Confirm with `i2cdetect -y -r 2` (bus number must match the script's `bus`
   argument, default `2`) that every expected address now responds:

   ![i2cdetect -y -r 2 output](images/i2cdetect_bus2.png)

   | Address | Device | Meaning |
   |---|---|---|
   | `0x2a` | MAX96792A deserializer | `DESERIALIZER_ADDR` — always present once powered, independent of GMSL link state. |
   | `0x40` | MAX96793 serializer | One of `SERIALIZER_ADDR_CANDIDATES`; only reachable through the deserializer's I2C pass-through once the GMSL link has trained and locked. |
   | `0x38` with `UU` | ADSD3500 | `UU` (not a hex value) means `i2cdetect` found this address already claimed by a kernel driver (`nv_adsd3500`) rather than probing it directly — confirms the sensor's kernel driver is bound and actively using the address, not just that something ACKs there. |
   | `0x58`, `0x59`, `0x69` | ADCAM port expanders | `0x58` is the `MAX7320_ADDR` this script drives (MFP0 camera sensor reset tunnel — see "Camera sensor reset / MFP0 GPIO tunnel" below); `0x59` and `0x69` are two additional port-expander devices on the ADCAM board, not used/written by this script. |

2. **Enable ToF sensor power**:
   ```bash
   sudo python3 tof-power-en.py
   ```
   Rerun this command if it fails the first time with a permission error.
3. **Send the camera's init sequence**:
   ```bash
   ./ctrl_app infile.txt
   ```
4. **Set MIPI speed to 1.5 Gbps and FPS to 30**:
   ```bash
   ./ctrl_app set_mipi.txt
   ```
5. **Capture a frame**:
   ```bash
   sudo ./get_frame_RAW8_16D_16AB_8C_ADTF3066_mode0.sh
   ```
6. Only after all of the above succeed will `/dev/videoN` exist and the
   capture script produce a valid frame.

Requires `smbus2` (`pip install smbus2` / `python3 -m pip install --user smbus2`).

Exit status: `0` on success, `1` if serializer detection or any I2C transaction
fails (`GmslConfigError`) or the I2C bus itself errors out (`OSError`) — see
`main()`.

**Stream the camera** using the script matching the desired ADSD3500 mode
(RAW8 16D/16AB/8C, `get_frame_RAW8_16D_16AB_8C_ADTF3066_mode<N>.sh`):

- mode 0, 2560×640
```bash
sudo ./get_frame_RAW8_16D_16AB_8C_ADTF3066_mode0.sh
```
- mode 1, 2560×640
```bash
sudo ./get_frame_RAW8_16D_16AB_8C_ADTF3066_mode1.sh
```
- mode 3, 1280×320
```bash
sudo ./get_frame_RAW8_16D_16AB_8C_ADTF3066_mode3.sh
```

## 4. CLI usage reference

All flags below (except `bus`/`--log-level`, which apply to every run) put
the script into a **standalone, single-purpose mode that skips the full GMSL
bring-up** — only one flag is honored per run, in the priority order listed.
Flags marked "while streaming" require the sensor to actually be transmitting
frames during the check; coordinate two terminals manually (e.g. start a
streaming script from the "Running sequence" section above, then run the
check in a second terminal).

| Option | Values / Default | Purpose | Example |
|---|---|---|---|
| `bus` (positional) | int, default `2` | I2C bus number for every mode | `python3 config_1_max96793_max96792a_init.py 2` |
| `--log-level` | `ALL`\|`DEBUG`\|`INFO`\|`WARNING`\|`ERROR`, default `ALL` | Logging verbosity for every mode (`ALL` shows everything) | `python3 config_1_max96793_max96792a_init.py --log-level INFO` |
| `--mipi-freq` | `800`\|`1000`\|`1500`\|`2000`\|`2500`, default: script constant (`DESERIALIZER_MIPI_OUTPUT_FREQ`, currently 1000) | Override the deserializer's CSI-2 output speed (Mbps/lane) for this run only, without editing the script — runs the **full bring-up** at that speed | `python3 config_1_max96793_max96792a_init.py --mipi-freq 800` |
| `--set-camera-reset` | `0`\|`1` | Skip bring-up; drive the MAX7320 O0 output (MFP0, camera sensor reset) directly. Requires the MFP0 tunnel to already be configured (i.e. a prior full bring-up run) | `python3 config_1_max96793_max96792a_init.py --set-camera-reset 1` |
| `--check-mfp0-tunnel` | flag | Skip bring-up; read-only check that deserializer/serializer MFP0 `GPIO_IN` levels match (does NOT toggle the reset line — the kernel's `maxim,max7320` GPIO driver owns that) | `python3 config_1_max96793_max96792a_init.py --check-mfp0-tunnel` |
| `--check-serializer-mipi-rx` | flag | Skip bring-up; sample the serializer's MIPI RX packet/clock counters twice to confirm the sensor is sending data into the serializer (**while streaming**) | `python3 config_1_max96793_max96792a_init.py --check-serializer-mipi-rx` |
| `--check-deserializer-csi-tx` | flag | Skip bring-up; sample the deserializer's CSI-2 output packet counters twice to confirm Port A is transmitting toward the Jetson (**while streaming**) | `python3 config_1_max96793_max96792a_init.py --check-deserializer-csi-tx` |
| `--check-deserializer-link-rx` | flag | Skip bring-up; confirm the deserializer is receiving ANY packets over the GMSL tunnel at all, independent of CSI-2 output (**while streaming**) | `python3 config_1_max96793_max96792a_init.py --check-deserializer-link-rx` |
| `--check-deserializer-errors` | flag | Skip bring-up; read the deserializer's tunnel-mode error status flags (CRC/ECC errors, video pipe overflow) | `python3 config_1_max96793_max96792a_init.py --check-deserializer-errors` |
| `--check-deserializer-pipe-enables` | flag | Skip bring-up; read the deserializer's LIVE video pipe enable bits (`REG2 VID_EN_Y/Z`, `VIDEO_PIPE_EN`) instead of trusting documented reset defaults | `python3 config_1_max96793_max96792a_init.py --check-deserializer-pipe-enables` |
| `--tun-pkt-start-addr` | int (accepts `0xNN`), default: script constant (`0x00`) | Override `MIPI_TX54 TUN_PKT_START_ADDR` (0-255) for this run only — runs the **full bring-up** | `python3 config_1_max96793_max96792a_init.py --tun-pkt-start-addr 0x10` |
| `--deskew-period` | `1`\|`2`\|`4`\|`8`\|`16`\|`32`\|`64`\|`128`, off by default | Opt in to periodic lane-deskew recalibration every N frames (only applies when deskew is enabled, i.e. `--mipi-freq >= 1500`) — runs the **full bring-up** | `python3 config_1_max96793_max96792a_init.py --mipi-freq 1500 --deskew-period 32` |
| `--disable-ffe-short-channel` | flag, off by default | Apply `max96793-errata.pdf` Errata #5 (`RLMSCE.enffe=0`) — only use if this board's GMSL coax cable is confirmed <1dB insertion loss — runs the **full bring-up** | `python3 config_1_max96793_max96792a_init.py --disable-ffe-short-channel` |
| `--set-dt-filter` | int (accepts `0xNN`) | Skip bring-up; experimental — enable the serializer's DT filtering (`mem_dt1_selz`, `0x0318`) for the given CSI-2 datatype ID. Not expected to have any effect in tunneling mode | `python3 config_1_max96793_max96792a_init.py --set-dt-filter 0x2A` |
| `--clear-dt-filter` | flag | Skip bring-up; disable the serializer's DT filtering, restoring the reset default | `python3 config_1_max96793_max96792a_init.py --clear-dt-filter` |
| `--eom-min-threshold` | int, `0`-`127` | Skip bring-up; set Link A's eye-opening-monitor pass/fail threshold (`RLMS5.EOM_MIN_THR`); the full bring-up applies `DESERIALIZER_EOM_MIN_THR_DEFAULT` automatically at the end of every run — only pass this to test a different value | `python3 config_1_max96793_max96792a_init.py --eom-min-threshold 14` |
| `--check-eom-min-threshold` | flag | Skip bring-up; read back Link A's configured `EOM_MIN_THR` | `python3 config_1_max96793_max96792a_init.py --check-eom-min-threshold` |
| `--check-eom-result` | flag | Skip bring-up; read Link A's last completed eye-opening measurement (`RLMS7`) once and compare it against the configured `EOM_MIN_THR` | `python3 config_1_max96793_max96792a_init.py --check-eom-result` |
| `--deskew-tun-offset` | int (accepts `0xNN`), `0`-`255` | Skip bring-up; set `MIPI_TX53 DESKEW_TUN_OFFSET` (`0x0475`) — experimental, not applied automatically by bring-up | `python3 config_1_max96793_max96792a_init.py --deskew-tun-offset 0x08` |
| `--check-deskew-tun-offset` | flag | Skip bring-up; read back `MIPI_TX53 DESKEW_TUN_OFFSET` | `python3 config_1_max96793_max96792a_init.py --check-deskew-tun-offset` |

Typical bring-up-and-diagnose session (bring up the link, defaults to
1000 Mbps/lane; probe the sensor driver; then, if capture still fails, work
through the diagnostic chain in order — run the last command while streaming,
e.g. in a second terminal):
```bash
python3 config_1_max96793_max96792a_init.py
python3 config_1_max96793_max96792a_init.py --check-deserializer-pipe-enables
python3 config_1_max96793_max96792a_init.py --check-deserializer-errors
python3 config_1_max96793_max96792a_init.py --check-serializer-mipi-rx
```

## 5. Script structure

- **`SCRIPT_VERSION`** — a `"YYYY-MM-DD.N"` string bumped on every edit to this
  file, printed by `main()` at the very start of every run (`config_1_max96793_max96792a_init.py
  version 2026-10-20.1`) specifically so a stale copy on the target hardware is
  immediately obvious during debugging.
- **`GmslConfigError(RuntimeError)`** — raised by the low-level I2C helpers on
  any `OSError`, and by `_detect_serializer_addr()` if neither candidate
  address ACKs. `main()` catches it (and plain `OSError`) and returns exit
  code `1` with a clean log message instead of a raw traceback.
- **`_i2c_write(bus, addr, payload, description="")`** / **`_i2c_read_byte(bus, addr, reg_addr)`**
  — shared low-level helpers used by every register access in the script.
  `_i2c_read_byte` always uses a single repeated-START transaction (write the
  register address, then read — no STOP in between) since a STOP would reset
  the device's internal register pointer.
- **`main(argv=None)`** — `argparse`-based CLI: positional `bus` (default `2`)
  and `--log-level` (default `ALL`), calls `gmsl_conf_max96793_max96792a()`,
  and translates exceptions into an exit code. `--mipi-freq` overrides the CSI
  output speed for a full bring-up run. Several `--check-*` flags bypass full
  GMSL bring-up for standalone, read-mostly diagnostic use instead, and several
  more (`--eom-min-threshold`, `--deskew-tun-offset`, `--set-dt-filter`, etc.)
  expose experimental/tunable registers for manual testing — see the
  "CLI usage reference" table above for the complete list with examples.
- Every major function logs its own name prefixed with `>>>` as its first
  line (e.g. `>>> _configure_deserializer_link()`), so the console output
  doubles as a call trace on top of the register-level trace.

## 6. What the script does, in order

1. **Log the deserializer's address** (`DESERIALIZER_ADDR = 0x2A`, fixed — no
   probing needed) and **read its REG13/REG14** chip ID/revision.
2. **Detect the serializer.** Probes `SERIALIZER_ADDR_CANDIDATES = [0x40, 0x41]`
   (7-bit addresses derived from the MAX96793's 8-bit default write addresses
   `0x80`/`0x81`) with a dummy `write_byte_data`, and uses whichever one ACKs,
   then **reads its REG13/REG14**.
3. **Replay the `config_1.cpp` register sequence and set up the MFP0 GPIO
   tunnel** via seven purpose-specific functions called from
   `gmsl_conf_max96793_max96792a()` — see "Configuration functions" below.
4. **Read back link status** and **I2C pass-through state** — see
   "I2C pass-through channel" below.

## 7. Device addressing

| Constant | Value | Meaning |
|---|---|---|
| `SERIALIZER_ADDR_CANDIDATES` | `[0x40, 0x41]` | MAX96793 7-bit address; two candidates because the default address is pin-strap selectable (`0x80/0x81` 8-bit → `>>1`). |
| `DESERIALIZER_ADDR` | `0x2A` | MAX96792A 7-bit address (`0x54` 8-bit → `>>1`), per `config_1.cpp`'s "Device Address: 0x54" comment. |
| `DESERIALIZER_MASKED_ADDR` | `0x2A` | Same physical 7-bit address as above. `config_1.cpp` addresses REG1/REG4/REG6 as `0x55` (one more than `0x54`) with an extra trailing **mask byte** in the payload — flagged in code as needing hardware review (see "Masked-write rows" below), replayed verbatim as a 4-byte write to the same address rather than assumed to be a distinct device. |

## 8. Chip ID / revision readback (added beyond `config_1.cpp`)

Both the MAX96793 and MAX96792A expose the same register layout for
identification, read via the shared `_i2c_read_byte()` helper's single
repeated-START I2C transaction (write the 2-byte register address, then read
1 byte — **no STOP** in between, or the device's internal register pointer
resets):

| Register | Address | Field | Notes |
|---|---|---|---|
| REG13 | `0x0D` | `DEV_ID[7:0]` | Read-only. `0xB7` = MAX96793, `0xB6` reset (`0xB` family nibble) = MAX96792A. |
| REG14 | `0x0E` | `DEV_REV[3:0]` | Read-only silicon revision ID; meaning is defined only in ADI's separate errata sheet for each part, not the datasheet. |

- `read_serializer_revision(bus, serializer_addr)` reads the MAX96793's REG13/REG14,
  warns if `DEV_ID != 0xB7`.
- `read_deserializer_revision(bus)` reads the MAX96792A's REG13/REG14, warns if
  the `DEV_ID` upper nibble isn't `0xB`, and maps `DEV_REV` to a known silicon
  revision via `DESERIALIZER_SILICON_REVISIONS` (currently `0x6 → "D-0B"`,
  confirmed against ADI's MAX96792A DEV_REV=6 errata sheet).
- Both helpers retry up to 3 times (5/20/50 msec increasing delay) on an `0xFF`
  read (a common NACK'd/floating-bus symptom right after power-up) before
  logging/returning the value.

**Known anomaly:** on this board, `DEV_ID` (REG13) reads `0xFF` on the
deserializer while `DEV_REV` (REG14) reads a valid, errata-sheet-confirmed
value (`0x6` = D-0B) from the same device — the chip is clearly a real,
responding MAX96792A, but only that one register misbehaves. This was checked
against ADI's D-0B errata sheet and is **not** a documented erratum; treat it
as a hardware/bus item to investigate independently (e.g. `i2ctransfer`/`i2cget`
outside Python), not a script bug — the serializer's equivalent read (`DEV_ID
0xB7`, `DEV_REV 0x6` = C-0D) works perfectly, confirming the read mechanism
itself is correct.

## 9. Configuration functions (`gmsl_conf_max96793_max96792a`)

`gmsl_conf_max96793_max96792a(bus_number)` is a thin orchestrator: it opens the
I2C bus, detects/reads both chips (see above), then calls **seven**
purpose-specific functions **in the exact order the hardware requires**,
mirroring the identical "Table 2. GMSL3 SerDes Start-Up Sequence" (21 steps)
shared by both `max96792a-device-specific-user-guide.pdf` (DES) and
`max96793-device-specific-user-guide.pdf` (SER). Register writes mirror
[config_1.cpp](config_1.cpp) row-by-row using the same conversion rules as
`rpi_adaptr_max96717_max96724_tunnel_porta.cpp` (a companion reference file,
not present in this workspace — see "Known issues / limitations" below): drop
the `0x04` write opcode, shift the 8-bit device address right by 1 bit, and
pass the remaining bytes as the `i2c_msg.write()` payload.

| Step | Description | Function |
|---|---|---|
| 0-2 | Power ramp-up / PWDNB release / CFG-pin link auto-config | external (power script) / hardware |
| 3-4 | Link configuration, GMSL link lock established | `_configure_deserializer_link(bus)` [DES] |
| 5-6 | I2C rate adjustment / SER address reassignment | not needed (default rate, single serializer) |
| 7 | Disable DES CSI output | `_configure_deserializer_link(bus)` [DES] |
| 8 | DES errata settings | revision read/logged only (`read_deserializer_revision()`) |
| 9 | DES MIPI TX configuration | `_configure_deserializer_mipi_output(bus)` [DES] |
| 10 | DES GPIO and other feature configuration | `configure_mfp0_gpio_tunnel(bus, serializer_addr)` [DES] |
| 11 | DES interrupt handling (ERRB)/ASIL | not implemented |
| 12 | SER errata settings | `_apply_serializer_errata_workarounds(bus, serializer_addr, dev_rev)` [SER] — see "Serializer errata workarounds" below (Errata #7 applied in step 13) |
| 13 | SER MIPI RX configuration | `_configure_serializer_mipi_input(bus, serializer_addr)` [SER] |
| 14 | SER GPIO and other feature configuration | `configure_mfp0_gpio_tunnel(bus, serializer_addr)` [SER] |
| 15 | SER interrupt handling (ERRB)/ASIL | not implemented |
| 16-17 | `RESET_LINK`=1 then `RESET_LINK`=0 | `_reset_and_relock_link(bus)` [DES] |
| 18 | DES enable CSI output | `_reset_and_relock_link(bus)` [DES] |
| 19-20 | Enable DES/SER register CRC safety (optional) | not implemented |
| 21 | Start video source | `_enable_serializer_video_output(bus, serializer_addr)` [SER] |

1. **`_configure_deserializer_link(bus)`** — deserializer only:
   - Disable CSI output (`BACKTOP12.CSI_OUT_EN = 0`) before reconfiguring anything.
   - Disable `AUTO_LINK`, set `RX_RATE`/`GMSL3_A`/`I2CSEL` (the masked-write
     REG1/REG4/REG6 rows), enable `LINK_EN_A`, then set `LINK_CFG`/`RESET_ONESHOT`
     to force a link reset — followed by a **120 msec delay** for the link to relock.
   - Re-enable/adjust `DIS_REM_CC` on REG1/REG3, followed by the tool's
     `~5 usec` (rounded up to ~1 msec) delay.
2. **`_configure_deserializer_mipi_output(bus)`** — deserializer only:
   - Force `REG2 VID_EN_Y`/`VID_EN_Z` and `VIDEO_PIPE_EN` enabled explicitly
     (not trusted at their documented reset defaults — see "Known anomaly"
     under "Chip ID / revision readback" above), then map Pipe Y to Link A
     stream 0.
   - MIPI D-PHY config: 1x4 port mode, Port A 2-lane count, PHY0/PHY1 lane
     maps and polarity — logs a `DEBUG`-level decoded lane map.
   - Coarse CSI output frequency set (soft-reset DPLL → write frequency
     divider via `DESERIALIZER_MIPI_FREQ_*` macros → release soft-reset, see
     "MIPI output frequency macros" below) and standby unused PHY2/PHY3.
   - Lane deskew (`DESKEW_INIT`/`DESKEW_PER`, `MIPI_TX3`/`MIPI_TX4`): auto-enabled
     only when the selected output speed is `>= 1500` Mbps/lane
     (`DESERIALIZER_DESKEW_REQUIRED_THRESHOLD_MBPS`) — required at that rate or
     the Jetson's D-PHY RX can fail to lock entirely, not just see corrupted
     data; periodic recalibration stays off unless `--deskew-period` opts in.
   - Tunnel mode: route Pipe Y to tunnel destination pipe 1, enable tunnel
     mode, and write `MIPI_TX54 TUN_PKT_START_ADDR` (`--tun-pkt-start-addr`
     override, reset default `0x00` otherwise).
3. **`configure_mfp0_gpio_tunnel(bus, serializer_addr)`** — both chips: routes
   the camera sensor's reset pin over GMSL before MIPI input starts (see
   "Camera sensor reset / MFP0 GPIO tunnel" below for the full mechanism).
   Called once but configures both ends (Start-Up Sequence steps 10 and 14).
4. **`_apply_serializer_errata_workarounds(bus, serializer_addr, dev_rev)`** —
   serializer only: applies `max96793-errata.pdf` Errata #5/#6 (`RLMSCE`,
   `0x14CE`) — see "Serializer errata workarounds" below.
5. **`_configure_serializer_mipi_input(bus, serializer_addr)`** — serializer only:
   - Disable video transmission (`VID_TX_EN_Z = 0`) before changing MIPI settings.
   - Apply Errata #7 (`mipi_rx_reset` toggle, `MIPI_RX0` bit 3) — see
     "Serializer errata workarounds" below.
   - MIPI D-PHY config: 1x4 port mode, non-continuous clock enabled
     (`mipi_noncont_clk_en`, matches the ADSD3500's actual clock mode and the
     Jetson DT's `discontinuous_clk="yes"`), tunnel mode enabled, Port B 2-lane
     count with `ctrl1_deskewen` auto-enabled at `>= 1500` Mbps/lane (mirrors
     the deserializer-side deskew threshold, since tunnel mode passes the
     sensor's real bit rate through unmodified), PHY1/PHY2 lane maps and
     polarity — logs a `DEBUG`-level decoded lane map (see "Lane-configuration
     debug tracing" below).
   - Controller→pipe mapping: start Port B video (`FRONTTOP_0`, `FRONTTOP_9`),
     select pipe Z (`CFGV__VIDEO_Z`).
6. **`_reset_and_relock_link(bus)`** — deserializer only (Start-Up Sequence
   steps 16-18): `RESET_LINK=1` then `RESET_LINK=0` (120 msec delay each) so
   the SER/DES MIPI TX/RX configuration above actually takes effect through a
   full data-path reset, then **re-enable CSI output**. Distinct from the
   self-clearing `RESET_ONESHOT` pulse used earlier just to establish the
   initial link lock.
7. **`_enable_serializer_video_output(bus, serializer_addr)`** — serializer
   only: re-enable video transmission (`VID_TX_EN_Z = 1`) — video is now
   flowing end-to-end.

After all seven functions run, `gmsl_conf_max96793_max96792a()` also calls
`set_eom_min_threshold_link_a(bus, DESERIALIZER_EOM_MIN_THR_DEFAULT)` —
**deliberately last, after `_reset_and_relock_link()`**, since `RESET_LINK`
reverts `RLMS5` back to its hardware reset default. See "Eye-opening monitor
(EOM) threshold tuning" below.

Every write is followed by a `logging.info(...)` call carrying the original
`.cpp` comment (or an equivalent description for writes added beyond
`config_1.cpp`), so the script's console output doubles as a register-level
trace of the bring-up sequence. Pass `--log-level DEBUG` (or the default
`ALL`) to also see each function's Start-Up-Sequence step number logged via
`logging.debug(...)`.

## 10. Camera sensor reset / MFP0 GPIO tunnel (MAX7320)

Added beyond `config_1.cpp`: routes the camera sensor's reset GPIO over the
GMSL link so it can be driven from the host, since the sensor's reset pin is
not directly wired to the Jetson — it's driven by a **MAX7320** I2C GPO port
expander on the host side, tunneled across GMSL to the camera module:

```
Orin Nano (I2C) -> MAX7320 O0 -> MAX96792A MFP0 -> MAX96793 MFP0 -> camera sensor reset GPIO
```

- **`MAX7320_ADDR = 0x58`** — address-only I2C GPO device (no internal register
  pointer; reads/writes go directly to the 8-bit output latch). `MAX7320_MFP0_BIT`
  (`0x01`) is O0, hardwired to MFP0.
- **`configure_mfp0_gpio_tunnel(bus, serializer_addr, channel_id=0)`** — one-time
  setup, called from `gmsl_conf_max96793_max96792a()`: tri-states the
  deserializer's own MFP0 driver (`GPIO_OUT_DIS=1`) so it doesn't fight the
  MAX7320's external drive, and forwards the externally-driven pin level over
  GMSL (`GPIO_TX_EN=1`); the serializer's MFP0 receives that value
  (`GPIO_RX_EN=1`) and drives it out on its own pin (`GPIO_OUT_DIS=0`), wired to
  the sensor's reset GPIO.
- **`set_camera_sensor_reset(bus, enable)`** — a read-modify-write on the
  MAX7320's output latch. Requires `configure_mfp0_gpio_tunnel()` to have run
  first. Exposed standalone via `--set-camera-reset {0,1}`, but **not called
  automatically** anywhere else in this script: on real hardware the kernel's
  `maxim,max7320` GPIO driver (bound to the ADSD3500's `reset-gpios` in the
  `.dts`) owns actual reset control once loaded, and userspace writes here
  would race with it. Only use this flag for manual bring-up/debugging before
  that driver is bound.
- **`read_mfp0_tunnel_status(bus, serializer_addr)`** / **`check_mfp0_tunnel(bus, serializer_addr)`**
  — read-only verification helpers, since GMSL GPIO tunneling has no "link
  established" status bit; it just continuously forwards the sampled pin
  level. They compare the read-only `GPIO_IN` bit (bit 3, `0x08`) on both ends
  — if the tunnel is forwarding correctly, deserializer and serializer
  `GPIO_IN` always match. `check_mfp0_tunnel()` only reads the current level
  on both ends (it does **not** call `set_camera_sensor_reset()`, to avoid
  fighting the kernel driver's control of the reset line). Exposed standalone
  via `--check-mfp0-tunnel`.

| Register | Address | Field | Notes |
|---|---|---|---|
| Deserializer GPIO_A (GPIO 0) | `0x02B0` | bits: `GPIO_OUT`(4) `GPIO_IN`(3, RO) `GPIO_RX_EN`(2) `GPIO_TX_EN`(1) `GPIO_OUT_DIS`(0) | Tunnel setup: `GPIO_TX_EN=1 GPIO_RX_EN=0 GPIO_OUT_DIS=1` |
| Deserializer GPIO_B (GPIO 0) | `0x02B1` | bits `[4:0]`: `GPIO_TX_ID` | Set to `channel_id` (default `0`) |
| Serializer GPIO_A (GPIO 0) | `0x02BE` | same bit layout as deserializer GPIO_A | Tunnel setup: `GPIO_RX_EN=1 GPIO_TX_EN=0 GPIO_OUT_DIS=0` |
| Serializer GPIO_C (GPIO 0) | `0x02C0` | bits `[4:0]`: `GPIO_RX_ID` | Set to `channel_id` (default `0`) |
| MAX7320 output latch | `0x58` (no register addr) | bit 0 = O0/MFP0 | Read-modify-write via `set_camera_sensor_reset()` |

## 11. Lane-configuration debug tracing

Both `_configure_serializer_mipi_input()` and `_configure_deserializer_mipi_output()`
decode their own lane-count/lane-map register constants and emit a
`logging.debug(...)` summary (visible at `--log-level DEBUG` or the default
`ALL`), filtered to only show mappings whose destination lane index is within
the active lane count — so a 2-lane configuration doesn't print misleading
Lane2/Lane3 entries that are configured in the register but not actually
enabled:

```
DEBUG - Serializer MIPI input lane config: 2 active lane(s), Sensor->Serializer map: Lane0<-Sensor0 Lane1<-Sensor1
DEBUG - Deserializer MIPI output lane config: 2 active lane(s), PHY->Port A map: PHY1.D0->Lane0 PHY1.D1->Lane1
```

## 12. MIPI output frequency macros

`DESERIALIZER_MIPI_FREQ_REG` (`BACKTOP25`, `0x0320`) plus
`DESERIALIZER_MIPI_FREQ_PREDEF_EN_BIT` (bit 5, enables the predefined-frequency
field) and named speed codes, decoded from `max96792a.pdf`'s
`phy1_csi_tx_dpll_predef_freq[4:0]` table:

| Macro | Value | Speed |
|---|---|---|
| `DESERIALIZER_MIPI_FREQ_800MBPS` | `0x08` | 800 Mbps/lane (original `config_1.cpp` value) |
| `DESERIALIZER_MIPI_FREQ_1000MBPS` | `0x0A` | 1000 Mbps/lane (used by the script — comfortably exceeds the ADSD3500's MIPI output rate) |
| `DESERIALIZER_MIPI_FREQ_1500MBPS` | `0x0F` | 1500 Mbps/lane |
| `DESERIALIZER_MIPI_FREQ_2000MBPS` | `0x14` | 2000 Mbps/lane |
| `DESERIALIZER_MIPI_FREQ_2500MBPS` | `0x19` | 2500 Mbps/lane |

The actual register write is
`DESERIALIZER_MIPI_FREQ_PREDEF_EN_BIT | DESERIALIZER_MIPI_FREQ_1000MBPS` = `0x2A`
(originally `0x28`/800 Mbps to match `config_1.cpp` byte-for-byte, since
changed for the ADSD3500 — see "MIPI D-PHY configuration summary" below); swap
in a different `_MBPS` macro to change the CSI output speed.

## 13. I2C pass-through channel (serializer REG1)

Added beyond `config_1.cpp`: helpers to bridge a downstream I2C device (e.g. a
port expander) wired to the serializer's local I2C pins onto the GMSL control
channel, so it becomes reachable from the host.

- `SERIALIZER_REG1` (`0x0001`) holds `IIC_1_EN` (bit 6, Channel 1: `SDA1/RX1`,
  `SCL1/TX1`) and `IIC_2_EN` (bit 7, Channel 2: `SDA2/RX2`, `SCL2/TX2`) — both
  disabled by default in `config_1.cpp`.
- `read_serializer_i2c_passthrough(bus, serializer_addr)` reads REG1 and logs
  both bits' state.
- `_set_serializer_passthrough_bit(...)` performs a **read-modify-write** on
  REG1 (it also holds `DIS_LOCAL_CC`/`DIS_REM_CC`/`TX_RATE`/`RX_RATE`, so a
  blind overwrite would clobber them).
- `enable_serializer_i2c_passthrough_channel1(bus, serializer_addr, enable=True)`
  / `enable_serializer_i2c_passthrough_channel2(...)` set/clear the
  corresponding bit and log the resulting REG1 value.
- `gmsl_conf_max96793_max96792a()` calls `enable_serializer_i2c_passthrough_channel1()`
  then `read_serializer_i2c_passthrough()` at the end of the run, purely to
  confirm the channel got enabled — it's not required for the base
  video-only bring-up.

## 14. MIPI D-PHY configuration summary

Pulled together from the individual register writes in
`gmsl_conf_max96793_max96792a()` — two independent D-PHY links: CSI-2 **input**
into the serializer (from the camera module) and CSI-2 **output** from the
deserializer (to the Jetson host).

### Serializer (MAX96793) — CSI-2 input, Port B

| Parameter | Value | Source write |
|---|---|---|
| Port configuration | 1x4 | `MIPI_RX0` (`0x0330`) = `0x00` |
| Clock mode | Non-continuous (`mipi_noncont_clk_en`) — matches the ADSD3500's actual clock mode and the Jetson DT's `discontinuous_clk="yes"` | `MIPI_RX0` (`0x0330`) bit 6 |
| MIPI RX reset (Errata #7) | Asserted then released, once per run, before the rest of MIPI input config | `MIPI_RX0` (`0x0330`) bit 3 |
| Active port | Port B | `MIPI_RX1` (`0x0331`) = `0x10` |
| Lane count | 2 | `MIPI_RX1` (`0x0331`) = `0x10` (`ctrl1_num_lanes`) |
| Lane deskew (`ctrl1_deskewen`) | Auto-enabled only when `DESERIALIZER_MIPI_OUTPUT_FREQ >= 1500` Mbps/lane (tunnel mode passes the sensor's real bit rate through unmodified) | `MIPI_RX1` (`0x0331`) bit 6 |
| Lane map | PHY1: D0→Lane 2, D1→Lane 3 | `MIPI_RX2` (`0x0332`) = `0xE0` |
| Lane map | PHY2: D0→Lane 0, D1→Lane 1 | `MIPI_RX3` (`0x0333`) = `0x04` |
| Polarity | PHY1 D0/D1: Normal | `MIPI_RX4` (`0x0334`) = `0x00` |
| Polarity | PHY2 D0/D1 + clock: Normal | `MIPI_RX5` (`0x0335`) = `0x00` |
| Tunnel mode | Enabled | `MIPI_RX_EXT:EXT11` (`0x0383`) = `0x80` |
| Speed | Not set here — GMSL3 forward link is a fixed 12Gbps PAM4 rate set by a hardware resistor strap (no MIPI RX speed register in `config_1.cpp`) | — |

### Deserializer (MAX96792A) — CSI-2 output, Port A

| Parameter | Value | Source write |
|---|---|---|
| Port configuration | 2 (1x4) | `MIPI_PHY0` (`0x0330`) = `0x04` |
| Active port | Port A | `MIPI_TX10` (`0x044A`) = `0x50` |
| Lane count | 2 | `MIPI_TX10` (`0x044A`) = `0x50` (`CSI2_LANE_CNT`) |
| Lane map | PHY0: D0→Lane 2, D1→Lane 3 | `MIPI_PHY3` (`0x0333`) = `0x4E` |
| Lane map | PHY1: D0→Lane 0, D1→Lane 1 | `MIPI_PHY3` (`0x0333`) = `0x4E` |
| Polarity | PHY0/PHY1 lanes + clock: Normal | `MIPI_PHY5` (`0x0335`) = `0x00` |
| Unused PHYs | PHY2/PHY3 put in standby (only PHY0/PHY1 drive Port A) | `MIPI_PHY2` (`0x0332`) = `0x34` |
| Speed | `DESERIALIZER_MIPI_OUTPUT_FREQ` (script default `1000` Mbps/lane; `--mipi-freq 1500` is the currently recommended Running sequence value), coarse frequency divider set while the DPLL is held in soft-reset | `DPLL_0` (`0x1D00`) = `0xF4` → `0x0320` = (`PREDEF_EN`\|freq code) → `DPLL_0` = `0xF5` |
| Lane deskew (`DESKEW_INIT`/`DESKEW_PER`) | Auto-enabled only when the selected speed is `>= 1500` Mbps/lane; periodic recalibration stays off unless `--deskew-period` opts in | `MIPI_TX3` (`0x0443`) / `MIPI_TX4` (`0x0444`) |
| Tunnel routing | Pipe Y → tunnel destination pipe 1, tunnel mode enabled | `MIPI_TX52` (`0x0474`) = `0x09` |
| Tunnel packet start address | `0x00` reset default, overridable via `--tun-pkt-start-addr` | `MIPI_TX54` (`0x0476`) |

The two D-PHY links are independent: the serializer's Port B (2 lanes) simply
tunnels raw GMSL3 payload through to the deserializer, which re-emits it on
its own Port A (2 lanes, at `DESERIALIZER_MIPI_OUTPUT_FREQ`) toward the host —
lane counts happen to match on both sides in this configuration but are set by
separate registers on each chip. At `>= 1500` Mbps/lane, lane deskew is
required and auto-enabled on **both** sides (serializer `ctrl1_deskewen` and
deserializer `DESKEW_INIT`) since the same bit rate passes through unmodified.

## 15. Delay markers

`config_1.cpp` encodes delays as `0x00,<value>,` rows where `<value>` is the
delay in milliseconds (e.g. `0x78` = 120 → "120 msec delay"). The script
converts these directly to `time.sleep(value / 1000.0)`.

## 16. Masked-write rows (`0x55` address)

Three rows in `config_1.cpp` (REG1/REG4/REG6) target device address `0x55`
instead of `0x54` and carry an extra trailing byte (e.g.
`0x04,0x55,0x00,0x01,0x03,0x03`). `0x55 >> 1` resolves to the same 7-bit
address as `0x54` (`0x2A`), so the script currently replays these as a single
4-byte block write (`[reg_hi, reg_lo, value, mask]`) to `DESERIALIZER_ADDR`.
This byte-for-byte replay matches the source table exactly, but the real
hardware semantics of the trailing mask byte (a genuine masked
read-modify-write vs. an artifact of the export tool) haven't been confirmed
against the MAX96792A datasheet/errata — worth reviewing if these three
registers don't take effect as expected on real hardware.

## 17. Deserializer (MAX96792A) register reference

Every register the script touches on the deserializer, in execution order.
Addresses are the full 16-bit `[reg_hi, reg_lo]` value used in the
`i2c_msg.write()` payload; "masked write" rows go to `DESERIALIZER_MASKED_ADDR`
(`0x55`) with a trailing mask byte instead of `DESERIALIZER_ADDR` (`0x54`).

| Register | Address | Value | Meaning |
|---|---|---|---|
| REG13 (read) | `0x000D` | — (read-only) | `DEV_ID`; expected `0xB6` (`0xB` family nibble) — currently reads `0xFF` on this board, see "Known anomaly" above |
| REG14 (read) | `0x000E` | — (read-only) | `DEV_REV`; `0x6` confirmed = silicon revision D-0B |
| BACKTOP12 | `0x0313` | `0x00` | `CSI_OUT_EN`: CSI output disabled |
| TCTRL:CTRL0 | `0x0010` | `0x01` | `AUTO_LINK`: Disabled |
| DEV:REG1 (masked) | `0x0001` | `0x03`, mask `0x03` | `RX_RATE` = `0b11` (12Gbps, GMSL3-only rate) |
| DEV:REG4 (masked) | `0x0004` | `0x40`, mask `0x40` | `GMSL3_A`: Enabled (Link A = GMSL3, not GMSL2) |
| DEV:REG6 (masked) | `0x0006` | `0x10`, mask `0x10` | `I2CSEL`: I2C |
| GMSL1_COMMON:GMSL1_EN | `0x0F00` | `0x01` | `LINK_EN_A`: Enabled, `LINK_EN_B`: Disabled |
| TCTRL:CTRL0 | `0x0010` | `0x21` | `LINK_CFG`=`0x1`, `RESET_ONESHOT` (Link A): Activated — forces link reset/relock |
| *(120 msec delay for link to relock)* | | | |
| DEV:REG1 | `0x0001` | `0x03` | `DIS_REM_CC`: Enabled |
| DEV:REG3 | `0x0003` | `0x57` | `DIS_REM_CC_B`: Disabled |
| *(~5 usec delay, rounded to ~1 msec)* | | | |
| GPIO_A (GPIO 0) | `0x02B0` | computed | `GPIO_TX_EN=1 GPIO_RX_EN=0 GPIO_OUT_DIS=1` (tri-state local driver, forward MAX7320-driven level over GMSL) — from `configure_mfp0_gpio_tunnel()` |
| GPIO_B (GPIO 0) | `0x02B1` | `0x00` | `GPIO_TX_ID`: 0 (tunnel channel) |
| DEV:REG2 | `0x0002` | forced `VID_EN_Y`/`VID_EN_Z` bits set | Not trusted at documented reset defaults — see "Known anomaly" above |
| VIDEO_PIPE_EN | `0x0160` | forced both pipe-enable bits set | Same "don't trust reset defaults" reasoning as REG2 |
| VIDEO_PIPE_SEL | `0x0161` | `0x30` | `VIDEO_PIPE_SEL_Y` (`STR_SELY`): Link A Stream Id 0 |
| MIPI_PHY0 | `0x0330` | `0x04` | `phy_4x2` (Port Configuration): 2 (1x4) |
| MIPI_TX10 | `0x044A` | `0x50` | `CSI2_LANE_CNT` (Port A Lane Count): 2 |
| MIPI_PHY3 | `0x0333` | `0x4E` | Lane map: PHY0 D0/D1, PHY1 D0/D1 |
| MIPI_PHY5 | `0x0335` | `0x00` | Polarity map: PHY0/PHY1 lanes + clock, all Normal |
| DPLL_0 | `0x1D00` | `0xF4` | `config_soft_rst_n` (PHY1): `0x0` — assert DPLL soft reset |
| DPLL_0 | `0x1D00` | `0xF4` | Repeated write (no unique field change in source table) |
| *(coarse frequency divider)* | `0x0320` | `PREDEF_EN`\|freq code | Sets CSI output frequency: `DESERIALIZER_MIPI_OUTPUT_FREQ` Mbps/lane (`--mipi-freq` override) |
| DPLL_0 | `0x1D00` | `0xF5` | `config_soft_rst_n` (PHY1): `0x1` — release DPLL soft reset |
| MIPI_TX3 (`DESKEW_INIT`) | `0x0443` | auto-enabled only `>= 1500` Mbps/lane | Required at that rate or the Jetson D-PHY RX can fail to lock |
| MIPI_TX4 (`DESKEW_PER`) | `0x0444` | off unless `--deskew-period` | Periodic recalibration, opt-in only |
| MIPI_PHY2 | `0x0332` | `0x34` | `phy_Stdby_n`: put unused PHY2/PHY3 in standby |
| MIPI_TX52 | `0x0474` | `0x09` | `TUN_DEST` (Pipe Y): 1, `TUN_EN`: Enabled |
| MIPI_TX54 | `0x0476` | `0x00` (reset default) | `TUN_PKT_START_ADDR`, overridable via `--tun-pkt-start-addr` |
| TCTRL:CTRL0 | `0x0010` | `RESET_LINK` bit set | `RESET_LINK`: Activated — forces a full data-path reset (Start-Up Sequence step 16) |
| *(120 msec delay for link to relock)* | | | |
| TCTRL:CTRL0 | `0x0010` | `RESET_LINK` bit cleared | `RESET_LINK`: Released (Start-Up Sequence step 17) |
| *(120 msec delay for link to relock)* | | | |
| BACKTOP12 | `0x0313` | `0x02` | `CSI_OUT_EN`: CSI output enabled (Start-Up Sequence step 18) |
| RLMS5 (Link A) | `0x1405` | `DESERIALIZER_EOM_MIN_THR_DEFAULT` (`0x0E`) | `EOM_MIN_THR`: applied last (after `RESET_LINK`, which reverts it to its `0x10` reset default) — see "Eye-opening monitor (EOM) threshold tuning" below |
| REG4 (read) | `0x0004` | — | Link status readback: `GMSL3_A` (bit 6) |
| REG1 (read) | `0x0001` | — | Link status readback: `RX_RATE` (bits `[1:0]`) |
| CTRL3 (read) | `0x0013` | — | Link status readback: `LOCKED` (bit 3), `CMU_LOCKED` (bit 1) |

## 18. Serializer (MAX96793) register reference

Every register the script touches on the serializer, in execution order.
Addresses are the full 16-bit `[reg_hi, reg_lo]` value; all writes go to
whichever address in `SERIALIZER_ADDR_CANDIDATES` ACKed during detection.

| Register | Address | Value | Meaning |
|---|---|---|---|
| REG13 (read) | `0x000D` | — (read-only) | `DEV_ID`; `0xB7` = MAX96793 (confirmed) |
| REG14 (read) | `0x000E` | — (read-only) | `DEV_REV`; `0x6` confirmed = silicon revision C-0D |
| RLMSCE | `0x14CE` | `enminus_man`/`enminus_reg` always set; `enffe` cleared only with `--disable-ffe-short-channel` | Errata #5/#6 — applied right after revision read, before the rest of bring-up — see "Serializer errata workarounds" below |
| GPIO_A (GPIO 0) | `0x02BE` | computed | `GPIO_RX_EN=1 GPIO_TX_EN=0 GPIO_OUT_DIS=0` (receive tunneled level, drive sensor reset pin) — from `configure_mfp0_gpio_tunnel()` |
| GPIO_C (GPIO 0) | `0x02C0` | `0x00` | `GPIO_RX_ID`: 0 (tunnel channel) |
| DEV:REG2 | `0x0002` | `0x03` | `VID_TX_EN_Z`: Disabled (before changing MIPI settings) |
| MIPI_RX0 | `0x0330` | `0x08` then `0x00` | `mipi_rx_reset` (Errata #7): Asserted then Released |
| MIPI_RX0 | `0x0330` | `0x40` | Port Configuration: 1x4 \| `mipi_noncont_clk_en`: Non-continuous clock |
| MIPI_RX_EXT:EXT11 | `0x0383` | `0x80` | `Tun_Mode`: Tunnel Mode Enabled |
| MIPI_RX1 | `0x0331` | `0x10` (`+0x40` if deskew enabled) | `ctrl1_num_lanes` (Port B Lane Count): 2 \| `ctrl1_deskewen`: auto-enabled only `>= 1500` Mbps/lane |
| MIPI_RX2 | `0x0332` | `0xE0` | Lane map: PHY1 D0 → Lane 2, D1 → Lane 3 |
| MIPI_RX3 | `0x0333` | `0x04` | Lane map: PHY2 D0 → Lane 0, D1 → Lane 1 |
| MIPI_RX4 | `0x0334` | `0x00` | Polarity map: PHY1 lanes Normal |
| MIPI_RX5 | `0x0335` | `0x00` | Polarity map: PHY2 lanes + clock Normal |
| FRONTTOP_0 | `0x0308` | `0x64` | `CLK_SELZ`: Port B, `START_PORTB`: Enabled |
| FRONTTOP_9 | `0x0311` | `0x40` | `START_PORTBZ`: Start Video |
| CFGV__VIDEO_Z:TX3 | `0x005B` | `0x00` | `TX_STR_SEL` (Pipe Z): `0x0` |
| DEV:REG2 | `0x0002` | `0x43` | `VID_TX_EN_Z`: Enabled — video now flowing |
| REG1 (read) | `0x0001` | — | I2C pass-through readback: `IIC_1_EN` (bit 6), `IIC_2_EN` (bit 7) |
| REG1 (read-modify-write) | `0x0001` | sets bit 6 | `enable_serializer_i2c_passthrough_channel1()`: bridges local I2C Channel 1 (`SDA1/SCL1`) onto the GMSL control channel, needed to reach downstream I2C devices (e.g. a port expander) wired to the serializer's local bus — not required for the base video-only bring-up, disabled by default in `config_1.cpp` |

## 19. Serializer errata workarounds (`max96793-errata.pdf`)

`_apply_serializer_errata_workarounds(bus, serializer_addr, dev_rev)` applies
three workarounds documented against `DEV_REV=6` (logs a warning, but still
applies them, if a different revision is read):

- **Errata #5 — "GMSL3 PAM4 short-channel operation requires register write
  for robust operation"**: `RLMSCE.enffe` (bit 0, reset default `1`/Enabled).
  Disabling FFE is only required/recommended on channels with **<1dB
  insertion loss** (a very short cable) — **off by default**
  (`SERIALIZER_DISABLE_FFE_SHORT_CHANNEL = False`) since this board's actual
  cable insertion loss has not been measured. Opt in with
  `--disable-ffe-short-channel` only once that has been confirmed.
- **Errata #6 — "Enable GMSL negative output (SION pin) in Coax mode for
  optimal performance"**: `RLMSCE.enminus_man`/`enminus_reg` (bits 3/4) —
  required in GMSL3 12Gbps mode on a coax/FAKRA cable (this board's
  configuration) — **applied unconditionally**.
- **Errata #7 — "MIPI Receiver Requires Reset on Startup"**: `MIPI_RX0.mipi_rx_reset`
  (bit 3) toggled `1`→`0` once per run, inside `_configure_serializer_mipi_input()`
  (not `_apply_serializer_errata_workarounds()` — applied in Start-Up Sequence
  step 13, right after video is disabled) — forces a clean D-PHY receiver
  re-sync in case the sensor's MIPI clock/data pins were not yet stable when
  the serializer powered on.

Both #5/#6 live in the same register (`RLMSCE`, `0x14CE`) and are written in
one combined I2C transaction.

## 20. Eye-opening monitor (EOM) threshold tuning (Link A)

`RLMS5` (`0x1405`) holds `EOM_MIN_THR[6:0]` — the eye-opening monitor's
pass/fail threshold, as a fraction of a full eye (`% eye-opening = EOM_MIN_THR/64`).
Datasheet reset default is `0x10` (25%). Per the datasheet, EOM is only a
*recommended diagnostic* for GMSL2 mode (3/6Gbps) — not GMSL3 mode (12Gbps,
this board's rate) — so threshold tuning here is an **empirical workaround**
for a marginal link, not a guaranteed fix.

- `DESERIALIZER_EOM_MIN_THR_DEFAULT = 0x0E` (21.875%) is applied automatically
  by `gmsl_conf_max96793_max96792a()`, **deliberately last** (after
  `_reset_and_relock_link()`), since `RESET_LINK` reverts `RLMS5` back to its
  hardware reset default (`0x10`). Confirmed empirically (2026-10-18): a
  marginal eye (measured ~19-22/64) was tripping the reset-default threshold
  and holding Pipe Y's MIPI TX output in a near-permanent reset (packet
  counters stuck at 0 despite the GMSL link + `VIDEO_LOCK` both showing
  healthy).
- `set_eom_min_threshold_link_a(bus, threshold)` / `--eom-min-threshold 0-127`
  — set a different threshold for this run only.
- `read_eom_min_threshold_link_a(bus)` / `--check-eom-min-threshold` — read
  back the currently configured threshold.
- `read_eom_result_link_a(bus)` / `--check-eom-result` — read `RLMS7`
  (`0x1407`, read-only: bit 7 = `EOM_DONE`, bits `[6:0]` = last completed
  measurement, same 0-64/64 scale). `EOM_EN`/`EOM_PER_MODE` are both enabled
  by reset default, so this updates continuously (~1Hz) without a manual
  trigger; `EOM_DONE=False` just means a measurement is still in progress,
  not an error.

## 21. Experimental tuning (deskew tunnel offset / DT filter / `TUN_PKT_START_ADDR`)

Three further tunable registers, none written automatically by the full
bring-up (no datasheet formula/tuning guidance is available for any of them
beyond the register name):

- **`MIPI_TX53 DESKEW_TUN_OFFSET`** (`0x0475`) — "Tunneling Deskew Width
  Offset", a tunnel-mode-specific deskew parameter distinct from
  `DESKEW_INIT`/`DESKEW_PER` (see "MIPI D-PHY configuration summary" above).
  `set_deskew_tun_offset(bus, offset)` / `--deskew-tun-offset 0-255` (accepts
  `0xNN`); `read_deskew_tun_offset(bus)` / `--check-deskew-tun-offset`.
- **Serializer DT filtering** (`mem_dt1_selz`, `0x0318`, pipe Z) —
  `set_serializer_dt_filter(bus, serializer_addr, datatype)` /
  `--set-dt-filter 0xNN` (e.g. `0x2A` for RAW8) / `--clear-dt-filter`. **Not
  expected to have any effect** in this board's configuration: tunneling mode
  (`TUN_EN=1`) does not support DT/VC filtering per the datasheet — exists
  purely for experimentation.
- **`MIPI_TX54 TUN_PKT_START_ADDR`** (`0x0476`) — start address of the long
  packet within the tunneled byte stream, reset default `0x00`. A sensor
  whose packet structure differs (e.g. an embedded-data line ahead of the
  image data) may need this adjusted — override with `--tun-pkt-start-addr`
  (accepts `0xNN`), applied automatically during the full bring-up (reset
  default otherwise).

## 22. Known issues / limitations

- **Deserializer `DEV_ID` (REG13) reads `0xFF`** while `DEV_REV` (REG14) reads
  a valid, errata-confirmed value (`0x6` = D-0B) — see "Chip ID / revision
  readback" above. Confirmed against ADI's D-0B errata sheet as **not** a
  documented erratum; treat as a hardware/bus item to investigate
  independently (e.g. `i2ctransfer`/`i2cget`), not a script bug.
- **Masked-write rows (REG1/REG4/REG6 at address `0x55`)** are replayed
  byte-for-byte from `config_1.cpp`, but the true hardware semantics of the
  trailing mask byte haven't been confirmed against the MAX96792A
  datasheet/errata — see "Masked-write rows" above.
- **`set_camera_sensor_reset()` can race the kernel's `maxim,max7320` GPIO
  driver** once it's bound — only use `--set-camera-reset` for manual
  bring-up/debugging before that driver loads.
- **Errata #5 (`--disable-ffe-short-channel`) and the EOM threshold
  (`DESERIALIZER_EOM_MIN_THR_DEFAULT`)** are both channel/board-specific
  empirical tunables, not guaranteed-correct defaults — re-verify against the
  actual cable/board before trusting them on a different unit.
