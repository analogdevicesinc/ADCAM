"""
Standalone CLI to validate registers from max96792a-device-specific-user-guide.pdf
against this board's expected configuration (set by config_1_max96793_max96792a_init.py).

Run the normal GMSL3 bring-up first:
    sudo python3 config_1_max96793_max96792a_init.py

Usage:
    # validate Table 3 (Pixel and Tunneling Mode Register Settings: TUN_EN, Pipe Y/Pipe Z)
    sudo python3 debug_max96792a_register_configuration.py --check-tunnel-mode
    sudo python3 debug_max96792a_register_configuration.py --check-tunnel-mode --bus 2 --log-level DEBUG

    # validate Table 6 (Link Initialization Registers: RX_RATE, GMSL3_A, CTRL0 reset bits)
    sudo python3 debug_max96792a_register_configuration.py --check-link-init

    # validate Table 7 (Single- vs. Dual-Link Operation: AUTO_LINK/LINK_CFG, LINK_EN_A/B)
    sudo python3 debug_max96792a_register_configuration.py --check-link-operation

    # validate Table 8 (Video Pipe Selection Registers: VIDEO_PIPE_EN, VIDEO_PIPE_SEL_Y/Z)
    sudo python3 debug_max96792a_register_configuration.py --check-video-pipe-sel

    # validate Table 9 (Video Pipe to MIPI PHY Controller Register: MAP_EN_L/H, Pipe Y/Pipe Z)
    sudo python3 debug_max96792a_register_configuration.py --check-pipe-controller-mapping

    # validate Table 12 (MIPI PHY Setting Registers: phy_2x4, phy_stdby_n, lane map/polarity,
    # CSI2_LANE_CNT, RST_MIPITX_LOC)
    sudo python3 debug_max96792a_register_configuration.py --check-mipi-phy-settings

    # validate Table 13 (MIPI D-PHY Deskew Registers: DESKEW_INIT/DESKEW_PER, Controller 1)
    sudo python3 debug_max96792a_register_configuration.py --check-mipi-deskew

    # sample Table 27 (MIPI Counter Registers) repeatedly to confirm MIPI data is
    # actively flowing on Controller 1/PHY1 (sensor must be streaming)
    sudo python3 debug_max96792a_register_configuration.py --check-mipi-packet-counters --samples 8 --interval 1.0

    # sample GMSL LOCKED/CMU_LOCKED (CTRL3) and Pipe Y's VIDEO_LOCK (0x01FC) repeatedly
    # to tell apart an idle-but-locked link from one actually carrying video
    sudo python3 debug_max96792a_register_configuration.py --check-video-lock --samples 8 --interval 1.0

    # live, end-to-end pipeline check (sensor must be streaming): GMSL PHY -> Video Pipe
    # Select/Crossbar -> Pipe-to-Controller (BACKTOP) -> CSI-2 Controller 1 -> PHY1 output
    # pins -> Pipe Y CSI-2 output PLL lock (CSIPLLY_LOCK), with a per-stage PASS/FAIL
    # summary so a broken stage can be isolated
    sudo python3 debug_max96792a_register_configuration.py --stream-check --samples 8 --interval 1.0

    # sample MIPI_PHY17 (0x0341) bit 5 repeatedly - Figure 3's "CHECK AND REMOVE GMSL CRC"
    # step, confirming TUN_DATA_CRC_ERR never asserts on the GMSL tunnel's own CRC check
    sudo python3 debug_max96792a_register_configuration.py --check-crc --samples 8 --interval 1.0

    # run every table validation with a consolidated PASS/FAIL summary
    sudo python3 debug_max96792a_register_configuration.py --all
    sudo python3 debug_max96792a_register_configuration.py --all --samples 8 --interval 1.0

Exit status: 0 if the requested check(s) pass, 1 otherwise.
"""
import argparse
import logging
import sys
import time
from typing import Optional, Sequence

from smbus2 import SMBus

import config_1_max96793_max96792a_init as m

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Table 3 ("MAX96792A Pixel and Tunneling Mode Register Settings") - TUN_EN bit 0
# of MIPI_TX52 (0x0474, Pipe Y - the pipe this board actually uses, see
# config_1_max96793_max96792a_init.py's DESERIALIZER_MIPI_TX52_REG) and the
# equivalent Pipe Z register (0x04B4, not configured by this board - Pipe Z is
# unused). POR 0b0 = Pixel Mode, 0b1 = Tunneling Mode.
DESERIALIZER_TUN_EN_PIPE_Y_REG = m.DESERIALIZER_MIPI_TX52_REG  # [0x04, 0x74]
DESERIALIZER_TUN_EN_PIPE_Z_REG = [0x04, 0xB4]
DESERIALIZER_TUN_EN_BIT = 0x01


def validate_pixel_tunnel_mode_table(bus: SMBus) -> bool:
    """Read back and validate the User Guide's Table 3 (Pixel and Tunneling Mode
    Register Settings: TUN_EN, Pipe Y/Pipe Z) against this board's expected
    configuration.

    Returns True if Pipe Y (the only pipe this board uses) reads back in
    Tunneling Mode. Pipe Z is logged for visibility only, not enforced - it's
    not configured by config_1_max96793_max96792a_init.py (unused on this board).
    """
    logging.info(">>> validate_pixel_tunnel_mode_table()")

    pipe_y = m._read_deserializer_reg(bus, DESERIALIZER_TUN_EN_PIPE_Y_REG)
    pipe_y_tunneling = bool(pipe_y & DESERIALIZER_TUN_EN_BIT)
    logging.info("MIPI_TX52 Pipe Y TUN_EN (0x0474) = 0x%02X | mode=%s | expect Tunneling Mode | %s",
                 pipe_y, "Tunneling Mode" if pipe_y_tunneling else "Pixel Mode",
                 "OK" if pipe_y_tunneling else "MISMATCH")

    pipe_z = m._read_deserializer_reg(bus, DESERIALIZER_TUN_EN_PIPE_Z_REG)
    pipe_z_tunneling = bool(pipe_z & DESERIALIZER_TUN_EN_BIT)
    logging.info("Pipe Z TUN_EN (0x04B4) = 0x%02X | mode=%s - informational only, not enforced "
                 "(Pipe Z unused on this board)", pipe_z,
                 "Tunneling Mode" if pipe_z_tunneling else "Pixel Mode")

    logging.info("RESULT: Table 3 Pixel/Tunneling Mode validation %s",
                 "PASSED" if pipe_y_tunneling else "FAILED")
    return pipe_y_tunneling


# Table 6 ("MAX96792A Link Initialization Registers") - RX_RATE (0x0001 bits[1:0],
# Link A rate) and GMSL3_A (0x0004 bit 6, Link A GMSL3 mode enable) are both
# configured by config_1_max96793_max96792a_init.py's _configure_deserializer_link()
# (reusing its exact constants/addresses). CTRL0 (0x0010) holds three reset-control
# bits that should all read back as 0 (inactive) once bring-up has completed:
# RESET_ALL (bit7, never touched by this script), RESET_LINK (bit6, toggled by
# _reset_and_relock_link() and expected released), RESET_ONESHOT (bit5, self-clearing,
# used once during initial link establishment).
DESERIALIZER_CTRL0_RESET_ALL_BIT = 0x80
DESERIALIZER_CTRL0_RESET_LINK_BIT = 0x40
DESERIALIZER_CTRL0_RESET_ONESHOT_BIT = 0x20
# CXTP_A/CXTP_B (0x0011 bits 0/2, Coax vs STP cable drive) and RESET_LINK_B (0x0013
# bit 0) are not configured anywhere in config_1_max96793_max96792a_init.py (Link B
# is unused on this single-link board) - read for visibility only, not enforced.
DESERIALIZER_CXTP_REG = [0x00, 0x11]
DESERIALIZER_CXTP_A_BIT = 0x01
DESERIALIZER_CXTP_B_BIT = 0x04
DESERIALIZER_RESET_LINK_B_BIT = 0x01


def validate_link_init_table(bus: SMBus) -> bool:
    """Read back and validate the User Guide's Table 6 (Link Initialization
    Registers: RX_RATE, GMSL3_A, CTRL0 reset bits) against this board's expected
    Link A-only, 12Gbps/GMSL3 configuration.

    Returns True if RX_RATE reads 12Gbps, GMSL3_A is enabled, and none of CTRL0's
    three reset bits are left asserted (CXTP_A/B and RESET_LINK_B are logged for
    visibility only, not enforced - Link B is unused on this board).
    """
    logging.info(">>> validate_link_init_table()")
    ok = True

    reg1 = m._read_deserializer_reg(bus, m.DESERIALIZER_REG1)
    rx_rate = reg1 & m.DESERIALIZER_REG1_RX_RATE_MASK
    rx_rate_ok = rx_rate == m.DESERIALIZER_REG1_RX_RATE_12GBPS_GMSL3
    ok = ok and rx_rate_ok
    logging.info("REG1 (0x0001) RX_RATE = 0b%02s | expect 0b11 (12Gbps) | %s",
                 bin(rx_rate)[2:].zfill(2), "OK" if rx_rate_ok else "MISMATCH")

    reg4 = m._read_deserializer_reg(bus, m.DESERIALIZER_REG4)
    gmsl3_a = bool(reg4 & m.DESERIALIZER_REG4_GMSL3_A_BIT)
    ok = ok and gmsl3_a
    logging.info("REG4 (0x0004) GMSL3_A = %s | expect True (enabled) | %s",
                 gmsl3_a, "OK" if gmsl3_a else "MISMATCH")

    ctrl0 = m._read_deserializer_reg(bus, m.DESERIALIZER_CTRL0_REG)
    reset_all = bool(ctrl0 & DESERIALIZER_CTRL0_RESET_ALL_BIT)
    reset_link = bool(ctrl0 & DESERIALIZER_CTRL0_RESET_LINK_BIT)
    reset_oneshot = bool(ctrl0 & DESERIALIZER_CTRL0_RESET_ONESHOT_BIT)
    resets_clear = not (reset_all or reset_link or reset_oneshot)
    ok = ok and resets_clear
    logging.info("CTRL0 (0x0010) = 0x%02X | RESET_ALL=%s RESET_LINK=%s RESET_ONESHOT=%s | "
                 "expect all False (released/self-cleared) | %s",
                 ctrl0, reset_all, reset_link, reset_oneshot,
                 "OK" if resets_clear else "MISMATCH (a reset bit is still asserted)")

    cxtp = m._read_deserializer_reg(bus, DESERIALIZER_CXTP_REG)
    cxtp_a = bool(cxtp & DESERIALIZER_CXTP_A_BIT)
    cxtp_b = bool(cxtp & DESERIALIZER_CXTP_B_BIT)
    logging.info("CXTP (0x0011) = 0x%02X | CXTP_A=%s CXTP_B=%s (%s) - informational only, "
                 "not enforced", cxtp, cxtp_a, cxtp_b, "Coax" if cxtp_a else "STP")

    reset_link_b = bool(m._read_deserializer_reg(bus, m.DESERIALIZER_CTRL3_REG) & DESERIALIZER_RESET_LINK_B_BIT)
    logging.info("CTRL3 (0x0013) RESET_LINK_B = %s - informational only, not enforced "
                 "(Link B unused on this board)", reset_link_b)

    logging.info("RESULT: Table 6 Link Initialization validation %s", "PASSED" if ok else "FAILED")
    return ok


# Table 7 ("MAX96792A Single- vs. Dual-Link Operation") - AUTO_LINK (CTRL0 0x0010
# bit 4) / LINK_CFG (CTRL0 bits[1:0]) select the link automatically, OR LINK_EN_A/B
# (0x0F00, matching config_1_max96793_max96792a_init.py's DESERIALIZER_GMSL1_EN_REG)
# can be driven manually with AUTO_LINK left disabled - this is an alternative,
# equally valid method documented under CTRL0's own LINK_CFG bitfield notes, and is
# the method this script actually uses (AUTO_LINK=0, LINK_EN_A=1/LINK_EN_B=0) rather
# than Table 7's literal "AUTO_LINK=0x1" row - so AUTO_LINK/LINK_CFG are informational
# only here; the real pass/fail criterion is LINK_EN_A/B actually landing on "Link A
# Only".
DESERIALIZER_CTRL0_AUTO_LINK_BIT = 0x10
DESERIALIZER_CTRL0_LINK_CFG_MASK = 0x03
DESERIALIZER_LINK_EN_A_BIT = 0x01
DESERIALIZER_LINK_EN_B_BIT = 0x10


def validate_link_operation_table(bus: SMBus) -> bool:
    """Read back and validate the User Guide's Table 7 (Single- vs. Dual-Link
    Operation: AUTO_LINK/LINK_CFG, LINK_EN_A/B) against this board's expected
    Link A-only configuration.

    Returns True if LINK_EN_A/B (0x0F00) reads back as Link A enabled, Link B
    disabled. AUTO_LINK/LINK_CFG are logged for visibility only, not enforced -
    this script deliberately uses the manual LINK_EN_A/B selection method (with
    AUTO_LINK disabled) rather than Table 7's literal AUTO_LINK=1 row, which is a
    documented alternative for the same "Link A Only" outcome.
    """
    logging.info(">>> validate_link_operation_table()")

    ctrl0 = m._read_deserializer_reg(bus, m.DESERIALIZER_CTRL0_REG)
    auto_link = bool(ctrl0 & DESERIALIZER_CTRL0_AUTO_LINK_BIT)
    link_cfg = ctrl0 & DESERIALIZER_CTRL0_LINK_CFG_MASK
    logging.info("CTRL0 (0x0010) = 0x%02X | AUTO_LINK=%s LINK_CFG=0b%02s - informational only, "
                 "not enforced (this script uses the manual LINK_EN_A/B method instead)",
                 ctrl0, auto_link, bin(link_cfg)[2:].zfill(2))

    link_en = m._read_deserializer_reg(bus, m.DESERIALIZER_GMSL1_EN_REG)
    link_en_a = bool(link_en & DESERIALIZER_LINK_EN_A_BIT)
    link_en_b = bool(link_en & DESERIALIZER_LINK_EN_B_BIT)
    link_a_only = link_en_a and not link_en_b
    logging.info("LINK_EN_A/B (0x0F00) = 0x%02X | LINK_EN_A=%s LINK_EN_B=%s | expect Link A Only "
                 "(True/False) | %s", link_en, link_en_a, link_en_b, "OK" if link_a_only else "MISMATCH")

    logging.info("RESULT: Table 7 Single-/Dual-Link Operation validation %s",
                 "PASSED" if link_a_only else "FAILED")
    return link_a_only


# Table 8 ("MAX96792A Video Pipe Selection Registers") - VIDEO_PIPE_EN (0x0160) and
# VIDEO_PIPE_SEL_Y/Z (0x0161), both matching config_1_max96793_max96792a_init.py's
# DESERIALIZER_VIDEO_PIPE_EN_REG/DESERIALIZER_VIDEO_PIPE_SEL_REG exactly. Pipe Y is
# the pipe this board actually uses (routed to Link A, Stream ID 0); Pipe Z is
# unused, so its selector is logged for visibility only, not enforced.
DESERIALIZER_VIDEO_PIPE_EN_PIPE_Y_BIT = 0x01
DESERIALIZER_VIDEO_PIPE_EN_PIPE_Z_BIT = 0x02
DESERIALIZER_VIDEO_PIPE_SEL_Y_MASK = 0x07
DESERIALIZER_VIDEO_PIPE_SEL_Z_SHIFT = 3
DESERIALIZER_VIDEO_PIPE_SEL_Z_MASK = 0x07 << DESERIALIZER_VIDEO_PIPE_SEL_Z_SHIFT
DESERIALIZER_VIDEO_PIPE_SEL_NAMES = {
    0b000: "GMSL Link A, str_id=00", 0b001: "GMSL Link A, str_id=01",
    0b010: "GMSL Link A, str_id=10", 0b011: "GMSL Link A, str_id=11",
    0b100: "GMSL Link B, str_id=00", 0b101: "GMSL Link B, str_id=01",
    0b110: "GMSL Link B, str_id=10", 0b111: "GMSL Link B, str_id=11",
}


def validate_video_pipe_selection_table(bus: SMBus) -> bool:
    """Read back and validate the User Guide's Table 8 (Video Pipe Selection
    Registers: VIDEO_PIPE_EN, VIDEO_PIPE_SEL_Y/Z) against this board's expected
    Pipe Y/Link A/Stream 0 configuration.

    Returns True if both video pipes are enabled and Pipe Y is selected as GMSL
    Link A, str_id=00. VIDEO_PIPE_SEL_Z is logged for visibility only, not
    enforced - Pipe Z is unused on this board.
    """
    logging.info(">>> validate_video_pipe_selection_table()")
    ok = True

    pipe_en = m._read_deserializer_reg(bus, m.DESERIALIZER_VIDEO_PIPE_EN_REG)
    pipe_y_en = bool(pipe_en & DESERIALIZER_VIDEO_PIPE_EN_PIPE_Y_BIT)
    pipe_z_en = bool(pipe_en & DESERIALIZER_VIDEO_PIPE_EN_PIPE_Z_BIT)
    pipe_en_ok = pipe_y_en and pipe_z_en
    ok = ok and pipe_en_ok
    logging.info("VIDEO_PIPE_EN (0x0160) = 0x%02X | Pipe Y enabled=%s Pipe Z enabled=%s | %s",
                 pipe_en, pipe_y_en, pipe_z_en, "OK" if pipe_en_ok else "MISMATCH")

    pipe_sel = m._read_deserializer_reg(bus, m.DESERIALIZER_VIDEO_PIPE_SEL_REG)
    pipe_sel_y = pipe_sel & DESERIALIZER_VIDEO_PIPE_SEL_Y_MASK
    pipe_sel_y_ok = pipe_sel_y == 0b000
    ok = ok and pipe_sel_y_ok
    logging.info("VIDEO_PIPE_SEL_Y (0x0161 bits[2:0]) = 0b%03s (%s) | expect 0b000 (GMSL Link A, "
                 "str_id=00) | %s", bin(pipe_sel_y)[2:].zfill(3),
                 DESERIALIZER_VIDEO_PIPE_SEL_NAMES.get(pipe_sel_y, "?"),
                 "OK" if pipe_sel_y_ok else "MISMATCH")

    pipe_sel_z = (pipe_sel & DESERIALIZER_VIDEO_PIPE_SEL_Z_MASK) >> DESERIALIZER_VIDEO_PIPE_SEL_Z_SHIFT
    logging.info("VIDEO_PIPE_SEL_Z (0x0161 bits[5:3]) = 0b%03s (%s) - informational only, not "
                 "enforced (Pipe Z unused on this board)", bin(pipe_sel_z)[2:].zfill(3),
                 DESERIALIZER_VIDEO_PIPE_SEL_NAMES.get(pipe_sel_z, "?"))

    logging.info("RESULT: Table 8 Video Pipe Selection validation %s", "PASSED" if ok else "FAILED")
    return ok


# Table 9 ("MAX96792A Video PIpe to MIPI PHY Controller Register") - MAP_EN_L/H
# (MIPI_TX11/MIPI_TX12, one bit per of 16 possible VC/DT remap-and-route entries)
# gate whether any MAP_SRC_x/MAP_DST_x/MAP_DPHY_DEST_x override is active for a
# pipe; POR 0x00 = no overrides, all VC/DT pass straight through to the pipe's
# default-mapped controller (Pipe Y -> Controller 1, Pipe Z -> Controller 2).
# config_1_max96793_max96792a_init.py never touches any of these registers -
# tunneling mode doesn't support VC reassignment (see Table 4), so this board
# relies entirely on the default pass-through mapping, meaning MAP_EN_L/H should
# both still read their reset default of 0x00 for Pipe Y (the pipe this board
# uses); Pipe Z is logged for visibility only, not enforced (unused).
DESERIALIZER_PIPE_Y_MAP_EN_L_REG = [0x04, 0x4B]
DESERIALIZER_PIPE_Y_MAP_EN_H_REG = [0x04, 0x4C]
DESERIALIZER_PIPE_Z_MAP_EN_L_REG = [0x04, 0x8B]
DESERIALIZER_PIPE_Z_MAP_EN_H_REG = [0x04, 0x8C]
# MAP_SRC_{0-15}/MAP_DST_{0-15} (16 VC/DT remap entries, odd/even register pairs)
# and MAP_DPHY_DEST_{0-15} (4 registers, 2 bits per map entry = controller destination).
# Pipe Y base addresses per Figure 5: MAP_SRC_0=0x044D, MAP_DPHY_DEST regs 0x046D-0x0470.
# Pipe Z base addresses: MAP_SRC_0=0x048D, MAP_DPHY_DEST regs 0x04AD-0x04B0.
DESERIALIZER_PIPE_Y_MAP_SRC_BASE = 0x044D
DESERIALIZER_PIPE_Y_MAP_DPHY_DEST_BASE = 0x046D
DESERIALIZER_PIPE_Z_MAP_SRC_BASE = 0x048D
DESERIALIZER_PIPE_Z_MAP_DPHY_DEST_BASE = 0x04AD
DESERIALIZER_MAP_DPHY_DEST_NAMES = {0b00: "Not supported", 0b01: "PHY1", 0b10: "PHY2", 0b11: "Not supported"}


def _log_pipe_mapping_entries(bus: SMBus, pipe_name: str, map_src_base: int, map_dphy_dest_base: int) -> None:
    """Log all 16 MAP_SRC_x/MAP_DST_x entries and the 4 MAP_DPHY_DEST_x registers
    for one pipe (informational - whether these have any effect depends on the
    corresponding MAP_EN_L/H bit for each entry, logged separately).
    """
    for i in range(16):
        src_addr = map_src_base + 2 * i
        dst_addr = src_addr + 1
        src = m._read_deserializer_reg(bus, [(src_addr >> 8) & 0xFF, src_addr & 0xFF])
        dst = m._read_deserializer_reg(bus, [(dst_addr >> 8) & 0xFF, dst_addr & 0xFF])
        logging.info("%s MAP_SRC_%d (0x%04X) = 0x%02X (VC=0x%X DT=0x%02X) | MAP_DST_%d (0x%04X) = "
                     "0x%02X (VC=0x%X DT=0x%02X)",
                     pipe_name, i, src_addr, src, (src >> 6) & 0x3, src & 0x3F,
                     i, dst_addr, dst, (dst >> 6) & 0x3, dst & 0x3F)

    for reg_idx in range(4):
        addr = map_dphy_dest_base + reg_idx
        value = m._read_deserializer_reg(bus, [(addr >> 8) & 0xFF, addr & 0xFF])
        maps = [reg_idx * 4 + k for k in range(4)]
        dests = [DESERIALIZER_MAP_DPHY_DEST_NAMES.get((value >> (2 * k)) & 0x3, "?") for k in range(4)]
        logging.info("%s MAP_DPHY_DEST (0x%04X) = 0x%02X | Map%d=%s Map%d=%s Map%d=%s Map%d=%s",
                     pipe_name, addr, value, maps[0], dests[0], maps[1], dests[1],
                     maps[2], dests[2], maps[3], dests[3])


def validate_pipe_controller_mapping_table(bus: SMBus) -> bool:
    """Read back and validate the User Guide's Table 9 (Video Pipe to MIPI PHY
    Controller Register: MAP_EN_L/H) against this board's expected pass-through
    (no VC/DT remap override) configuration.

    Returns True if Pipe Y's MAP_EN_L/H both read their reset default (0x00, no
    mapping overrides active - relying on the default Pipe Y -> Controller 1
    routing, since tunneling mode doesn't support VC reassignment). Pipe Z is
    logged for visibility only, not enforced - unused on this board.
    """
    logging.info(">>> validate_pipe_controller_mapping_table()")

    pipe_y_en_l = m._read_deserializer_reg(bus, DESERIALIZER_PIPE_Y_MAP_EN_L_REG)
    pipe_y_en_h = m._read_deserializer_reg(bus, DESERIALIZER_PIPE_Y_MAP_EN_H_REG)
    pipe_y_ok = pipe_y_en_l == 0x00 and pipe_y_en_h == 0x00
    logging.info("Pipe Y MAP_EN_L/H (MIPI_TX11/12, 0x044B/0x044C) = 0x%02X/0x%02X | expect "
                 "0x00/0x00 (no VC/DT remap override, default Pipe Y -> Controller 1 routing) | %s",
                 pipe_y_en_l, pipe_y_en_h, "OK" if pipe_y_ok else "MISMATCH")

    pipe_z_en_l = m._read_deserializer_reg(bus, DESERIALIZER_PIPE_Z_MAP_EN_L_REG)
    pipe_z_en_h = m._read_deserializer_reg(bus, DESERIALIZER_PIPE_Z_MAP_EN_H_REG)
    logging.info("Pipe Z MAP_EN_L/H (MIPI_TX11/12, 0x048B/0x048C) = 0x%02X/0x%02X - informational "
                 "only, not enforced (Pipe Z unused on this board)", pipe_z_en_l, pipe_z_en_h)

    _log_pipe_mapping_entries(bus, "Pipe Y", DESERIALIZER_PIPE_Y_MAP_SRC_BASE,
                               DESERIALIZER_PIPE_Y_MAP_DPHY_DEST_BASE)
    _log_pipe_mapping_entries(bus, "Pipe Z", DESERIALIZER_PIPE_Z_MAP_SRC_BASE,
                               DESERIALIZER_PIPE_Z_MAP_DPHY_DEST_BASE)

    logging.info("RESULT: Table 9 Video Pipe to MIPI PHY Controller validation %s",
                 "PASSED" if pipe_y_ok else "FAILED")
    return pipe_y_ok


# Jetson Orin Nano Camera #0 Connector (J20, per carrier board Table 3-1) <-> MAX96792A
# PHY1 ("Main" PHY, the one actually carrying this board's 2 active data lanes + clock
# per MIPI_PHY3's lane map - see validate_mipi_phy_settings_table()) pin mapping:
#
#   MAX96792A PHY1 signal   J20 Module Pin Name   J20 Pin #   J20 Usage/Description
#   ----------------------  --------------------  ----------  -----------------------
#   CLKAP/N (Clock)         CSI1_CLK_P/N          14 / 15     CSI 0 Clock
#   DA1P/N  (Lane 1)        CSI0_D1_P/N           8 / 9       CSI 0 Data 1
#   DA0P/N  (Lane 0)        CSI0_D0_P/N           11 / 12     CSI 0 Data 0
#
# Note: J20's module pin name for the clock pair (CSI1_CLK_P/N) doesn't match its own
# Usage/Description ("CSI 0 Clock") - that's a naming quirk in the carrier board's own
# pinout table, not an error here; the Usage/Description column is what was used above.
#
# Note on polarity (see MIPI_PHY5/0x0335 check below, expected 0x00 = normal): on Orin
# NX 16GB/8GB and Orin Nano 8GB/4GB modules, CSI0 D1 and CSI1 D0 have their P/N traces
# physically swizzled on the module itself, so the Jetson's own NVCSI receiver must
# logically re-invert those two lanes - this is why the ADSD3500 node's mode0 in the
# Jetson DT sets lane_polarity="6" (tegra_sinterface="serial_b", confirmed matching
# this board's mclk_khz=104250/512x512 QMP mode). That compensation happens entirely
# on the Jetson/NVCSI side via the DT, NOT by inverting the deserializer's own MIPI_PHY5
# output polarity bits - MIPI_PHY5=0x00 (normal) on the deserializer is correct as-is
# and should not be changed to "match" lane_polarity=6.

# Table 12 ("MAX96792A MIPI PHY Setting Registers") - all fields below match
# config_1_max96793_max96792a_init.py's constants/addresses exactly for the active
# Port A/PHY0-1/Controller 1 path (this board's only MIPI output). Port B/PHY2-3/
# Controller 2 fields are never configured by that script (unused on this board)
# and are logged for visibility only, not enforced.
DESERIALIZER_PHY_1X4_BIT = 0x02
DESERIALIZER_PHY_2X4_BIT = 0x04
DESERIALIZER_PHY_STDBY_N_PHY0_BIT = 0x10
DESERIALIZER_PHY_STDBY_N_PHY1_BIT = 0x20
DESERIALIZER_PHY_STDBY_N_PHY2_BIT = 0x40
DESERIALIZER_PHY_STDBY_N_PHY3_BIT = 0x80
DESERIALIZER_PHY4_LANE_MAP_REG = [0x03, 0x34]  # phy2_lane_map/phy3_lane_map - Port B, unused
DESERIALIZER_PHY6_POL_MAP_REG = [0x03, 0x36]   # phy2_pol_map/phy3_pol_map - Port B, unused
DESERIALIZER_RST_MIPITX_LOC_REG = [0x03, 0x3F]
DESERIALIZER_RST_MIPITX_LOC_CTRL1_BIT = 0x02
DESERIALIZER_RST_MIPITX_LOC_CTRL2_BIT = 0x04
DESERIALIZER_PIPE_Z_CSI2_LANE_CNT_REG = [0x04, 0x8A]  # Controller 2 lane count, unused
# phy2_csi_tx_dpll_predef_freq (0x0323, bits[4:0]) - Controller 2/PHY2's output data
# rate, the Table 12 counterpart to m.DESERIALIZER_MIPI_FREQ_REG (0x0320, Controller
# 1/PHY1's rate, already enforced elsewhere) - unused/informational on this board.
DESERIALIZER_PHY2_CSI_TX_DPLL_FREQ_REG = [0x03, 0x23]


def validate_mipi_phy_settings_table(bus: SMBus) -> bool:
    """Read back and validate the User Guide's Table 12 (MIPI PHY Setting Registers)
    against this board's expected Port A/PHY0-1/Controller 1, 2-lane configuration.

    Returns True if MIPI_PHY0 (2x4 mode, not 1x4), MIPI_PHY2 (PHY0/1 active, PHY2/3
    standby), MIPI_PHY3 (PHY0/1 lane map), MIPI_PHY5 (normal polarity), MIPI_TX10
    (2-lane Port A), and RST_MIPITX_LOC (Controller 1 not held in reset) all match.
    Port B/PHY2-3/Controller 2 fields are logged for visibility only, not enforced -
    unused on this board.
    """
    logging.info(">>> validate_mipi_phy_settings_table()")
    ok = True

    phy0 = m._read_deserializer_reg(bus, m.DESERIALIZER_MIPI_PHY0_REG)
    phy_1x4 = bool(phy0 & DESERIALIZER_PHY_1X4_BIT)
    phy_2x4 = bool(phy0 & DESERIALIZER_PHY_2X4_BIT)
    phy0_ok = phy_2x4 and not phy_1x4
    ok = ok and phy0_ok
    logging.info("MIPI_PHY0 (0x0330) = 0x%02X | phy_1x4=%s phy_2x4=%s | expect 2x4 mode | %s",
                 phy0, phy_1x4, phy_2x4, "OK" if phy0_ok else "MISMATCH")

    phy2 = m._read_deserializer_reg(bus, m.DESERIALIZER_MIPI_PHY2_REG)
    phy0_active = bool(phy2 & DESERIALIZER_PHY_STDBY_N_PHY0_BIT)
    phy1_active = bool(phy2 & DESERIALIZER_PHY_STDBY_N_PHY1_BIT)
    phy2_active = bool(phy2 & DESERIALIZER_PHY_STDBY_N_PHY2_BIT)
    phy3_active = bool(phy2 & DESERIALIZER_PHY_STDBY_N_PHY3_BIT)
    stdby_ok = phy0_active and phy1_active and not phy2_active and not phy3_active
    ok = ok and stdby_ok
    logging.info("MIPI_PHY2 (0x0332) = 0x%02X | PHY0=%s PHY1=%s PHY2=%s PHY3=%s | expect PHY0/1 "
                 "active, PHY2/3 standby | %s", phy2, phy0_active, phy1_active, phy2_active,
                 phy3_active, "OK" if stdby_ok else "MISMATCH")

    phy3 = m._read_deserializer_reg(bus, m.DESERIALIZER_MIPI_PHY3_REG)
    lane_map_ok = phy3 == m.DESERIALIZER_MIPI_PHY3_LANE_MAP_PHY0_PHY1
    ok = ok and lane_map_ok
    logging.info("MIPI_PHY3 (0x0333) = 0x%02X | expect 0x%02X (PHY0/1 lane map) | %s",
                 phy3, m.DESERIALIZER_MIPI_PHY3_LANE_MAP_PHY0_PHY1, "OK" if lane_map_ok else "MISMATCH")

    phy5 = m._read_deserializer_reg(bus, m.DESERIALIZER_MIPI_PHY5_REG)
    pol_ok = phy5 == m.DESERIALIZER_MIPI_PHY5_POLARITY_NORMAL
    ok = ok and pol_ok
    logging.info("MIPI_PHY5 (0x0335) = 0x%02X | expect 0x%02X (normal polarity - the Jetson DT's "
                 "lane_polarity=6 compensates for the Orin module's own CSI0/CSI1 D1/D0 swizzle "
                 "on the NVCSI side, not here) | %s",
                 phy5, m.DESERIALIZER_MIPI_PHY5_POLARITY_NORMAL, "OK" if pol_ok else "MISMATCH")

    tx10 = m._read_deserializer_reg(bus, m.DESERIALIZER_MIPI_TX10_REG)
    tx10_ok = tx10 == m.DESERIALIZER_MIPI_TX10_PORTA_2LANE
    ok = ok and tx10_ok
    logging.info("MIPI_TX10 (0x044A) CSI2_LANE_CNT = 0x%02X | expect 0x%02X (2 lanes) | %s",
                 tx10, m.DESERIALIZER_MIPI_TX10_PORTA_2LANE, "OK" if tx10_ok else "MISMATCH")

    dpll_freq = m._read_deserializer_reg(bus, m.DESERIALIZER_MIPI_FREQ_REG)
    expected_dpll_freq = m.DESERIALIZER_MIPI_FREQ_PREDEF_EN_BIT | m.DESERIALIZER_MIPI_OUTPUT_FREQ
    dpll_freq_ok = dpll_freq == expected_dpll_freq
    ok = ok and dpll_freq_ok
    logging.info("phy1_csi_tx_dpll_predef_freq (0x0320) = 0x%02X | expect 0x%02X (%s Mbps/lane) | %s",
                 dpll_freq, expected_dpll_freq,
                 m.DESERIALIZER_MIPI_FREQ_MBPS.get(m.DESERIALIZER_MIPI_OUTPUT_FREQ, "unknown"),
                 "OK" if dpll_freq_ok else "MISMATCH")

    rst_mipitx = m._read_deserializer_reg(bus, DESERIALIZER_RST_MIPITX_LOC_REG)
    ctrl1_reset = bool(rst_mipitx & DESERIALIZER_RST_MIPITX_LOC_CTRL1_BIT)
    ctrl2_reset = bool(rst_mipitx & DESERIALIZER_RST_MIPITX_LOC_CTRL2_BIT)
    reset_ok = not ctrl1_reset
    ok = ok and reset_ok
    logging.info("RST_MIPITX_LOC (0x033F) = 0x%02X | Controller1_reset=%s Controller2_reset=%s "
                 "| expect Controller1_reset=False | %s", rst_mipitx, ctrl1_reset, ctrl2_reset,
                 "OK" if reset_ok else "MISMATCH")

    phy4_lane_map = m._read_deserializer_reg(bus, DESERIALIZER_PHY4_LANE_MAP_REG)
    phy6_pol_map = m._read_deserializer_reg(bus, DESERIALIZER_PHY6_POL_MAP_REG)
    pipe_z_lane_cnt = m._read_deserializer_reg(bus, DESERIALIZER_PIPE_Z_CSI2_LANE_CNT_REG)
    phy2_dpll_freq = m._read_deserializer_reg(bus, DESERIALIZER_PHY2_CSI_TX_DPLL_FREQ_REG)
    logging.info("MIPI_PHY4 (0x0334) = 0x%02X, MIPI_PHY6 (0x0336) = 0x%02X, Pipe Z CSI2_LANE_CNT "
                 "(0x048A) = 0x%02X, phy2_csi_tx_dpll_predef_freq (0x0323) = 0x%02X - informational "
                 "only, not enforced (Port B/Controller 2 unused on this board)",
                 phy4_lane_map, phy6_pol_map, pipe_z_lane_cnt, phy2_dpll_freq)

    logging.info("RESULT: Table 12 MIPI PHY Settings validation %s", "PASSED" if ok else "FAILED")
    return ok


# Table 13 ("MAX96792A MIPI D-PHY Deskew Registers") - DESKEW_INIT/DESKEW_PER (0x0443/
# 0x0444, Controller 1 - this board's only active controller), matching
# config_1_max96793_max96792a_init.py's DESERIALIZER_DESKEW_INIT_REG/DESKEW_PER_REG
# exactly. Deskew is only required at >=1.5Gbps/lane (optional below) - the main
# script dynamically enables/disables it based on DESERIALIZER_MIPI_OUTPUT_FREQ, so
# this check reproduces that same threshold logic to compute the expected DESKEW_INIT
# state rather than hardcoding one. DESKEW_PER (periodic recalibration) is logged for
# visibility only, not enforced - it's only opt-in via --deskew-period on the main
# script and this check has no way to know whether that flag was used.
DESERIALIZER_DESKEW_INIT_AUTO_EN_BIT = 0x80
DESERIALIZER_DESKEW_INIT_MANUAL_TRIGGER_BIT = 0x20
DESERIALIZER_DESKEW_INIT_MANUAL_EN_BIT = 0x10
DESERIALIZER_DESKEW_INIT_WIDTH_MASK = 0x07
DESERIALIZER_DESKEW_PER_CAL_EN_BIT = 0x80
DESERIALIZER_DESKEW_PER_EDGE_SEL_BIT = 0x40
DESERIALIZER_DESKEW_PER_INTERVAL_SHIFT = 3
DESERIALIZER_DESKEW_PER_INTERVAL_MASK = 0x07 << DESERIALIZER_DESKEW_PER_INTERVAL_SHIFT
DESERIALIZER_DESKEW_PER_WIDTH_MASK = 0x07
DESERIALIZER_DESKEW_PERIOD_FRAMES = {0: 128, 1: 1, 2: 2, 3: 4, 4: 8, 5: 16, 6: 32, 7: 64}


def validate_mipi_deskew_table(bus: SMBus) -> bool:
    """Read back and validate the User Guide's Table 13 (MIPI D-PHY Deskew Registers:
    DESKEW_INIT/DESKEW_PER, Controller 1) against this board's expected configuration,
    computed dynamically from the configured output frequency (deskew is only required
    at >=1.5Gbps/lane).

    Returns True if DESKEW_INIT matches the expected auto-enable/width state for the
    currently configured DESERIALIZER_MIPI_OUTPUT_FREQ. DESKEW_PER (periodic
    recalibration) is logged for visibility only, not enforced - it's only opt-in via
    --deskew-period on the main bring-up script.
    """
    logging.info(">>> validate_mipi_deskew_table()")

    output_freq_mbps = m.DESERIALIZER_MIPI_FREQ_MBPS.get(m.DESERIALIZER_MIPI_OUTPUT_FREQ, 0)
    deskew_required = output_freq_mbps >= m.DESERIALIZER_DESKEW_REQUIRED_THRESHOLD_MBPS
    expected_init = (m.DESERIALIZER_DESKEW_AUTO_ENABLE_WIDEST if deskew_required
                     else m.DESERIALIZER_DESKEW_DISABLE)

    deskew_init = m._read_deserializer_reg(bus, m.DESERIALIZER_DESKEW_INIT_REG)
    auto_en = bool(deskew_init & DESERIALIZER_DESKEW_INIT_AUTO_EN_BIT)
    manual_trigger = bool(deskew_init & DESERIALIZER_DESKEW_INIT_MANUAL_TRIGGER_BIT)
    manual_en = bool(deskew_init & DESERIALIZER_DESKEW_INIT_MANUAL_EN_BIT)
    width = (deskew_init & DESERIALIZER_DESKEW_INIT_WIDTH_MASK)
    init_ok = deskew_init == expected_init
    logging.info(
        "DESKEW_INIT Controller 1 (0x0443) = 0x%02X | auto_en=%s manual_trigger=%s manual_en=%s "
        "width_code=%d | output_freq=%d Mbps/lane, deskew_required=%s, expect 0x%02X | %s",
        deskew_init, auto_en, manual_trigger, manual_en, width, output_freq_mbps,
        deskew_required, expected_init, "OK" if init_ok else "MISMATCH")

    deskew_per = m._read_deserializer_reg(bus, m.DESERIALIZER_DESKEW_PER_REG)
    periodic_en = bool(deskew_per & DESERIALIZER_DESKEW_PER_CAL_EN_BIT)
    edge_sel = bool(deskew_per & DESERIALIZER_DESKEW_PER_EDGE_SEL_BIT)
    interval_field = (deskew_per & DESERIALIZER_DESKEW_PER_INTERVAL_MASK) >> DESERIALIZER_DESKEW_PER_INTERVAL_SHIFT
    interval_frames = DESERIALIZER_DESKEW_PERIOD_FRAMES.get(interval_field, "?")
    per_width = deskew_per & DESERIALIZER_DESKEW_PER_WIDTH_MASK
    logging.info(
        "DESKEW_PER Controller 1 (0x0444) = 0x%02X | periodic_en=%s edge_sel=%s interval=every "
        "%s frame(s) width_code=%d - informational only, not enforced (opt-in via --deskew-period "
        "on config_1_max96793_max96792a_init.py)",
        deskew_per, periodic_en, "rising" if edge_sel else "falling", interval_frames, per_width)

    logging.info("RESULT: Table 13 MIPI D-PHY Deskew validation %s", "PASSED" if init_ok else "FAILED")
    return init_ok


# Table 27 ("MAX96792A MIPI Counter Registers") - 8-bit toggling packet counters used
# to confirm MIPI data is actually flowing (not just correctly configured). 0x0342
# bits[3:0]/MIPI PHY20 (0x0344) bits[7:4] match config_1_max96793_max96792a_init.py's
# read_deserializer_csi_tx_counters() exactly (Controller 1/PHY1, this board's active
# path). The duplicate-Controller-1 counter (0x0343 bits[3:0]) and all Controller
# 2/PHY0/PHY2/PHY3 counters are logged for visibility only, not enforced - Controller
# 2/Port B is unused on this board and PHY0 carries no active lanes (see Table 12).
DESERIALIZER_MIPI_CTRL2_PKT_CNT_REG = [0x03, 0x42]   # bits[7:4] = Controller 2
DESERIALIZER_MIPI_CTRL2_PKT_CNT_SHIFT = 4
DESERIALIZER_MIPI_DUP_PKT_CNT_REG = [0x03, 0x43]     # bits[3:0]=dup Ctrl1, bits[7:4]=dup Ctrl2
DESERIALIZER_MIPI_PHY0_PKT_CNT_SHIFT = 0             # 0x0344 bits[3:0] = PHY0
DESERIALIZER_MIPI_PHY23_PKT_CNT_REG = [0x03, 0x45]   # bits[3:0]=PHY2, bits[7:4]=PHY3


def _sample_mipi_packet_counters(bus: SMBus, samples: int, interval: float) -> tuple:
    """Shared sampling loop for Table 27 (MIPI Counter Registers), used by both
    check_mipi_packet_counters() and check_stream_check(). Controller1_pkt_cnt
    confirms the Pipe->Controller (BACKTOP) handoff into CSI-2 Controller 1;
    PHY1_pkt_cnt confirms data crossing Polarity Inversion/Lane Map and actually
    reaching PHY1 (Main)'s output pins - see Figure 2 (MAX96792A Video Path).

    Returns (ctrl1_active, phy1_active) - each True if that counter changed at
    least once across the sampling window.
    """
    ctrl1_values = []
    phy1_values = []
    for i in range(samples):
        ctrl1_cnt, phy1_cnt = m.read_deserializer_csi_tx_counters(bus)
        ctrl2_cnt = (m._read_deserializer_reg(bus, DESERIALIZER_MIPI_CTRL2_PKT_CNT_REG)
                     >> DESERIALIZER_MIPI_CTRL2_PKT_CNT_SHIFT) & 0x0F
        dup = m._read_deserializer_reg(bus, DESERIALIZER_MIPI_DUP_PKT_CNT_REG)
        dup_ctrl1_cnt = dup & 0x0F
        phy0_cnt = m._read_deserializer_reg(bus, m.DESERIALIZER_MIPI_PHY20_REG) & 0x0F
        phy23 = m._read_deserializer_reg(bus, DESERIALIZER_MIPI_PHY23_PKT_CNT_REG)
        phy2_cnt = phy23 & 0x0F
        phy3_cnt = (phy23 >> 4) & 0x0F
        ctrl1_values.append(ctrl1_cnt)
        phy1_values.append(phy1_cnt)
        logging.info(
            "[%d] Controller1_pkt_cnt=%d PHY1_pkt_cnt=%d | dup_Controller1_pkt_cnt=%d "
            "Controller2_pkt_cnt=%d PHY0_pkt_cnt=%d PHY2_pkt_cnt=%d PHY3_pkt_cnt=%d",
            i, ctrl1_cnt, phy1_cnt, dup_ctrl1_cnt, ctrl2_cnt, phy0_cnt, phy2_cnt, phy3_cnt)
        if i < samples - 1:
            time.sleep(interval)

    return (len(set(ctrl1_values)) > 1, len(set(phy1_values)) > 1)


def check_mipi_packet_counters(bus: SMBus, samples: int, interval: float) -> bool:
    """Sample the User Guide's Table 27 (MIPI Counter Registers) repeatedly (sensor
    must be streaming) to confirm MIPI data is actively flowing on Controller 1/PHY1 -
    this board's active path.

    Returns True if both the Controller 1 (0x0342 bits[3:0]) and PHY1 (0x0344
    bits[7:4]) packet counters changed at least once across the sampling window.
    Controller 2, the duplicate-Controller-1 counter, and PHY0/2/3 are logged for
    visibility only, not enforced.
    """
    logging.info(">>> check_mipi_packet_counters()")
    ctrl1_active, phy1_active = _sample_mipi_packet_counters(bus, samples, interval)
    ok = ctrl1_active and phy1_active
    logging.info("RESULT: Table 27 MIPI Counter validation %s (Controller1_toggled=%s "
                 "PHY1_toggled=%s)", "PASSED" if ok else "FAILED", ctrl1_active, phy1_active)
    return ok


# Dynamic link/video lock status (not a numbered table - GMSL LOCKED/CMU_LOCKED come
# from CTRL3 0x0013, already defined in config_1_max96793_max96792a_init.py; VIDEO_LOCK
# is a separate real-time bit per pipe that only asserts while valid video data is
# actually being received, unlike LOCKED which just reflects GMSL serdes sync).
DESERIALIZER_VIDEO_LOCK_PIPE_Y_REG = [0x01, 0xFC]
DESERIALIZER_VIDEO_LOCK_PIPE_Z_REG = [0x02, 0x1C]
DESERIALIZER_VIDEO_LOCK_BIT = 0x01


def check_video_lock(bus: SMBus, samples: int, interval: float) -> bool:
    """Sample GMSL LOCKED/CMU_LOCKED (CTRL3 0x0013) and Pipe Y's VIDEO_LOCK (0x01FC bit
    0) repeatedly to tell apart a link that is up but idle from one that is actually
    carrying video (sensor must be streaming for VIDEO_LOCK to assert). Pipe Z's
    VIDEO_LOCK (0x021C bit 0) is logged for visibility only - unused on this board.

    Returns True if LOCKED and Pipe Y's VIDEO_LOCK both asserted on at least one sample.
    """
    logging.info(">>> check_video_lock()")
    any_locked = False
    any_video_lock_y = False
    for i in range(samples):
        _, _, locked, cmu_locked = m.read_deserializer_link_status(bus)
        video_lock_y = bool(m._read_deserializer_reg(bus, DESERIALIZER_VIDEO_LOCK_PIPE_Y_REG)
                             & DESERIALIZER_VIDEO_LOCK_BIT)
        video_lock_z = bool(m._read_deserializer_reg(bus, DESERIALIZER_VIDEO_LOCK_PIPE_Z_REG)
                             & DESERIALIZER_VIDEO_LOCK_BIT)
        any_locked = any_locked or locked
        any_video_lock_y = any_video_lock_y or video_lock_y
        logging.info("[%d] LOCKED=%s CMU_LOCKED=%s VIDEO_LOCK Pipe Y (0x01FC)=%s Pipe Z "
                     "(0x021C, informational)=%s", i, locked, cmu_locked, video_lock_y, video_lock_z)
        if i < samples - 1:
            time.sleep(interval)

    ok = any_locked and any_video_lock_y
    logging.info("RESULT: Video/Link Lock validation %s (LOCKED_asserted=%s "
                 "VIDEO_LOCK_Y_asserted=%s)", "PASSED" if ok else "FAILED", any_locked, any_video_lock_y)
    return ok


def check_backtop_vs_controller1(bus: SMBus, samples: int, interval: float) -> bool:
    """Tightly correlate BACKTOP's own buffer-overflow flags (LMO_Y/cmd_overflow2,
    0x0312 - upstream of the Mapping/Routing Block, i.e. "is BACKTOP still receiving
    data it can't drain") against Controller 1/PHY1's TX packet counters (0x0342/
    0x0344) sample-for-sample, to answer: when TX packets stop, is BACKTOP backing up
    (proving data keeps arriving but Controller 1 stopped draining it), or does
    BACKTOP itself go idle too (proving the stall is further upstream, at/before
    BACKTOP)? No single register directly counts packets handed from BACKTOP to
    Controller 1 - this is the closest indirect proof available in the register map.

    Returns True if no BACKTOP overflow was observed (regardless of TX activity -
    this check is diagnostic/correlational, not pass/fail in the usual sense).
    """
    logging.info(">>> check_backtop_vs_controller1()")
    any_overflow = False
    for i in range(samples):
        backtop11 = m._read_deserializer_reg(bus, DESERIALIZER_BACKTOP11_REG)
        lmo_y = bool(backtop11 & DESERIALIZER_BACKTOP11_LMO_Y_BIT)
        cmd_overflow2 = bool(backtop11 & DESERIALIZER_BACKTOP11_CMD_OVERFLOW2_BIT)
        ctrl1_cnt, phy1_cnt = m.read_deserializer_csi_tx_counters(bus)
        any_overflow = any_overflow or lmo_y or cmd_overflow2
        logging.info("[%d] BACKTOP11 (0x0312) LMO_Y=%s cmd_overflow2=%s | Controller1_pkt_cnt=%d "
                     "PHY1_pkt_cnt=%d", i, lmo_y, cmd_overflow2, ctrl1_cnt, phy1_cnt)
        if i < samples - 1:
            time.sleep(interval)

    logging.info("RESULT: BACKTOP-vs-Controller1 correlation check complete (overflow_seen=%s) - "
                 "if TX counters went idle while LMO_Y/cmd_overflow2 stayed False the whole time, "
                 "BACKTOP itself also went idle (stall is at/before BACKTOP); if an overflow "
                 "appeared right as TX counters stopped, BACKTOP kept receiving data that "
                 "Controller 1 stopped draining (stall is at/after Controller 1)", any_overflow)
    return not any_overflow


def check_csi_out_en(bus: SMBus) -> bool:
    """Read BACKTOP12 (0x0313) CSI_OUT_EN - Table 2 Start-Up Sequence step 18 ("DES
    Enable CSI Output"). If VIDEO_LOCK is asserted (data is arriving on Pipe Y) but
    this bit reads 0, the deserializer is holding its CSI-2 PHY output disabled,
    which exactly explains VIDEO_LOCK=True with MIPI TX packet counters stuck at 0.

    Returns True if CSI_OUT_EN is enabled.
    """
    logging.info(">>> check_csi_out_en()")
    backtop12 = m._read_deserializer_reg(bus, m.DESERIALIZER_BACKTOP12_REG)
    enabled = backtop12 == m.DESERIALIZER_CSI_OUT_ENABLE
    logging.info("BACKTOP12 (0x0313) CSI_OUT_EN = 0x%02X | expect 0x%02X (enabled) | %s",
                 backtop12, m.DESERIALIZER_CSI_OUT_ENABLE, "OK" if enabled else "MISMATCH (CSI output disabled)")
    return enabled


# BACKTOP1 (0x0308) - per-pipe CSI-2 output PLL lock status (max96792a.pdf Register Map,
# not covered by the device-specific user guide's own tables). If VIDEO_LOCK is
# asserted and CSI_OUT_EN is enabled but CSIPLLY_LOCK never asserts, Pipe Y's MIPI TX
# output clock itself isn't locked, which would explain packet counters stuck at 0
# despite everything upstream looking healthy.
DESERIALIZER_BACKTOP1_REG = [0x03, 0x08]
DESERIALIZER_BACKTOP1_CSIPLLZ_LOCK_BIT = 0x40
DESERIALIZER_BACKTOP1_CSIPLLY_LOCK_BIT = 0x20


def check_csi_pll_lock(bus: SMBus, samples: int, interval: float) -> bool:
    """Sample BACKTOP1 (0x0308) CSIPLLY_LOCK (bit 5) repeatedly to confirm Pipe Y's
    CSI-2 output PLL is locked. CSIPLLZ_LOCK (bit 6) is logged for visibility only -
    Pipe Z is unused on this board.

    Returns True if CSIPLLY_LOCK asserted on at least one sample.
    """
    logging.info(">>> check_csi_pll_lock()")
    any_locked_y = False
    for i in range(samples):
        backtop1 = m._read_deserializer_reg(bus, DESERIALIZER_BACKTOP1_REG)
        pll_y = bool(backtop1 & DESERIALIZER_BACKTOP1_CSIPLLY_LOCK_BIT)
        pll_z = bool(backtop1 & DESERIALIZER_BACKTOP1_CSIPLLZ_LOCK_BIT)
        any_locked_y = any_locked_y or pll_y
        logging.info("[%d] BACKTOP1 (0x0308) = 0x%02X | CSIPLLY_LOCK=%s CSIPLLZ_LOCK (informational)=%s",
                     i, backtop1, pll_y, pll_z)
        if i < samples - 1:
            time.sleep(interval)

    logging.info("RESULT: CSI-2 output PLL lock validation %s (CSIPLLY_LOCK_asserted=%s)",
                 "PASSED" if any_locked_y else "FAILED", any_locked_y)
    return any_locked_y


# RLMS5/RLMS7 Link A (0x1405/0x1407, max96792a.pdf Register Map) - GMSL3 Eye-Opening
# Monitor (EOM). EOM_EN/EOM_PER_MODE are both enabled by reset default, so EOM runs
# continuously without needing a manual trigger. A marginal eye (EOM result close to
# EOM_MIN_THR) can cause exactly the symptom observed here: GMSL PHY-level LOCKED
# stays solid while a downstream video-qualification stage (Pipe Y's VIDEO_LOCK)
# intermittently fails - this was the confirmed root cause of an identical symptom
# on a different board (MAX96726A), fixed by lowering EOM_MIN_THR from the same
# reset default (0x10) used here.
DESERIALIZER_RLMS5_LINKA_REG = [0x14, 0x05]
DESERIALIZER_EOM_MIN_THR_MASK = 0x7F
DESERIALIZER_RLMS7_LINKA_REG = [0x14, 0x07]
DESERIALIZER_EOM_DONE_BIT = 0x80
DESERIALIZER_EOM_RESULT_MASK = 0x7F


def check_eom_result(bus: SMBus, samples: int, interval: float) -> bool:
    """Sample RLMS7 Link A (0x1407) repeatedly to read the GMSL3 Eye-Opening
    Monitor's periodic result (EOM_PER_MODE is enabled by reset default, so no
    manual trigger is needed) and compare it against the configured EOM_MIN_THR
    (RLMS5 Link A, 0x1405). Both are expressed as a fraction of 64 (% eye opening
    = value/64).

    Returns True if every completed measurement stayed at least 4/64 above
    EOM_MIN_THR (a safety margin, not a hard datasheet requirement) - a result
    that merely clears the threshold by 0-3/64 is still a marginal eye that can
    randomly fail round to round.
    """
    logging.info(">>> check_eom_result()")
    min_thr = m._read_deserializer_reg(bus, DESERIALIZER_RLMS5_LINKA_REG) & DESERIALIZER_EOM_MIN_THR_MASK
    logging.info("RLMS5 Link A (0x1405) EOM_MIN_THR = %d/64 (%.1f%% eye opening required)",
                 min_thr, min_thr / 64 * 100)

    margin_thr = min_thr + 4
    any_marginal = False
    results = []
    for i in range(samples):
        rlms7 = m._read_deserializer_reg(bus, DESERIALIZER_RLMS7_LINKA_REG)
        done = bool(rlms7 & DESERIALIZER_EOM_DONE_BIT)
        result = rlms7 & DESERIALIZER_EOM_RESULT_MASK
        if done:
            results.append(result)
            marginal = result < margin_thr
            any_marginal = any_marginal or marginal
            logging.info("[%d] RLMS7 Link A (0x1407) EOM_DONE=True EOM=%d/64 (%.1f%%) | margin over "
                         "threshold=%d/64 | %s", i, result, result / 64 * 100, result - min_thr,
                         "MARGINAL" if marginal else "OK")
        else:
            logging.info("[%d] RLMS7 Link A (0x1407) EOM_DONE=False (measurement in progress)", i)
        if i < samples - 1:
            time.sleep(interval)

    ok = bool(results) and not any_marginal
    logging.info("RESULT: EOM margin validation %s (samples_completed=%d, marginal_seen=%s)",
                 "PASSED" if ok else "FAILED", len(results), any_marginal)
    return ok


# INTR5 (0x001D) - EOM_ERR_FLAG_A/FEC_RX_ERR_FLAG (max96792a.pdf Register Map). These
# are hardware-asserted error flags at the raw GMSL3 link layer, upstream of everything
# else checked so far: EOM_ERR_FLAG_A fires whenever the eye opening drops below
# EOM_MIN_THR (a direct hardware confirmation, not just our own computed margin);
# FEC_RX_ERR_FLAG fires when the link's mandatory Forward Error Correction (always-on
# at GMSL3 12Gbps per the datasheet) has had to correct enough raw bit errors to exceed
# its own threshold - i.e. proof of a high raw physical bit-error-rate that FEC is
# already struggling to fully compensate for. Both are sticky/clear-on-read.
DESERIALIZER_INTR5_REG = [0x00, 0x1D]
DESERIALIZER_INTR5_EOM_ERR_FLAG_A_BIT = 0x40
DESERIALIZER_INTR5_FEC_RX_ERR_FLAG_BIT = 0x20
# CLEAR_STATS Link A (0x2000) CLEAR_ALL_STATS (bit 0, write-1-to-clear). Per the
# datasheet, FEC_RX_ERR_FLAG only re-arms after its underlying FEC statistics
# counters are reset here - without this, a flag that already tripped once earlier
# would stay clear even if the same error condition is still actively occurring.
DESERIALIZER_CLEAR_STATS_REG = [0x20, 0x00]
DESERIALIZER_CLEAR_STATS_CLEAR_ALL_BIT = 0x01


def check_link_a_error_flags(bus: SMBus, samples: int, interval: float) -> bool:
    """Reset Link A's FEC statistics counters (CLEAR_STATS, 0x2000) so
    FEC_RX_ERR_FLAG can re-arm, then sample INTR5 (0x001D) EOM_ERR_FLAG_A/
    FEC_RX_ERR_FLAG repeatedly - hardware-asserted, clear-on-read flags at the raw
    GMSL3 link layer (upstream of the tunnel/MIPI TX stage). FEC_RX_ERR_FLAG
    asserting is strong evidence of a high raw physical bit-error-rate that FEC
    (mandatory and always-on at 12Gbps) is already struggling to fully correct -
    pointing at link/cable/connector signal integrity rather than anything further
    fixable by register configuration.

    Returns True if neither flag was ever asserted across the sampling window.
    """
    logging.info(">>> check_link_a_error_flags()")
    m._i2c_write(bus, m.DESERIALIZER_ADDR,
                 DESERIALIZER_CLEAR_STATS_REG + [DESERIALIZER_CLEAR_STATS_CLEAR_ALL_BIT],
                 "\tCLEAR_STATS (Link A) | CLEAR_ALL_STATS: FEC statistics counters reset")
    any_eom_err = False
    any_fec_err = False
    for i in range(samples):
        intr5 = m._read_deserializer_reg(bus, DESERIALIZER_INTR5_REG)
        eom_err = bool(intr5 & DESERIALIZER_INTR5_EOM_ERR_FLAG_A_BIT)
        fec_err = bool(intr5 & DESERIALIZER_INTR5_FEC_RX_ERR_FLAG_BIT)
        any_eom_err = any_eom_err or eom_err
        any_fec_err = any_fec_err or fec_err
        logging.info("[%d] INTR5 (0x001D) = 0x%02X | EOM_ERR_FLAG_A(sticky)=%s FEC_RX_ERR_FLAG(sticky)=%s",
                     i, intr5, eom_err, fec_err)
        if i < samples - 1:
            time.sleep(interval)

    ok = not (any_eom_err or any_fec_err)
    logging.info("RESULT: Link A error flag validation %s (EOM_err_seen=%s FEC_err_seen=%s)",
                 "PASSED" if ok else "FAILED", any_eom_err, any_fec_err)
    return ok


# MIPI_PHY17 (0x0341) - tunnel integrity error flags (max96792a.pdf Register Map, not
# covered by the device-specific user guide's own tables). Tunneling mode protects
# data with an end-to-end CRC; if TUN_DATA_CRC_ERR/TUN_ECC_UNCORR_ERR are persistently
# asserted, every tunneled packet could be failing its integrity check and getting
# silently dropped before reaching the MIPI TX output stage - which would explain
# VIDEO_LOCK=True (enough structure recognized to lock) with zero packet egress.
DESERIALIZER_MIPI_PHY17_REG = [0x03, 0x41]
DESERIALIZER_MIPI_PHY17_TUN_DATA_CRC_ERR_BIT = 0x20
DESERIALIZER_MIPI_PHY17_TUN_ECC_UNCORR_ERR_BIT = 0x10
DESERIALIZER_MIPI_PHY17_TUN_ECC_CORR_ERR_BIT = 0x08
DESERIALIZER_MIPI_PHY17_VID_OVERFLOW_FLAG_BIT = 0x01


def check_tunnel_errors(bus: SMBus, samples: int, interval: float) -> bool:
    """Sample MIPI_PHY17 (0x0341) repeatedly to check for tunnel integrity errors
    (TUN_DATA_CRC_ERR, TUN_ECC_UNCORR_ERR, VID_OVERFLOW_FLAG) that would cause every
    tunneled packet to be silently dropped before reaching the MIPI TX output stage.
    TUN_ECC_CORR_ERR (correctable, auto-recovered) is logged for visibility only.

    Returns True if none of TUN_DATA_CRC_ERR/TUN_ECC_UNCORR_ERR/VID_OVERFLOW_FLAG
    were ever asserted across the sampling window.
    """
    logging.info(">>> check_tunnel_errors()")
    any_crc_err = False
    any_uncorr_err = False
    any_overflow = False
    for i in range(samples):
        phy17 = m._read_deserializer_reg(bus, DESERIALIZER_MIPI_PHY17_REG)
        crc_err = bool(phy17 & DESERIALIZER_MIPI_PHY17_TUN_DATA_CRC_ERR_BIT)
        uncorr_err = bool(phy17 & DESERIALIZER_MIPI_PHY17_TUN_ECC_UNCORR_ERR_BIT)
        corr_err = bool(phy17 & DESERIALIZER_MIPI_PHY17_TUN_ECC_CORR_ERR_BIT)
        overflow = bool(phy17 & DESERIALIZER_MIPI_PHY17_VID_OVERFLOW_FLAG_BIT)
        any_crc_err = any_crc_err or crc_err
        any_uncorr_err = any_uncorr_err or uncorr_err
        any_overflow = any_overflow or overflow
        logging.info("[%d] MIPI_PHY17 (0x0341) = 0x%02X | TUN_DATA_CRC_ERR=%s TUN_ECC_UNCORR_ERR=%s "
                     "TUN_ECC_CORR_ERR (informational)=%s VID_OVERFLOW_FLAG=%s",
                     i, phy17, crc_err, uncorr_err, corr_err, overflow)
        if i < samples - 1:
            time.sleep(interval)

    ok = not (any_crc_err or any_uncorr_err or any_overflow)
    logging.info("RESULT: Tunnel integrity error validation %s (CRC_err_seen=%s "
                 "ECC_uncorr_err_seen=%s overflow_seen=%s)",
                 "PASSED" if ok else "FAILED", any_crc_err, any_uncorr_err, any_overflow)
    return ok


def check_gmsl_crc(bus: SMBus, samples: int, interval: float) -> bool:
    """Sample MIPI_PHY17 (0x0341) bit 5 (TUN_DATA_CRC_ERR) repeatedly - Figure 3's
    ("Pixel and Tunneling Mode Comparison") "CHECK AND REMOVE GMSL CRC" step,
    confirming the deserializer's end-to-end GMSL tunnel CRC check on data arriving
    from the serializer passes, before that data is handed to the MIPI TX output
    stage. This is the single bit check_tunnel_errors() already samples as part of
    its broader tunnel-integrity check; exposed standalone for direct comparison
    against the serializer's --check-crc (CSI-2 CRC).

    Returns True if TUN_DATA_CRC_ERR was never asserted across the sampling window.
    """
    logging.info(">>> check_gmsl_crc()")
    any_crc_err = False
    for i in range(samples):
        phy17 = m._read_deserializer_reg(bus, DESERIALIZER_MIPI_PHY17_REG)
        crc_err = bool(phy17 & DESERIALIZER_MIPI_PHY17_TUN_DATA_CRC_ERR_BIT)
        any_crc_err = any_crc_err or crc_err
        logging.info("[%d] MIPI_PHY17 (0x0341) = 0x%02X | TUN_DATA_CRC_ERR=%s", i, phy17, crc_err)
        if i < samples - 1:
            time.sleep(interval)

    logging.info("RESULT: GMSL CRC validation %s (CRC_err_seen=%s)",
                 "PASSED" if not any_crc_err else "FAILED", any_crc_err)
    return not any_crc_err


# INTR14 (0x5013)/VIDEO_RX14 (0x501B)/BACKTOP11 (0x0312) - sticky, clear-on-read flags
# (max96792a.pdf Register Map) that latch brief glitches a 1Hz poll of LOCKED/
# VIDEO_LOCK would otherwise miss entirely (e.g. a packet counter resetting to 0
# mid-stream, as "packets since video started" implies video briefly relocked).
DESERIALIZER_INTR14_REG = [0x50, 0x13]
DESERIALIZER_INTR14_FEC_B_INACTIVE_BIT = 0x80
DESERIALIZER_INTR14_FEC_A_INACTIVE_BIT = 0x40
DESERIALIZER_INTR14_VIDEO_MEM_OVERFLOW_BIT = 0x02
DESERIALIZER_INTR14_LOSS_OF_LOCK_FLAG_BIT = 0x01
DESERIALIZER_VIDEO_RX14_PIPE_Y_REG = [0x50, 0x1B]
DESERIALIZER_LOSS_OF_VIDEO_LOCK_BIT = 0x01
DESERIALIZER_BACKTOP11_REG = [0x03, 0x12]
DESERIALIZER_BACKTOP11_CMD_OVERFLOW3_BIT = 0x40
DESERIALIZER_BACKTOP11_CMD_OVERFLOW2_BIT = 0x20
DESERIALIZER_BACKTOP11_LMO_Z_BIT = 0x04
DESERIALIZER_BACKTOP11_LMO_Y_BIT = 0x02


def check_sticky_errors(bus: SMBus, samples: int, interval: float) -> bool:
    """Sample the sticky, clear-on-read loss-of-lock/overflow flags repeatedly.
    Each read clears the flag, so a flag reading True on any sample after the
    first proves a NEW glitch occurred during that sampling interval - catching
    brief relock events a plain 1Hz LOCKED/VIDEO_LOCK poll would miss entirely.

    Returns True if no loss-of-lock, loss-of-video-lock, or memory overflow event
    was observed across the sampling window.
    """
    logging.info(">>> check_sticky_errors()")
    any_loss_of_lock = False
    any_loss_of_video_lock = False
    any_mem_overflow = False
    for i in range(samples):
        intr14 = m._read_deserializer_reg(bus, DESERIALIZER_INTR14_REG)
        loss_of_lock = bool(intr14 & DESERIALIZER_INTR14_LOSS_OF_LOCK_FLAG_BIT)
        mem_overflow = bool(intr14 & DESERIALIZER_INTR14_VIDEO_MEM_OVERFLOW_BIT)
        video_rx14 = m._read_deserializer_reg(bus, DESERIALIZER_VIDEO_RX14_PIPE_Y_REG)
        loss_of_video_lock = bool(video_rx14 & DESERIALIZER_LOSS_OF_VIDEO_LOCK_BIT)
        backtop11 = m._read_deserializer_reg(bus, DESERIALIZER_BACKTOP11_REG)
        lmo_y = bool(backtop11 & DESERIALIZER_BACKTOP11_LMO_Y_BIT)
        lmo_z = bool(backtop11 & DESERIALIZER_BACKTOP11_LMO_Z_BIT)
        cmd_overflow2 = bool(backtop11 & DESERIALIZER_BACKTOP11_CMD_OVERFLOW2_BIT)
        cmd_overflow3 = bool(backtop11 & DESERIALIZER_BACKTOP11_CMD_OVERFLOW3_BIT)
        any_loss_of_lock = any_loss_of_lock or loss_of_lock
        any_loss_of_video_lock = any_loss_of_video_lock or loss_of_video_lock
        any_mem_overflow = any_mem_overflow or mem_overflow
        logging.info("[%d] INTR14 (0x5013) LOSS_OF_LOCK_FLAG(sticky)=%s video_mem_overflow=%s | "
                     "VIDEO_RX14 (0x501B) LOSS_OF_VIDEO_LOCK Pipe Y (sticky)=%s | BACKTOP11 (0x0312) "
                     "LMO_Y=%s LMO_Z=%s cmd_overflow2=%s cmd_overflow3=%s",
                     i, loss_of_lock, mem_overflow, loss_of_video_lock, lmo_y, lmo_z,
                     cmd_overflow2, cmd_overflow3)
        if i < samples - 1:
            time.sleep(interval)

    ok = not (any_loss_of_lock or any_loss_of_video_lock or any_mem_overflow)
    logging.info("RESULT: Sticky error flag validation %s (loss_of_lock_seen=%s "
                 "loss_of_video_lock_seen=%s mem_overflow_seen=%s)",
                 "PASSED" if ok else "FAILED", any_loss_of_lock, any_loss_of_video_lock, any_mem_overflow)
    return ok


def check_stream_check(bus: SMBus, samples: int, interval: float) -> bool:
    """Live, end-to-end pipeline check (sensor must be streaming), one stage per box
    in Figure 2 (MAX96792A Video Path): GMSL PHY link up through the Video Pipe
    Select/crossbar (LOCKED + Pipe Y's VIDEO_LOCK), the Pipe->Controller (BACKTOP)
    handoff into CSI-2 Controller 1 (Controller1_pkt_cnt), Polarity Inversion/Lane
    Map through to PHY1 (Main)'s output pins (PHY1_pkt_cnt), and Pipe Y's CSI-2
    output PLL lock (CSIPLLY_LOCK) - reported individually so a broken stage can be
    isolated from a healthy upstream/downstream one.

    Returns True only if every stage passes.
    """
    logging.info(">>> check_stream_check()")
    logging.info("---- Stage 1/4: GMSL PHY Link -> Video Pipe Select -> Crossbar (LOCKED + VIDEO_LOCK) ----")
    video_lock_ok = check_video_lock(bus, samples, interval)
    logging.info("---- Stages 2-3/4: Pipe->Controller (BACKTOP) -> CSI-2 Controller 1 -> PHY1 output (packet counters) ----")
    ctrl1_ok, phy1_ok = _sample_mipi_packet_counters(bus, samples, interval)
    logging.info("---- Stage 4/4: Pipe Y CSI-2 Output PLL Lock (CSIPLLY_LOCK) ----")
    pll_ok = check_csi_pll_lock(bus, samples, interval)

    overall = video_lock_ok and ctrl1_ok and phy1_ok and pll_ok
    logging.info("==================== STREAM CHECK SUMMARY (Figure 2 pipeline) ====================")
    logging.info("%-65s %s", "1. GMSL PHY Link -> Video Pipe/Crossbar (LOCKED + VIDEO_LOCK)",
                 "PASSED" if video_lock_ok else "FAILED")
    logging.info("%-65s %s", "2. Pipe->Controller (BACKTOP) -> CSI-2 Controller 1 (Controller1_pkt_cnt)",
                 "PASSED" if ctrl1_ok else "FAILED")
    logging.info("%-65s %s", "3. Polarity Inversion/Lane Map -> PHY1 output pins (PHY1_pkt_cnt)",
                 "PASSED" if phy1_ok else "FAILED")
    logging.info("%-65s %s", "4. Pipe Y CSI-2 Output PLL Lock (CSIPLLY_LOCK)",
                 "PASSED" if pll_ok else "FAILED")
    logging.info("------------------------------------------------------------------------------------")
    logging.info("Overall: %s", "PASSED" if overall else "FAILED")
    logging.info("======================================================================================")
    return overall


def run_all_checks(bus: SMBus, samples: int, interval: float) -> bool:
    """Run every --check-* table validation and print a consolidated PASS/FAIL summary.

    Returns True only if every check passes.
    """
    results = {
        "Table 3 (Pixel/Tunneling Mode)": validate_pixel_tunnel_mode_table(bus),
        "Table 6 (Link Initialization)": validate_link_init_table(bus),
        "Table 7 (Single-/Dual-Link Operation)": validate_link_operation_table(bus),
        "Table 8 (Video Pipe Selection)": validate_video_pipe_selection_table(bus),
        "Table 9 (Video Pipe to MIPI PHY Controller)": validate_pipe_controller_mapping_table(bus),
        "Table 12 (MIPI PHY Settings)": validate_mipi_phy_settings_table(bus),
        "Table 13 (MIPI D-PHY Deskew)": validate_mipi_deskew_table(bus),
        "CSI_OUT_EN (Table 2 step 18)": check_csi_out_en(bus),
        "CSI-2 Output PLL Lock (BACKTOP1 CSIPLLY_LOCK)": check_csi_pll_lock(bus, samples, interval),
        "GMSL3 Eye-Opening Monitor (EOM) Margin": check_eom_result(bus, samples, interval),
        "Tunnel Integrity Errors (MIPI_PHY17)": check_tunnel_errors(bus, samples, interval),
        "Sticky Loss-of-Lock/Overflow Flags": check_sticky_errors(bus, samples, interval),
        "Video/Link Lock (LOCKED + VIDEO_LOCK)": check_video_lock(bus, samples, interval),
        "Table 27 (MIPI Packet Counters)": check_mipi_packet_counters(bus, samples, interval),
    }

    overall = all(results.values())
    logging.info("==================== SUMMARY ====================")
    for name, passed in results.items():
        logging.info("%-42s %s", name, "PASSED" if passed else "FAILED")
    logging.info("--------------------------------------------------")
    logging.info("Overall: %s", "PASSED" if overall else "FAILED")
    logging.info("==================================================")
    summarize_configuration(bus)
    return overall


def summarize_configuration(bus: SMBus) -> None:
    """Log a low-level, human-readable report of every table's current register
    state, independent of pass/fail - so the user can see exactly what is set.
    """
    logging.info("============== CURRENT CONFIGURATION (low-level report) ==============")

    pipe_y = m._read_deserializer_reg(bus, DESERIALIZER_TUN_EN_PIPE_Y_REG)
    pipe_z = m._read_deserializer_reg(bus, DESERIALIZER_TUN_EN_PIPE_Z_REG)
    logging.info("[Table 3] TUN_EN: Pipe Y=0x%02X (%s), Pipe Z=0x%02X (%s)",
                 pipe_y, "Tunneling" if pipe_y & DESERIALIZER_TUN_EN_BIT else "Pixel",
                 pipe_z, "Tunneling" if pipe_z & DESERIALIZER_TUN_EN_BIT else "Pixel")

    reg1 = m._read_deserializer_reg(bus, m.DESERIALIZER_REG1)
    reg4 = m._read_deserializer_reg(bus, m.DESERIALIZER_REG4)
    ctrl0 = m._read_deserializer_reg(bus, m.DESERIALIZER_CTRL0_REG)
    cxtp = m._read_deserializer_reg(bus, DESERIALIZER_CXTP_REG)
    logging.info("[Table 6] RX_RATE=0b%02s GMSL3_A=%s CTRL0=0x%02X CXTP_A=%s CXTP_B=%s",
                 bin(reg1 & m.DESERIALIZER_REG1_RX_RATE_MASK)[2:].zfill(2),
                 bool(reg4 & m.DESERIALIZER_REG4_GMSL3_A_BIT), ctrl0,
                 bool(cxtp & DESERIALIZER_CXTP_A_BIT), bool(cxtp & DESERIALIZER_CXTP_B_BIT))

    link_en = m._read_deserializer_reg(bus, m.DESERIALIZER_GMSL1_EN_REG)
    logging.info("[Table 7] AUTO_LINK=%s LINK_CFG=0b%02s LINK_EN_A=%s LINK_EN_B=%s",
                 bool(ctrl0 & DESERIALIZER_CTRL0_AUTO_LINK_BIT),
                 bin(ctrl0 & DESERIALIZER_CTRL0_LINK_CFG_MASK)[2:].zfill(2),
                 bool(link_en & DESERIALIZER_LINK_EN_A_BIT), bool(link_en & DESERIALIZER_LINK_EN_B_BIT))

    pipe_en = m._read_deserializer_reg(bus, m.DESERIALIZER_VIDEO_PIPE_EN_REG)
    pipe_sel = m._read_deserializer_reg(bus, m.DESERIALIZER_VIDEO_PIPE_SEL_REG)
    pipe_sel_y = pipe_sel & DESERIALIZER_VIDEO_PIPE_SEL_Y_MASK
    pipe_sel_z = (pipe_sel & DESERIALIZER_VIDEO_PIPE_SEL_Z_MASK) >> DESERIALIZER_VIDEO_PIPE_SEL_Z_SHIFT
    logging.info("[Table 8] Pipe Y: enabled=%s sel=%s | Pipe Z: enabled=%s sel=%s",
                 bool(pipe_en & DESERIALIZER_VIDEO_PIPE_EN_PIPE_Y_BIT),
                 DESERIALIZER_VIDEO_PIPE_SEL_NAMES.get(pipe_sel_y, "?"),
                 bool(pipe_en & DESERIALIZER_VIDEO_PIPE_EN_PIPE_Z_BIT),
                 DESERIALIZER_VIDEO_PIPE_SEL_NAMES.get(pipe_sel_z, "?"))

    pipe_y_en_l = m._read_deserializer_reg(bus, DESERIALIZER_PIPE_Y_MAP_EN_L_REG)
    pipe_y_en_h = m._read_deserializer_reg(bus, DESERIALIZER_PIPE_Y_MAP_EN_H_REG)
    logging.info("[Table 9] Pipe Y MAP_EN_L/H=0x%02X/0x%02X (0x00/0x00=pass-through, no VC/DT "
                 "remap)", pipe_y_en_l, pipe_y_en_h)

    phy0 = m._read_deserializer_reg(bus, m.DESERIALIZER_MIPI_PHY0_REG)
    phy2 = m._read_deserializer_reg(bus, m.DESERIALIZER_MIPI_PHY2_REG)
    tx10 = m._read_deserializer_reg(bus, m.DESERIALIZER_MIPI_TX10_REG)
    dpll_freq = m._read_deserializer_reg(bus, m.DESERIALIZER_MIPI_FREQ_REG)
    lane_cnt = ((tx10 >> 6) & 0x3) + 1
    logging.info("[Table 12] phy_2x4=%s PHY0_active=%s PHY1_active=%s lanes=%d rate=%s Mbps/lane "
                 "(no continuous/noncontinuous clock bit exists on the deserializer - that's a "
                 "serializer-only field, see debug_max96793_register_configuration.py --show-config)",
                 bool(phy0 & DESERIALIZER_PHY_2X4_BIT), bool(phy2 & DESERIALIZER_PHY_STDBY_N_PHY0_BIT),
                 bool(phy2 & DESERIALIZER_PHY_STDBY_N_PHY1_BIT), lane_cnt,
                 m.DESERIALIZER_MIPI_FREQ_MBPS.get(dpll_freq & 0x1F, "unknown"))

    deskew_init = m._read_deserializer_reg(bus, m.DESERIALIZER_DESKEW_INIT_REG)
    deskew_per = m._read_deserializer_reg(bus, m.DESERIALIZER_DESKEW_PER_REG)
    logging.info("[Table 13] DESKEW_INIT=0x%02X (auto_en=%s) DESKEW_PER=0x%02X (periodic_en=%s)",
                 deskew_init, bool(deskew_init & DESERIALIZER_DESKEW_INIT_AUTO_EN_BIT),
                 deskew_per, bool(deskew_per & DESERIALIZER_DESKEW_PER_CAL_EN_BIT))

    logging.info("=========================================================================")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bus", nargs="?", type=int, default=2, help="I2C bus number (default: 2)")
    parser.add_argument("--check-tunnel-mode", action="store_true",
                         help="Read back and validate the User Guide's Table 3 (Pixel and "
                              "Tunneling Mode Register Settings: TUN_EN, Pipe Y/Pipe Z) against "
                              "this board's expected configuration, then exit")
    parser.add_argument("--check-link-init", action="store_true",
                         help="Read back and validate the User Guide's Table 6 (Link "
                              "Initialization Registers: RX_RATE, GMSL3_A, CTRL0 reset bits) "
                              "against this board's expected Link A-only, 12Gbps/GMSL3 "
                              "configuration, then exit")
    parser.add_argument("--check-link-operation", action="store_true",
                         help="Read back and validate the User Guide's Table 7 (Single- vs. "
                              "Dual-Link Operation: AUTO_LINK/LINK_CFG, LINK_EN_A/B) against "
                              "this board's expected Link A-only configuration, then exit")
    parser.add_argument("--check-video-pipe-sel", action="store_true",
                         help="Read back and validate the User Guide's Table 8 (Video Pipe "
                              "Selection Registers: VIDEO_PIPE_EN, VIDEO_PIPE_SEL_Y/Z) against "
                              "this board's expected Pipe Y/Link A/Stream 0 configuration, then exit")
    parser.add_argument("--check-pipe-controller-mapping", action="store_true",
                         help="Read back and validate the User Guide's Table 9 (Video Pipe to "
                              "MIPI PHY Controller Register: MAP_EN_L/H) against this board's "
                              "expected pass-through (no VC/DT remap override) configuration, "
                              "then exit")
    parser.add_argument("--check-mipi-phy-settings", action="store_true",
                         help="Read back and validate the User Guide's Table 12 (MIPI PHY "
                              "Setting Registers: phy_2x4, phy_stdby_n, lane map/polarity, "
                              "CSI2_LANE_CNT, RST_MIPITX_LOC) against this board's expected "
                              "Port A/PHY0-1/Controller 1, 2-lane configuration, then exit")
    parser.add_argument("--check-mipi-deskew", action="store_true",
                         help="Read back and validate the User Guide's Table 13 (MIPI D-PHY "
                              "Deskew Registers: DESKEW_INIT/DESKEW_PER, Controller 1) against "
                              "this board's expected configuration (computed from the "
                              "configured output frequency), then exit")
    parser.add_argument("--check-mipi-packet-counters", action="store_true",
                         help="Sample the User Guide's Table 27 (MIPI Counter Registers) "
                              "repeatedly (sensor must be streaming) to confirm MIPI data is "
                              "actively flowing on Controller 1/PHY1, then exit")
    parser.add_argument("--check-video-lock", action="store_true",
                         help="Sample GMSL LOCKED/CMU_LOCKED (CTRL3 0x0013) and Pipe Y's "
                              "VIDEO_LOCK (0x01FC bit 0) repeatedly (sensor must be streaming "
                              "for VIDEO_LOCK to assert) to tell apart an idle-but-locked link "
                              "from one actually carrying video, then exit")
    parser.add_argument("--stream-check", action="store_true",
                         help="Live, end-to-end pipeline check (sensor must be streaming): walks "
                              "GMSL PHY Link -> Video Pipe Select/Crossbar (LOCKED + VIDEO_LOCK), "
                              "then Pipe->Controller (BACKTOP) -> CSI-2 Controller 1 -> PHY1 output "
                              "pins (Table 27 packet counters), then Pipe Y's CSI-2 output PLL lock "
                              "(CSIPLLY_LOCK), reporting a per-stage PASS/FAIL, then exit")
    parser.add_argument("--check-csi-out-en", action="store_true",
                         help="Read BACKTOP12 (0x0313) CSI_OUT_EN (Table 2 Start-Up Sequence "
                              "step 18) to confirm the deserializer's CSI-2 PHY output is "
                              "actually enabled, then exit")
    parser.add_argument("--check-csi-pll-lock", action="store_true",
                         help="Sample BACKTOP1 (0x0308) CSIPLLY_LOCK repeatedly to confirm "
                              "Pipe Y's CSI-2 output PLL is locked, then exit")
    parser.add_argument("--check-eom-result", action="store_true",
                         help="Sample RLMS7 Link A (0x1407) repeatedly to read the GMSL3 "
                              "Eye-Opening Monitor's periodic result and compare it against "
                              "EOM_MIN_THR (RLMS5 Link A, 0x1405), flagging a marginal eye, "
                              "then exit")
    parser.add_argument("--check-link-a-error-flags", action="store_true",
                         help="Sample INTR5 (0x001D) EOM_ERR_FLAG_A/FEC_RX_ERR_FLAG repeatedly - "
                              "hardware-asserted raw GMSL3 link-layer error flags, upstream of "
                              "the tunnel/MIPI TX stage, then exit")
    parser.add_argument("--check-tunnel-errors", action="store_true",
                         help="Sample MIPI_PHY17 (0x0341) repeatedly to check for tunnel "
                              "integrity errors (TUN_DATA_CRC_ERR, TUN_ECC_UNCORR_ERR, "
                              "VID_OVERFLOW_FLAG) that would cause packets to be silently "
                              "dropped before reaching the MIPI TX output stage, then exit")
    parser.add_argument("--check-crc", action="store_true",
                         help="Sample MIPI_PHY17 (0x0341) bit 5 (TUN_DATA_CRC_ERR) repeatedly - "
                              "Figure 3's (Pixel and Tunneling Mode Comparison) \"CHECK AND "
                              "REMOVE GMSL CRC\" step, confirming the end-to-end GMSL tunnel CRC "
                              "check passes before data reaches the MIPI TX output stage, then exit")
    parser.add_argument("--check-sticky-errors", action="store_true",
                         help="Sample the sticky, clear-on-read LOSS_OF_LOCK_FLAG (INTR14), "
                              "LOSS_OF_VIDEO_LOCK (VIDEO_RX14), and BACKTOP11 overflow flags "
                              "repeatedly to catch brief lock glitches a plain 1Hz LOCKED/ "
                              "VIDEO_LOCK poll would miss, then exit")
    parser.add_argument("--check-backtop-vs-controller1", action="store_true",
                         help="Sample BACKTOP11 overflow flags (LMO_Y/cmd_overflow2) alongside "
                              "Controller 1/PHY1 TX packet counters sample-for-sample, to tell "
                              "apart a stall upstream of BACKTOP (both go idle together) from a "
                              "stall at/after Controller 1 (BACKTOP backs up while TX stays idle), "
                              "then exit")
    parser.add_argument("--all", action="store_true",
                         help="Run every --check-* table validation and print a consolidated "
                              "PASS/FAIL summary")
    parser.add_argument("--show-config", action="store_true",
                         help="Print a low-level report of every table's current register "
                              "state (what is actually set, independent of pass/fail), then exit")
    parser.add_argument("--samples", type=int, default=5,
                         help="Number of samples to take for --check-mipi-packet-counters, "
                              "--check-video-lock, --check-crc, --stream-check, and other sampled "
                              "checks (default: 5)")
    parser.add_argument("--interval", type=float, default=1.0,
                         help="Seconds between samples for --check-mipi-packet-counters, "
                              "--check-video-lock, --check-crc, --stream-check, and other sampled "
                              "checks (default: 1.0)")
    parser.add_argument("--mipi-freq", choices=sorted(m.DESERIALIZER_MIPI_FREQ_CHOICES, key=int),
                         default=None,
                         help="Override the expected CSI output frequency (Mbps/lane) used by "
                              "--check-mipi-phy-settings/--check-mipi-deskew to match whatever "
                              "--mipi-freq was passed to config_1_max96793_max96792a_init.py, "
                              "without editing either script")
    parser.add_argument("--log-level", default="INFO",
                         choices=["DEBUG", "INFO", "WARNING", "ERROR", "ALL"],
                         help="Logging verbosity (default: INFO)")
    args = parser.parse_args(argv)
    # "ALL" is not a real logging level; DEBUG is the lowest level, so it shows everything
    logging.getLogger().setLevel(logging.DEBUG if args.log_level == "ALL" else args.log_level)

    if args.mipi_freq is not None:
        m.DESERIALIZER_MIPI_OUTPUT_FREQ = m.DESERIALIZER_MIPI_FREQ_CHOICES[args.mipi_freq]

    with SMBus(args.bus) as bus:
        if args.all:
            return 0 if run_all_checks(bus, args.samples, args.interval) else 1
        if args.show_config:
            summarize_configuration(bus)
            return 0
        if args.check_tunnel_mode:
            return 0 if validate_pixel_tunnel_mode_table(bus) else 1
        if args.check_link_init:
            return 0 if validate_link_init_table(bus) else 1
        if args.check_link_operation:
            return 0 if validate_link_operation_table(bus) else 1
        if args.check_video_pipe_sel:
            return 0 if validate_video_pipe_selection_table(bus) else 1
        if args.check_pipe_controller_mapping:
            return 0 if validate_pipe_controller_mapping_table(bus) else 1
        if args.check_mipi_phy_settings:
            return 0 if validate_mipi_phy_settings_table(bus) else 1
        if args.check_mipi_deskew:
            return 0 if validate_mipi_deskew_table(bus) else 1
        if args.check_mipi_packet_counters:
            return 0 if check_mipi_packet_counters(bus, args.samples, args.interval) else 1
        if args.check_video_lock:
            return 0 if check_video_lock(bus, args.samples, args.interval) else 1
        if args.stream_check:
            return 0 if check_stream_check(bus, args.samples, args.interval) else 1
        if args.check_csi_out_en:
            return 0 if check_csi_out_en(bus) else 1
        if args.check_csi_pll_lock:
            return 0 if check_csi_pll_lock(bus, args.samples, args.interval) else 1
        if args.check_eom_result:
            return 0 if check_eom_result(bus, args.samples, args.interval) else 1
        if args.check_link_a_error_flags:
            return 0 if check_link_a_error_flags(bus, args.samples, args.interval) else 1
        if args.check_tunnel_errors:
            return 0 if check_tunnel_errors(bus, args.samples, args.interval) else 1
        if args.check_crc:
            return 0 if check_gmsl_crc(bus, args.samples, args.interval) else 1
        if args.check_sticky_errors:
            return 0 if check_sticky_errors(bus, args.samples, args.interval) else 1
        if args.check_backtop_vs_controller1:
            return 0 if check_backtop_vs_controller1(bus, args.samples, args.interval) else 1
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
