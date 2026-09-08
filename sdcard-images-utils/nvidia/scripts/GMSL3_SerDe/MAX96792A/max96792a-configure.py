#!/usr/bin/env python3
"""Configure the MAX96792A GMSL deserializer over I2C.

This follows the MAX96792A path in Linux's max9296a.c/max_des.c driver.
Serializer setup, sensor setup, and I2C address translation are intentionally
outside this tool.
"""

import argparse
import logging
import time

from smbus2 import SMBus, i2c_msg


LOG = logging.getLogger("max96792a")

# Global reset and link-control registers.
REG_CTRL0 = 0x10
CTRL0_LINK_CFG = 0x03
CTRL0_AUTO_LINK = 1 << 4
CTRL0_RESET_LINK_A = 1 << 6
CTRL0_RESET_ALL = 1 << 7
REG_CTRL3 = 0x13
CTRL3_RESET_LINK_B = 1
REG_DEVICE_ID = 0x0000

# GMSL link-rate and link-mode registers.
REG_LINK_RATE_A = 0x01
REG_LINK_RATE_B = 0x04
LINK_RATE_MASK = 0x03
REG_GMSL2_LINKS = 0x06
REG_GMSL1_ENABLE = 0xF00
GMSL_LINK_ENABLE_MASK = 0x03
GMSL3_LINK_SHIFT = 6
GMSL3_FEC_ENABLE = 1 << 1
GMSL3_RATE = 0x03
GMSL2_6GBPS_RATE = 0x02
GMSL2_3GBPS_RATE = 0x01

# Video-pipe enable and stream-selection registers.
REG_VIDEO_PIPE_ENABLE = 0x160
REG_VIDEO_PIPE_SELECT = 0x161
PIPE_SELECT_MASK = 0x03
PIPE_SELECT_SHIFT = 3
REG_BACKTOP12 = 0x313
REG_MIPI_PHY2 = 0x332
PHY_ACTIVE_MASK = 0x30

# CSI-2 PHY, DPLL, and video-pipe register bases.
REG_MIPI_PHY3 = 0x333
REG_MIPI_PHY5 = 0x335
REG_MIPI_TX10 = 0x40A
REG_MIPI_TX11 = 0x40B
REG_MIPI_TX12 = 0x40C
REG_MIPI_TX13 = 0x40D
REG_MIPI_TX14 = 0x40E
REG_MIPI_TX45 = 0x42D
REG_MIPI_TX51 = 0x433
REG_MIPI_TX52 = 0x434
REG_MIPI_TX0 = 0x028
REG_BACKTOP22 = 0x31D
REG_MIPI_TX3 = 0x403
REG_MIPI_TX4 = 0x404
REG_DPLL0 = 0x1C00

# Register strides and bit masks used by the MAX96792A register map.
REGISTER_STRIDE_PIPE = 0x40
REGISTER_STRIDE_GMSL3 = 0x5000
REGISTER_STRIDE_DPLL = 0x100
REGISTER_STRIDE_PHY = 0x03
CSI_LANE_COUNT_MASK = 0xC0
CSI_PHY_LANE_MAP_MASK = 0xFF
CSI_PHY_POLARITY_MASK = 0x1F
DPLL_RESET_N = 1
DPLL_ENABLE = 1 << 5
PHY_STANDBY_MASK = 0x30
PIPE_TUNNEL_MASK = 0x03
PIPE_PHY_SELECT = 1 << 1
CSI_OUTPUT_ENABLE_MASK = 1 << 1

# Supported MAX96792A resources and CSI-2 frame types.
MAX_LINKS = 2
MAX_PHYS = 2
MAX_PIPES = 2
MAX_CSI_LANES = 4
MAX_VIRTUAL_CHANNEL = 3
CSI_FRAME_START = 0x00
CSI_FRAME_END = 0x01
CSI_REMAP_COUNT = 3

# Default single-camera configuration. Command-line options may override these.
DEFAULT_BUS = 2
DEFAULT_ADDRESS = 0x27
DEFAULT_LINKS = "0"
DEFAULT_VERSION = "gmsl3"
DEFAULT_LANES = 2
DEFAULT_LINK_FREQUENCY = 750_000_000
DEFAULT_DATA_TYPE = 0x2A
DEFAULT_VIRTUAL_CHANNEL = 0


def reg_addr(base, index, stride=0x40):
    return base + index * stride


class Max96792A:
    """Small 16-bit-register, 8-bit-value I2C client."""

    def __init__(self, bus_number, address):
        LOG.debug("Opening I2C bus %d, MAX96792A address 0x%02x", bus_number, address)
        self.bus = SMBus(bus_number)
        self.address = address

    def close(self):
        LOG.debug("Closing I2C bus")
        self.bus.close()

    def read(self, register):
        LOG.debug("I2C read: register=0x%04x", register)
        write = i2c_msg.write(self.address, [register >> 8, register & 0xFF])
        read = i2c_msg.read(self.address, 1)
        self.bus.i2c_rdwr(write, read)
        value = list(read)[0]
        LOG.debug("I2C read result: register=0x%04x value=0x%02x", register, value)
        return value

    def write(self, register, value):
        if not 0 <= value <= 0xFF:
            raise ValueError(f"register value out of range: 0x{value:x}")
        LOG.debug("I2C write: register=0x%04x value=0x%02x", register, value)
        message = i2c_msg.write(
            self.address, [register >> 8, register & 0xFF, value]
        )
        self.bus.i2c_rdwr(message)

    def update(self, register, mask, value):
        current = self.read(register)
        updated = (current & ~mask) | (value & mask)
        LOG.debug(
            "I2C update: register=0x%04x current=0x%02x mask=0x%02x "
            "value=0x%02x result=0x%02x",
            register,
            current,
            mask,
            value,
            updated,
        )
        self.write(register, updated)

    def set_bits(self, register, mask):
        self.update(register, mask, mask)

    def clear_bits(self, register, mask):
        self.update(register, mask, 0)

    def wait_for_device(self):
        LOG.debug("Waiting for MAX96792A to become available")
        for attempt in range(10):
            try:
                device_value = self.read(REG_DEVICE_ID)
                if device_value:
                    LOG.debug("MAX96792A responded with 0x%02x", device_value)
                    return
            except OSError as error:
                LOG.debug("Deserializer read failed: %s", error)
            LOG.info("Waiting for MAX96792A (%d/10)", attempt + 1)
            time.sleep(0.1)
        raise RuntimeError("MAX96792A did not respond")

    def reset(self):
        LOG.debug("Starting MAX96792A global reset")
        self.wait_for_device()
        self.set_bits(REG_CTRL0, CTRL0_RESET_ALL)
        time.sleep(0.1)
        self.wait_for_device()
        LOG.debug("MAX96792A global reset completed")

    def hold_link_reset(self, link_mask):
        """Hold selected link data paths in RESET_LINK during configuration."""
        LOG.debug("Asserting RESET_LINK: mask=0x%02x", link_mask)
        if link_mask & 0x01:
            self.set_bits(REG_CTRL0, CTRL0_RESET_LINK_A)
        if link_mask & 0x02:
            self.set_bits(REG_CTRL3, CTRL3_RESET_LINK_B)

    def release_link_reset(self, link_mask):
        """Release selected RESET_LINK bits and start link acquisition."""
        LOG.debug("Releasing RESET_LINK: mask=0x%02x", link_mask)
        if link_mask & 0x01:
            self.clear_bits(REG_CTRL0, CTRL0_RESET_LINK_A)
        if link_mask & 0x02:
            self.clear_bits(REG_CTRL3, CTRL3_RESET_LINK_B)

    def select_links(self, link_mask):
        if not link_mask:
            raise ValueError("at least one GMSL link must be selected")
        LOG.debug("Selecting GMSL links: mask=0x%02x", link_mask)
        self.update(REG_GMSL1_ENABLE, GMSL_LINK_ENABLE_MASK, link_mask)
        self.update(
            REG_CTRL0,
            CTRL0_AUTO_LINK | CTRL0_LINK_CFG,
            CTRL0_AUTO_LINK | (link_mask & CTRL0_LINK_CFG),
        )
        LOG.debug("GMSL link selection completed")

    def set_link_version(self, link, version):
        if version == "gmsl3":
            rate = GMSL3_RATE
            gmsl3 = True
        elif version == "gmsl2-6g":
            rate = GMSL2_6GBPS_RATE
            gmsl3 = False
        elif version == "gmsl2-3g":
            rate = GMSL2_3GBPS_RATE
            gmsl3 = False
        else:
            raise ValueError(f"unsupported link version: {version}")

        LOG.debug("Configuring link %d for %s, rate field=0x%02x", link, version, rate)
        rate_register = REG_LINK_RATE_A if link == 0 else REG_LINK_RATE_B
        self.update(rate_register, LINK_RATE_MASK, rate)
        tx_index = link
        if gmsl3:
            self.set_bits(reg_addr(REG_MIPI_TX0, tx_index, REGISTER_STRIDE_GMSL3), GMSL3_FEC_ENABLE)
            self.clear_bits(REG_GMSL2_LINKS, 1 << (GMSL3_LINK_SHIFT + tx_index))
            self.set_bits(REG_LINK_RATE_B, 1 << (GMSL3_LINK_SHIFT + tx_index))
        else:
            self.clear_bits(reg_addr(REG_MIPI_TX0, tx_index, REGISTER_STRIDE_GMSL3), GMSL3_FEC_ENABLE)
            self.set_bits(REG_GMSL2_LINKS, 1 << (GMSL3_LINK_SHIFT + tx_index))
            self.clear_bits(REG_LINK_RATE_B, 1 << (GMSL3_LINK_SHIFT + tx_index))

    def init_phy(self, phy, lanes, link_frequency):
        if not 1 <= lanes <= MAX_CSI_LANES:
            raise ValueError(f"CSI-2 lane count must be between 1 and {MAX_CSI_LANES}")
        hardware_phy = phy + 1
        dpll_frequency = link_frequency * 2
        LOG.debug(
            "Initializing PHY %d: hardware_phy=%d lanes=%d link_frequency=%d "
            "dpll_frequency=%d",
            phy,
            hardware_phy,
            lanes,
            link_frequency,
            dpll_frequency,
        )
        self.update(
            reg_addr(REG_MIPI_TX10, hardware_phy),
            CSI_LANE_COUNT_MASK,
            (lanes - 1) << 6,
        )

        lane_map = sum(index << (index * 2) for index in range(MAX_CSI_LANES))
        self.write(REG_MIPI_PHY3 + phy, lane_map & CSI_PHY_LANE_MAP_MASK)
        self.clear_bits(REG_MIPI_PHY5 + phy, CSI_PHY_POLARITY_MASK)
        self.clear_bits(reg_addr(REG_DPLL0, hardware_phy, REGISTER_STRIDE_DPLL), DPLL_RESET_N)
        self.update(
            REG_BACKTOP22 + hardware_phy * REGISTER_STRIDE_PHY,
            0x1F,
            dpll_frequency // 100_000_000,
        )
        self.set_bits(REG_BACKTOP22 + hardware_phy * REGISTER_STRIDE_PHY, DPLL_ENABLE)
        self.set_bits(reg_addr(REG_DPLL0, hardware_phy, REGISTER_STRIDE_DPLL), DPLL_RESET_N)

        deskew = 0x81 if dpll_frequency > 1_500_000_000 else 0
        self.write(REG_MIPI_TX3 + hardware_phy * REGISTER_STRIDE_PIPE, deskew)
        self.write(REG_MIPI_TX4 + hardware_phy * REGISTER_STRIDE_PIPE, deskew)
        LOG.debug("PHY %d initialization completed, deskew=0x%02x", phy, deskew)

    def set_phy_active(self, phy, active):
        mask = PHY_STANDBY_MASK << (phy * 2)
        LOG.debug("Setting PHY %d active=%s", phy, active)
        self.update(REG_MIPI_PHY2, mask, mask if active else 0)

    def configure_pipe(self, pipe, phy, stream_id, data_type, virtual_channel):
        hardware_pipe = pipe + 1
        LOG.debug(
            "Configuring pipe %d: hardware_pipe=%d phy=%d stream_id=%d "
            "data_type=0x%02x virtual_channel=%d",
            pipe,
            hardware_pipe,
            phy,
            stream_id,
            data_type,
            virtual_channel,
        )
        self.clear_bits(REG_VIDEO_PIPE_ENABLE, 1 << pipe)
        self.clear_bits(reg_addr(REG_MIPI_TX52, hardware_pipe, REGISTER_STRIDE_PIPE), PIPE_TUNNEL_MASK)
        self.update(
            REG_VIDEO_PIPE_SELECT,
            PIPE_SELECT_MASK << (pipe * PIPE_SELECT_SHIFT),
            stream_id << (pipe * PIPE_SELECT_SHIFT),
        )

        remaps = [
            (data_type, virtual_channel),
            (CSI_FRAME_START, virtual_channel),
            (CSI_FRAME_END, virtual_channel),
        ]
        for remap_index, (source_dt, source_vc) in enumerate(remaps[:CSI_REMAP_COUNT]):
            source = source_dt | (source_vc << 6)
            self.write(
                REG_MIPI_TX13 + hardware_pipe * REGISTER_STRIDE_PIPE + remap_index * 2,
                source,
            )
            self.write(
                REG_MIPI_TX14 + hardware_pipe * REGISTER_STRIDE_PIPE + remap_index * 2,
                source,
            )
            destination = (phy + 1) << (2 * (remap_index % 4))
            self.update(
                REG_MIPI_TX45 + hardware_pipe * REGISTER_STRIDE_PIPE + remap_index // 4,
                0x03 << (2 * (remap_index % 4)),
                destination,
            )
        self.write(REG_MIPI_TX11 + hardware_pipe * REGISTER_STRIDE_PIPE, (1 << CSI_REMAP_COUNT) - 1)
        self.write(REG_MIPI_TX12 + hardware_pipe * REGISTER_STRIDE_PIPE, 0)

        self.update(
            reg_addr(REG_MIPI_TX52, hardware_pipe, REGISTER_STRIDE_PIPE),
            PIPE_PHY_SELECT,
            (phy & 1) << 1,
        )
        self.set_bits(REG_VIDEO_PIPE_ENABLE, 1 << pipe)
        LOG.debug("Pipe %d configuration completed", pipe)

    def enable_output(self):
        LOG.debug("Enabling CSI-2 output")
        self.set_bits(REG_BACKTOP12, CSI_OUTPUT_ENABLE_MASK)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bus", type=int, default=DEFAULT_BUS, help="I2C bus number")
    parser.add_argument(
        "--address", type=lambda value: int(value, 0), default=DEFAULT_ADDRESS
    )
    parser.add_argument(
        "--links",
        default=DEFAULT_LINKS,
        help="comma-separated active links, each 0 or 1 (default: 0)",
    )
    parser.add_argument(
        "--version",
        choices=("gmsl2-3g", "gmsl2-6g", "gmsl3"),
        default=DEFAULT_VERSION,
    )
    parser.add_argument(
        "--lanes", type=int, default=DEFAULT_LANES, help="CSI-2 lanes per PHY"
    )
    parser.add_argument(
        "--link-frequency",
        type=int,
        default=DEFAULT_LINK_FREQUENCY,
        help="CSI-2 link frequency in Hz",
    )
    parser.add_argument(
        "--data-type", type=lambda value: int(value, 0), default=DEFAULT_DATA_TYPE
    )
    parser.add_argument(
        "--virtual-channel", type=int, default=DEFAULT_VIRTUAL_CHANNEL
    )
    return parser.parse_args()


def main():
    args = parse_args()
    links = [int(value) for value in args.links.split(",") if value != ""]
    if sorted(set(links)) != links or any(link not in (0, 1) for link in links):
        raise ValueError("--links must contain unique values from 0 and 1")
    if not 0 <= args.data_type <= 0x3F:
        raise ValueError("--data-type must be a CSI-2 data type from 0 to 0x3f")
    if not 0 <= args.virtual_channel <= MAX_VIRTUAL_CHANNEL:
        raise ValueError(f"--virtual-channel must be between 0 and {MAX_VIRTUAL_CHANNEL}")

    LOG.debug(
        "Configuration: bus=%d address=0x%02x links=%s version=%s lanes=%d "
        "link_frequency=%d data_type=0x%02x virtual_channel=%d",
        args.bus,
        args.address,
        links,
        args.version,
        args.lanes,
        args.link_frequency,
        args.data_type,
        args.virtual_channel,
    )

    deserializer = Max96792A(args.bus, args.address)
    try:
        link_mask = sum(1 << link for link in links)
        LOG.debug("Calculated active-link mask: 0x%02x", link_mask)
        deserializer.reset()
        deserializer.hold_link_reset(link_mask)
        for link in links:
            deserializer.set_link_version(link, args.version)
        deserializer.select_links(link_mask)
        deserializer.clear_bits(REG_BACKTOP12, CSI_OUTPUT_ENABLE_MASK)

        for phy in range(len(links)):
            deserializer.init_phy(phy, args.lanes, args.link_frequency)
            deserializer.set_phy_active(phy, False)

        for pipe, link in enumerate(links):
            deserializer.configure_pipe(
                pipe,
                pipe,
                link,
                args.data_type,
                args.virtual_channel,
            )

        for phy in range(len(links)):
            deserializer.set_phy_active(phy, True)
        deserializer.release_link_reset(link_mask)
        deserializer.enable_output()
        LOG.debug("All MAX96792A configuration stages completed")
        LOG.info("MAX96792A configuration completed")
    finally:
        deserializer.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    main()