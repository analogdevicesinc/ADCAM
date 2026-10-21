"""
Standalone CLI to validate registers from max96793-device-specific-user-guide.pdf
(MAX96793 serializer) against this board's expected configuration. The serializer
is physically identical across both board pairings in this repo, so this script
works with either config script's module - it imports
config_1_max96793_max96792a_init.py if present, otherwise falls back to
config_1_max96793_max96726A_init.py (both expose the same SERIALIZER_* register
constants/helpers used here).

Run the normal GMSL3 bring-up first:
    sudo python3 config_1_max96793_max96792a_init.py
    # or, on the MAX96726A-paired board:
    sudo python3 config_1_max96793_max96726A_init.py

Usage:
    # validate Table 3 (Pixel and Tunneling Mode Register Settings: TUN_EN)
    sudo python3 debug_max96793_register_configuration.py --check-tunnel-mode
    sudo python3 debug_max96793_register_configuration.py --check-tunnel-mode --bus 2 --log-level DEBUG

    # validate Table 6 (Link Initialization Registers: TX_RATE, CXTP_A, CTRL0 reset bits)
    sudo python3 debug_max96793_register_configuration.py --check-link-init

    # validate Table 7 (Video Pipe Selection Registers: TX_STR_SEL Pipe Z)
    sudo python3 debug_max96793_register_configuration.py --check-video-pipe-sel

    # validate Table 8 (Video Pipe and Filtering Registers: START_PORTB, CLK_SELZ,
    # VID_TX_EN_Z, TX_STR_SEL, DT/VC filtering)
    sudo python3 debug_max96793_register_configuration.py --check-video-pipe-filtering

    # validate Table 14 (MIPI PHY Setting Registers: mipi_noncontclk_en, phy_config,
    # ctrl1_num_lanes, lane map/polarity, ctrl1_deskewen)
    sudo python3 debug_max96793_register_configuration.py --check-mipi-phy-settings

    # sample EXT21-24 (0x038D-0x0390) repeatedly (sensor must be streaming) to confirm
    # packets are actually received from the sensor, processed, and pushed into the
    # GMSL tunnel
    sudo python3 debug_max96793_register_configuration.py --check-mipi-packet-counters --samples 8 --interval 1.0

    # sample CSI_ERR_L (0x0343) bit 7 repeatedly (sensor must be streaming) - Figure 3's
    # "CHECK CSI-2 CRC" step, confirming CRC_ERR never asserts on the sensor-facing input
    sudo python3 debug_max96793_register_configuration.py --check-crc --samples 8 --interval 1.0

    # live, end-to-end pipeline check (sensor must be streaming): sensor -> serializer
    # clock (PCLKDET) -> CSI-2 PHY -> Controller 1/Video Pipe -> GMSL Tunnel, with a
    # per-stage PASS/FAIL summary so a broken stage can be isolated
    sudo python3 debug_max96793_register_configuration.py --stream-check --samples 8 --interval 1.0

    # run every table validation with a consolidated PASS/FAIL summary
    sudo python3 debug_max96793_register_configuration.py --all

    # print a low-level report of every table's current register state, no checks
    sudo python3 debug_max96793_register_configuration.py --show-config

Exit status: 0 if the requested check(s) pass, 1 otherwise.
"""
import argparse
import logging
import sys
import time
from typing import Optional, Sequence

from smbus2 import SMBus

try:
    import config_1_max96793_max96792a_init as m
except ImportError:
    import config_1_max96793_max96726A_init as m

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def _serializer_addr(bus: SMBus) -> int:
    return m._detect_serializer_addr(bus, m.SERIALIZER_ADDR_CANDIDATES)


# Table 3 ("MAX96793 Pixel and Tunneling Mode Register Settings") - TUN_EN (0x0383
# bit 7), matching config_1_max96793_max96792a_init.py's SERIALIZER_EXT11_REG exactly.
# POR 0b0 = Pixel Mode, 0b1 = Tunneling Mode.
DESERIALIZER_TUN_EN_BIT = 0x80  # named for the register's own bit, not a deserializer field


def validate_pixel_tunnel_mode_table(bus: SMBus, serializer_addr: int) -> bool:
    """Read back and validate the User Guide's Table 3 (Pixel and Tunneling Mode
    Register Settings: TUN_EN) against this board's expected Tunneling Mode
    configuration.

    Returns True if TUN_EN reads back as Tunneling Mode.
    """
    logging.info(">>> validate_pixel_tunnel_mode_table()")

    ext11 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_EXT11_REG)
    tunneling = bool(ext11 & DESERIALIZER_TUN_EN_BIT)
    logging.info("EXT11 TUN_EN (0x0383) = 0x%02X | mode=%s | expect Tunneling Mode | %s",
                 ext11, "Tunneling Mode" if tunneling else "Pixel Mode",
                 "OK" if tunneling else "MISMATCH")

    logging.info("RESULT: Table 3 Pixel/Tunneling Mode validation %s", "PASSED" if tunneling else "FAILED")
    return tunneling


# Table 6 ("MAX96793 Link Initialization Registers") - CTRL0 (0x0010) holds the same
# three reset-control bits as the deserializer's CTRL0 (RESET_ALL/RESET_LINK/
# RESET_ONESHOT), expected all released/self-cleared after bring-up. TX_RATE (0x0001
# bits[3:2]) and CXTP_A (0x0011 bit 0) are NOT configured by
# config_1_max96793_max96792a_init.py - the serializer's GMSL3/12Gbps rate is fixed
# via a hardware CFG-pin strap, not software, so these are logged for visibility
# only (confirming the strap landed on the expected rate), not enforced.
SERIALIZER_CTRL0_REG = [0x00, 0x10]
SERIALIZER_CTRL0_RESET_ALL_BIT = 0x80
SERIALIZER_CTRL0_RESET_LINK_BIT = 0x40
SERIALIZER_CTRL0_RESET_ONESHOT_BIT = 0x20
SERIALIZER_TX_RATE_REG = [0x00, 0x01]
SERIALIZER_TX_RATE_SHIFT = 2
SERIALIZER_TX_RATE_MASK = 0x03 << SERIALIZER_TX_RATE_SHIFT
SERIALIZER_TX_RATE_NAMES = {0b00: "RSVD", 0b01: "3Gbps", 0b10: "6Gbps", 0b11: "12Gbps"}
SERIALIZER_CXTP_A_REG = [0x00, 0x11]
SERIALIZER_CXTP_A_BIT = 0x01


def validate_link_init_table(bus: SMBus, serializer_addr: int) -> bool:
    """Read back and validate the User Guide's Table 6 (Link Initialization
    Registers: TX_RATE, CXTP_A, CTRL0 reset bits) against this board's expected
    configuration.

    Returns True if none of CTRL0's three reset bits are left asserted. TX_RATE
    and CXTP_A are logged for visibility only, not enforced - the serializer's
    GMSL3 rate/cable mode is fixed via a hardware CFG-pin strap, not software.
    """
    logging.info(">>> validate_link_init_table()")

    ctrl0 = m._read_serializer_reg(bus, serializer_addr, SERIALIZER_CTRL0_REG)
    reset_all = bool(ctrl0 & SERIALIZER_CTRL0_RESET_ALL_BIT)
    reset_link = bool(ctrl0 & SERIALIZER_CTRL0_RESET_LINK_BIT)
    reset_oneshot = bool(ctrl0 & SERIALIZER_CTRL0_RESET_ONESHOT_BIT)
    resets_clear = not (reset_all or reset_link or reset_oneshot)
    logging.info("CTRL0 (0x0010) = 0x%02X | RESET_ALL=%s RESET_LINK=%s RESET_ONESHOT=%s | "
                 "expect all False (released/self-cleared) | %s",
                 ctrl0, reset_all, reset_link, reset_oneshot,
                 "OK" if resets_clear else "MISMATCH (a reset bit is still asserted)")

    tx_rate = (m._read_serializer_reg(bus, serializer_addr, SERIALIZER_TX_RATE_REG)
               & SERIALIZER_TX_RATE_MASK) >> SERIALIZER_TX_RATE_SHIFT
    logging.info("TX_RATE (0x0001 bits[3:2]) = 0b%02s (%s) - informational only, not enforced "
                 "(fixed via hardware CFG-pin strap, not software)",
                 bin(tx_rate)[2:].zfill(2), SERIALIZER_TX_RATE_NAMES.get(tx_rate, "?"))

    cxtp_a = bool(m._read_serializer_reg(bus, serializer_addr, SERIALIZER_CXTP_A_REG) & SERIALIZER_CXTP_A_BIT)
    logging.info("CXTP_A (0x0011 bit 0) = %s (%s) - informational only, not enforced",
                 cxtp_a, "Coax" if cxtp_a else "STP")

    logging.info("RESULT: Table 6 Link Initialization validation %s", "PASSED" if resets_clear else "FAILED")
    return resets_clear


# Table 7 ("MAX96793 Video Pipe Selection Registers") - TX_STR_SEL (0x005B bits[1:0],
# Pipe Z's stream ID), matching config_1_max96793_max96792a_init.py's SERIALIZER_TX3_REG
# exactly. Reset default is Stream ID 2 (0b10), but this board's script explicitly
# overrides it to Stream ID 0 (0b00) to match the deserializer's VIDEO_PIPE_SEL_Y
# expectation (Link A, str_id=00).
SERIALIZER_TX_STR_SEL_MASK = 0x03
SERIALIZER_TX_STR_SEL_NAMES = {0b00: "Stream ID 0", 0b01: "Stream ID 1",
                               0b10: "Stream ID 2", 0b11: "Stream ID 3"}


def validate_video_pipe_selection_table(bus: SMBus, serializer_addr: int) -> bool:
    """Read back and validate the User Guide's Table 7 (Video Pipe Selection
    Registers: TX_STR_SEL, Pipe Z) against this board's expected Stream ID 0
    configuration.

    Returns True if TX_STR_SEL reads back as Stream ID 0.
    """
    logging.info(">>> validate_video_pipe_selection_table()")

    tx3 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_TX3_REG)
    str_sel = tx3 & SERIALIZER_TX_STR_SEL_MASK
    str_sel_ok = str_sel == m.SERIALIZER_TX3_STR_SEL_PIPEZ
    logging.info("TX_STR_SEL Pipe Z (0x005B) = 0x%02X (%s) | expect 0x%02X (%s) | %s",
                 tx3, SERIALIZER_TX_STR_SEL_NAMES.get(str_sel, "?"), m.SERIALIZER_TX3_STR_SEL_PIPEZ,
                 SERIALIZER_TX_STR_SEL_NAMES.get(m.SERIALIZER_TX3_STR_SEL_PIPEZ, "?"),
                 "OK" if str_sel_ok else "MISMATCH")

    logging.info("RESULT: Table 7 Video Pipe Selection validation %s", "PASSED" if str_sel_ok else "FAILED")
    return str_sel_ok


# Table 8 ("MAX96793 Video Pipe and Filtering Registers") - START_PORTB/CLK_SELZ
# (0x0308), VID_TX_EN_Z (0x0002 bit 6), TX_STR_SEL (0x005B, same register validated
# by Table 7), all matching config_1_max96793_max96792a_init.py's constants exactly.
# DT filtering (mem_dt{1,2,7,8}_selz, e.g. 0x0318) and VC filtering (VC_SELZ_L/H,
# 0x030D/0x030E) are NOT configured by this board's script - tunneling mode doesn't
# support DT/VC filtering at all (see Table 4), so these are logged for visibility
# only, expected to remain at their reset defaults (filtering disabled, all VCs
# allowed).
SERIALIZER_FRONTTOP_0_START_PORTB_BIT = 0x20
SERIALIZER_FRONTTOP_0_CLK_SELZ_BIT = 0x04
SERIALIZER_REG2_VID_TX_EN_Z_BIT = 0x40
SERIALIZER_MEM_DT1_SELZ_REG = [0x03, 0x18]
SERIALIZER_MEM_DT_SELZ_FILTER_EN_BIT = 0x40
SERIALIZER_MEM_DT_SELZ_DT_MASK = 0x3F
SERIALIZER_VC_SELZ_L_REG = [0x03, 0x0D]
SERIALIZER_VC_SELZ_H_REG = [0x03, 0x0E]


def validate_video_pipe_filtering_table(bus: SMBus, serializer_addr: int) -> bool:
    """Read back and validate the User Guide's Table 8 (Video Pipe and Filtering
    Registers: START_PORTB, CLK_SELZ, VID_TX_EN_Z, TX_STR_SEL) against this board's
    expected configuration.

    Returns True if Port B/pipe Z video output is enabled and routed, and TX_STR_SEL
    is Stream ID 0. DT/VC filtering registers are logged for visibility only, not
    enforced - tunneling mode doesn't support DT/VC filtering, so this board's
    script never touches them.
    """
    logging.info(">>> validate_video_pipe_filtering_table()")
    ok = True

    fronttop_0 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_FRONTTOP_0_REG)
    start_portb = bool(fronttop_0 & SERIALIZER_FRONTTOP_0_START_PORTB_BIT)
    clk_selz = bool(fronttop_0 & SERIALIZER_FRONTTOP_0_CLK_SELZ_BIT)
    fronttop_0_ok = start_portb and clk_selz
    ok = ok and fronttop_0_ok
    logging.info("FRONTTOP_0 (0x0308) = 0x%02X | START_PORTB=%s CLK_SELZ=%s | expect both True | %s",
                 fronttop_0, start_portb, clk_selz, "OK" if fronttop_0_ok else "MISMATCH")

    reg2 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_REG2_REG)
    vid_tx_en_z = bool(reg2 & SERIALIZER_REG2_VID_TX_EN_Z_BIT)
    ok = ok and vid_tx_en_z
    logging.info("REG2 (0x0002) VID_TX_EN_Z = %s | expect True (enabled) | %s",
                 vid_tx_en_z, "OK" if vid_tx_en_z else "MISMATCH")

    tx3 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_TX3_REG)
    str_sel = tx3 & SERIALIZER_TX_STR_SEL_MASK
    str_sel_ok = str_sel == m.SERIALIZER_TX3_STR_SEL_PIPEZ
    ok = ok and str_sel_ok
    logging.info("TX_STR_SEL Pipe Z (0x005B) = 0x%02X (%s) | expect 0x%02X (%s) | %s",
                 tx3, SERIALIZER_TX_STR_SEL_NAMES.get(str_sel, "?"), m.SERIALIZER_TX3_STR_SEL_PIPEZ,
                 SERIALIZER_TX_STR_SEL_NAMES.get(m.SERIALIZER_TX3_STR_SEL_PIPEZ, "?"),
                 "OK" if str_sel_ok else "MISMATCH")

    dt_filter = m._read_serializer_reg(bus, serializer_addr, SERIALIZER_MEM_DT1_SELZ_REG)
    dt_filter_en = bool(dt_filter & SERIALIZER_MEM_DT_SELZ_FILTER_EN_BIT)
    dt_filter_value = dt_filter & SERIALIZER_MEM_DT_SELZ_DT_MASK
    vc_selz_l = m._read_serializer_reg(bus, serializer_addr, SERIALIZER_VC_SELZ_L_REG)
    vc_selz_h = m._read_serializer_reg(bus, serializer_addr, SERIALIZER_VC_SELZ_H_REG)
    logging.info("mem_dt1_selz (0x0318) = 0x%02X | filter_en=%s datatype=0x%02X, VC_SELZ_L/H "
                 "(0x030D/0x030E) = 0x%02X/0x%02X - informational only, not enforced (DT/VC "
                 "filtering not supported in tunneling mode)",
                 dt_filter, dt_filter_en, dt_filter_value, vc_selz_l, vc_selz_h)

    logging.info("RESULT: Table 8 Video Pipe and Filtering validation %s", "PASSED" if ok else "FAILED")
    return ok


# Table 14 ("MAX96793 MIPI PHY Setting Registers") - all fields below match
# config_1_max96793_max96792a_init.py's SERIALIZER_MIPI_RX* constants/addresses
# exactly for this board's active sensor-facing CSI-2 input (Port B, 2 lanes).
SERIALIZER_MIPI_RX0_VC_MAP_EN_BIT = 0x20
SERIALIZER_MIPI_RX0_RESET_BIT = 0x08
SERIALIZER_MIPI_RX0_PHY_CONFIG_MASK = 0x07
SERIALIZER_MIPI_RX1_VCX_EN_BIT = 0x80
SERIALIZER_MIPI_RX1_DESKEW_EN_BIT = 0x40
SERIALIZER_MIPI_RX1_NUM_LANES_SHIFT = 4
SERIALIZER_MIPI_RX1_NUM_LANES_MASK = 0x03 << SERIALIZER_MIPI_RX1_NUM_LANES_SHIFT
SERIALIZER_MIPI_RX1_NUM_LANES_NAMES = {0b00: "1 lane", 0b01: "2 lanes", 0b10: "3 lanes", 0b11: "4 lanes"}


def validate_mipi_phy_settings_table(bus: SMBus, serializer_addr: int) -> bool:
    """Read back and validate the User Guide's Table 14 (MIPI PHY Setting Registers)
    against this board's expected Port B, 2-lane, non-continuous-clock configuration.

    Returns True if MIPI_RX0 (non-continuous clock enabled, phy_config=1x4, MIPI RX
    not held in reset), MIPI_RX1 (2 data lanes, deskew disabled - this board's
    configured rate is below the 1.5Gbps/lane threshold), MIPI_RX2/RX3 (lane map),
    and MIPI_RX4/RX5 (normal polarity) all match. ctrl1_vc_map_en/ctrl1_vcx_en are
    logged for visibility only, not enforced (not configured by this board's script).
    """
    logging.info(">>> validate_mipi_phy_settings_table()")
    ok = True

    rx0 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_MIPI_RX0_REG)
    noncont_clk = bool(rx0 & m.SERIALIZER_MIPI_RX0_NONCONT_CLK_EN_BIT)
    vc_map_en = bool(rx0 & SERIALIZER_MIPI_RX0_VC_MAP_EN_BIT)
    rx_reset = bool(rx0 & SERIALIZER_MIPI_RX0_RESET_BIT)
    phy_config = rx0 & SERIALIZER_MIPI_RX0_PHY_CONFIG_MASK
    rx0_ok = noncont_clk and not rx_reset and phy_config == 0
    ok = ok and rx0_ok
    logging.info("MIPI_RX0 (0x0330) = 0x%02X | mipi_noncontclk_en=%s mipi_rx_reset=%s "
                 "phy_config=0x%X | expect noncont_clk=True, reset=False, phy_config=0x0 (1x4) | %s",
                 rx0, noncont_clk, rx_reset, phy_config, "OK" if rx0_ok else "MISMATCH")
    logging.info("MIPI_RX0 ctrl1_vc_map_en = %s - informational only, not enforced", vc_map_en)

    rx1 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_MIPI_RX1_REG)
    vcx_en = bool(rx1 & SERIALIZER_MIPI_RX1_VCX_EN_BIT)
    deskew_en = bool(rx1 & SERIALIZER_MIPI_RX1_DESKEW_EN_BIT)
    num_lanes = (rx1 & SERIALIZER_MIPI_RX1_NUM_LANES_MASK) >> SERIALIZER_MIPI_RX1_NUM_LANES_SHIFT
    # deskew is only required at >=1.5Gbps/lane on the MAX96792A-paired board - reuse
    # the deserializer output frequency as the shared link rate reference (tunnel mode
    # passes the sensor's exact rate through unmodified end-to-end). The MAX96726A-paired
    # board has no such threshold constant - that board enables deskew unconditionally
    # (confirmed on hardware: disabling it below 1.5Gbps/lane left PHY1's data lanes
    # stuck in LP while the clock lane still entered HS), so deskew is always required
    # when running against that config module instead.
    output_freq_mbps = m.DESERIALIZER_MIPI_FREQ_MBPS.get(m.DESERIALIZER_MIPI_OUTPUT_FREQ, 0)
    if hasattr(m, "DESERIALIZER_DESKEW_REQUIRED_THRESHOLD_MBPS"):
        deskew_required = output_freq_mbps >= m.DESERIALIZER_DESKEW_REQUIRED_THRESHOLD_MBPS
    else:
        deskew_required = True
    rx1_ok = (num_lanes == 0b01) and (deskew_en == deskew_required)
    ok = ok and rx1_ok
    logging.info("MIPI_RX1 (0x0331) = 0x%02X | ctrl1_num_lanes=%s ctrl1_deskewen=%s | link_rate=%d "
                 "Mbps/lane, deskew_required=%s | expect 2 lanes, deskew_en=%s | %s",
                 rx1, SERIALIZER_MIPI_RX1_NUM_LANES_NAMES.get(num_lanes, "?"), deskew_en,
                 output_freq_mbps, deskew_required, deskew_required, "OK" if rx1_ok else "MISMATCH")
    logging.info("MIPI_RX1 ctrl1_vcx_en = %s - informational only, not enforced", vcx_en)

    rx2 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_MIPI_RX2_REG)
    rx2_ok = rx2 == m.SERIALIZER_MIPI_RX2_LANE_MAP_PHY1
    ok = ok and rx2_ok
    logging.info("MIPI_RX2 (0x0332) phy1_lane_map = 0x%02X | expect 0x%02X | %s",
                 rx2, m.SERIALIZER_MIPI_RX2_LANE_MAP_PHY1, "OK" if rx2_ok else "MISMATCH")

    rx3 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_MIPI_RX3_REG)
    rx3_ok = rx3 == m.SERIALIZER_MIPI_RX3_LANE_MAP_PHY2
    ok = ok and rx3_ok
    logging.info("MIPI_RX3 (0x0333) phy2_lane_map = 0x%02X | expect 0x%02X | %s",
                 rx3, m.SERIALIZER_MIPI_RX3_LANE_MAP_PHY2, "OK" if rx3_ok else "MISMATCH")

    rx4 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_MIPI_RX4_REG)
    rx4_ok = rx4 == m.SERIALIZER_MIPI_RX4_POLARITY_NORMAL
    ok = ok and rx4_ok
    logging.info("MIPI_RX4 (0x0334) phy1_pol_map = 0x%02X | expect 0x%02X (normal polarity) | %s",
                 rx4, m.SERIALIZER_MIPI_RX4_POLARITY_NORMAL, "OK" if rx4_ok else "MISMATCH")

    rx5 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_MIPI_RX5_REG)
    rx5_ok = rx5 == m.SERIALIZER_MIPI_RX5_POLARITY_NORMAL
    ok = ok and rx5_ok
    logging.info("MIPI_RX5 (0x0335) phy2_pol_map = 0x%02X | expect 0x%02X (normal polarity) | %s",
                 rx5, m.SERIALIZER_MIPI_RX5_POLARITY_NORMAL, "OK" if rx5_ok else "MISMATCH")

    logging.info("RESULT: Table 14 MIPI PHY Settings validation %s", "PASSED" if ok else "FAILED")
    return ok


# EXT21-24 (0x038D-0x0390, max96793.pdf Register Map - not covered by the device-
# specific user guide's own tables) - full 8-bit free-running packet counters along
# the sensor-to-GMSL-tunnel datapath. phy1_pkt_cnt confirms the ADSD3500 is actually
# sending CSI-2 packets into the serializer; csi1_pkt_cnt confirms Controller 1 is
# processing them; tun_pkt_cnt confirms they are being pushed into the GMSL tunnel
# (the critical one for tunnel mode - this is what actually reaches the deserializer);
# phy_clk_cnt confirms the MIPI RX clock lane itself is running.
SERIALIZER_EXT21_PHY1_PKT_CNT_REG = [0x03, 0x8D]
SERIALIZER_EXT22_CSI1_PKT_CNT_REG = [0x03, 0x8E]
SERIALIZER_EXT23_TUN_PKT_CNT_REG = [0x03, 0x8F]
SERIALIZER_EXT24_PHY_CLK_CNT_REG = [0x03, 0x90]


def _sample_mipi_packet_counters(bus: SMBus, serializer_addr: int, samples: int,
                                  interval: float) -> tuple:
    """Shared sampling loop for EXT21-24 (0x038D-0x0390), used by both
    check_mipi_packet_counters() and check_stream_check(). Maps directly onto
    Figure 2 (MAX96793 Video Path): phy1_pkt_cnt = CSI-2 Port B PHY reception,
    csi1_pkt_cnt = CSI-2 Controller 1 processing, tun_pkt_cnt = past the Video
    Pipe (VC Filter/STR_ID assignment) and into the GMSL Core/tunnel.

    Returns (phy1_active, csi1_active, tun_active) - each True if that counter
    changed at least once across the sampling window.
    """
    phy1_values = []
    csi1_values = []
    tun_values = []
    for i in range(samples):
        phy1_cnt = m._read_serializer_reg(bus, serializer_addr, SERIALIZER_EXT21_PHY1_PKT_CNT_REG)
        csi1_cnt = m._read_serializer_reg(bus, serializer_addr, SERIALIZER_EXT22_CSI1_PKT_CNT_REG)
        tun_cnt = m._read_serializer_reg(bus, serializer_addr, SERIALIZER_EXT23_TUN_PKT_CNT_REG)
        clk_cnt = m._read_serializer_reg(bus, serializer_addr, SERIALIZER_EXT24_PHY_CLK_CNT_REG)
        phy1_values.append(phy1_cnt)
        csi1_values.append(csi1_cnt)
        tun_values.append(tun_cnt)
        logging.info("[%d] phy1_pkt_cnt (0x038D)=%d csi1_pkt_cnt (0x038E)=%d tun_pkt_cnt (0x038F)=%d "
                     "phy_clk_cnt (0x0390, informational)=%d", i, phy1_cnt, csi1_cnt, tun_cnt, clk_cnt)
        if i < samples - 1:
            time.sleep(interval)

    return (len(set(phy1_values)) > 1, len(set(csi1_values)) > 1, len(set(tun_values)) > 1)


def check_mipi_packet_counters(bus: SMBus, serializer_addr: int, samples: int, interval: float) -> bool:
    """Sample EXT21-24 (0x038D-0x0390) repeatedly (sensor must be streaming) to confirm
    packets are actually received from the ADSD3500, processed by Controller 1, pushed
    into the GMSL tunnel, and that the MIPI RX clock lane is running.

    Returns True if phy1_pkt_cnt, csi1_pkt_cnt, and tun_pkt_cnt all changed at least
    once across the sampling window. phy_clk_cnt is logged for visibility only.
    """
    logging.info(">>> check_mipi_packet_counters()")
    phy1_active, csi1_active, tun_active = _sample_mipi_packet_counters(bus, serializer_addr, samples, interval)
    ok = phy1_active and csi1_active and tun_active
    logging.info("RESULT: MIPI Packet Counter validation %s (phy1_toggled=%s csi1_toggled=%s "
                 "tun_toggled=%s)", "PASSED" if ok else "FAILED", phy1_active, csi1_active, tun_active)
    return ok


# REG0x0112 bit 7 (PCLKDET, max96793-device-specific-user-guide.pdf "Video Lock Check")
# - in tunneling mode, asserts only while the serializer is receiving a valid CSI-2
# clock from the sensor AND GMSL Link LOCK=1. Sampling this repeatedly alongside the
# deserializer's sticky LOSS_OF_VIDEO_LOCK flag tells apart two different root causes:
# if PCLKDET also drops out, the instability originates right at the ADSD3500-to-
# serializer MIPI boundary (sensor clock/signal integrity); if PCLKDET stays solid
# the whole time, the glitch is downstream, inside the GMSL tunnel/deserializer
# reconstruction stage instead.
SERIALIZER_REG0x112_REG = [0x01, 0x12]
SERIALIZER_PCLKDET_BIT = 0x80


def check_pclkdet(bus: SMBus, serializer_addr: int, samples: int, interval: float) -> bool:
    """Sample REG0x0112 bit 7 (PCLKDET) repeatedly to confirm the serializer is
    continuously receiving a valid CSI-2 clock from the sensor with GMSL Link LOCK=1.

    Returns True if PCLKDET stayed asserted on every single sample (no dropout).
    """
    logging.info(">>> check_pclkdet()")
    all_asserted = True
    for i in range(samples):
        reg = m._read_serializer_reg(bus, serializer_addr, SERIALIZER_REG0x112_REG)
        pclkdet = bool(reg & SERIALIZER_PCLKDET_BIT)
        all_asserted = all_asserted and pclkdet
        logging.info("[%d] REG0x0112 (0x0112) = 0x%02X | PCLKDET=%s", i, reg, pclkdet)
        if i < samples - 1:
            time.sleep(interval)

    logging.info("RESULT: PCLKDET validation %s (asserted_every_sample=%s)",
                 "PASSED" if all_asserted else "FAILED", all_asserted)
    return all_asserted


def check_stream_check(bus: SMBus, serializer_addr: int, samples: int, interval: float) -> bool:
    """Live, end-to-end pipeline check (sensor must be streaming), one stage per box
    in Figure 2 (MAX96793 Video Path): sensor->serializer MIPI clock (PCLKDET), CSI-2
    Port B PHY reception, CSI-2 Controller 1 processing, and Video Pipe (VC Filter/
    STR_ID assignment) through to the GMSL Core/tunnel - reported individually so a
    broken stage can be isolated from a healthy upstream/downstream one.

    Returns True only if every stage passes.
    """
    logging.info(">>> check_stream_check()")
    logging.info("---- Stage 1/4: Sensor -> Serializer MIPI clock boundary (PCLKDET) ----")
    pclkdet_ok = check_pclkdet(bus, serializer_addr, samples, interval)
    logging.info("---- Stages 2-4/4: CSI-2 PHY -> Controller 1 -> Video Pipe -> GMSL Tunnel (packet counters) ----")
    phy1_ok, csi1_ok, tun_ok = _sample_mipi_packet_counters(bus, serializer_addr, samples, interval)

    overall = pclkdet_ok and phy1_ok and csi1_ok and tun_ok
    logging.info("==================== STREAM CHECK SUMMARY (Figure 2 pipeline) ====================")
    logging.info("%-55s %s", "1. Sensor -> Serializer clock (PCLKDET)", "PASSED" if pclkdet_ok else "FAILED")
    logging.info("%-55s %s", "2. CSI-2 Port B PHY reception (phy1_pkt_cnt)", "PASSED" if phy1_ok else "FAILED")
    logging.info("%-55s %s", "3. CSI-2 Controller 1 processing (csi1_pkt_cnt)", "PASSED" if csi1_ok else "FAILED")
    logging.info("%-55s %s", "4. Video Pipe (VC Filter/STR_ID) -> GMSL Tunnel (tun_pkt_cnt)",
                 "PASSED" if tun_ok else "FAILED")
    logging.info("------------------------------------------------------------------------------------")
    logging.info("Overall: %s", "PASSED" if overall else "FAILED")
    logging.info("======================================================================================")
    return overall


# CSI_ERR_L/H (0x0343/0x0344, max96793.pdf Register Map) - CSI-2 Controller 1
# (sensor-facing) input error status, read-clears-all. Figure 3 ("Pixel and
# Tunneling Mode Comparison") shows the serializer as the point that "CHECK
# CSI-2 CRC" on data arriving from the sensor, before it ever reaches the GMSL
# tunnel - CRC_ERR (bit 7 of CSI_ERR_L) is that check. ECC/unsupported-DT/
# early-termination/frame-count bits are logged for additional diagnostic
# context, not gated on pass/fail (CRC is the only bit Figure 3 calls out).
SERIALIZER_CSI_ERR_L_REG = [0x03, 0x43]
SERIALIZER_CSI_ERR_H_REG = [0x03, 0x44]
SERIALIZER_CSI_ERR_L_ECC_1BIT_BIT = 0x01
SERIALIZER_CSI_ERR_L_ECC_2BIT_BIT = 0x02
SERIALIZER_CSI_ERR_L_CRC_ERR_BIT = 0x80
SERIALIZER_CSI_ERR_H_EARLY_TERM_BIT = 0x01
SERIALIZER_CSI_ERR_H_FRAME_CNT_ERR_BIT = 0x02
SERIALIZER_CSI_ERR_H_UNSUPPORTED_DT_BIT = 0x04


def check_csi2_crc(bus: SMBus, serializer_addr: int, samples: int, interval: float) -> bool:
    """Sample CSI_ERR_L (0x0343) bit 7 (CRC_ERR) repeatedly (sensor must be
    streaming) - Figure 3's "CHECK CSI-2 CRC" step, confirming the CSI-2 packets
    the serializer receives from the ADSD3500 pass their own CRC before ever
    being handed to the GMSL tunnel. ECC/unsupported-DT/early-termination/
    frame-count bits are logged for additional context, not enforced.

    Returns True if CRC_ERR was never asserted across the sampling window.
    """
    logging.info(">>> check_csi2_crc()")
    any_crc_err = False
    for i in range(samples):
        err_l = m._read_serializer_reg(bus, serializer_addr, SERIALIZER_CSI_ERR_L_REG)
        err_h = m._read_serializer_reg(bus, serializer_addr, SERIALIZER_CSI_ERR_H_REG)
        crc_err = bool(err_l & SERIALIZER_CSI_ERR_L_CRC_ERR_BIT)
        ecc_1bit = bool(err_l & SERIALIZER_CSI_ERR_L_ECC_1BIT_BIT)
        ecc_2bit = bool(err_l & SERIALIZER_CSI_ERR_L_ECC_2BIT_BIT)
        unsupported_dt = bool(err_h & SERIALIZER_CSI_ERR_H_UNSUPPORTED_DT_BIT)
        any_crc_err = any_crc_err or crc_err
        logging.info("[%d] CSI_ERR_L (0x0343) = 0x%02X | CRC_ERR=%s ecc_1bit (informational)=%s "
                     "ecc_2bit (informational)=%s | CSI_ERR_H (0x0344) unsupported_dt (informational)=%s",
                     i, err_l, crc_err, ecc_1bit, ecc_2bit, unsupported_dt)
        if i < samples - 1:
            time.sleep(interval)

    logging.info("RESULT: CSI-2 CRC validation %s (CRC_err_seen=%s)",
                 "PASSED" if not any_crc_err else "FAILED", any_crc_err)
    return not any_crc_err


def run_all_checks(bus: SMBus, serializer_addr: int) -> bool:
    """Run every --check-* table validation and print a consolidated PASS/FAIL summary.

    Returns True only if every check passes.
    """
    results = {
        "Table 3 (Pixel/Tunneling Mode)": validate_pixel_tunnel_mode_table(bus, serializer_addr),
        "Table 6 (Link Initialization)": validate_link_init_table(bus, serializer_addr),
        "Table 7 (Video Pipe Selection)": validate_video_pipe_selection_table(bus, serializer_addr),
        "Table 8 (Video Pipe and Filtering)": validate_video_pipe_filtering_table(bus, serializer_addr),
        "Table 14 (MIPI PHY Settings)": validate_mipi_phy_settings_table(bus, serializer_addr),
    }

    overall = all(results.values())
    logging.info("==================== SUMMARY ====================")
    for name, passed in results.items():
        logging.info("%-42s %s", name, "PASSED" if passed else "FAILED")
    logging.info("--------------------------------------------------")
    logging.info("Overall: %s", "PASSED" if overall else "FAILED")
    logging.info("==================================================")
    summarize_configuration(bus, serializer_addr)
    return overall


def summarize_configuration(bus: SMBus, serializer_addr: int) -> None:
    """Log a low-level, human-readable report of every table's current register
    state, independent of pass/fail - so the user can see exactly what is set.
    """
    logging.info("============== CURRENT CONFIGURATION (low-level report) ==============")

    ext11 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_EXT11_REG)
    logging.info("[Table 3] TUN_EN (0x0383) = 0x%02X (%s)",
                 ext11, "Tunneling" if ext11 & DESERIALIZER_TUN_EN_BIT else "Pixel")

    ctrl0 = m._read_serializer_reg(bus, serializer_addr, SERIALIZER_CTRL0_REG)
    tx_rate = (m._read_serializer_reg(bus, serializer_addr, SERIALIZER_TX_RATE_REG)
               & SERIALIZER_TX_RATE_MASK) >> SERIALIZER_TX_RATE_SHIFT
    cxtp_a = bool(m._read_serializer_reg(bus, serializer_addr, SERIALIZER_CXTP_A_REG) & SERIALIZER_CXTP_A_BIT)
    logging.info("[Table 6] CTRL0=0x%02X TX_RATE=%s CXTP_A=%s",
                 ctrl0, SERIALIZER_TX_RATE_NAMES.get(tx_rate, "?"), cxtp_a)

    tx3 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_TX3_REG)
    str_sel = tx3 & SERIALIZER_TX_STR_SEL_MASK
    logging.info("[Table 7] TX_STR_SEL Pipe Z = %s", SERIALIZER_TX_STR_SEL_NAMES.get(str_sel, "?"))

    fronttop_0 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_FRONTTOP_0_REG)
    reg2 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_REG2_REG)
    vc_selz_l = m._read_serializer_reg(bus, serializer_addr, SERIALIZER_VC_SELZ_L_REG)
    vc_selz_h = m._read_serializer_reg(bus, serializer_addr, SERIALIZER_VC_SELZ_H_REG)
    logging.info("[Table 8] START_PORTB=%s CLK_SELZ=%s VID_TX_EN_Z=%s VC_SELZ_L/H=0x%02X/0x%02X",
                 bool(fronttop_0 & SERIALIZER_FRONTTOP_0_START_PORTB_BIT),
                 bool(fronttop_0 & SERIALIZER_FRONTTOP_0_CLK_SELZ_BIT),
                 bool(reg2 & SERIALIZER_REG2_VID_TX_EN_Z_BIT), vc_selz_l, vc_selz_h)

    rx0 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_MIPI_RX0_REG)
    rx1 = m._read_serializer_reg(bus, serializer_addr, m.SERIALIZER_MIPI_RX1_REG)
    num_lanes = (rx1 & SERIALIZER_MIPI_RX1_NUM_LANES_MASK) >> SERIALIZER_MIPI_RX1_NUM_LANES_SHIFT
    logging.info("[Table 14] mipi_noncontclk_en=%s phy_config=0x%X ctrl1_num_lanes=%s "
                 "ctrl1_deskewen=%s",
                 bool(rx0 & m.SERIALIZER_MIPI_RX0_NONCONT_CLK_EN_BIT),
                 rx0 & SERIALIZER_MIPI_RX0_PHY_CONFIG_MASK,
                 SERIALIZER_MIPI_RX1_NUM_LANES_NAMES.get(num_lanes, "?"),
                 bool(rx1 & SERIALIZER_MIPI_RX1_DESKEW_EN_BIT))

    logging.info("=========================================================================")


# MAX96792A Errata #2 workaround: "Video transmission does not automatically restart
# after the GMSL link loses lock and relocks during video transmission in tunneling
# mode" - executing RESET_LINK (part of normal bring-up) is one of the documented
# trigger conditions. Workaround: disable, then re-enable VID_TX_EN (REG2 bit 6) on
# the serializer, AFTER the link has already relocked - not just once at the end of
# the initial bring-up sequence.
def restart_video_tx(bus: SMBus, serializer_addr: int, settle_s: float = 0.5) -> None:
    """Disable then re-enable the serializer's VID_TX_EN_Z (REG2 bit 6), per
    MAX96792A Errata #2's documented workaround for video not automatically
    restarting after a RESET_LINK during tunneling mode. Run this AFTER the normal
    bring-up (config_1_max96793_max96792a_init.py) has already completed and the
    link has relocked - then re-check CSIPLLY_LOCK on the deserializer.
    """
    logging.info(">>> restart_video_tx()")
    m._i2c_write(bus, serializer_addr, m.SERIALIZER_REG2_REG + [m.SERIALIZER_REG2_VID_TX_EN_Z_DISABLE],
                 "\tDEV : REG2 | VID_TX_EN_Z (VID_TX_EN_Z): Disabled (errata #2 workaround)")
    time.sleep(settle_s)
    m._i2c_write(bus, serializer_addr, m.SERIALIZER_REG2_REG + [m.SERIALIZER_REG2_VID_TX_EN_Z_ENABLE],
                 "\tDEV : REG2 | VID_TX_EN_Z (VID_TX_EN_Z): Enabled (errata #2 workaround)")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bus", nargs="?", type=int, default=2, help="I2C bus number (default: 2)")
    parser.add_argument("--check-tunnel-mode", action="store_true",
                         help="Read back and validate the User Guide's Table 3 (Pixel and "
                              "Tunneling Mode Register Settings: TUN_EN) against this board's "
                              "expected Tunneling Mode configuration, then exit")
    parser.add_argument("--check-link-init", action="store_true",
                         help="Read back and validate the User Guide's Table 6 (Link "
                              "Initialization Registers: TX_RATE, CXTP_A, CTRL0 reset bits) "
                              "against this board's expected configuration, then exit")
    parser.add_argument("--check-video-pipe-sel", action="store_true",
                         help="Read back and validate the User Guide's Table 7 (Video Pipe "
                              "Selection Registers: TX_STR_SEL, Pipe Z) against this board's "
                              "expected Stream ID 0 configuration, then exit")
    parser.add_argument("--check-video-pipe-filtering", action="store_true",
                         help="Read back and validate the User Guide's Table 8 (Video Pipe and "
                              "Filtering Registers: START_PORTB, CLK_SELZ, VID_TX_EN_Z, "
                              "TX_STR_SEL, DT/VC filtering) against this board's expected "
                              "configuration, then exit")
    parser.add_argument("--check-mipi-phy-settings", action="store_true",
                         help="Read back and validate the User Guide's Table 14 (MIPI PHY "
                              "Setting Registers: mipi_noncontclk_en, phy_config, "
                              "ctrl1_num_lanes, lane map/polarity, ctrl1_deskewen) against this "
                              "board's expected Port B, 2-lane configuration, then exit")
    parser.add_argument("--check-mipi-packet-counters", action="store_true",
                         help="Sample EXT21-24 (0x038D-0x0390) repeatedly (sensor must be "
                              "streaming) to confirm packets are actually received from the "
                              "sensor, processed, and pushed into the GMSL tunnel, then exit")
    parser.add_argument("--check-pclkdet", action="store_true",
                         help="Sample REG0x0112 bit 7 (PCLKDET) repeatedly to confirm the "
                              "serializer is continuously receiving a valid CSI-2 clock from "
                              "the sensor with GMSL Link LOCK=1, then exit")
    parser.add_argument("--check-crc", action="store_true",
                         help="Sample CSI_ERR_L (0x0343) bit 7 (CRC_ERR) repeatedly (sensor must "
                              "be streaming) - Figure 3's (Pixel and Tunneling Mode Comparison) "
                              "\"CHECK CSI-2 CRC\" step, confirming CSI-2 packets from the sensor "
                              "pass their own CRC before being handed to the GMSL tunnel, then exit")
    parser.add_argument("--stream-check", action="store_true",
                         help="Live, end-to-end pipeline check (sensor must be streaming): walks "
                              "sensor->serializer MIPI clock (PCLKDET), then CSI-2 PHY -> "
                              "Controller 1/Video Pipe -> GMSL Tunnel (packet counters), "
                              "reporting a per-stage PASS/FAIL, then exit")
    parser.add_argument("--restart-video-tx", action="store_true",
                         help="Disable then re-enable VID_TX_EN_Z (REG2 bit 6) - MAX96792A "
                              "Errata #2's documented workaround for video not automatically "
                              "restarting after a RESET_LINK during tunneling mode bring-up. "
                              "Run after the normal bring-up has already completed, then "
                              "re-check CSIPLLY_LOCK on the deserializer")
    parser.add_argument("--all", action="store_true",
                         help="Run every --check-* table validation and print a consolidated "
                              "PASS/FAIL summary")
    parser.add_argument("--show-config", action="store_true",
                         help="Print a low-level report of every table's current register "
                              "state (what is actually set, independent of pass/fail), then exit")
    parser.add_argument("--samples", type=int, default=5,
                         help="Number of samples to take for --check-mipi-packet-counters, "
                              "--check-pclkdet, --check-crc, --stream-check (default: 5)")
    parser.add_argument("--interval", type=float, default=1.0,
                         help="Seconds between samples for --check-mipi-packet-counters, "
                              "--check-pclkdet, --check-crc, --stream-check (default: 1.0)")
    parser.add_argument("--mipi-freq", choices=sorted(m.DESERIALIZER_MIPI_FREQ_CHOICES, key=int),
                         default=None,
                         help="Override the expected CSI output frequency (Mbps/lane) used by "
                              "--check-mipi-phy-settings to match whatever --mipi-freq was "
                              "passed to config_1_max96793_max96792a_init.py, without editing "
                              "either script")
    parser.add_argument("--log-level", default="INFO",
                         choices=["DEBUG", "INFO", "WARNING", "ERROR", "ALL"],
                         help="Logging verbosity (default: INFO)")
    args = parser.parse_args(argv)
    # "ALL" is not a real logging level; DEBUG is the lowest level, so it shows everything
    logging.getLogger().setLevel(logging.DEBUG if args.log_level == "ALL" else args.log_level)

    if args.mipi_freq is not None:
        m.DESERIALIZER_MIPI_OUTPUT_FREQ = m.DESERIALIZER_MIPI_FREQ_CHOICES[args.mipi_freq]

    with SMBus(args.bus) as bus:
        serializer_addr = _serializer_addr(bus)
        if args.all:
            return 0 if run_all_checks(bus, serializer_addr) else 1
        if args.show_config:
            summarize_configuration(bus, serializer_addr)
            return 0
        if args.check_tunnel_mode:
            return 0 if validate_pixel_tunnel_mode_table(bus, serializer_addr) else 1
        if args.check_link_init:
            return 0 if validate_link_init_table(bus, serializer_addr) else 1
        if args.check_video_pipe_sel:
            return 0 if validate_video_pipe_selection_table(bus, serializer_addr) else 1
        if args.check_video_pipe_filtering:
            return 0 if validate_video_pipe_filtering_table(bus, serializer_addr) else 1
        if args.check_mipi_phy_settings:
            return 0 if validate_mipi_phy_settings_table(bus, serializer_addr) else 1
        if args.check_mipi_packet_counters:
            return 0 if check_mipi_packet_counters(bus, serializer_addr, args.samples, args.interval) else 1
        if args.check_pclkdet:
            return 0 if check_pclkdet(bus, serializer_addr, args.samples, args.interval) else 1
        if args.check_crc:
            return 0 if check_csi2_crc(bus, serializer_addr, args.samples, args.interval) else 1
        if args.stream_check:
            return 0 if check_stream_check(bus, serializer_addr, args.samples, args.interval) else 1
        if args.restart_video_tx:
            restart_video_tx(bus, serializer_addr)
            return 0
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
