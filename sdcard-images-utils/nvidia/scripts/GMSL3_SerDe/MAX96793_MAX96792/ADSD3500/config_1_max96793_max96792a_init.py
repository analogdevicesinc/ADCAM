"""
GMSL2/3 link + MIPI CSI-2 tunnel-mode init for MAX96793 (serializer) /
MAX96792A (deserializer), converted from config_1.cpp (CSIConfigurationTool
export) using the byte-mapping rules documented in README.md:
  - drop the leading 0x04 "write" opcode
  - shift the 8-bit device address right by 1 bit to get the 7-bit I2C address
  - pass the remaining bytes (reg_hi, reg_lo, value[, mask]) as the write payload
  - replace 0x00,<n> delay markers with time.sleep(n / 1000.0)

Usage:
    python3 config_1_max96793_max96792a_init.py [bus] [--log-level LEVEL]

Exit status: 0 on success, 1 if any I2C transaction or the serializer
detection step fails (see GmslConfigError).
"""
import argparse
import sys
import time
import logging
from typing import List, Optional, Sequence, Tuple

from smbus2 import SMBus, i2c_msg

# Bump on every edit - logged on every run so a stale copy on the target is obvious.
SCRIPT_VERSION = "2026-10-20.1"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class GmslConfigError(RuntimeError):
    """Raised when an I2C transaction to the serializer/deserializer fails."""


SERIALIZER_ADDR_CANDIDATES = [0x40, 0x41]  # MAX96793: 0x80/0x81 >> 1
DESERIALIZER_ADDR = 0x2A                   # MAX96792A: 0x54 >> 1
# config_1.cpp also targets device address 0x55 for a handful of registers
# (REG1/REG4/REG6) with an extra trailing mask byte. 0x55 >> 1 resolves to the
# same 7-bit address as 0x54, so these rows are replayed as 4-byte payloads
# ([reg_hi, reg_lo, value, mask]) to the same DESERIALIZER_ADDR.
DESERIALIZER_MASKED_ADDR = 0x2A            # MAX96792A: 0x55 >> 1

# REG13 (address 0x0D), DEV_ID[7:0], read-only (max96792a.pdf, Register Map, REG13 0xD)
DESERIALIZER_DEV_ID_REG = [0x00, 0x0D]
# REG14 (address 0x0E), DEV_REV[3:0], read-only (max96792a.pdf, Register Map, REG14 0xE)
DESERIALIZER_REV_ID_REG = [0x00, 0x0E]

# DEV_REV -> silicon revision, per ADI MAX96792A errata sheets
DESERIALIZER_SILICON_REVISIONS = {
    0x6: "D-0B",
}

# REG13 (address 0x0D), DEV_ID[7:0], read-only (max96793.pdf, Register Map, REG13 0xD)
SERIALIZER_DEV_ID_REG = [0x00, 0x0D]
# REG14 (address 0x0E), DEV_REV[3:0], read-only (max96793.pdf, Register Map, REG14 0xE)
SERIALIZER_REV_ID_REG = [0x00, 0x0E]

# ---- Deserializer (MAX96792A) register map, max96792a.pdf Register Map ----

# BACKTOP25 (address 0x0320), phy1_csi_tx_dpll_predef_freq[4:0] (max96792a.pdf, Register Map, BACKTOP25 0x320)
DESERIALIZER_MIPI_FREQ_REG = [0x03, 0x20]
DESERIALIZER_MIPI_FREQ_PREDEF_EN_BIT = 0x20  # bit 5: use the predefined frequency field below
DESERIALIZER_MIPI_FREQ_800MBPS = 0x08
DESERIALIZER_MIPI_FREQ_1000MBPS = 0x0A
DESERIALIZER_MIPI_FREQ_1500MBPS = 0x0F
DESERIALIZER_MIPI_FREQ_2000MBPS = 0x14
DESERIALIZER_MIPI_FREQ_2500MBPS = 0x19

# freq code -> Mbps/lane, for logging whichever speed macro is actually used below
DESERIALIZER_MIPI_FREQ_MBPS = {
    DESERIALIZER_MIPI_FREQ_800MBPS: 800,
    DESERIALIZER_MIPI_FREQ_1000MBPS: 1000,
    DESERIALIZER_MIPI_FREQ_1500MBPS: 1500,
    DESERIALIZER_MIPI_FREQ_2000MBPS: 2000,
    DESERIALIZER_MIPI_FREQ_2500MBPS: 2500,
}

# selected CSI Phy 1 output speed; change to any DESERIALIZER_MIPI_FREQ_*MBPS macro above,
# or override per-run with --mipi-freq without editing this file.
# ADSD3500 (RAW8, confirmed real DT 0x2A, non-continuous clock): 1000 Mbps/lane
DESERIALIZER_MIPI_OUTPUT_FREQ = DESERIALIZER_MIPI_FREQ_1000MBPS

# maps --mipi-freq CLI choices to the macros above
DESERIALIZER_MIPI_FREQ_CHOICES = {
    "800": DESERIALIZER_MIPI_FREQ_800MBPS,
    "1000": DESERIALIZER_MIPI_FREQ_1000MBPS,
    "1500": DESERIALIZER_MIPI_FREQ_1500MBPS,
    "2000": DESERIALIZER_MIPI_FREQ_2000MBPS,
    "2500": DESERIALIZER_MIPI_FREQ_2500MBPS,
}

# BACKTOP12 (address 0x0313), CSI_OUT_EN
DESERIALIZER_BACKTOP12_REG = [0x03, 0x13]
DESERIALIZER_CSI_OUT_DISABLE = 0x00
DESERIALIZER_CSI_OUT_ENABLE = 0x02

# TCTRL:CTRL0 (address 0x0010), AUTO_LINK / LINK_CFG[1:0] / RESET_ONESHOT
DESERIALIZER_CTRL0_REG = [0x00, 0x10]
DESERIALIZER_CTRL0_AUTO_LINK_DISABLE = 0x01
DESERIALIZER_CTRL0_LINK_CFG1_RESET_ONESHOT_A = 0x21

# RESET_LINK (bit 6): manual two-step reset ("write 1 to activate, write 0 to
# release") per Start-Up Sequence steps 16-17, applied after all SER/DES MIPI
# config so those changes take effect through a full data-path reset before CSI
# output is re-enabled - distinct from the self-clearing RESET_ONESHOT pulse
# used earlier just to establish the initial link lock.
DESERIALIZER_CTRL0_RESET_LINK_BIT = 0x40
DESERIALIZER_CTRL0_LINK_CFG1 = 0x01

# DEV:REG1 (address 0x0001), RX_RATE[1:0] / DIS_REM_CC
DESERIALIZER_REG1 = [0x00, 0x01]
DESERIALIZER_REG1_RX_RATE_12GBPS_GMSL3 = 0x03
DESERIALIZER_REG1_RX_RATE_MASK = 0x03
DESERIALIZER_REG1_DIS_REM_CC_ENABLE = 0x03

# DEV:REG3 (address 0x0003), DIS_REM_CC_B
DESERIALIZER_REG3 = [0x00, 0x03]
DESERIALIZER_REG3_DIS_REM_CC_B_DISABLE = 0x57

# DEV:REG4 (address 0x0004), GMSL3_A (bit 6)
DESERIALIZER_REG4 = [0x00, 0x04]
DESERIALIZER_REG4_GMSL3_A_ENABLE = 0x40
DESERIALIZER_REG4_GMSL3_A_MASK = 0x40
DESERIALIZER_REG4_GMSL3_A_BIT = 0x40

# DEV:REG6 (address 0x0006), I2CSEL
DESERIALIZER_REG6 = [0x00, 0x06]
DESERIALIZER_REG6_I2CSEL_I2C = 0x10
DESERIALIZER_REG6_I2CSEL_MASK = 0x10

# GMSL1_COMMON:GMSL1_EN (address 0x0F00), LINK_EN_A / LINK_EN_B
DESERIALIZER_GMSL1_EN_REG = [0x0F, 0x00]
DESERIALIZER_GMSL1_EN_LINK_A_ONLY = 0x01

# VIDEO_PIPE_SEL:VIDEO_PIPE_SEL (address 0x0161), STR_SELY
DESERIALIZER_VIDEO_PIPE_SEL_REG = [0x01, 0x61]
DESERIALIZER_VIDEO_PIPE_SEL_Y_LINKA_STREAM0 = 0x30

# MIPI_PHY:MIPI_PHY0 (address 0x0330), phy_4x2 port configuration
DESERIALIZER_MIPI_PHY0_REG = [0x03, 0x30]
DESERIALIZER_MIPI_PHY0_2X4_MODE = 0x04

# MIPI_TX__1:MIPI_TX10 (address 0x044A), CSI2_LANE_CNT (Port A)
DESERIALIZER_MIPI_TX10_REG = [0x04, 0x4A]
DESERIALIZER_MIPI_TX10_PORTA_2LANE = 0x50

# MIPI_TX__1:MIPI_TX3/MIPI_TX4 (addresses 0x0443/0x0444), PHY1 D-PHY lane deskew.
# Per datasheet: deskew patterns are required at >=1.5Gbps/lane, optional below - must be
# turned on explicitly here, the deserializer does NOT forward the sensor's own deskew
# pattern transparently through the GMSL tunnel.
DESERIALIZER_DESKEW_INIT_REG = [0x04, 0x43]
DESERIALIZER_DESKEW_PER_REG = [0x04, 0x44]
DESERIALIZER_DESKEW_ENABLE_BIT = 0x80
DESERIALIZER_DESKEW_WIDTH_WIDEST = 0x07  # bits[2:0]=111: widest (8x32k UI) calibration window
DESERIALIZER_DESKEW_AUTO_ENABLE_WIDEST = DESERIALIZER_DESKEW_ENABLE_BIT | DESERIALIZER_DESKEW_WIDTH_WIDEST
DESERIALIZER_DESKEW_DISABLE = 0x00
DESERIALIZER_DESKEW_REQUIRED_THRESHOLD_MBPS = 1500

# DESKEW_PER bits[5:3]: periodic recalibration interval, in frames (datasheet-defined steps).
# The Jetson only needs the one-time initial deskew (DESKEW_INIT) before the first frame,
# not ongoing per-frame recalibration - periodic deskew is opt-in via --deskew-period.
DESERIALIZER_DESKEW_PERIOD_CHOICES = {
    "1": 0b000, "2": 0b001, "4": 0b010, "8": 0b011,
    "16": 0b100, "32": 0b101, "64": 0b110, "128": 0b111,
}
# periodic recalibration is off by default; --deskew-period enables it at the given interval
DESERIALIZER_DESKEW_PERIODIC_ENABLED = False
DESERIALIZER_DESKEW_PERIOD_BITS = DESERIALIZER_DESKEW_PERIOD_CHOICES["1"]

# MIPI_TX53 (address 0x0475), DESKEW_TUN_OFFSET[7:0] - "Tunneling Deskew Width Offset",
# a tunnel-mode-specific deskew parameter distinct from DESKEW_INIT/DESKEW_PER above.
# Datasheet reset default is 0x00; no formula/tuning guidance is given beyond the name -
# not written automatically by this script's bring-up, exposed only for experimentation
# via --deskew-tun-offset.
DESERIALIZER_DESKEW_TUN_OFFSET_REG = [0x04, 0x75]
DESERIALIZER_DESKEW_TUN_OFFSET_RESET_DEFAULT = 0x00

# MIPI_PHY:MIPI_PHY3 (address 0x0333), phy0/phy1 lane map
DESERIALIZER_MIPI_PHY3_REG = [0x03, 0x33]
DESERIALIZER_MIPI_PHY3_LANE_MAP_PHY0_PHY1 = 0x4E

# MIPI_PHY:MIPI_PHY5 (address 0x0335), phy0/phy1 polarity map
DESERIALIZER_MIPI_PHY5_REG = [0x03, 0x35]
DESERIALIZER_MIPI_PHY5_POLARITY_NORMAL = 0x00

# DPLL__CSI2:DPLL_0 (address 0x1D00), config_soft_rst_n (PHY1)
DESERIALIZER_DPLL0_REG = [0x1D, 0x00]
DESERIALIZER_DPLL0_SOFT_RESET_ASSERT = 0xF4
DESERIALIZER_DPLL0_SOFT_RESET_RELEASE = 0xF5

# MIPI_PHY:MIPI_PHY2 (address 0x0332), phy_Stdby_n (PHY2/PHY3)
DESERIALIZER_MIPI_PHY2_REG = [0x03, 0x32]
DESERIALIZER_MIPI_PHY2_PHY23_STANDBY = 0x34

# MIPI_TX__1:MIPI_TX52 (address 0x0474), TUN_DEST / TUN_EN (Pipe Y)
DESERIALIZER_MIPI_TX52_REG = [0x04, 0x74]
DESERIALIZER_MIPI_TX52_TUNNEL_PIPEY_DEST1_ENABLE = 0x09

# MIPI_TX__1:MIPI_TX54 (address 0x0476), TUN_PKT_START_ADDR[7:0] - start address of the
# long packet within the tunneled byte stream. Left at its reset default (0x00) unless
# overridden - a sensor whose packet structure differs (e.g. an extra embedded-data line
# ahead of the image data) may need this adjusted to match where its real long packet
# actually begins; override per-run with --tun-pkt-start-addr without editing this file.
DESERIALIZER_TUN_PKT_START_ADDR_REG = [0x04, 0x76]
DESERIALIZER_TUN_PKT_START_ADDR = 0x00

# TCTRL:CTRL3 (address 0x0013), LOCKED / CMU_LOCKED (read-only link status)
DESERIALIZER_CTRL3_REG = [0x00, 0x13]
DESERIALIZER_CTRL3_LOCKED_BIT = 0x08
DESERIALIZER_CTRL3_CMU_LOCKED_BIT = 0x02

# GPIO_A/B/C for GPIO 0 / MFP0 (address 0x02B0-0x02B2, max96792a.pdf Register Map)
DESERIALIZER_GPIO0_A_REG = [0x02, 0xB0]
DESERIALIZER_GPIO0_B_REG = [0x02, 0xB1]
DESERIALIZER_GPIO0_GPIO_OUT_BIT = 0x10       # bit 4: output drive value (used when GPIO_RX_EN=0)
DESERIALIZER_GPIO0_GPIO_IN_BIT = 0x08         # bit 3: read-only, live sampled level on the pin
DESERIALIZER_GPIO0_GPIO_RX_EN_BIT = 0x04     # bit 2: receive GPIO value from GMSL
DESERIALIZER_GPIO0_GPIO_TX_EN_BIT = 0x02     # bit 1: transmit this pin's value over GMSL
DESERIALIZER_GPIO0_GPIO_OUT_DIS_BIT = 0x01   # bit 0: 0 = output driver enabled, 1 = disabled
DESERIALIZER_GPIO0_TX_ID_MASK = 0x1F         # GPIO_B bits[4:0]: GPIO_TX_ID

# REG2 (address 0x0002), VID_EN_Y/VID_EN_Z - enable data transmission through
# video pipes Y/Z. Reset default is 0b1 (enabled) per max96792a.pdf, but this
# board's REG13 DEV_ID also doesn't match its documented value (see "known
# anomaly" in README), so reset defaults aren't trusted here - explicitly set.
DESERIALIZER_REG2 = [0x00, 0x02]
DESERIALIZER_REG2_VID_EN_Y_BIT = 0x20        # bit 5: enable video pipe Y
DESERIALIZER_REG2_VID_EN_Z_BIT = 0x40        # bit 6: enable video pipe Z

# VIDEO_PIPE_EN (address 0x0160), enables for video pipes. Reset default is
# 0b11 (both enabled), not explicitly written by config_1.cpp - same "don't
# trust reset defaults on this chip" reasoning as REG2 above.
DESERIALIZER_VIDEO_PIPE_EN_REG = [0x01, 0x60]
DESERIALIZER_VIDEO_PIPE_EN_MASK = 0x03

# MIPI_PHY18/MIPI_PHY20 (address 0x0342/0x0344), CSI-2/PHY output packet counters
# (max96792a.pdf: "MIPI TX is outputting data: csi2_tx1/2_pkt_cnt, csi2_dup1/2_pkt_cnt,
# phy0/1/2/3_pkt_cnt"). 4-bit nibble counters, wrap at 16. This config routes video to
# PHY1 (see lane map above) via tunnel destination pipe 1 -> csi2_tx1_pkt_cnt.
DESERIALIZER_MIPI_PHY18_REG = [0x03, 0x42]   # bits[3:0] = csi2_tx1_pkt_cnt
DESERIALIZER_MIPI_PHY20_REG = [0x03, 0x44]   # bits[7:4] = phy1_pkt_cnt

# RX0 (address 0x002C), PKT_CNT_SEL[3:0] - selects the packet type counted by the
# generic received-packet counter at CNT3/PKT_CNT (0x0025, 8-bit, scaled by
# PKT_CNT_EXP). Used to confirm the deserializer is receiving ANY packets over the
# GMSL tunnel at all, independent of whether they're successfully routed out to
# CSI-2 (see MIPI_PHY18/20 above, and the "known anomaly" DEV_ID=0xFF note).
DESERIALIZER_RX0_REG = [0x00, 0x2C]
DESERIALIZER_PKT_CNT_SEL_MASK = 0x0F
DESERIALIZER_PKT_CNT_SEL_ALL = 0x0E          # 0xE: count all received packet types
DESERIALIZER_PKT_CNT_REG = [0x00, 0x25]      # CNT3: received packet count

# MIPI_PHY17 (address 0x0341), tunnel-mode error status flags, read-only
# (max96792a.pdf Register Map). Any of these being set explains zero CSI TX output
# even with healthy serializer input: the deserializer is detecting/dropping corrupted
# or overflowing tunneled data rather than passing it through.
DESERIALIZER_MIPI_PHY17_REG = [0x03, 0x41]
DESERIALIZER_MIPI_PHY17_TUN_DATA_CRC_ERR_BIT = 0x20     # bit 5
DESERIALIZER_MIPI_PHY17_TUN_ECC_UNCORR_ERR_BIT = 0x10   # bit 4
DESERIALIZER_MIPI_PHY17_TUN_ECC_CORR_ERR_BIT = 0x08     # bit 3
DESERIALIZER_MIPI_PHY17_VID_OVERFLOW_FLAG_BIT = 0x01    # bit 0

# ---- Serializer (MAX96793) register map, max96793.pdf Register Map ----

# REG2 (address 0x0002), VID_TX_EN_Z
SERIALIZER_REG2_REG = [0x00, 0x02]
SERIALIZER_REG2_VID_TX_EN_Z_DISABLE = 0x03
SERIALIZER_REG2_VID_TX_EN_Z_ENABLE = 0x43

# RLMSCE (address 0x14CE, max96793.pdf Register Map) - GMSL3 PAM4 analog TX
# tuning, not covered by the device-specific user guide's own tables.
# max96793-errata.pdf (DEV_REV=6) Errata #5 and #6 both live in this one register:
#   bit 0 (enffe, reset default 0b1/Enabled) - Errata #5 "GMSL3 PAM4 short-channel
#     operation requires register write for robust operation": disabling FFE is
#     only required/recommended on channels with <1dB insertion loss (a very
#     short cable) - NOT disabled by default since this board's actual cable
#     insertion loss has not been measured; opt in via --disable-ffe-short-channel
#     only once that has been confirmed.
#   bit 3 (enminus_man) / bit 4 (enminus_reg) - Errata #6 "Enable GMSL negative
#     output (SION pin) in Coax mode for optimal performance": required in GMSL3
#     12Gbps mode (this board's rate, on a coax/FAKRA cable) - applied
#     unconditionally.
SERIALIZER_RLMSCE_REG = [0x14, 0xCE]
SERIALIZER_RLMSCE_ENFFE_BIT = 0x01
SERIALIZER_RLMSCE_ENMINUS_MAN_BIT = 0x08
SERIALIZER_RLMSCE_ENMINUS_REG_BIT = 0x10

# Errata #5 is channel-length-dependent (see RLMSCE comment above) - off by
# default, set via --disable-ffe-short-channel.
SERIALIZER_DISABLE_FFE_SHORT_CHANNEL = False

# MIPI_RX0 (address 0x0330), Port Configuration
SERIALIZER_MIPI_RX0_REG = [0x03, 0x30]
SERIALIZER_MIPI_RX0_PORT_CONFIG_1X4 = 0x00

# MIPI_RX0 (0x0330) bit 3, mipi_rx_reset - max96793-errata.pdf Errata #7 "MIPI
# Receiver Requires Reset on Startup": if the sensor's MIPI clock/data pins were
# not yet stable when this serializer powered up, its D-PHY receiver can latch up
# and never detect the start-of-transmission sequence. Toggled 1->0 in
# _configure_serializer_mipi_input() (serializer already powered, video still
# disabled at that point) - not a persistent config bit, self-clears once written.
SERIALIZER_MIPI_RX0_RESET_BIT = 0x08

# MIPI_RX0 (0x0330) bit 6, mipi_noncont_clk_en: the sensor-facing CSI-2 RX's
# expected clock mode, must match what the ADSD3500 actually transmits (confirmed
# non-continuous/gated) and the Jetson DT's discontinuous_clk="yes". Reset default
# 0b0 = continuous clock, which mismatches both - must be set.
SERIALIZER_MIPI_RX0_NONCONT_CLK_EN_BIT = 0x40

# MIPI_RX_EXT:EXT11 (address 0x0383), Tun_Mode
SERIALIZER_EXT11_REG = [0x03, 0x83]
SERIALIZER_EXT11_TUN_MODE_ENABLE = 0x80

# MIPI_RX1 (address 0x0331), ctrl1_num_lanes (Port B Lane Count)
SERIALIZER_MIPI_RX1_REG = [0x03, 0x31]
SERIALIZER_MIPI_RX1_PORTB_2LANE = 0x10
# ctrl1_deskewen (bit 6) - required at >=1.5Gbps/lane (same threshold/shared end-to-end
# rate as the deserializer's own output deskew, since tunnel mode passes the sensor's
# real bit rate through unmodified) for the serializer's own MIPI RX input from the
# sensor. Previously hardcoded off regardless of frequency - computed dynamically in
# _configure_serializer_mipi_input() instead, mirroring DESERIALIZER_DESKEW_* logic.
SERIALIZER_MIPI_RX1_DESKEW_EN_BIT = 0x40

# MIPI_RX2 (address 0x0332), phy1_lane_map
SERIALIZER_MIPI_RX2_REG = [0x03, 0x32]
SERIALIZER_MIPI_RX2_LANE_MAP_PHY1 = 0xE0

# MIPI_RX3 (address 0x0333), phy2_lane_map
SERIALIZER_MIPI_RX3_REG = [0x03, 0x33]
SERIALIZER_MIPI_RX3_LANE_MAP_PHY2 = 0x04

# MIPI_RX4 (address 0x0334), phy1_pol_map
SERIALIZER_MIPI_RX4_REG = [0x03, 0x34]
SERIALIZER_MIPI_RX4_POLARITY_NORMAL = 0x00

# MIPI_RX5 (address 0x0335), phy2_pol_map
SERIALIZER_MIPI_RX5_REG = [0x03, 0x35]
SERIALIZER_MIPI_RX5_POLARITY_NORMAL = 0x00

# FRONTTOP_0 (address 0x0308), CLK_SELZ / START_PORTB
SERIALIZER_FRONTTOP_0_REG = [0x03, 0x08]
SERIALIZER_FRONTTOP_0_PORTB_START = 0x64

# mem_dt1_selz (address 0x0318), DT filtering for pipe Z (Table 8 of the serializer's
# device-specific user guide). Bit 6 = filter enable, bits[5:0] = datatype ID to
# allow onto the pipe. NOT configured anywhere in this script by default - tunneling
# mode (what this board uses) does not support DT/VC filtering at all, so this is
# exposed only via --set-dt-filter for experimentation; it has no documented effect
# while TUN_EN=1.
SERIALIZER_MEM_DT1_SELZ_REG = [0x03, 0x18]
SERIALIZER_MEM_DT_SELZ_FILTER_EN_BIT = 0x40
SERIALIZER_MEM_DT_SELZ_DT_MASK = 0x3F

# FRONTTOP_9 (address 0x0311), START_PORTBZ
SERIALIZER_FRONTTOP_9_REG = [0x03, 0x11]
SERIALIZER_FRONTTOP_9_START_VIDEO = 0x40

# CFGV__VIDEO_Z:TX3 (address 0x005B), TX_STR_SEL (Pipe Z)
SERIALIZER_TX3_REG = [0x00, 0x5B]
SERIALIZER_TX3_STR_SEL_PIPEZ = 0x00

# REG1 (address 0x01) pass-through I2C channel enables (max96793.pdf, Register Map, REG1 0x1)
SERIALIZER_REG1 = [0x00, 0x01]
SERIALIZER_IIC_1_EN_BIT = 0x40  # bit 6: pass-through Channel 1 (SDA1/RX1, SCL1/TX1)
SERIALIZER_IIC_2_EN_BIT = 0x80  # bit 7: pass-through Channel 2 (SDA2/RX2, SCL2/TX2)

# GPIO_A/C for GPIO 0 / MFP0 (address 0x02BE/0x02C0, max96793.pdf Register Map)
SERIALIZER_GPIO0_A_REG = [0x02, 0xBE]
SERIALIZER_GPIO0_C_REG = [0x02, 0xC0]
SERIALIZER_GPIO0_GPIO_IN_BIT = 0x08          # bit 3: read-only, live sampled level on the pin
SERIALIZER_GPIO0_GPIO_RX_EN_BIT = 0x04       # bit 2: receive GPIO value from GMSL
SERIALIZER_GPIO0_GPIO_TX_EN_BIT = 0x02       # bit 1: transmit this pin's value over GMSL
SERIALIZER_GPIO0_GPIO_OUT_DIS_BIT = 0x01     # bit 0: 0 = output driver enabled, 1 = disabled
SERIALIZER_GPIO0_RX_ID_MASK = 0x1F           # GPIO_C bits[4:0]: GPIO_RX_ID

# GMSL GPIO channel ID (0-31) shared by both ends of the MFP0 tunnel
GPIO0_TUNNEL_CHANNEL_ID = 0

# MIPI_RX_EXT (address 0x038D-0x0390), free-running 8-bit packet/clock counters
# (max96793.pdf, Register Map, EXT21-EXT24). Used to confirm MIPI data is actually
# being received from the camera sensor into the serializer, independent of whether
# it ever reaches the deserializer/host: "read the following registers to determine
# if MIPI data is received: phy1_pkt_cnt, csi1_pkt_cnt. In Tunneling mode, tun_pkt_cnt
# can be read."
SERIALIZER_PHY1_PKT_CNT_REG = [0x03, 0x8D]   # phy1_pkt_cnt: physical-layer packets detected
SERIALIZER_CSI1_PKT_CNT_REG = [0x03, 0x8E]   # csi1_pkt_cnt: valid CSI-2 packets decoded
SERIALIZER_TUN_PKT_CNT_REG = [0x03, 0x8F]    # tun_pkt_cnt: packets forwarded via tunnel mode
SERIALIZER_PHY_CLK_CNT_REG = [0x03, 0x90]    # phy_clk_cnt: MIPI HS clock lane transitions detected

# ---- MAX7320 GPIO port expander (U7), host-side I2C GPO device ----
# O0-O7 are hardwired to MFP0/MFP1/MFP4/MFP5/MFP7/MFP8/MFP9/MFP10; no internal
# register address, reads/writes go directly to the 8-bit output latch.
# Shares the same I2C bus as the deserializer (set via AD0/AD2 address pins).
MAX7320_ADDR = 0x58
MAX7320_MFP0_BIT = 0x01  # O0 -> MFP0 (tunneled to camera sensor reset GPIO)


def _i2c_write(bus: SMBus, addr: int, payload: Sequence[int], description: str = "") -> None:
    """Write `payload` to `addr` and log `description`; raises GmslConfigError on failure."""
    try:
        bus.i2c_rdwr(i2c_msg.write(addr, list(payload)))
    except OSError as exc:
        raise GmslConfigError(
            "I2C write to 0x{:02X} {} failed: {}".format(addr, list(payload), exc)) from exc
    if description:
        logging.info(description)


def _i2c_read_byte(bus: SMBus, addr: int, reg_addr: Sequence[int]) -> int:
    """Read a single byte from `reg_addr` at `addr`.

    Uses one repeated-START transaction (write register address, then read):
    a STOP between the write and read would reset the device's register pointer.
    """
    read = i2c_msg.read(addr, 1)
    try:
        bus.i2c_rdwr(i2c_msg.write(addr, list(reg_addr)), read)
    except OSError as exc:
        raise GmslConfigError(
            "I2C read from 0x{:02X} reg {} failed: {}".format(addr, list(reg_addr), exc)) from exc
    return list(read)[0]


def _read_deserializer_reg(bus: SMBus, reg_addr: Sequence[int]) -> int:
    return _i2c_read_byte(bus, DESERIALIZER_ADDR, reg_addr)


def read_deserializer_revision(bus: SMBus) -> Tuple[int, int]:
    """Read MAX96792A REG13/REG14 and return (DEV_ID[7:0], DEV_REV[3:0])."""
    logging.info(">>> read_deserializer_revision()")
    dev_id = _read_deserializer_reg(bus, DESERIALIZER_DEV_ID_REG)
    # 0xFF looks like a NACK'd/floating read (chip not yet awake/settled) - retry a
    # few times with increasing delay before trusting it; a single 1ms retry was
    # observed to not always be enough.
    for retry_delay_s in (0.005, 0.02, 0.05):
        if dev_id != 0xFF:
            break
        time.sleep(retry_delay_s)
        dev_id = _read_deserializer_reg(bus, DESERIALIZER_DEV_ID_REG)
    if (dev_id >> 4) != 0xB:
        logging.warning("Deserializer REG13 DEV_ID 0x%X does not match expected family ID 0xB", dev_id)
    rev_id = _read_deserializer_reg(bus, DESERIALIZER_REV_ID_REG) & 0x0F
    silicon_rev = DESERIALIZER_SILICON_REVISIONS.get(rev_id, "unknown, check errata sheet")
    logging.info("Deserializer REG13 DEV_ID: 0x%X | REG14 DEV_REV: 0x%X (silicon revision %s)",
                 dev_id, rev_id, silicon_rev)
    return dev_id, rev_id


def _read_serializer_reg(bus: SMBus, serializer_addr: int, reg_addr: Sequence[int]) -> int:
    return _i2c_read_byte(bus, serializer_addr, reg_addr)


def read_serializer_revision(bus: SMBus, serializer_addr: int) -> Tuple[int, int]:
    """Read MAX96793 REG13/REG14 and return (DEV_ID[7:0], DEV_REV[3:0])."""
    logging.info(">>> read_serializer_revision()")
    dev_id = _read_serializer_reg(bus, serializer_addr, SERIALIZER_DEV_ID_REG)
    # see read_deserializer_revision() - same NACK'd/floating-read retry strategy
    for retry_delay_s in (0.005, 0.02, 0.05):
        if dev_id != 0xFF:
            break
        time.sleep(retry_delay_s)
        dev_id = _read_serializer_reg(bus, serializer_addr, SERIALIZER_DEV_ID_REG)
    if dev_id != 0xB7:
        logging.warning("Serializer REG13 DEV_ID 0x%X does not match expected MAX96793 ID 0xB7", dev_id)
    rev_id = _read_serializer_reg(bus, serializer_addr, SERIALIZER_REV_ID_REG) & 0x0F
    logging.info("Serializer REG13 DEV_ID: 0x%X | REG14 DEV_REV: 0x%X", dev_id, rev_id)
    return dev_id, rev_id


def _apply_serializer_errata_workarounds(bus: SMBus, serializer_addr: int, dev_rev: int) -> None:
    """Apply max96793-errata.pdf workarounds #5/#6 (RLMSCE, 0x14CE) - both documented
    against DEV_REV=6; logs a note (does not block) if a different revision is read,
    since this errata sheet may not apply verbatim to other revisions.

    Errata #6 "Enable GMSL negative output (SION pin) in Coax mode for optimal
    performance": required in GMSL3 12Gbps mode on a coax cable (this board) -
    applied unconditionally (enminus_man=1, enminus_reg=1).

    Errata #5 "GMSL3 PAM4 short-channel operation requires register write for
    robust operation": disabling FFE (enffe=0) is only required/recommended on
    channels with <1dB insertion loss - NOT applied unless
    SERIALIZER_DISABLE_FFE_SHORT_CHANNEL has been explicitly set (--disable-ffe-
    short-channel), since this board's actual cable insertion loss is unverified.

    Errata #7 "MIPI Receiver Requires Reset on Startup" is applied separately in
    _configure_serializer_mipi_input(), right after the serializer is detected and
    before video is re-enabled - see SERIALIZER_MIPI_RX0_RESET_BIT comment.
    """
    logging.info(">>> _apply_serializer_errata_workarounds()")
    if dev_rev != 6:
        logging.info("Serializer DEV_REV=0x%X (errata sheet documented against DEV_REV=6) - "
                     "applying anyway, but double-check max96793-errata.pdf covers this revision",
                     dev_rev)

    value = SERIALIZER_RLMSCE_ENMINUS_MAN_BIT | SERIALIZER_RLMSCE_ENMINUS_REG_BIT
    if not SERIALIZER_DISABLE_FFE_SHORT_CHANNEL:
        value |= SERIALIZER_RLMSCE_ENFFE_BIT  # preserve reset default (FFE enabled)
    _i2c_write(bus, serializer_addr, SERIALIZER_RLMSCE_REG + [value],
               "\tRLMSCE (Errata #6) | enminus_man: Manual | enminus_reg: Enabled (SION) | "
               "(Errata #5) enffe: {}".format(
                   "Disabled (short-channel, <1dB insertion loss)" if SERIALIZER_DISABLE_FFE_SHORT_CHANNEL
                   else "Enabled (default - short-channel not confirmed)"))


def read_serializer_i2c_passthrough(bus: SMBus, serializer_addr: int) -> Tuple[bool, bool]:
    """Read MAX96793 REG1 and return (IIC_1_EN, IIC_2_EN) pass-through channel state."""
    logging.info(">>> read_serializer_i2c_passthrough()")
    reg1 = _read_serializer_reg(bus, serializer_addr, SERIALIZER_REG1)
    iic_1_en = bool(reg1 & SERIALIZER_IIC_1_EN_BIT)
    iic_2_en = bool(reg1 & SERIALIZER_IIC_2_EN_BIT)
    logging.info("Serializer REG1: IIC_1_EN=%s (Channel 1: SDA1/SCL1) | IIC_2_EN=%s (Channel 2: SDA2/SCL2)",
                 iic_1_en, iic_2_en)
    return iic_1_en, iic_2_en


def _set_serializer_passthrough_bit(bus: SMBus, serializer_addr: int, bit_mask: int, enable: bool) -> int:
    # read-modify-write: REG1 also holds DIS_LOCAL_CC/DIS_REM_CC/TX_RATE/RX_RATE
    reg1 = _read_serializer_reg(bus, serializer_addr, SERIALIZER_REG1)
    new_reg1 = (reg1 | bit_mask) if enable else (reg1 & ~bit_mask)
    _i2c_write(bus, serializer_addr, SERIALIZER_REG1 + [new_reg1])
    return new_reg1


def enable_serializer_i2c_passthrough_channel1(bus: SMBus, serializer_addr: int, enable: bool = True) -> int:
    """Set/clear MAX96793 REG1 IIC_1_EN (pass-through Channel 1: SDA1/RX1, SCL1/TX1)."""
    logging.info(">>> enable_serializer_i2c_passthrough_channel1()")
    new_reg1 = _set_serializer_passthrough_bit(bus, serializer_addr, SERIALIZER_IIC_1_EN_BIT, enable)
    logging.info("Serializer REG1 IIC_1_EN set to %s (REG1=0x%X)", enable, new_reg1)
    return new_reg1


def enable_serializer_i2c_passthrough_channel2(bus: SMBus, serializer_addr: int, enable: bool = True) -> int:
    """Set/clear MAX96793 REG1 IIC_2_EN (pass-through Channel 2: SDA2/RX2, SCL2/TX2)."""
    logging.info(">>> enable_serializer_i2c_passthrough_channel2()")
    new_reg1 = _set_serializer_passthrough_bit(bus, serializer_addr, SERIALIZER_IIC_2_EN_BIT, enable)
    logging.info("Serializer REG1 IIC_2_EN set to %s (REG1=0x%X)", enable, new_reg1)
    return new_reg1


def read_deserializer_link_status(bus: SMBus) -> Tuple[bool, int, bool, bool]:
    """Read back MAX96792A REG4/REG1/CTRL3 to confirm Link A is running GMSL3 and locked.

    The MAX96793 serializer has no equivalent GMSL3_A/RX_RATE register: its GMSL3
    12Gbps rate is fixed via a hardware resistor strap, so only the deserializer
    side needs to be checked here.
    """
    logging.info(">>> read_deserializer_link_status()")
    reg4 = _read_deserializer_reg(bus, DESERIALIZER_REG4)
    gmsl3_a = bool(reg4 & DESERIALIZER_REG4_GMSL3_A_BIT)
    reg1 = _read_deserializer_reg(bus, DESERIALIZER_REG1)
    rx_rate = reg1 & DESERIALIZER_REG1_RX_RATE_MASK
    ctrl3 = _read_deserializer_reg(bus, DESERIALIZER_CTRL3_REG)
    locked = bool(ctrl3 & DESERIALIZER_CTRL3_LOCKED_BIT)
    cmu_locked = bool(ctrl3 & DESERIALIZER_CTRL3_CMU_LOCKED_BIT)
    logging.info(
        "Deserializer Link A: GMSL3_A=%s RX_RATE=0b%02s (%s) LOCKED=%s CMU_LOCKED=%s",
        gmsl3_a, bin(rx_rate)[2:].zfill(2),
        "12Gbps/GMSL3" if rx_rate == 0x3 else "not GMSL3 rate",
        locked, cmu_locked)
    return gmsl3_a, rx_rate, locked, cmu_locked


# RLMS5 Link A (0x1405) - EOM_MIN_THR[6:0]: the eye-opening monitor's pass/fail
# threshold, as a fraction of a full eye: % eye-opening = EOM_MIN_THR/64. Datasheet
# reset default is 0x10 (25%). Per the datasheet, EOM is only a recommended
# diagnostic for GMSL2 mode (3/6Gbps), not GMSL3 mode (12Gbps, this board's rate) -
# treat any threshold tuning here as an empirical workaround for a marginal link,
# not a guaranteed fix; not written automatically by this script's bring-up.
DESERIALIZER_RLMS5_LINKA_REG = [0x14, 0x05]
DESERIALIZER_RLMS5_EOM_MIN_THR_MASK = 0x7F  # bits[6:0]
DESERIALIZER_EOM_MIN_THR_RESET_DEFAULT = 0x10  # 25%, datasheet reset value
DESERIALIZER_EOM_MIN_THR_DEFAULT = 0x0E  # 21.875%, empirically tuned - see comment above
# RLMS7 Link A (0x1407), read-only: bit7=EOM_DONE, bits[6:0]=last completed EOM
# result (0-64/64 scale, same as EOM_MIN_THR). EOM_EN/EOM_PER_MODE are both enabled
# by reset default, so this updates continuously (~1Hz) without a manual trigger.
DESERIALIZER_RLMS7_LINKA_REG = [0x14, 0x07]
DESERIALIZER_RLMS7_EOM_DONE_BIT = 0x80       # bit 7
DESERIALIZER_RLMS7_EOM_MASK = 0x7F           # bits[6:0]


def set_eom_min_threshold_link_a(bus: SMBus, threshold: int) -> None:
    """Set Link A's eye-opening-monitor pass/fail threshold (RLMS5.EOM_MIN_THR)."""
    logging.info(">>> set_eom_min_threshold_link_a()")
    if not 0 <= threshold <= DESERIALIZER_RLMS5_EOM_MIN_THR_MASK:
        raise ValueError("EOM_MIN_THR must be 0-{}".format(DESERIALIZER_RLMS5_EOM_MIN_THR_MASK))
    rlms5 = _read_deserializer_reg(bus, DESERIALIZER_RLMS5_LINKA_REG)
    rlms5 = (rlms5 & ~DESERIALIZER_RLMS5_EOM_MIN_THR_MASK) | threshold
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_RLMS5_LINKA_REG + [rlms5],
               "\tRLMS5 (Link A) | EOM_MIN_THR: {} ({:.3f}%)".format(threshold, threshold / 64 * 100))


def read_eom_min_threshold_link_a(bus: SMBus) -> int:
    """Read back Link A's configured EOM_MIN_THR (RLMS5, bits[6:0])."""
    logging.info(">>> read_eom_min_threshold_link_a()")
    threshold = _read_deserializer_reg(bus, DESERIALIZER_RLMS5_LINKA_REG) & DESERIALIZER_RLMS5_EOM_MIN_THR_MASK
    logging.info("RLMS5 (Link A) EOM_MIN_THR: %d (%.3f%%)", threshold, threshold / 64 * 100)
    return threshold


def read_eom_result_link_a(bus: SMBus) -> Tuple[bool, int]:
    """Read Link A's last completed eye-opening measurement (RLMS7, read-only).

    EOM_DONE=False means a measurement is still in progress (it refreshes at ~1Hz),
    not an error.
    """
    logging.info(">>> read_eom_result_link_a()")
    rlms7 = _read_deserializer_reg(bus, DESERIALIZER_RLMS7_LINKA_REG)
    eom_done = bool(rlms7 & DESERIALIZER_RLMS7_EOM_DONE_BIT)
    eom_result = rlms7 & DESERIALIZER_RLMS7_EOM_MASK
    if eom_done:
        logging.info("RLMS7 (Link A): EOM=%d (%.3f%%), DONE=True", eom_result, eom_result / 64 * 100)
    else:
        logging.info("RLMS7 (Link A): EOM=INVALID/MEASURING, DONE=False")
    return eom_done, eom_result


def set_deskew_tun_offset(bus: SMBus, offset: int) -> None:
    """Set MIPI_TX53 DESKEW_TUN_OFFSET (0x0475) - experimental, no datasheet formula/
    tuning guidance is available beyond the register's name ("Tunneling Deskew Width
    Offset"); not written automatically by this script's bring-up.
    """
    logging.info(">>> set_deskew_tun_offset()")
    if not 0 <= offset <= 0xFF:
        raise ValueError("DESKEW_TUN_OFFSET must be 0-255")
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_DESKEW_TUN_OFFSET_REG + [offset],
               "\tMIPI_TX53 | DESKEW_TUN_OFFSET: {} (0x{:02X})".format(offset, offset))


def read_deskew_tun_offset(bus: SMBus) -> int:
    """Read back MIPI_TX53 DESKEW_TUN_OFFSET (0x0475)."""
    logging.info(">>> read_deskew_tun_offset()")
    offset = _read_deserializer_reg(bus, DESERIALIZER_DESKEW_TUN_OFFSET_REG)
    logging.info("MIPI_TX53 DESKEW_TUN_OFFSET: %d (0x%02X)", offset, offset)
    return offset


def read_deserializer_csi_tx_counters(bus: SMBus) -> Tuple[int, int]:
    """Read the deserializer's CSI-2/PHY1 output packet counters (4-bit nibbles, wrap at 16).

    Confirms whether the deserializer's Port A (PHY1, per this script's lane map) is
    actually transmitting CSI-2 packets toward the Jetson - independent of whether
    the sensor->serializer input side is healthy.

    Returns (csi2_tx1_pkt_cnt, phy1_pkt_cnt).
    """
    logging.info(">>> read_deserializer_csi_tx_counters()")
    phy18 = _read_deserializer_reg(bus, DESERIALIZER_MIPI_PHY18_REG)
    phy20 = _read_deserializer_reg(bus, DESERIALIZER_MIPI_PHY20_REG)
    csi2_tx1_pkt_cnt = phy18 & 0x0F
    phy1_pkt_cnt = (phy20 >> 4) & 0x0F
    logging.info(
        "Deserializer CSI TX counters: csi2_tx1_pkt_cnt=%d phy1_pkt_cnt=%d (raw MIPI_PHY18=0x%02X MIPI_PHY20=0x%02X)",
        csi2_tx1_pkt_cnt, phy1_pkt_cnt, phy18, phy20)
    return csi2_tx1_pkt_cnt, phy1_pkt_cnt


def check_deserializer_csi_tx(bus: SMBus, sample_interval: float = 1.0) -> bool:
    """Sample the deserializer's CSI-2 output counters twice to confirm Port A is transmitting.

    Run this while the sensor is streaming, after confirming (via
    check_serializer_mipi_rx()) that the serializer's input side is healthy - this
    isolates the remaining deserializer -> Jetson leg.

    Returns True if both counters changed between samples (4-bit wraparound counts).
    """
    logging.info(">>> check_deserializer_csi_tx()")
    logging.info("Sampling deserializer CSI TX counters twice, %.1f sec apart "
                 "(sensor must be streaming during this window)...", sample_interval)
    tx1_before, phy1_before = read_deserializer_csi_tx_counters(bus)
    time.sleep(sample_interval)
    tx1_after, phy1_after = read_deserializer_csi_tx_counters(bus)

    tx1_active = tx1_after != tx1_before
    phy1_active = phy1_after != phy1_before

    if not phy1_active:
        logging.error(
            "phy1_pkt_cnt did NOT change (%d -> %d): the deserializer's Port A PHY1 is NOT "
            "transmitting any CSI-2 packets toward the Jetson, even though the sensor/serializer "
            "input is healthy - check DESERIALIZER_MIPI_OUTPUT_FREQ, lane map, or tunnel routing "
            "(MIPI_TX52 TUN_DEST/TUN_EN, BACKTOP12 CSI_OUT_EN).", phy1_before, phy1_after)
    elif not tx1_active:
        logging.error(
            "phy1_pkt_cnt changed (%d -> %d) but csi2_tx1_pkt_cnt did NOT (%d -> %d): PHY1 is "
            "transmitting bits but CSI-2 Controller 1 isn't outputting packets - check "
            "MIPI_TX52 TUN_DEST (should route to controller 1).",
            phy1_before, phy1_after, tx1_before, tx1_after)
    else:
        logging.info(
            "Both counters incremented (csi2_tx1_pkt_cnt %d->%d, phy1_pkt_cnt %d->%d): the "
            "deserializer IS transmitting valid CSI-2 data out Port A. If the Jetson still "
            "times out, the issue is on the Jetson side (CSI receiver config/cabling/D-PHY "
            "lock), not this GMSL link.", tx1_before, tx1_after, phy1_before, phy1_after)

    return tx1_active and phy1_active


def read_deserializer_tunnel_errors(bus: SMBus) -> Tuple[bool, bool, bool, bool]:
    """Read MIPI_PHY17 tunnel-mode error status flags (read-only; read to clear).

    If any are set, the deserializer detected a real error in the tunneled MIPI
    stream (or a video pipe FIFO overflow) - this can explain zero CSI TX output
    even though the serializer's input side is healthy.

    Returns (tun_data_crc_err, tun_ecc_uncorr_err, tun_ecc_corr_err, vid_overflow_flag).
    """
    logging.info(">>> read_deserializer_tunnel_errors()")
    phy17 = _read_deserializer_reg(bus, DESERIALIZER_MIPI_PHY17_REG)
    tun_data_crc_err = bool(phy17 & DESERIALIZER_MIPI_PHY17_TUN_DATA_CRC_ERR_BIT)
    tun_ecc_uncorr_err = bool(phy17 & DESERIALIZER_MIPI_PHY17_TUN_ECC_UNCORR_ERR_BIT)
    tun_ecc_corr_err = bool(phy17 & DESERIALIZER_MIPI_PHY17_TUN_ECC_CORR_ERR_BIT)
    vid_overflow_flag = bool(phy17 & DESERIALIZER_MIPI_PHY17_VID_OVERFLOW_FLAG_BIT)
    logging.info(
        "Deserializer tunnel error flags: TUN_DATA_CRC_ERR=%s TUN_ECC_UNCORR_ERR=%s "
        "TUN_ECC_CORR_ERR=%s VID_OVERFLOW_FLAG=%s",
        tun_data_crc_err, tun_ecc_uncorr_err, tun_ecc_corr_err, vid_overflow_flag)
    if tun_data_crc_err or tun_ecc_uncorr_err:
        logging.error(
            "Uncorrectable tunnel error detected - the GMSL link is corrupting the tunneled "
            "MIPI data (DPHY/CPHY CRC or ECC error), which can silently stall CSI-2 output on "
            "Port A even though the serializer's input is healthy.")
    if vid_overflow_flag:
        logging.error(
            "VID_OVERFLOW_FLAG set - a video pipe FIFO overflowed, likely because the CSI "
            "output rate (DESERIALIZER_MIPI_OUTPUT_FREQ) can't keep up with the incoming "
            "tunneled data rate, or output was never actually draining (Port A not receiving).")
    return tun_data_crc_err, tun_ecc_uncorr_err, tun_ecc_corr_err, vid_overflow_flag


def check_deserializer_link_rx(bus: SMBus, sample_interval: float = 1.0) -> bool:
    """Confirm the deserializer receives ANY packets over the GMSL tunnel at all.

    This is independent of check_deserializer_csi_tx(): that checks whether
    received data makes it OUT to CSI-2/Port A; this checks whether anything
    arrives at the deserializer over the link in the first place. Selects
    PKT_CNT_SEL=All on RX0 (0x002C), then samples PKT_CNT (0x0025). PKT_CNT is
    "Read Clears All" (reading it resets it to 0), so a throwaway read is done
    first to establish a real zero baseline before timing the actual window -
    otherwise a counter already saturated at 0xFF from before this function ran
    would give a meaningless 255->255 comparison. Run while the sensor is streaming.

    Returns True if PKT_CNT is nonzero after the clear-then-wait window.
    """
    logging.info(">>> check_deserializer_link_rx()")
    rx0 = _read_deserializer_reg(bus, DESERIALIZER_RX0_REG)
    rx0 = (rx0 & ~DESERIALIZER_PKT_CNT_SEL_MASK) | DESERIALIZER_PKT_CNT_SEL_ALL
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_RX0_REG + [rx0],
               "\tRX0 : PKT_CNT_SEL set to 'All' (count all received packet types)")

    # PKT_CNT is read-clears-all: this throwaway read zeroes it out for a clean baseline
    stale = _read_deserializer_reg(bus, DESERIALIZER_PKT_CNT_REG)
    logging.info("Cleared stale PKT_CNT value (was %d before clearing)", stale)

    logging.info("Waiting %.1f sec on a freshly-cleared counter "
                 "(sensor must be streaming during this window)...", sample_interval)
    time.sleep(sample_interval)
    after = _read_deserializer_reg(bus, DESERIALIZER_PKT_CNT_REG)
    logging.info("Deserializer PKT_CNT (all received packets) since clearing: %d", after)

    active = after > 0
    if not active:
        logging.error(
            "PKT_CNT is 0 after a freshly-cleared %.1f sec window: the deserializer is NOT "
            "receiving ANY packets over the GMSL tunnel, despite the link showing LOCKED - the "
            "fault is in tunnel/link-level packet reception, not just CSI-2 output routing.",
            sample_interval)
    else:
        logging.info(
            "PKT_CNT=%d after a freshly-cleared %.1f sec window: the deserializer IS receiving "
            "packets over the GMSL tunnel. Combined with zero CSI-2 output, this isolates the "
            "fault specifically to the receive-to-CSI2-output routing/PHY stage internal to the "
            "deserializer, not tunnel reception itself.", after, sample_interval)
    return active


def read_deserializer_video_pipe_enables(bus: SMBus) -> Tuple[bool, bool, int]:
    """Read the deserializer's video pipe enable bits (REG2 VID_EN_Y/Z, VIDEO_PIPE_EN).

    Reset defaults document these as enabled (REG2 VID_EN_Y/Z=1, VIDEO_PIPE_EN=0b11),
    but this board's REG13 DEV_ID also doesn't match its documented reset value, so
    defaults aren't trusted - this reads the LIVE state rather than assuming it.

    Returns (vid_en_y, vid_en_z, video_pipe_en_bits).
    """
    logging.info(">>> read_deserializer_video_pipe_enables()")
    reg2 = _read_deserializer_reg(bus, DESERIALIZER_REG2)
    vid_en_y = bool(reg2 & DESERIALIZER_REG2_VID_EN_Y_BIT)
    vid_en_z = bool(reg2 & DESERIALIZER_REG2_VID_EN_Z_BIT)
    video_pipe_en_bits = _read_deserializer_reg(bus, DESERIALIZER_VIDEO_PIPE_EN_REG) & DESERIALIZER_VIDEO_PIPE_EN_MASK
    logging.info("Deserializer pipe enables: REG2 VID_EN_Y=%s VID_EN_Z=%s | VIDEO_PIPE_EN=0b%02s",
                 vid_en_y, vid_en_z, bin(video_pipe_en_bits)[2:].zfill(2))
    if not vid_en_y or video_pipe_en_bits == 0:
        logging.error(
            "Pipe Y is NOT enabled on this hardware (VID_EN_Y=%s, VIDEO_PIPE_EN=0b%02s) despite "
            "documented reset defaults saying it should be - this alone would explain healthy "
            "tunnel reception with zero CSI-2 output. Re-run the full bring-up (this script "
            "without a --check-* flag) to explicitly force these bits on.",
            vid_en_y, bin(video_pipe_en_bits)[2:].zfill(2))
    return vid_en_y, vid_en_z, video_pipe_en_bits


def _detect_serializer_addr(bus: SMBus, candidates: Sequence[int]) -> int:
    for addr in candidates:
        try:
            bus.write_byte_data(addr, 0x0, 0x0)
        except OSError:
            continue
        return addr
    raise GmslConfigError("Serializer not responding on addresses {}".format(
        ", ".join(hex(a) for a in candidates)))


def configure_mfp0_gpio_tunnel(bus: SMBus, serializer_addr: int,
                               channel_id: int = GPIO0_TUNNEL_CHANNEL_ID) -> None:
    """Tunnel deserializer MFP0 (GPIO 0) to serializer MFP0 (GPIO 0) over GMSL.

    Orin Nano (I2C) -> MAX7320 O0 -> MAX96792A MFP0 -> MAX96793 MFP0 -> camera sensor GPIO.
    MFP0 is driven externally by the MAX7320 GPIO port expander, not by the
    deserializer itself: the deserializer's own output driver is tri-stated
    (GPIO_OUT_DIS=1) so it doesn't fight that external drive, and the pin's
    externally-driven level is simply forwarded (GPIO_TX_EN=1) across the GMSL
    link; serializer MFP0 receives that value and drives it out on its own
    pin, wired to the camera sensor's reset GPIO. Use set_camera_sensor_reset() to
    change the level (via the MAX7320), not this function.
    """
    logging.info(">>> configure_mfp0_gpio_tunnel()")

    logging.debug("Start-Up Sequence Step 10 [DES Table 2]: DES GPIO and Other Feature Configuration")
    # Deserializer MFP0: local driver tri-stated, forwards the MAX7320-driven pin state over GMSL
    gpio_a = _read_deserializer_reg(bus, DESERIALIZER_GPIO0_A_REG)
    gpio_a |= DESERIALIZER_GPIO0_GPIO_TX_EN_BIT
    gpio_a &= ~DESERIALIZER_GPIO0_GPIO_RX_EN_BIT
    gpio_a |= DESERIALIZER_GPIO0_GPIO_OUT_DIS_BIT
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_GPIO0_A_REG + [gpio_a],
               "\tGPIO_A (GPIO 0): GPIO_TX_EN=1 GPIO_RX_EN=0 GPIO_OUT_DIS=1 (pin driven externally by MAX7320)")

    gpio_b = _read_deserializer_reg(bus, DESERIALIZER_GPIO0_B_REG)
    gpio_b = (gpio_b & ~DESERIALIZER_GPIO0_TX_ID_MASK) | (channel_id & DESERIALIZER_GPIO0_TX_ID_MASK)
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_GPIO0_B_REG + [gpio_b],
               "\tGPIO_B (GPIO 0): GPIO_TX_ID={}".format(channel_id))

    logging.debug("Start-Up Sequence Step 14 [SER Table 2]: SER GPIO and Other Feature Configuration")
    # Serializer MFP0: receives the tunneled value, output driver enabled to drive the sensor GPIO
    gpio_a = _read_serializer_reg(bus, serializer_addr, SERIALIZER_GPIO0_A_REG)
    gpio_a |= SERIALIZER_GPIO0_GPIO_RX_EN_BIT
    gpio_a &= ~SERIALIZER_GPIO0_GPIO_TX_EN_BIT
    gpio_a &= ~SERIALIZER_GPIO0_GPIO_OUT_DIS_BIT
    _i2c_write(bus, serializer_addr, SERIALIZER_GPIO0_A_REG + [gpio_a],
               "\tGPIO_A (GPIO 0): GPIO_RX_EN=1 GPIO_TX_EN=0 GPIO_OUT_DIS=0")

    gpio_c = _read_serializer_reg(bus, serializer_addr, SERIALIZER_GPIO0_C_REG)
    gpio_c = (gpio_c & ~SERIALIZER_GPIO0_RX_ID_MASK) | (channel_id & SERIALIZER_GPIO0_RX_ID_MASK)
    _i2c_write(bus, serializer_addr, SERIALIZER_GPIO0_C_REG + [gpio_c],
               "\tGPIO_C (GPIO 0): GPIO_RX_ID={}".format(channel_id))

    logging.info(
        "MFP0 GPIO tunnel configured: MAX7320 -> MAX96792A MFP0 -> MAX96793 MFP0 -> CAM sensor GPIO "
        "(channel=%d)", channel_id)


def read_mfp0_tunnel_status(bus: SMBus, serializer_addr: int) -> Tuple[bool, bool]:
    """Read back the live GPIO_IN level on both ends of the MFP0 tunnel.

    GMSL GPIO tunneling has no "link established" status bit: it just
    continuously forwards the sampled pin level. So the only way to confirm the
    tunnel is actually forwarding is to compare GPIO_IN (bit 3, read-only, live
    sampled level) on the deserializer's MFP0 against the serializer's MFP0 -
    they should always match if the tunnel is working.
    """
    logging.info(">>> read_mfp0_tunnel_status()")
    deser_gpio_a = _read_deserializer_reg(bus, DESERIALIZER_GPIO0_A_REG)
    deser_in = bool(deser_gpio_a & DESERIALIZER_GPIO0_GPIO_IN_BIT)
    ser_gpio_a = _read_serializer_reg(bus, serializer_addr, SERIALIZER_GPIO0_A_REG)
    ser_in = bool(ser_gpio_a & SERIALIZER_GPIO0_GPIO_IN_BIT)
    match = (deser_in == ser_in)
    logging.info("MFP0 tunnel: deserializer GPIO_IN=%s | serializer GPIO_IN=%s | %s",
                 deser_in, ser_in,
                 "MATCH (tunnel forwarding correctly)" if match else "MISMATCH (tunnel NOT forwarding)")
    return deser_in, ser_in


def check_mfp0_tunnel(bus: SMBus, serializer_addr: int) -> bool:
    """Confirm the MFP0 tunnel is forwarding, without touching the reset level.

    Read-only: does NOT call set_camera_sensor_reset(). The kernel's
    maxim,max7320 GPIO driver (bound to the sensor's reset-gpios in the .dts)
    owns the actual reset control on real hardware; toggling it here from
    userspace would fight that driver. Just compares the current GPIO_IN
    level on both ends, whatever it happens to be.

    Returns True if GPIO_IN matches on both ends.
    """
    logging.info(">>> check_mfp0_tunnel()")
    deser_in, ser_in = read_mfp0_tunnel_status(bus, serializer_addr)
    matched = (deser_in == ser_in)
    logging.info("MFP0 tunnel check: %s", "PASS" if matched else "FAIL")
    return matched


def _max7320_read(bus: SMBus) -> int:
    # address-only device: no register pointer, a read returns the current output latch
    read = i2c_msg.read(MAX7320_ADDR, 1)
    try:
        bus.i2c_rdwr(read)
    except OSError as exc:
        raise GmslConfigError("I2C read from MAX7320 0x{:02X} failed: {}".format(MAX7320_ADDR, exc)) from exc
    return list(read)[0]


def read_serializer_mipi_rx_counters(bus: SMBus, serializer_addr: int) -> Tuple[int, int, int, int]:
    """Read the serializer's free-running MIPI RX packet/clock counters (8-bit, wrap at 256).

    Returns (phy1_pkt_cnt, csi1_pkt_cnt, tun_pkt_cnt, phy_clk_cnt).
    """
    logging.info(">>> read_serializer_mipi_rx_counters()")
    phy1_pkt_cnt = _read_serializer_reg(bus, serializer_addr, SERIALIZER_PHY1_PKT_CNT_REG)
    csi1_pkt_cnt = _read_serializer_reg(bus, serializer_addr, SERIALIZER_CSI1_PKT_CNT_REG)
    tun_pkt_cnt = _read_serializer_reg(bus, serializer_addr, SERIALIZER_TUN_PKT_CNT_REG)
    phy_clk_cnt = _read_serializer_reg(bus, serializer_addr, SERIALIZER_PHY_CLK_CNT_REG)
    logging.info(
        "Serializer MIPI RX counters: phy1_pkt_cnt=%d csi1_pkt_cnt=%d tun_pkt_cnt=%d phy_clk_cnt=%d",
        phy1_pkt_cnt, csi1_pkt_cnt, tun_pkt_cnt, phy_clk_cnt)
    return phy1_pkt_cnt, csi1_pkt_cnt, tun_pkt_cnt, phy_clk_cnt


def check_serializer_mipi_rx(bus: SMBus, serializer_addr: int, sample_interval: float = 1.0) -> bool:
    """Sample the MIPI RX counters twice to confirm the sensor is sending data.

    Isolates sensor -> serializer from serializer -> deserializer -> Jetson: these
    counters live entirely on the serializer, so they reflect what's arriving from
    the sensor regardless of whether anything ever reaches the host. Run this
    while the sensor is actively streaming (e.g. right after triggering a capture).

    Returns True if every counter changed between samples (8-bit wraparound also
    counts as a change/activity).
    """
    logging.info(">>> check_serializer_mipi_rx()")
    logging.info("Sampling serializer MIPI RX counters twice, %.1f sec apart "
                 "(sensor must be streaming during this window)...", sample_interval)
    phy1_before, csi1_before, tun_before, clk_before = read_serializer_mipi_rx_counters(bus, serializer_addr)
    time.sleep(sample_interval)
    phy1_after, csi1_after, tun_after, clk_after = read_serializer_mipi_rx_counters(bus, serializer_addr)

    clk_active = clk_after != clk_before
    phy_active = phy1_after != phy1_before
    csi_active = csi1_after != csi1_before
    tun_active = tun_after != tun_before

    if not clk_active:
        logging.error(
            "phy_clk_cnt did NOT change (%d -> %d): the MIPI HS clock lane from the sensor "
            "is not toggling at all - check the sensor->serializer FFC cable/connector and "
            "confirm the sensor is actually powered and streaming.", clk_before, clk_after)
    elif not phy_active:
        logging.error(
            "phy_clk_cnt changed (clock lane is toggling) but phy1_pkt_cnt did NOT "
            "(%d -> %d): clock present but no valid D-PHY packets detected - check data lane "
            "wiring/polarity or a lane-count mismatch.", phy1_before, phy1_after)
    elif not csi_active:
        logging.error(
            "phy1_pkt_cnt changed (%d -> %d) but csi1_pkt_cnt did NOT (%d -> %d): physical "
            "packets are arriving but not decoding as valid CSI-2 - check MIPI_RX1 lane count / "
            "MIPI_RX2/MIPI_RX3 lane map / MIPI_RX4/MIPI_RX5 polarity settings.",
            phy1_before, phy1_after, csi1_before, csi1_after)
    elif not tun_active:
        logging.error(
            "csi1_pkt_cnt changed (%d -> %d) but tun_pkt_cnt did NOT (%d -> %d): valid CSI-2 "
            "packets are decoded but not forwarded via tunnel mode - check EXT11 Tun_Mode and "
            "FRONTTOP_0/FRONTTOP_9/TX3 pipe routing.", csi1_before, csi1_after, tun_before, tun_after)
    else:
        logging.info(
            "All counters incremented (phy_clk_cnt %d->%d, phy1_pkt_cnt %d->%d, "
            "csi1_pkt_cnt %d->%d, tun_pkt_cnt %d->%d): the sensor IS sending valid MIPI data "
            "and the serializer IS tunneling it. If the Jetson still times out, the problem is "
            "downstream: deserializer CSI output/D-PHY config or the Jetson-side CSI "
            "receiver/cabling, not the sensor or serializer input.",
            clk_before, clk_after, phy1_before, phy1_after, csi1_before, csi1_after,
            tun_before, tun_after)

    return clk_active and phy_active and csi_active and tun_active


def set_camera_sensor_reset(bus: SMBus, enable: bool) -> None:
    """Drive MAX7320 O0 (wired to MFP0, tunneled to the camera sensor's reset GPIO).

    Requires configure_mfp0_gpio_tunnel() to have been run first so the
    deserializer/serializer MFP0 path is already forwarding this pin.
    """
    logging.info(">>> set_camera_sensor_reset()")
    current = _max7320_read(bus)
    new_value = (current | MAX7320_MFP0_BIT) if enable else (current & ~MAX7320_MFP0_BIT)
    _i2c_write(bus, MAX7320_ADDR, [new_value & 0xFF],
               "\tMAX7320: O0 (MFP0 / camera sensor reset) set to {}".format(enable))


def set_serializer_dt_filter(bus: SMBus, serializer_addr: int, datatype: Optional[int]) -> None:
    """Experimental: enable/disable the serializer's DT filtering (mem_dt1_selz, 0x0318)
    for pipe Z, allowing only the given CSI-2 datatype ID (e.g. 0x2A for RAW8) onto
    the pipe.

    Not expected to have any effect in this board's configuration: tunneling mode
    (TUN_EN=1, see EXT11) does not support DT/VC filtering per the datasheet - this
    exists purely for experimentation. Pass datatype=None to disable filtering
    (write 0x00, the reset default).
    """
    logging.info(">>> set_serializer_dt_filter(datatype=%s)", hex(datatype) if datatype is not None else None)
    if datatype is None:
        value = 0x00
        desc = "disabled (reset default)"
    else:
        value = SERIALIZER_MEM_DT_SELZ_FILTER_EN_BIT | (datatype & SERIALIZER_MEM_DT_SELZ_DT_MASK)
        desc = "enabled, datatype=0x{:02X}".format(datatype & SERIALIZER_MEM_DT_SELZ_DT_MASK)
    _i2c_write(bus, serializer_addr, SERIALIZER_MEM_DT1_SELZ_REG + [value],
               "\tmem_dt1_selz (0x0318) | filter {}".format(desc))


def _configure_deserializer_link(bus: SMBus) -> None:
    """Bring up the deserializer's GMSL3 Link A (disable CSI out, set rate/mode, reset, relock)."""
    logging.info(">>> _configure_deserializer_link()")
    logging.info("Deserializer:")

    logging.debug("Start-Up Sequence Step 7 [DES Table 2]: Disable DES CSI Output")
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_BACKTOP12_REG + [DESERIALIZER_CSI_OUT_DISABLE],
               "\tBACKTOP : BACKTOP12 | CSI_OUT_EN (CSI_OUT_EN): CSI output disabled")

    logging.info("Link Initialization for Deserializer:")

    logging.debug("Start-Up Sequence Step 3 [DES Table 2]: Link Configuration (Single Link vs. Multilink Operation Setup)")
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_CTRL0_REG + [DESERIALIZER_CTRL0_AUTO_LINK_DISABLE],
               "\tTCTRL : CTRL0 | AUTO_LINK (AUTO_LINK): Disabled")

    _i2c_write(bus, DESERIALIZER_MASKED_ADDR,
               DESERIALIZER_REG1 + [DESERIALIZER_REG1_RX_RATE_12GBPS_GMSL3, DESERIALIZER_REG1_RX_RATE_MASK],
               "\tDEV : REG1 | RX_RATE (RX_RATE_PHYA): 12")

    _i2c_write(bus, DESERIALIZER_MASKED_ADDR,
               DESERIALIZER_REG4 + [DESERIALIZER_REG4_GMSL3_A_ENABLE, DESERIALIZER_REG4_GMSL3_A_MASK],
               "\tDEV : REG4 | GMSL3_A (GMSL3_A): Enabled")

    _i2c_write(bus, DESERIALIZER_MASKED_ADDR,
               DESERIALIZER_REG6 + [DESERIALIZER_REG6_I2CSEL_I2C, DESERIALIZER_REG6_I2CSEL_MASK],
               "\tDEV : REG6 | I2CSEL (I2CSEL): I2C")

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_GMSL1_EN_REG + [DESERIALIZER_GMSL1_EN_LINK_A_ONLY],
               "\tGMSL1_COMMON : GMSL1_EN | LINK_EN_A (LINK_EN_A): Enabled | LINK_EN_B (LINK_EN_B): Disabled")

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_CTRL0_REG + [DESERIALIZER_CTRL0_LINK_CFG1_RESET_ONESHOT_A],
               "\tTCTRL : CTRL0 | LINK_CFG (LINK_CFG): 0x1 | RESET_ONESHOT (RESET_ONESHOT LINK A): Activated")

    time.sleep(0x78 / 1000.0)
    logging.info("\t120 msec delay")

    logging.debug("Start-Up Sequence Step 4 [DES Table 2]: GMSL Link Lock is Established")
    logging.info("Link Initialization for Deserializer:")

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_REG1 + [DESERIALIZER_REG1_DIS_REM_CC_ENABLE],
               "\tDEV : REG1 | DIS_REM_CC (GMSL Link A I2C Port 0): Enabled")

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_REG3 + [DESERIALIZER_REG3_DIS_REM_CC_B_DISABLE],
               "\tDEV : REG3 | DIS_REM_CC_B (GMSL Link B I2C Port 0): Disabled")

    time.sleep(0x01 / 1000.0)
    logging.info("\tWarning: the actual recommended delay is 5 usec")


def _configure_serializer_mipi_input(bus: SMBus, serializer_addr: int) -> None:
    """Configure the serializer's CSI-2 input (Port B, 2 lanes, tunnel mode) from the camera."""
    logging.info(">>> _configure_serializer_mipi_input()")
    logging.debug("Start-Up Sequence Step 13 [SER Table 2]: SER MIPI RX Configuration")
    logging.info("Video Transmit Configuration for Serializer(s):")

    _i2c_write(bus, serializer_addr, SERIALIZER_REG2_REG + [SERIALIZER_REG2_VID_TX_EN_Z_DISABLE],
               "\tDEV : REG2 | VID_TX_EN_Z (VID_TX_EN_Z): Disabled")

    # Errata #7 (max96793-errata.pdf) "MIPI Receiver Requires Reset on Startup":
    # toggle mipi_rx_reset 1->0 here - serializer is powered up, video is still
    # disabled above - to force a clean D-PHY receiver re-sync in case the sensor's
    # MIPI clock/data pins were not yet stable when the serializer powered on.
    _i2c_write(bus, serializer_addr, SERIALIZER_MIPI_RX0_REG + [SERIALIZER_MIPI_RX0_RESET_BIT],
               "\tMIPI_RX : MIPI_RX0 | mipi_rx_reset (Errata #7): Asserted")
    _i2c_write(bus, serializer_addr, SERIALIZER_MIPI_RX0_REG + [0x00],
               "\tMIPI_RX : MIPI_RX0 | mipi_rx_reset (Errata #7): Released")

    logging.info("Instructions for GMSL-A serializer MAX96793:")
    logging.info("MIPI D-PHY Configuration:")

    _i2c_write(bus, serializer_addr, SERIALIZER_MIPI_RX0_REG + [SERIALIZER_MIPI_RX0_PORT_CONFIG_1X4 | SERIALIZER_MIPI_RX0_NONCONT_CLK_EN_BIT],
               "\tMIPI_RX : MIPI_RX0 | RSVD (Port Configuration): 1x4 | mipi_noncont_clk_en: Non-continuous clock")

    _i2c_write(bus, serializer_addr, SERIALIZER_EXT11_REG + [SERIALIZER_EXT11_TUN_MODE_ENABLE],
               "\tMIPI_RX_EXT : EXT11 | Tun_Mode (Tunnel Mode): Enabled")

    # ctrl1_deskewen required at >=1.5Gbps/lane - same threshold/shared end-to-end rate
    # as the deserializer's own output deskew (tunnel mode passes the sensor's real bit
    # rate through unmodified)
    output_freq_mbps = DESERIALIZER_MIPI_FREQ_MBPS.get(DESERIALIZER_MIPI_OUTPUT_FREQ, 0)
    rx_deskew_enabled = output_freq_mbps >= DESERIALIZER_DESKEW_REQUIRED_THRESHOLD_MBPS
    rx1_value = SERIALIZER_MIPI_RX1_PORTB_2LANE | (SERIALIZER_MIPI_RX1_DESKEW_EN_BIT if rx_deskew_enabled else 0)
    _i2c_write(bus, serializer_addr, SERIALIZER_MIPI_RX1_REG + [rx1_value],
               "\tMIPI_RX : MIPI_RX1 | ctrl1_num_lanes (Port B - Lane Count): 2 | ctrl1_deskewen: {} "
               "(sensor input is {} Mbps/lane, required >= {} Mbps)".format(
                   "enabled" if rx_deskew_enabled else "disabled", output_freq_mbps,
                   DESERIALIZER_DESKEW_REQUIRED_THRESHOLD_MBPS))

    _i2c_write(bus, serializer_addr, SERIALIZER_MIPI_RX2_REG + [SERIALIZER_MIPI_RX2_LANE_MAP_PHY1],
               "\tMIPI_RX : MIPI_RX2 | phy1_lane_map (Lane Map - PHY1 D0): Lane 2 | phy1_lane_map (Lane Map - PHY1 D1): Lane 3")

    _i2c_write(bus, serializer_addr, SERIALIZER_MIPI_RX3_REG + [SERIALIZER_MIPI_RX3_LANE_MAP_PHY2],
               "\tMIPI_RX : MIPI_RX3 | phy2_lane_map (Lane Map - PHY2 D0): Lane 0 | phy2_lane_map (Lane Map - PHY2 D1): Lane 1")

    # decode the constants above to trace the effective Sensor Lane -> Serializer Lane mapping
    num_lanes = ((SERIALIZER_MIPI_RX1_PORTB_2LANE >> 4) & 0x3) + 1
    lane_sources = {
        0: SERIALIZER_MIPI_RX3_LANE_MAP_PHY2 & 0x3,
        1: (SERIALIZER_MIPI_RX3_LANE_MAP_PHY2 >> 2) & 0x3,
        2: (SERIALIZER_MIPI_RX2_LANE_MAP_PHY1 >> 4) & 0x3,
        3: (SERIALIZER_MIPI_RX2_LANE_MAP_PHY1 >> 6) & 0x3,
    }
    active_map = " ".join("Lane{}<-Sensor{}".format(lane, src)
                          for lane, src in lane_sources.items() if lane < num_lanes)
    logging.debug(
        "Serializer MIPI input lane config: %d active lane(s), Sensor->Serializer map: %s",
        num_lanes, active_map)

    _i2c_write(bus, serializer_addr, SERIALIZER_MIPI_RX4_REG + [SERIALIZER_MIPI_RX4_POLARITY_NORMAL],
               "\tMIPI_RX : MIPI_RX4 | phy1_pol_map (Polarity - PHY1 Lane 0): Normal | phy1_pol_map (Polarity - PHY1 Lane 1): Normal")

    _i2c_write(bus, serializer_addr, SERIALIZER_MIPI_RX5_REG + [SERIALIZER_MIPI_RX5_POLARITY_NORMAL],
               "\tMIPI_RX : MIPI_RX5 | phy2_pol_map (Polarity - PHY2 Lane 0): Normal | phy2_pol_map (Polarity - PHY2 Lane 1): Normal | phy2_pol_map (Polarity - PHY2 Clock Lane): Normal")

    logging.info("Controller to Pipe Mapping Configuration:")

    _i2c_write(bus, serializer_addr, SERIALIZER_FRONTTOP_0_REG + [SERIALIZER_FRONTTOP_0_PORTB_START],
               "\tFRONTTOP : FRONTTOP_0 | RSVD (CLK_SELZ): Port B | START_PORTB (START_PORTB): Enabled")

    _i2c_write(bus, serializer_addr, SERIALIZER_FRONTTOP_9_REG + [SERIALIZER_FRONTTOP_9_START_VIDEO],
               "\tFRONTTOP : FRONTTOP_9 | START_PORTBZ (START_PORTBZ): Start Video")

    logging.info("Pipe Configuration:")

    _i2c_write(bus, serializer_addr, SERIALIZER_TX3_REG + [SERIALIZER_TX3_STR_SEL_PIPEZ],
               "\tCFGV__VIDEO_Z : TX3 | TX_STR_SEL (TX_STR_SEL Pipe Z): 0x0")


def _configure_deserializer_mipi_output(bus: SMBus) -> None:
    """Configure the deserializer's CSI-2 output (Port A, 2 lanes, tunnel routing).

    CSI output speed is set by DESERIALIZER_MIPI_OUTPUT_FREQ (default 800 Mbps/lane).
    """
    logging.info(">>> _configure_deserializer_mipi_output()")
    logging.debug("Start-Up Sequence Step 9 [DES Table 2]: DES MIPI TX Configuration")
    logging.info("Instructions for deserializer MAX96792A:")
    logging.info("Video Pipes And Routing Configuration:")

    # Not present in config_1.cpp (relies on documented reset defaults: REG2
    # VID_EN_Y=1, VIDEO_PIPE_EN=0b11). This board's REG13 DEV_ID also doesn't
    # match its documented reset value, so reset defaults aren't trusted here -
    # force these pipe-enable bits on explicitly rather than assuming they held.
    reg2 = _read_deserializer_reg(bus, DESERIALIZER_REG2)
    reg2 |= DESERIALIZER_REG2_VID_EN_Y_BIT | DESERIALIZER_REG2_VID_EN_Z_BIT
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_REG2 + [reg2],
               "\tDEV : REG2 | VID_EN_Y/VID_EN_Z: forced Enabled (not trusting reset default)")

    pipe_en = _read_deserializer_reg(bus, DESERIALIZER_VIDEO_PIPE_EN_REG)
    pipe_en |= DESERIALIZER_VIDEO_PIPE_EN_MASK
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_VIDEO_PIPE_EN_REG + [pipe_en],
               "\tVIDEO_PIPE_EN : VIDEO_PIPE_EN forced Enabled (not trusting reset default)")

    _i2c_write(bus, DESERIALIZER_ADDR,
               DESERIALIZER_VIDEO_PIPE_SEL_REG + [DESERIALIZER_VIDEO_PIPE_SEL_Y_LINKA_STREAM0],
               "\tVIDEO_PIPE_SEL : VIDEO_PIPE_SEL | VIDEO_PIPE_SEL_Y (STR_SELY): Link A Stream Id 0")

    logging.info("MIPI D-PHY Configuration:")

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_MIPI_PHY0_REG + [DESERIALIZER_MIPI_PHY0_2X4_MODE],
               "\tMIPI_PHY : MIPI_PHY0 | phy_4x2 (Port Configuration): 2 (1x4)")

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_MIPI_TX10_REG + [DESERIALIZER_MIPI_TX10_PORTA_2LANE],
               "\tMIPI_TX__1 : MIPI_TX10 | CSI2_LANE_CNT (Port A - Lane Count): 2")

    _i2c_write(bus, DESERIALIZER_ADDR,
               DESERIALIZER_MIPI_PHY3_REG + [DESERIALIZER_MIPI_PHY3_LANE_MAP_PHY0_PHY1],
               "\tMIPI_PHY : MIPI_PHY3 | phy0_lane_map (Lane Map - PHY0 D0): Lane 2 | phy0_lane_map (Lane Map - PHY0 D1): Lane 3 | phy1_lane_map (Lane Map - PHY1 D0): Lane 0 | phy1_lane_map (Lane Map - PHY1 D1): Lane 1")

    # decode the constants above to trace the effective PHY -> Port A lane mapping
    num_lanes = ((DESERIALIZER_MIPI_TX10_PORTA_2LANE >> 6) & 0x3) + 1
    lane_sources = {
        "PHY0.D0": DESERIALIZER_MIPI_PHY3_LANE_MAP_PHY0_PHY1 & 0x3,
        "PHY0.D1": (DESERIALIZER_MIPI_PHY3_LANE_MAP_PHY0_PHY1 >> 2) & 0x3,
        "PHY1.D0": (DESERIALIZER_MIPI_PHY3_LANE_MAP_PHY0_PHY1 >> 4) & 0x3,
        "PHY1.D1": (DESERIALIZER_MIPI_PHY3_LANE_MAP_PHY0_PHY1 >> 6) & 0x3,
    }
    active_map = " ".join("{}->Lane{}".format(src, lane)
                          for src, lane in lane_sources.items() if lane < num_lanes)
    logging.debug(
        "Deserializer MIPI output lane config: %d active lane(s), PHY->Port A map: %s",
        num_lanes, active_map)

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_MIPI_PHY5_REG + [DESERIALIZER_MIPI_PHY5_POLARITY_NORMAL],
               "\tMIPI_PHY : MIPI_PHY5 | phy0_pol_map (Polarity - PHY0 Lane 0): Normal | phy0_pol_map (Polarity - PHY0 Lane 1): Normal | phy1_pol_map (Polarity - PHY1 Lane 0): Normal | phy1_pol_map (Polarity - PHY1 Lane 1): Normal | phy1_pol_map (Polarity - PHY1 Clock Lane): Normal")

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_DPLL0_REG + [DESERIALIZER_DPLL0_SOFT_RESET_ASSERT],
               "\tDPLL__CSI2 : DPLL_0 | config_soft_rst_n (config_soft_rst_n - PHY1): 0x0")

    logging.info("\tSet predefined (coarse) CSI output frequency: CSI Phy 1 is %s Mbps/lane",
                 DESERIALIZER_MIPI_FREQ_MBPS.get(DESERIALIZER_MIPI_OUTPUT_FREQ, "unknown"))

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_DPLL0_REG + [DESERIALIZER_DPLL0_SOFT_RESET_ASSERT],
               "\tDPLL__CSI2 : DPLL_0 | (Default)")

    _i2c_write(bus, DESERIALIZER_ADDR,
               DESERIALIZER_MIPI_FREQ_REG + [DESERIALIZER_MIPI_FREQ_PREDEF_EN_BIT | DESERIALIZER_MIPI_OUTPUT_FREQ])

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_DPLL0_REG + [DESERIALIZER_DPLL0_SOFT_RESET_RELEASE],
               "\tDPLL__CSI2 : DPLL_0 | config_soft_rst_n (config_soft_rst_n - PHY1): 0x1")

    # Lane deskew is required at >=1.5Gbps/lane (optional below) and the deserializer does
    # not forward the sensor's own deskew pattern transparently - without this, the Jetson's
    # D-PHY RX can fail to lock even though packets are being transmitted (see
    # check_deserializer_csi_tx()). The Jetson only needs the one-time initial calibration
    # (DESKEW_INIT) before the first frame, not ongoing per-frame recalibration, so
    # DESKEW_PER stays off unless --deskew-period explicitly opts in.
    output_freq_mbps = DESERIALIZER_MIPI_FREQ_MBPS.get(DESERIALIZER_MIPI_OUTPUT_FREQ, 0)
    # >= (not >): datasheet requires deskew at 1.5Gbps/lane and above, inclusive - using
    # strict > previously left DESKEW_INIT disabled at exactly 1500, causing a complete
    # Jetson D-PHY lock failure (uncorr_err timeout) instead of just rate-mismatch corruption.
    deskew_enabled = output_freq_mbps >= DESERIALIZER_DESKEW_REQUIRED_THRESHOLD_MBPS
    deskew_init_value = DESERIALIZER_DESKEW_AUTO_ENABLE_WIDEST if deskew_enabled else DESERIALIZER_DESKEW_DISABLE
    periodic_enabled = deskew_enabled and DESERIALIZER_DESKEW_PERIODIC_ENABLED
    deskew_per_value = ((DESERIALIZER_DESKEW_ENABLE_BIT
                         | (DESERIALIZER_DESKEW_PERIOD_BITS << 3)
                         | DESERIALIZER_DESKEW_WIDTH_WIDEST)
                        if periodic_enabled else DESERIALIZER_DESKEW_DISABLE)
    deskew_period_frames = next((k for k, v in DESERIALIZER_DESKEW_PERIOD_CHOICES.items()
                                  if v == DESERIALIZER_DESKEW_PERIOD_BITS), "?")
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_DESKEW_INIT_REG + [deskew_init_value],
               "\tMIPI_TX__1 : MIPI_TX3 | DESKEW_INIT: {} (PHY1 output is {} Mbps/lane, required >= {} Mbps)".format(
                   "auto-enabled" if deskew_enabled else "disabled", output_freq_mbps,
                   DESERIALIZER_DESKEW_REQUIRED_THRESHOLD_MBPS))
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_DESKEW_PER_REG + [deskew_per_value],
               "\tMIPI_TX__1 : MIPI_TX4 | DESKEW_PER: {}".format(
                   "enabled, every {} frame(s)".format(deskew_period_frames) if periodic_enabled else "disabled"))

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_MIPI_PHY2_REG + [DESERIALIZER_MIPI_PHY2_PHY23_STANDBY],
               "\tMIPI_PHY : MIPI_PHY2 | phy_Stdby_n (phy_Stdby_2): Put PHY2 in standby mode | phy_Stdby_n (phy_Stdby_3): Put PHY3 in standby mode")

    logging.info("Tunnel Mode Configuration:")

    _i2c_write(bus, DESERIALIZER_ADDR,
               DESERIALIZER_MIPI_TX52_REG + [DESERIALIZER_MIPI_TX52_TUNNEL_PIPEY_DEST1_ENABLE],
               "\tMIPI_TX__1 : MIPI_TX52 | TUN_DEST (Tunneling Destination Pipe Y): 1 | TUN_EN (Pipe Y Tunnel Mode): Enabled")

    _i2c_write(bus, DESERIALIZER_ADDR,
               DESERIALIZER_TUN_PKT_START_ADDR_REG + [DESERIALIZER_TUN_PKT_START_ADDR],
               "\tMIPI_TX__1 : MIPI_TX54 | TUN_PKT_START_ADDR: 0x{:02X}".format(DESERIALIZER_TUN_PKT_START_ADDR))


def _reset_and_relock_link(bus: SMBus) -> None:
    """RESET LINK=1 / RESET LINK=0 (Start-Up Sequence steps 16-17): reset the whole
    data path so the SER/DES MIPI TX/RX configuration just applied takes effect,
    then release the reset and wait for the link to relock before CSI output is
    re-enabled.
    """
    logging.info(">>> _reset_and_relock_link()")
    logging.debug("Start-Up Sequence Step 16 [DES Table 2]: RESET LINK=1")
    _i2c_write(bus, DESERIALIZER_ADDR,
               DESERIALIZER_CTRL0_REG + [DESERIALIZER_CTRL0_LINK_CFG1 | DESERIALIZER_CTRL0_RESET_LINK_BIT],
               "\tTCTRL : CTRL0 | RESET_LINK (RESET_LINK): Activated")
    time.sleep(0x78 / 1000.0)
    logging.info("\t120 msec delay")

    logging.debug("Start-Up Sequence Step 17 [DES Table 2]: RESET LINK=0")
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_CTRL0_REG + [DESERIALIZER_CTRL0_LINK_CFG1],
               "\tTCTRL : CTRL0 | RESET_LINK (RESET_LINK): Released")
    time.sleep(0x78 / 1000.0)
    logging.info("\t120 msec delay for link to relock")

    logging.debug("Start-Up Sequence Step 18 [DES Table 2]: DES Enable CSI Output")
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_BACKTOP12_REG + [DESERIALIZER_CSI_OUT_ENABLE],
               "\tBACKTOP : BACKTOP12 | CSI_OUT_EN (CSI_OUT_EN): CSI output enabled")


def _enable_serializer_video_output(bus: SMBus, serializer_addr: int) -> None:
    """Re-enable the serializer's video transmit pipe now that both sides are configured."""
    logging.info(">>> _enable_serializer_video_output()")
    logging.debug("Start-Up Sequence Step 21 [SER Table 2]: Start Video Source")
    logging.info("Serializer:")

    _i2c_write(bus, serializer_addr, SERIALIZER_REG2_REG + [SERIALIZER_REG2_VID_TX_EN_Z_ENABLE],
               "\tDEV : REG2 | VID_TX_EN_Z (VID_TX_EN_Z): Enabled")


def gmsl_conf_max96793_max96792a(bus_number: int) -> None:
    """Replay the register sequence from config_1.cpp over I2C.

    Follows the identical "Table 2. GMSL3 SerDes Start-Up Sequence" (21 steps)
    shared by both max96792a-device-specific-user-guide.pdf (DES) and
    max96793-device-specific-user-guide.pdf (SER). Reference (see logging.debug
    output at --log-level DEBUG for exactly where each step executes):
        0  Ramp-Up Voltage Power Supply              - external (power script)
        1  Release PWDNB Pin                         - external (power script)
        2  CFG Pins Automatically Set Link           - hardware (POR-sampled)
        3  Link Configuration                        - _configure_deserializer_link() [DES]
        4  GMSL Link Lock is Established              - _configure_deserializer_link() [DES]
        5  I2C Rate Adjustment (if necessary)        - not needed, default rate used
        6  SER I2C Device Address Reassignment       - not needed, single serializer
           (if necessary)
        7  Disable DES CSI Output                    - _configure_deserializer_link() [DES]
        8  DES Errata Settings (if necessary)         - revision read/logged only (read_deserializer_revision())
        9  DES MIPI TX Configuration                 - _configure_deserializer_mipi_output() [DES]
        10 DES GPIO and Other Feature Configuration  - configure_mfp0_gpio_tunnel() [DES]
        11 DES Interrupt Handling (ERRB)/ASIL         - not implemented
        12 SER Errata Settings (if necessary)         - _apply_serializer_errata_workarounds() [SER]
           (max96793-errata.pdf #5/#6, RLMSCE 0x14CE; #7 applied in step 13)
        13 SER MIPI RX Configuration                 - _configure_serializer_mipi_input() [SER]
        14 SER GPIO and Other Feature Configuration  - configure_mfp0_gpio_tunnel() [SER]
        15 SER Interrupt Handling (ERRB)/ASIL         - not implemented
        16 RESET LINK=1                              - _reset_and_relock_link() [DES]
        17 RESET LINK=0                              - _reset_and_relock_link() [DES]
        18 DES Enable CSI Output                     - _reset_and_relock_link() [DES]
        19 Enable DES Register CRC Safety (optional) - not implemented
        20 Enable SER Register CRC Safety (optional) - not implemented
        21 Start Video Source                        - _enable_serializer_video_output() [SER]

    Raises GmslConfigError if the serializer can't be detected or any I2C
    transaction fails.
    """
    logging.info(">>> gmsl_conf_max96793_max96792a()")
    with SMBus(bus_number) as bus:
        logging.info("Deserializer detected at address %s", hex(DESERIALIZER_ADDR))
        read_deserializer_revision(bus)

        serializer_addr = _detect_serializer_addr(bus, SERIALIZER_ADDR_CANDIDATES)
        logging.info("Serializer detected at address %s", hex(serializer_addr))
        _, serializer_rev = read_serializer_revision(bus, serializer_addr)
        _apply_serializer_errata_workarounds(bus, serializer_addr, serializer_rev)
        logging.info("Configuration started")

        _configure_deserializer_link(bus)
        # route the camera sensor's reset pin over GMSL before MIPI input starts
        configure_mfp0_gpio_tunnel(bus, serializer_addr)
        _configure_serializer_mipi_input(bus, serializer_addr)
        _configure_deserializer_mipi_output(bus)
        # Start-Up Sequence steps 16-18: reset/relock the link so the MIPI TX/RX
        # config above takes effect, then enable CSI output (done inside this call)
        _reset_and_relock_link(bus)
        _enable_serializer_video_output(bus, serializer_addr)

        # Applied last (after RESET_LINK) since RESET_LINK reverts RLMS5 back to its
        # hardware reset default (0x10) - confirmed empirically on 2026-10-18: a
        # marginal eye (measured ~19-22/64) was tripping the reset-default threshold
        # and holding Pipe Y's MIPI TX output in a near-permanent reset (packet
        # counters stuck at 0 despite GMSL link + VIDEO_LOCK both showing healthy).
        # See DESERIALIZER_EOM_MIN_THR_DEFAULT comment for the caveat that EOM is
        # only a recommended diagnostic for GMSL2 mode (3/6Gbps), not GMSL3 (12Gbps,
        # this board's rate) - this is an empirical workaround, not a guaranteed fix.
        set_eom_min_threshold_link_a(bus, DESERIALIZER_EOM_MIN_THR_DEFAULT)

        logging.info("Configuration completed")
        read_deserializer_link_status(bus)
        enable_serializer_i2c_passthrough_channel1(bus, serializer_addr)
        read_serializer_i2c_passthrough(bus, serializer_addr)


def main(argv: Optional[List[str]] = None) -> int:
    print("config_1_max96793_max96792a_init.py version {}".format(SCRIPT_VERSION))
    parser = argparse.ArgumentParser(
        description="Bring up the MAX96793/MAX96792A GMSL2/3 tunnel-mode link over I2C.")
    parser.add_argument("bus", nargs="?", type=int, default=2,
                        help="I2C bus number (default: 2)")
    parser.add_argument("--log-level", default="ALL",
                        choices=["ALL", "DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging verbosity (default: ALL, i.e. show every log level)")
    parser.add_argument("--set-camera-reset", type=int, choices=[0, 1], default=None,
                        help="Skip GMSL bring-up; just drive the MAX7320 O0 output (MFP0, "
                             "camera sensor reset) high(1) or low(0)")
    parser.add_argument("--check-mfp0-tunnel", action="store_true",
                        help="Skip GMSL bring-up; toggle the MAX7320-driven MFP0 tunnel and "
                             "confirm the deserializer/serializer GPIO_IN levels match")
    parser.add_argument("--mipi-freq", choices=sorted(DESERIALIZER_MIPI_FREQ_CHOICES, key=int),
                        default=None,
                        help="Override DESERIALIZER_MIPI_OUTPUT_FREQ (Mbps/lane) for this run only, "
                             "without editing the script")
    parser.add_argument("--tun-pkt-start-addr", type=lambda s: int(s, 0), default=None,
                        help="Override MIPI_TX54 TUN_PKT_START_ADDR (0-255, accepts 0xNN) for this "
                             "run only - the start address of the long packet within the tunneled "
                             "byte stream, left at reset default (0x00) otherwise. A sensor whose "
                             "packet structure differs (e.g. an embedded-data line ahead of the "
                             "image data) may need this adjusted.")
    parser.add_argument("--deskew-period", choices=sorted(DESERIALIZER_DESKEW_PERIOD_CHOICES, key=int),
                        default=None,
                        help="Opt in to periodic lane-deskew recalibration every N frames for "
                             "this run only (off by default - the Jetson only needs the one-time "
                             "initial deskew before the first frame, not per-frame recalibration). "
                             "Only applies when deskew is enabled, i.e. --mipi-freq >= 1500")
    parser.add_argument("--check-serializer-mipi-rx", action="store_true",
                        help="Skip GMSL bring-up; sample the serializer's MIPI RX packet/clock "
                             "counters twice to confirm the sensor is actually sending data into "
                             "the serializer (run this while the sensor is streaming)")
    parser.add_argument("--check-deserializer-csi-tx", action="store_true",
                        help="Skip GMSL bring-up; sample the deserializer's CSI-2 output packet "
                             "counters twice to confirm Port A is actually transmitting toward "
                             "the Jetson (run this while the sensor is streaming)")
    parser.add_argument("--check-deserializer-errors", action="store_true",
                        help="Skip GMSL bring-up; read the deserializer's tunnel-mode error "
                             "status flags (CRC/ECC errors, video pipe overflow)")
    parser.add_argument("--check-deserializer-link-rx", action="store_true",
                        help="Skip GMSL bring-up; sample the deserializer's generic received-"
                             "packet counter twice to confirm it's receiving ANY packets over "
                             "the GMSL tunnel (independent of CSI-2 output; run while streaming)")
    parser.add_argument("--check-deserializer-pipe-enables", action="store_true",
                        help="Skip GMSL bring-up; read the deserializer's live video pipe "
                             "enable bits (REG2 VID_EN_Y/Z, VIDEO_PIPE_EN) instead of trusting "
                             "documented reset defaults")
    parser.add_argument("--set-dt-filter", type=lambda s: int(s, 0), default=None,
                        help="Skip GMSL bring-up; experimental - enable the serializer's DT "
                             "filtering (mem_dt1_selz, 0x0318) for the given CSI-2 datatype ID "
                             "(e.g. 0x2A for RAW8), only allowing that datatype onto pipe Z. "
                             "Not expected to have any effect in tunneling mode (this board's "
                             "configuration) - DT/VC filtering is a pixel-mode-only feature per "
                             "the datasheet.")
    parser.add_argument("--clear-dt-filter", action="store_true",
                        help="Skip GMSL bring-up; disable the serializer's DT filtering "
                             "(mem_dt1_selz, 0x0318), restoring the reset default (0x00)")
    parser.add_argument("--eom-min-threshold", type=int, default=None,
                        metavar="0-127",
                        help="Skip GMSL bring-up; set Link A's eye-opening-monitor pass/fail "
                             "threshold (RLMS5.EOM_MIN_THR, %% eye-opening = value/64) without "
                             "running the full bring-up. Datasheet reset default is {} "
                             "({:.3f}%%); this script's own bring-up now applies {} ({:.3f}%%) "
                             "automatically at the end of every run (see "
                             "DESERIALIZER_EOM_MIN_THR_DEFAULT comment for the multi-board "
                             "validation caveat) - only pass this flag to test a different "
                             "value".format(
                                 DESERIALIZER_EOM_MIN_THR_RESET_DEFAULT,
                                 DESERIALIZER_EOM_MIN_THR_RESET_DEFAULT / 64 * 100,
                                 DESERIALIZER_EOM_MIN_THR_DEFAULT,
                                 DESERIALIZER_EOM_MIN_THR_DEFAULT / 64 * 100))
    parser.add_argument("--check-eom-min-threshold", action="store_true",
                        help="Skip GMSL bring-up; read back Link A's configured EOM_MIN_THR")
    parser.add_argument("--check-eom-result", action="store_true",
                        help="Skip GMSL bring-up; read Link A's last completed eye-opening "
                             "measurement (RLMS7) once and compare it against the configured "
                             "EOM_MIN_THR - for repeated sampling use "
                             "debug_max96792a_register_configuration.py --check-eom-result")
    parser.add_argument("--deskew-tun-offset", type=lambda s: int(s, 0), default=None,
                        metavar="0-255",
                        help="Skip GMSL bring-up; set MIPI_TX53 DESKEW_TUN_OFFSET (0x0475, "
                             "accepts 0xNN) - experimental tunnel-mode-specific deskew width "
                             "offset, datasheet reset default is 0 and gives no tuning formula "
                             "beyond the register's name; not applied automatically by bring-up")
    parser.add_argument("--check-deskew-tun-offset", action="store_true",
                        help="Skip GMSL bring-up; read back MIPI_TX53 DESKEW_TUN_OFFSET")
    parser.add_argument("--disable-ffe-short-channel", action="store_true",
                        help="Apply max96793-errata.pdf Errata #5 (RLMSCE.enffe=0) for this run - "
                             "only use if this board's GMSL coax cable has been confirmed to have "
                             "<1dB insertion loss (a very short cable); off by default")
    args = parser.parse_args(argv)
    # "ALL" is not a real logging level; DEBUG is the lowest level, so it shows everything
    logging.getLogger().setLevel(logging.DEBUG if args.log_level == "ALL" else args.log_level)

    if args.mipi_freq is not None:
        global DESERIALIZER_MIPI_OUTPUT_FREQ
        DESERIALIZER_MIPI_OUTPUT_FREQ = DESERIALIZER_MIPI_FREQ_CHOICES[args.mipi_freq]

    if args.tun_pkt_start_addr is not None:
        if not (0 <= args.tun_pkt_start_addr <= 0xFF):
            parser.error("--tun-pkt-start-addr must be 0-255 (0x00-0xFF)")
        global DESERIALIZER_TUN_PKT_START_ADDR
        DESERIALIZER_TUN_PKT_START_ADDR = args.tun_pkt_start_addr

    if args.deskew_period is not None:
        global DESERIALIZER_DESKEW_PERIODIC_ENABLED, DESERIALIZER_DESKEW_PERIOD_BITS
        DESERIALIZER_DESKEW_PERIODIC_ENABLED = True
        DESERIALIZER_DESKEW_PERIOD_BITS = DESERIALIZER_DESKEW_PERIOD_CHOICES[args.deskew_period]

    if args.disable_ffe_short_channel:
        global SERIALIZER_DISABLE_FFE_SHORT_CHANNEL
        SERIALIZER_DISABLE_FFE_SHORT_CHANNEL = True

    try:
        if args.check_mfp0_tunnel:
            with SMBus(args.bus) as bus:
                serializer_addr = _detect_serializer_addr(bus, SERIALIZER_ADDR_CANDIDATES)
                if not check_mfp0_tunnel(bus, serializer_addr):
                    return 1
        elif args.check_serializer_mipi_rx:
            with SMBus(args.bus) as bus:
                serializer_addr = _detect_serializer_addr(bus, SERIALIZER_ADDR_CANDIDATES)
                if not check_serializer_mipi_rx(bus, serializer_addr):
                    return 1
        elif args.check_deserializer_csi_tx:
            with SMBus(args.bus) as bus:
                if not check_deserializer_csi_tx(bus):
                    return 1
        elif args.check_deserializer_errors:
            with SMBus(args.bus) as bus:
                errors = read_deserializer_tunnel_errors(bus)
                if any(errors):
                    return 1
        elif args.check_deserializer_link_rx:
            with SMBus(args.bus) as bus:
                if not check_deserializer_link_rx(bus):
                    return 1
        elif args.check_deserializer_pipe_enables:
            with SMBus(args.bus) as bus:
                vid_en_y, vid_en_z, video_pipe_en_bits = read_deserializer_video_pipe_enables(bus)
                if not vid_en_y or video_pipe_en_bits == 0:
                    return 1
        elif args.set_camera_reset is not None:
            with SMBus(args.bus) as bus:
                set_camera_sensor_reset(bus, bool(args.set_camera_reset))
        elif args.set_dt_filter is not None:
            with SMBus(args.bus) as bus:
                serializer_addr = _detect_serializer_addr(bus, SERIALIZER_ADDR_CANDIDATES)
                set_serializer_dt_filter(bus, serializer_addr, args.set_dt_filter)
        elif args.clear_dt_filter:
            with SMBus(args.bus) as bus:
                serializer_addr = _detect_serializer_addr(bus, SERIALIZER_ADDR_CANDIDATES)
                set_serializer_dt_filter(bus, serializer_addr, None)
        elif args.eom_min_threshold is not None:
            with SMBus(args.bus) as bus:
                set_eom_min_threshold_link_a(bus, args.eom_min_threshold)
        elif args.check_eom_min_threshold:
            with SMBus(args.bus) as bus:
                read_eom_min_threshold_link_a(bus)
        elif args.check_eom_result:
            with SMBus(args.bus) as bus:
                eom_done, eom_result = read_eom_result_link_a(bus)
                threshold = read_eom_min_threshold_link_a(bus)
                if eom_done and eom_result < threshold:
                    return 1
        elif args.deskew_tun_offset is not None:
            with SMBus(args.bus) as bus:
                set_deskew_tun_offset(bus, args.deskew_tun_offset)
        elif args.check_deskew_tun_offset:
            with SMBus(args.bus) as bus:
                read_deskew_tun_offset(bus)
        else:
            gmsl_conf_max96793_max96792a(args.bus)
    except GmslConfigError as exc:
        logging.error("GMSL configuration failed: %s", exc)
        return 1
    except OSError as exc:
        logging.error("I2C bus error on bus %s: %s", args.bus, exc)
        return 1

    logging.info("GMSL configuration succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())

