# MAX96792A GMSL3 Configuration

This directory contains a Python utility for configuring the MAX96792A GMSL deserializer over I2C:

- `max96792a-configure.py`

The implementation follows the MAX96792A configuration path in the Linux driver:

- `drivers/media/i2c/maxim-serdes/max9296a.c`
- `drivers/media/i2c/maxim-serdes/max_des.c`

## Scope

The script configures the MAX96792A deserializer for GMSL3 and CSI-2 output. It performs:

1. Device detection and reset.
2. GMSL link selection.
3. GMSL3 link-rate and mode configuration.
4. CSI-2 PHY lane and DPLL configuration.
5. Video-pipe selection and stream mapping.
6. Virtual-channel and data-type remapping.
7. PHY activation and CSI output enable.

The script does not configure the remote serializer, image sensor, serializer aliases, or I2C address translation. Those devices must be configured separately before or alongside this script.

## Default Configuration

Running the script without arguments uses:

| Setting | Default |
| --- | --- |
| I2C bus | `2` |
| MAX96792A address | `0x27` |
| Active links | Link `0` |
| GMSL version | GMSL3 |
| CSI-2 lanes per PHY | `2` |
| CSI-2 link frequency | `750000000` Hz |
| CSI-2 data type | `0x2a` |
| Virtual channel | `0` |

The GMSL3 option enables the MAX96792A GMSL3/FEC path and clears the corresponding GMSL2 link bits. The script does not require host control of the physical `PWDNB` pin. It asserts the selected link's `RESET_LINK` bit while programming the registers, then clears it to start link acquisition.
For single-link operation, the script enables `AUTO_LINK` and selects Link A or Link B through `LINK_CFG` and `LINK_EN_A/B`. For both links, it uses reverse-splitter mode with `LINK_CFG=0b11`.

## Usage

Install the Python I2C dependency if it is not already available:

```bash
python3 -m pip install smbus2
```

Run the default single-camera GMSL3 configuration. No runtime options are required:

```bash
sudo python3 max96792a-configure.py
```

Run the script using its full repository path:

```bash
sudo python3 \
  sdcard-images-utils/nvidia/scripts/GMSL3_SerDe/MAX96792A/max96792a-configure.py
```

Configure only link 0:

```bash
sudo python3 max96792a-configure.py --links 0
```

Configure a different MAX96792A I2C address or bus:

```bash
sudo python3 max96792a-configure.py --bus 2 --address 0x27
```

The GMSL version can be overridden for testing:

```bash
python3 max96792a-configure.py --version gmsl2-6g
python3 max96792a-configure.py --version gmsl2-3g
python3 max96792a-configure.py --version gmsl3
```

## Important Options

- `--bus`: Linux I2C bus number. Default: `2`.
- `--address`: MAX96792A 7-bit I2C address. Supports decimal or hexadecimal values. Default: `0x27`.
- `--links`: Optional comma-separated active links: `0`, `1`, or `0,1`. Default: `0`.
- `--version`: `gmsl3`, `gmsl2-6g`, or `gmsl2-3g`. Default: `gmsl3`.
- `--lanes`: CSI-2 data lanes per PHY, from `1` to `4`. Default: `2`.
- `--link-frequency`: CSI-2 link frequency in Hz. This is the CSI-2 output frequency, not the GMSL cable rate.
- `--data-type`: CSI-2 data type in decimal or hexadecimal form. Default: RAW8, `0x2a`.
- `--virtual-channel`: CSI-2 virtual channel from `0` to `3`.

## Register Configuration Summary

The script uses 16-bit register addresses and 8-bit register values.

### Reset and Link Selection

- `0x0010`: MAX96792A global reset, Link A reset, and link configuration control.
- `0x0013[0]`: Link B `RESET_LINK` control.
- `0x0006`: GMSL2/GMSL3 link mode selection.
- `0x0f00`: Active GMSL link enable mask.
- `0x0001` and `0x0004`: Link A and Link B rate fields.
- `0x0028` and `0x5028`: Link A and Link B GMSL3/FEC control registers.

The script asserts Link A `RESET_LINK` at `0x0010[6]` and Link B `RESET_LINK` at `0x0013[0]`, programs the link-rate and GMSL mode registers while the selected paths are held in reset, then clears `RESET_LINK` to start link acquisition.

### CSI-2 PHYs

For each active PHY, the script configures:

- CSI-2 lane count.
- Logical-to-physical lane mapping.
- Lane polarity defaults.
- DPLL reset, frequency, and enable state.
- Initial and periodic deskew settings.
- PHY standby/active state.

The default single-camera configuration uses Link 0, two CSI-2 data lanes, and the lane mapping `0,1`.

### Video Pipes

Each active link is mapped to one MAX96792A video pipe:

- Pipe 0 maps link 0 to PHY 0.
- Pipe 1 maps link 1 to PHY 1.

The script configures stream selection, data-type remapping, virtual-channel remapping, frame-start/frame-end remapping, destination PHY, and pipe enable state.

### CSI Output

CSI output is disabled while the configuration is updated and enabled at the end through register `0x0313`.

## Hardware Requirements

- NVIDIA/Linux system with access to the selected I2C bus.
- `smbus2` Python package.
- MAX96792A powered and visible at the selected I2C address.
- Remote serializer already configured for the same GMSL version and link rate.
- Sensor and CSI-2 format configured consistently with `--data-type`, `--lanes`, and `--virtual-channel`.

## Validation

The script only reports completion after sending the register transactions. It does not currently validate GMSL3 link lock, video lock, CSI packet counters, or sensor streaming.

After running it, validate the complete path with the platform tools and driver status. If the link does not stream, check the following first:

1. Serializer and deserializer GMSL versions match.
2. The selected I2C bus and MAX96792A address are correct.
3. Link A/B selection matches the physical connection.
4. CSI-2 lane count and link frequency match the device tree.
5. Sensor data type and virtual channel match the pipe remapping.
6. The remote serializer and sensor have completed their own initialization.

This utility performs live I2C writes and should only be run when the camera hardware is connected and in a known power state.
