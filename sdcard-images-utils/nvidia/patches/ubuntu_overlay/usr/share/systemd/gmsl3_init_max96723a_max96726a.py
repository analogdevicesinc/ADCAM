"""GMSL2/3 link + MIPI CSI-2 tunnel-mode init for MAX96723A (serializer) /
MAX96726A (deserializer).

Board: MAX96723A serializer (dual camera input, Port A/ToF + Port B/RGB) /
MAX96726A deserializer (Port A/ToF -> Jetson J21, Port B/RGB -> Jetson J20).
"""
import argparse
import sys
import time
import logging
from typing import List, Optional, Sequence, Tuple

from smbus2 import SMBus, i2c_msg

SCRIPT_VERSION = "2026-11-24.9"

logger = logging.getLogger(__name__)


class GmslConfigError(RuntimeError):
    """Raised when an I2C transaction to the serializer/deserializer fails."""

SERIALIZER_ADDR_CANDIDATES = [0x40, 0x41]

DESERIALIZER_ADDR = 0x33

DESERIALIZER_DEV_ID13_REG = [0x00, 0x0D]
DESERIALIZER_DEV_ID16_BYTE0_REG = [0x00, 0x0E]
DESERIALIZER_DEV_ID16_BYTE1_REG = [0x00, 0x0F]

SERIALIZER_DEV_ID_REG = [0x00, 0x0D]
SERIALIZER_REV_ID_REG = [0x00, 0x0E]

DESERIALIZER_REG16 = [0x00, 0x10]
DESERIALIZER_REG16_RX_RATE_12GBPS_GMSL3 = 0xC0
DESERIALIZER_REG16_RX_RATE_MASK = 0xC0

DESERIALIZER_REG7 = [0x00, 0x07]
DESERIALIZER_REG7_GMSL3_D_BIT = 0x80
DESERIALIZER_REG7_LINK_EN_D_BIT = 0x08
DESERIALIZER_REG7_LINK_ABC_BITS = 0x70 | 0x07

DESERIALIZER_FEC_MODE_D_REG = [0x11, 0x10]
DESERIALIZER_FEC_MODE_D_RX_FEC_EN_VALUE = 0x07

DESERIALIZER_CTRL1_REG = [0x00, 0x1E]
DESERIALIZER_CTRL1_RESET_ONESHOT_D_BIT = 0x08

DESERIALIZER_BACKTOP4_REG = [0x04, 0x04]
DESERIALIZER_CSI_OUT_EN_BIT = 0x08

DESERIALIZER_DEC_EN_REG = [0x00, 0x29]
DESERIALIZER_DEC_EN_DISABLE_VALUE = 0x00

DESERIALIZER_HEARTBEAT_TIMEOUT_REG = [0x01, 0xE0]
DESERIALIZER_HEARTBEAT_TIMEOUT_MAX = 0xFF

DESERIALIZER_PIPE0_CONFIG_0_REG = [0x04, 0x20]
DESERIALIZER_CONFIG_0_CON_DEST_MASK = 0x03
DESERIALIZER_CONFIG_0_CON_DEST_CONTROLLER2 = 0x02

DESERIALIZER_CONFIG_0_DPHY_MODE_BIT = 0x40

DESERIALIZER_VC_CTRL_PIPE0_REG = [0x04, 0x26]
DESERIALIZER_VC_CTRL_OVERRIDE_ENABLE_VALUE = 0x20
DESERIALIZER_SRC_VC_PIPE0_REG = [0x04, 0x27]
DESERIALIZER_DST_VC_PIPE0_REG = [0x04, 0x28]
DESERIALIZER_VC0_VALUE = 0x00

DESERIALIZER_VIDEO_PIPE_SEL_0_REG = [0x00, 0xF0]
DESERIALIZER_VIDEO_PIPE_SEL_0_MASK = 0x0F
DESERIALIZER_VIDEO_PIPE_SEL_0_LINKD_STREAM0 = 0x0C

DESERIALIZER_VIDEO_PIPE_EN_REG = [0x00, 0xF4]
DESERIALIZER_VIDEO_PIPE_EN_PIPE0_BIT = 0x01

DESERIALIZER_VIDEO_RX0_PIPE0_REG = [0x01, 0x00]
DESERIALIZER_VIDEO_RX0_PIPE1_REG = [0x01, 0x1C]
DESERIALIZER_VIDEO_RX0_SEQ_MISS_EN_BIT = 0x10

DESERIALIZER_LIM_HEART_REG = [0x01, 0xDF]
DESERIALIZER_LIM_HEART_PIPE0_BIT = 0x01
DESERIALIZER_LIM_HEART_PIPE1_BIT = 0x02

DESERIALIZER_MIPI_PHY0_REG = [0x08, 0xB0]
DESERIALIZER_MIPI_PHY0_PHY1_EN_BIT = 0x02
DESERIALIZER_MIPI_PHY0_PHY2_EN_BIT = 0x04

DESERIALIZER_MIPI_TX10_REG = [0x0A, 0x46]
DESERIALIZER_MIPI_TX10_2LANE_DPHY = 0x40

DESERIALIZER_DESKEW_INIT_REG = [0x0A, 0x42]
DESERIALIZER_DESKEW_PER_REG = [0x0A, 0x43]
DESERIALIZER_DESKEW_ENABLE_BIT = 0x80
DESERIALIZER_DESKEW_WIDTH_WIDEST = 0x07
DESERIALIZER_DESKEW_AUTO_ENABLE_WIDEST = DESERIALIZER_DESKEW_ENABLE_BIT | DESERIALIZER_DESKEW_WIDTH_WIDEST
DESERIALIZER_DESKEW_DISABLE = 0x00

DESERIALIZER_DESKEW_PERIOD_CHOICES = {
    "1": 0b000, "2": 0b001, "4": 0b010, "8": 0b011,
    "16": 0b100, "32": 0b101, "64": 0b110, "128": 0b111,
}

DESERIALIZER_DESKEW_PERIODIC_ENABLED = False
DESERIALIZER_DESKEW_PERIOD_BITS = DESERIALIZER_DESKEW_PERIOD_CHOICES["1"]

DESERIALIZER_DPLL0_REG = [0x1E, 0x00]
DESERIALIZER_DPLL0_SOFT_RESET_ASSERT = 0xF4
DESERIALIZER_DPLL0_SOFT_RESET_RELEASE = 0xF5

DESERIALIZER_MIPI_FREQ_REG = [0x09, 0x92]
DESERIALIZER_MIPI_FREQ_PREDEF_EN_BIT = 0x80
DESERIALIZER_MIPI_FREQ_800MBPS = 0x08
DESERIALIZER_MIPI_FREQ_1000MBPS = 0x0A
DESERIALIZER_MIPI_FREQ_1500MBPS = 0x0F
DESERIALIZER_MIPI_FREQ_2000MBPS = 0x14
DESERIALIZER_MIPI_FREQ_2500MBPS = 0x19

DESERIALIZER_MIPI_FREQ_MBPS = {
    DESERIALIZER_MIPI_FREQ_800MBPS: 800,
    DESERIALIZER_MIPI_FREQ_1000MBPS: 1000,
    DESERIALIZER_MIPI_FREQ_1500MBPS: 1500,
    DESERIALIZER_MIPI_FREQ_2000MBPS: 2000,
    DESERIALIZER_MIPI_FREQ_2500MBPS: 2500,
}

DESERIALIZER_MIPI_OUTPUT_FREQ = DESERIALIZER_MIPI_FREQ_1000MBPS

DESERIALIZER_MIPI_FREQ_CHOICES = {
    "800": DESERIALIZER_MIPI_FREQ_800MBPS,
    "1000": DESERIALIZER_MIPI_FREQ_1000MBPS,
    "1500": DESERIALIZER_MIPI_FREQ_1500MBPS,
    "2000": DESERIALIZER_MIPI_FREQ_2000MBPS,
    "2500": DESERIALIZER_MIPI_FREQ_2500MBPS,
}

DESERIALIZER_MIPI_TX54_REG = [0x0A, 0x59]
DESERIALIZER_MIPI_TX54_DESKEW_TUN_SRC_PIPE0 = 0x00

DESERIALIZER_CTRL3_REG = [0x00, 0x20]
DESERIALIZER_CTRL3_LOCK_PIN_BIT = 0x01

DESERIALIZER_GPIO_TUNNEL_BASE = 0x0200
DESERIALIZER_GPIO_TUNNEL_BLOCK_SIZE = 8
DESERIALIZER_GPIOX_2_OUT_DIS_BIT = 0x04
DESERIALIZER_GPIOD_0_TX_EN_BIT = 0x02
DESERIALIZER_GPIOD_0_RX_EN_BIT = 0x01
DESERIALIZER_GPIOD_0_TXRX_ID_SHIFT = 2
DESERIALIZER_GPIOD_0_TXRX_ID_MASK = 0x7C
MFP9_CHANNEL_ID = 0
MFP10_CHANNEL_ID = 1
MFP6_CHANNEL_ID = 2

DESERIALIZER_GPIO_PIN_TABLE = {
    0: ("GMSL_SPI_MOSI", None),
    1: ("GMSL_IMU_DRDY", None),
    2: ("NA", None),
    3: ("GMSL_LINK_LOCK", None),
    4: ("GMSL_FSYNC", "OUTPUT"),
    5: ("NA", None),
    6: ("GMSL_CAM_FAULT", "INPUT"),
    7: ("GMSL_ERRB", None),
    8: ("GMSL_SPI_CS0", None),
    9: ("GMSL_MFP9", "OUTPUT"),
    10: ("GMSL_MFP10", "OUTPUT"),
    14: ("GMSL_SPI_SCK", None),
    15: ("GMSL_SPI_MISO", None),
}

DESERIALIZER_VIDEO_PIPE_SEL_1_MASK = 0xF0
DESERIALIZER_VIDEO_PIPE_SEL_1_LINKD_STREAM1 = 0xD0

DESERIALIZER_VIDEO_PIPE_EN_PIPE1_BIT = 0x02

DESERIALIZER_PIPE1_CONFIG_0_REG = [0x04, 0x38]
DESERIALIZER_CONFIG_0_CON_DEST_CONTROLLER1 = 0x01

DESERIALIZER_VC_CTRL_PIPE1_REG = [0x04, 0x3E]
DESERIALIZER_VC_OVERRIDE_MODE_MASK = 0xE0

DESERIALIZER_MIPI_TX10_CTRL1_REG = [0x0A, 0x06]

DESERIALIZER_DESKEW_INIT_CTRL1_REG = [0x0A, 0x02]
DESERIALIZER_DESKEW_PER_CTRL1_REG = [0x0A, 0x03]

DESERIALIZER_DPLL0_CTRL1_REG = [0x1D, 0x00]

DESERIALIZER_MIPI_FREQ_CTRL1_REG = [0x09, 0x8F]

DESERIALIZER_MIPI_OUTPUT_FREQ_RGB = DESERIALIZER_MIPI_FREQ_1000MBPS

DESERIALIZER_MIPI_TX54_CTRL1_REG = [0x0A, 0x19]
DESERIALIZER_MIPI_TX54_DESKEW_TUN_SRC_PIPE1 = 0x01

SERIALIZER_MIPI_RX0_REG = [0xA0, 0x05]
SERIALIZER_MIPI_RX0_DESKEW_EN_BIT = 0x80
SERIALIZER_MIPI_RX0_LANE_COUNT_MASK = 0x60
SERIALIZER_MIPI_RX0_LANE_COUNT_2LANE = 0x20
SERIALIZER_MIPI_DESKEW_REQUIRED_THRESHOLD_MBPS = 1500

SERIALIZER_MIPI_INPUT_DESKEW_ENABLED = False

SERIALIZER_MIPI_RX0_CTRL1_REG = [0xA4, 0x05]
SERIALIZER_MIPI_INPUT_DESKEW_ENABLED_RGB = False

SERIALIZER_VIDEO_TX_REG = [0x20, 0x03]
SERIALIZER_VIDEO_TX_CTRL1_REG = [0x21, 0x03]
SERIALIZER_VIDEO_TX_LIMITED_HEARTBEAT_BIT = 0x04

SERIALIZER_CC_CTRL_REG = [0x00, 0x01]
SERIALIZER_CC_CTRL_I2C_PT_ENA_BIT = 0x04

SERIALIZER_STATUS_REG = [0x00, 0x13]
SERIALIZER_STATUS_LOCKED_BIT = 0x08

SERIALIZER_GPIO_CFG0_BASE = 0x302B
SERIALIZER_GPIO_RXID_BASE = 0x302D
SERIALIZER_GPIO_TXID_BASE = 0x302E
SERIALIZER_GPIO_TUNNEL_STRIDE = 0x0A
SERIALIZER_GPIO_CFG0_OUT_DIS_BIT = 0x01
SERIALIZER_GPIO_CFG0_TX_EN_BIT = 0x02
SERIALIZER_GPIO_CFG0_RX_EN_BIT = 0x04
SERIALIZER_GPIO_CFG0_OUT_BIT = 0x08
SERIALIZER_GPIO_CFG0_OUT_TYPE_PUSH_PULL_BIT = 0x10
SERIALIZER_GPIO_ID_MASK = 0x1F

# Empirically required on hardware for GPIO0 to drive out a measurable 1.8V level.
SERIALIZER_REG1_REG = [0x01, 0x01]
SERIALIZER_REG1_GPIO0_DRIVE_ENABLE_VALUE = 0x90

SERIALIZER_GPIO_PIN_TABLE = {
    0: ("GMSL_RGBISP_RST", "OUTPUT"),
    1: ("GMSL_TOFISP_RST_L", "OUTPUT"),
    2: ("TOFISP_GMSL_INTERRUPT", "INPUT"),
    3: ("Using RoR", None),
    4: ("GMSL_EN_RGB", "OUTPUT"),
    5: ("GMSL_EN_TOF", "OUTPUT"),
    6: ("GMSL_IMU_RESET_L", "OUTPUT"),

    7: ("GMSL_TOF_FSYNC", "HIZ"),
    8: ("GMSL_RGB_FSYNC", "HIZ"),
    9: ("IMU_GMSL_DATA_RDY", None),

    10: ("GMSL_RUN_VAUX", "OUTPUT"),
    11: ("GMSL_STATUS_LED_EN", "OUTPUT"),

    12: ("GMSL_SPI_SCLK", None),
    13: ("GMSL_SPI_MOSI", None),
    14: ("GMSL_SPI_MISO", None),
    15: ("GMSL_SPI_IMU_CSB", None),
    16: ("IMU_GMSL_NOK", None),
    17: ("GMSL_EN_TOFISP", "OUTPUT"),
    18: ("GMSL_EN_RGBISP", "OUTPUT"),
    19: ("GMSL_TOFISP_BS0", "OUTPUT"),
    20: ("GMSL_IMU_FSYNC", "HIZ"),
}

FSYNC_TARGETS = ("GMSL_TOF_FSYNC", "GMSL_RGB_FSYNC", "GMSL_IMU_FSYNC")

GPIO_HIGH = 1
GPIO_LOW = 0

GPIO_TUNNEL_HOST_TO_SENSOR = "HOST_TO_SENSOR"
GPIO_TUNNEL_SENSOR_TO_HOST = "SENSOR_TO_HOST"

GPIO_TUNNELS = {
    "mfp0": ("GMSL_MFP9", "GMSL_RGBISP_RST", MFP9_CHANNEL_ID, GPIO_TUNNEL_HOST_TO_SENSOR),
    "mfp1": ("GMSL_MFP10", "GMSL_TOFISP_RST_L", MFP10_CHANNEL_ID, GPIO_TUNNEL_HOST_TO_SENSOR),
    "mfp2": ("GMSL_CAM_FAULT", "TOFISP_GMSL_INTERRUPT", MFP6_CHANNEL_ID, GPIO_TUNNEL_SENSOR_TO_HOST),
}

SERIALIZER_GPIO_TUNNEL_DRIVEN_NAMES = frozenset(
    ser_pin for _deser_mfp, ser_pin, _channel_id, _direction in GPIO_TUNNELS.values())

SERIALIZER_GPIO_RESERVED_NAMES = frozenset(
    {"GMSL_SPI_SCLK", "GMSL_SPI_MOSI", "GMSL_SPI_MISO", "GMSL_SPI_IMU_CSB"})


def _i2c_write(bus: SMBus, addr: int, payload: Sequence[int], description: str = "") -> None:
    """Write `payload` to `addr` and log `description`; raises GmslConfigError on failure."""
    try:
        bus.i2c_rdwr(i2c_msg.write(addr, list(payload)))
    except OSError as exc:
        raise GmslConfigError(
            "I2C write to 0x{:02X} {} failed: {}".format(addr, list(payload), exc)) from exc
    if description:
        logger.info(description)


def _i2c_read_byte(bus: SMBus, addr: int, reg_addr: Sequence[int]) -> int:
    """Read a single byte from `reg_addr` at `addr`."""
    read = i2c_msg.read(addr, 1)
    try:
        bus.i2c_rdwr(i2c_msg.write(addr, list(reg_addr)), read)
    except OSError as exc:
        raise GmslConfigError(
            "I2C read from 0x{:02X} reg {} failed: {}".format(addr, list(reg_addr), exc)) from exc
    return list(read)[0]


def _read_deserializer_reg(bus: SMBus, reg_addr: Sequence[int]) -> int:
    return _i2c_read_byte(bus, DESERIALIZER_ADDR, reg_addr)


def _read_serializer_reg(bus: SMBus, serializer_addr: int, reg_addr: Sequence[int]) -> int:
    return _i2c_read_byte(bus, serializer_addr, reg_addr)


def _deserializer_gpio_tunnel_regs(mfp_pin: int) -> Tuple[List[int], List[int], List[int]]:
    """Return (GPIOx_2, GPIOx_1, GPIOD_0) register addresses for MFP pin `mfp_pin`."""
    base = DESERIALIZER_GPIO_TUNNEL_BASE + DESERIALIZER_GPIO_TUNNEL_BLOCK_SIZE * mfp_pin
    return [base >> 8, base & 0xFF], [(base + 1) >> 8, (base + 1) & 0xFF], [(base + 5) >> 8, (base + 5) & 0xFF]


def _deserializer_mfp_pin_by_name(name: str) -> int:
    """Look up a DESERIALIZER_GPIO_PIN_TABLE pin number by its board signal name."""
    for pin, (signal_name, _direction) in DESERIALIZER_GPIO_PIN_TABLE.items():
        if signal_name == name:
            return pin
    raise GmslConfigError(
        "Unknown deserializer GPIO pin name '{}' - not found in DESERIALIZER_GPIO_PIN_TABLE".format(name))


def _resolve_deserializer_mfp(mfp) -> int:
    """Accept either a deserializer MFP pin number or its board signal name (e.g. "GMSL_MFP9")."""
    return _deserializer_mfp_pin_by_name(mfp) if isinstance(mfp, str) else mfp


def _serializer_gpio_cfg0_reg(pin: int) -> List[int]:
    """Return the GPIO_CFG0_<pin> register address."""
    cfg0 = SERIALIZER_GPIO_CFG0_BASE + SERIALIZER_GPIO_TUNNEL_STRIDE * pin
    return [cfg0 >> 8, cfg0 & 0xFF]


def _serializer_gpio_pin_by_name(name: str) -> int:
    """Look up a SERIALIZER_GPIO_PIN_TABLE pin number by its board signal name."""
    for pin, (signal_name, _direction) in SERIALIZER_GPIO_PIN_TABLE.items():
        if signal_name == name:
            return pin
    raise GmslConfigError(
        "Unknown serializer GPIO signal name '{}' - not found in SERIALIZER_GPIO_PIN_TABLE".format(name))


def _serializer_gpio_tunnel_regs(mfp_pin: int) -> Tuple[List[int], List[int], List[int]]:
    """Return (GPIO_CFG0_<n>, GPIO_RXID_<n>, GPIO_TXID_<n>) register addresses for MFP pin `mfp_pin`."""
    offset = SERIALIZER_GPIO_TUNNEL_STRIDE * mfp_pin
    cfg0 = SERIALIZER_GPIO_CFG0_BASE + offset
    rxid = SERIALIZER_GPIO_RXID_BASE + offset
    txid = SERIALIZER_GPIO_TXID_BASE + offset
    return [cfg0 >> 8, cfg0 & 0xFF], [rxid >> 8, rxid & 0xFF], [txid >> 8, txid & 0xFF]


def _resolve_serializer_pin(pin) -> int:
    """Accept either a serializer GPIO pin number or its board signal name (e.g. "GMSL_RGBISP_RST")."""
    return _serializer_gpio_pin_by_name(pin) if isinstance(pin, str) else pin


def _detect_serializer_addr(bus: SMBus, candidates: Sequence[int]) -> int:
    for addr in candidates:
        try:
            bus.write_byte_data(addr, 0x0, 0x0)
        except OSError:
            continue
        return addr
    raise GmslConfigError("Serializer not responding on addresses {}".format(
        ", ".join(hex(a) for a in candidates)))


def read_deserializer_revision(bus: SMBus) -> int:
    """Read MAX96726A DEV_ID16_BYTE_0/1 and return the combined 16-bit device ID."""
    logger.info(">>> read_deserializer_revision()")
    reg13 = _read_deserializer_reg(bus, DESERIALIZER_DEV_ID13_REG)
    byte0 = _read_deserializer_reg(bus, DESERIALIZER_DEV_ID16_BYTE0_REG)
    byte1 = _read_deserializer_reg(bus, DESERIALIZER_DEV_ID16_BYTE1_REG)
    dev_id16 = (byte1 << 8) | byte0
    logger.info("Deserializer REG13: 0x%X (expected 0xFF, not used for ID) | DEV_ID16: 0x%04X",
                 reg13, dev_id16)
    return dev_id16


def read_serializer_revision(bus: SMBus, serializer_addr: int) -> Tuple[int, int]:
    """Read serializer REG13/REG14 and return (DEV_ID[7:0], DEV_REV[3:0])."""
    logger.info(">>> read_serializer_revision()")
    dev_id = _read_serializer_reg(bus, serializer_addr, SERIALIZER_DEV_ID_REG)
    if dev_id == 0xFF:
        time.sleep(0.001)
        dev_id = _read_serializer_reg(bus, serializer_addr, SERIALIZER_DEV_ID_REG)
    rev_id = _read_serializer_reg(bus, serializer_addr, SERIALIZER_REV_ID_REG) & 0x0F
    logger.info("Serializer REG13 DEV_ID: 0x%X | REG14 DEV_REV: 0x%X", dev_id, rev_id)
    return dev_id, rev_id


def read_serializer_link_status(bus: SMBus, serializer_addr: int) -> bool:
    """Read the serializer's STATUS register and return the LOCKED bit."""
    logger.info(">>> read_serializer_link_status()")
    status = _read_serializer_reg(bus, serializer_addr, SERIALIZER_STATUS_REG)
    locked = bool(status & SERIALIZER_STATUS_LOCKED_BIT)
    logger.info("Serializer STATUS: LOCKED=%s", locked)
    return locked


def read_deserializer_link_status(bus: SMBus) -> Tuple[bool, int, bool]:
    """Read back MAX96726A REG7/REG16/CTRL3 to confirm Link D is running GMSL3 and locked."""
    logger.info(">>> read_deserializer_link_status()")
    reg7 = _read_deserializer_reg(bus, DESERIALIZER_REG7)
    gmsl3_d = bool(reg7 & DESERIALIZER_REG7_GMSL3_D_BIT)
    reg16 = _read_deserializer_reg(bus, DESERIALIZER_REG16)
    rx_rate = (reg16 & DESERIALIZER_REG16_RX_RATE_MASK) >> 6
    ctrl3 = _read_deserializer_reg(bus, DESERIALIZER_CTRL3_REG)
    locked = bool(ctrl3 & DESERIALIZER_CTRL3_LOCK_PIN_BIT)
    logger.info(
        "Deserializer Link D: GMSL3_D=%s RX_RATE=0b%02s (%s) LOCK_PIN=%s",
        gmsl3_d, bin(rx_rate)[2:].zfill(2),
        "12Gbps/GMSL3" if rx_rate == 0x3 else "not GMSL3 rate",
        locked)
    return gmsl3_d, rx_rate, locked


def read_serializer_i2c_passthrough(bus: SMBus, serializer_addr: int) -> bool:
    """Read CC_CTRL and return the I2C_PT_ENA pass-through channel state."""
    logger.info(">>> read_serializer_i2c_passthrough()")
    cc_ctrl = _read_serializer_reg(bus, serializer_addr, SERIALIZER_CC_CTRL_REG)
    i2c_pt_ena = bool(cc_ctrl & SERIALIZER_CC_CTRL_I2C_PT_ENA_BIT)
    logger.info("Serializer CC_CTRL: I2C_PT_ENA=%s", i2c_pt_ena)
    return i2c_pt_ena


def enable_serializer_i2c_passthrough(bus: SMBus, serializer_addr: int, enable: bool = True) -> int:
    """Set/clear CC_CTRL I2C_PT_ENA (the single pass-through I2C channel)."""
    logger.info(">>> enable_serializer_i2c_passthrough()")

    cc_ctrl = _read_serializer_reg(bus, serializer_addr, SERIALIZER_CC_CTRL_REG)
    new_cc_ctrl = (cc_ctrl | SERIALIZER_CC_CTRL_I2C_PT_ENA_BIT) if enable else (
        cc_ctrl & ~SERIALIZER_CC_CTRL_I2C_PT_ENA_BIT)
    _i2c_write(bus, serializer_addr, SERIALIZER_CC_CTRL_REG + [new_cc_ctrl])
    logger.info("Serializer CC_CTRL I2C_PT_ENA set to %s (CC_CTRL=0x%X)", enable, new_cc_ctrl)
    return new_cc_ctrl


def configure_gpio_tunnel(bus: SMBus, serializer_addr: int, deser_mfp, ser_mfp,
                           channel_id: int, direction: str = GPIO_TUNNEL_HOST_TO_SENSOR) -> None:
    """Configure one GPIO tunnel between deserializer MFP `deser_mfp` and serializer MFP
    `ser_mfp` - single generic function replacing the old per-pin
    configure_mfp0_gpio_tunnel()/configure_mfp1_gpio_tunnel()/configure_mfp2_gpio_tunnel();
    call directly with whichever MFP pins a new tunnel needs."""
    deser_mfp = _resolve_deserializer_mfp(deser_mfp)
    ser_mfp = _resolve_serializer_pin(ser_mfp)
    gpiox_2_reg, _gpiox_1_reg, gpiod_0_reg = _deserializer_gpio_tunnel_regs(deser_mfp)
    gpiox_2 = _read_deserializer_reg(bus, gpiox_2_reg)
    gpiox_2 |= DESERIALIZER_GPIOX_2_OUT_DIS_BIT
    _i2c_write(bus, DESERIALIZER_ADDR, gpiox_2_reg + [gpiox_2],
               "\tGPIO{0}_2 (deserializer MFP{0}) | GPIO_OUT_DIS: tri-stated".format(deser_mfp))

    gpiod_0 = _read_deserializer_reg(bus, gpiod_0_reg)
    gpiod_0 = (gpiod_0 & ~DESERIALIZER_GPIOD_0_TXRX_ID_MASK) | (channel_id << DESERIALIZER_GPIOD_0_TXRX_ID_SHIFT)
    cfg0_reg, rxid_reg, txid_reg = _serializer_gpio_tunnel_regs(ser_mfp)
    cfg0 = _read_serializer_reg(bus, serializer_addr, cfg0_reg)

    if direction == GPIO_TUNNEL_HOST_TO_SENSOR:
        gpiod_0 |= DESERIALIZER_GPIOD_0_TX_EN_BIT
        gpiod_0 &= ~DESERIALIZER_GPIOD_0_RX_EN_BIT
        _i2c_write(bus, DESERIALIZER_ADDR, gpiod_0_reg + [gpiod_0],
                   "\tGPIOD_0 (deserializer MFP{}) | GPIO_TX_EN_D=1, GPIO_RX_EN_D=0, GPIO_TXRX_ID_D={}".format(
                       deser_mfp, channel_id))

        cfg0 |= SERIALIZER_GPIO_CFG0_RX_EN_BIT
        cfg0 &= ~(SERIALIZER_GPIO_CFG0_TX_EN_BIT | SERIALIZER_GPIO_CFG0_OUT_DIS_BIT)
        _i2c_write(bus, serializer_addr, cfg0_reg + [cfg0],
                   "\tGPIO_CFG0_{} (serializer MFP{}) | RX_EN=1, TX_EN=0, OUT_DIS=0".format(ser_mfp, ser_mfp))
        if ser_mfp == 0:
            _i2c_write(bus, serializer_addr, SERIALIZER_REG1_REG + [SERIALIZER_REG1_GPIO0_DRIVE_ENABLE_VALUE],
                       "\tREG1 | GPIO0 drive enable: required for GPIO0 to reach 1.8V")

        id_reg, id_name = rxid_reg, "RXID"
    elif direction == GPIO_TUNNEL_SENSOR_TO_HOST:
        gpiod_0 |= DESERIALIZER_GPIOD_0_RX_EN_BIT
        gpiod_0 &= ~DESERIALIZER_GPIOD_0_TX_EN_BIT
        _i2c_write(bus, DESERIALIZER_ADDR, gpiod_0_reg + [gpiod_0],
                   "\tGPIOD_0 (deserializer MFP{}) | GPIO_RX_EN_D=1, GPIO_TX_EN_D=0, GPIO_TXRX_ID_D={}".format(
                       deser_mfp, channel_id))

        cfg0 |= SERIALIZER_GPIO_CFG0_OUT_DIS_BIT | SERIALIZER_GPIO_CFG0_TX_EN_BIT
        cfg0 &= ~SERIALIZER_GPIO_CFG0_RX_EN_BIT
        _i2c_write(bus, serializer_addr, cfg0_reg + [cfg0],
                   "\tGPIO_CFG0_{} (serializer MFP{}) | OUT_DIS=1, TX_EN=1, RX_EN=0 (input, forwarded)".format(
                       ser_mfp, ser_mfp))

        id_reg, id_name = txid_reg, "TXID"
    else:
        raise GmslConfigError("Unknown GPIO tunnel direction: {!r}".format(direction))

    id_val = _read_serializer_reg(bus, serializer_addr, id_reg)
    id_val = (id_val & ~SERIALIZER_GPIO_ID_MASK) | (channel_id & SERIALIZER_GPIO_ID_MASK)
    _i2c_write(bus, serializer_addr, id_reg + [id_val],
               "\tGPIO_{}_{} (serializer MFP{}) | GPIO_{}={} (must match deserializer GPIO_TXRX_ID_D)".format(
                   id_name, ser_mfp, ser_mfp, id_name, channel_id))


def configure_serializer_gpio_pin(bus: SMBus, serializer_addr: int, pin: int, name: str,
                                   direction: Optional[str]) -> None:
    """Configure a single serializer GPIO pin's direction - standalone, so a pin can be
    reconfigured on its own without touching SERIALIZER_GPIO_PIN_TABLE or re-running
    configure_serializer_gpio_pins() for every other pin."""
    if direction is None:
        logger.info("\tGPIO%d (%s): no direction specified - left at reset default", pin, name)
        return
    cfg0_reg = _serializer_gpio_cfg0_reg(pin)
    cfg0 = _read_serializer_reg(bus, serializer_addr, cfg0_reg)
    if direction == "OUTPUT":
        cfg0 |= SERIALIZER_GPIO_CFG0_OUT_TYPE_PUSH_PULL_BIT
        cfg0 &= ~(SERIALIZER_GPIO_CFG0_OUT_DIS_BIT | SERIALIZER_GPIO_CFG0_RX_EN_BIT
                  | SERIALIZER_GPIO_CFG0_TX_EN_BIT | SERIALIZER_GPIO_CFG0_OUT_BIT)
    elif direction == "INPUT":
        cfg0 |= SERIALIZER_GPIO_CFG0_OUT_DIS_BIT | SERIALIZER_GPIO_CFG0_TX_EN_BIT
        cfg0 &= ~SERIALIZER_GPIO_CFG0_RX_EN_BIT
    elif direction == "HIZ":
        cfg0 |= SERIALIZER_GPIO_CFG0_OUT_DIS_BIT
        cfg0 &= ~(SERIALIZER_GPIO_CFG0_TX_EN_BIT | SERIALIZER_GPIO_CFG0_RX_EN_BIT)
    else:
        raise GmslConfigError("Unknown GPIO direction '{}' for GPIO{} ({})".format(direction, pin, name))
    _i2c_write(bus, serializer_addr, cfg0_reg + [cfg0],
               "\tGPIO_CFG0_{} (GPIO{}/{}) | {}".format(pin, pin, name, direction))


def configure_serializer_gpio_pins(bus: SMBus, serializer_addr: int) -> None:
    """Configure every serializer GPIO pin in SERIALIZER_GPIO_PIN_TABLE per its
    board-assigned direction (GPIO0/GPIO1/GPIO2 are skipped - see
    configure_gpio_tunnel()).
    Thin loop over configure_serializer_gpio_pin() - call that directly instead to
    reconfigure a single pin on its own."""
    logger.info(">>> configure_serializer_gpio_pins()")
    for pin, (name, direction) in sorted(SERIALIZER_GPIO_PIN_TABLE.items()):
        if pin in (0, 1, 2):
            continue
        configure_serializer_gpio_pin(bus, serializer_addr, pin, name, direction)


def set_serializer_gpio_output(bus: SMBus, serializer_addr: int, name: str, value: int) -> None:
    """Drive a serializer GPIO pin configured as OUTPUT in SERIALIZER_GPIO_PIN_TABLE,
    identified by its board signal `name` (e.g. "GMSL_EN_TOF") rather than a raw pin
    number, to `value` (GPIO_HIGH/GPIO_LOW), via its local GPIO_OUT bit."""
    if name in SERIALIZER_GPIO_TUNNEL_DRIVEN_NAMES:
        raise GmslConfigError(
            "GPIO '{}' is tunnel-driven (configure_gpio_tunnel(), GPIO0/1/2) - --set-gpio is "
            "not supported for it. Toggle the Jetson host GPIO directly instead (PP.00 for "
            "ToF/GMSL_RGBISP_RST, PP.01 for RGB/GMSL_TOFISP_RST_L), or use --check-mfp0-tunnel/"
            "--check-mfp1-tunnel/--check-mfp2-tunnel to read it back.".format(name))
    if name in SERIALIZER_GPIO_RESERVED_NAMES:
        raise GmslConfigError(
            "GPIO '{}' (GPIO12-15) is reserved pending confirmation of the board's actual "
            "SPI/ADC usage (GPIO15 has a documented ADC analog voltage-monitoring function) - "
            "--set-gpio is not supported for it.".format(name))
    pin = _serializer_gpio_pin_by_name(name)
    logger.info(">>> set_serializer_gpio_output(name=%s, value=%d)", name, value)
    _name, direction = SERIALIZER_GPIO_PIN_TABLE[pin]
    if direction != "OUTPUT":
        raise GmslConfigError("GPIO{} ({}) is not configured as OUTPUT in SERIALIZER_GPIO_PIN_TABLE".format(pin, name))
    cfg0_reg = _serializer_gpio_cfg0_reg(pin)
    cfg0 = _read_serializer_reg(bus, serializer_addr, cfg0_reg)
    cfg0 = (cfg0 | SERIALIZER_GPIO_CFG0_OUT_BIT) if value else (cfg0 & ~SERIALIZER_GPIO_CFG0_OUT_BIT)
    _i2c_write(bus, serializer_addr, cfg0_reg + [cfg0],
               "\tGPIO_CFG0_{} (GPIO{}/{}) | GPIO_OUT: {}".format(pin, pin, name, value))


def get_serializer_gpio_output(bus: SMBus, serializer_addr: int, name: str) -> int:
    """Read back a serializer GPIO pin's current GPIO_OUT bit, identified by its
    board signal `name` (e.g. "GMSL_EN_TOF") - the counterpart read of
    set_serializer_gpio_output(). Returns GPIO_HIGH/GPIO_LOW."""
    if name in SERIALIZER_GPIO_TUNNEL_DRIVEN_NAMES:
        raise GmslConfigError(
            "GPIO '{}' is tunnel-driven (configure_gpio_tunnel(), GPIO0/1/2) - --get-gpio is "
            "not supported for it. Use --check-mfp0-tunnel/--check-mfp1-tunnel/"
            "--check-mfp2-tunnel instead.".format(name))
    if name in SERIALIZER_GPIO_RESERVED_NAMES:
        raise GmslConfigError(
            "GPIO '{}' (GPIO12-15) is reserved pending confirmation of the board's actual "
            "SPI/ADC usage (GPIO15 has a documented ADC analog voltage-monitoring function) - "
            "--get-gpio is not supported for it.".format(name))
    pin = _serializer_gpio_pin_by_name(name)
    _name, direction = SERIALIZER_GPIO_PIN_TABLE[pin]
    if direction != "OUTPUT":
        raise GmslConfigError("GPIO{} ({}) is not configured as OUTPUT in SERIALIZER_GPIO_PIN_TABLE".format(pin, name))
    cfg0_reg = _serializer_gpio_cfg0_reg(pin)
    cfg0 = _read_serializer_reg(bus, serializer_addr, cfg0_reg)
    value = GPIO_HIGH if (cfg0 & SERIALIZER_GPIO_CFG0_OUT_BIT) else GPIO_LOW
    logger.info(">>> get_serializer_gpio_output(name=%s) = %s", name, "HIGH" if value else "LOW")
    return value


def read_serializer_gpio_direction(bus: SMBus, serializer_addr: int, name: str) -> str:
    """Read back a serializer GPIO pin's actual configured direction straight off
    GPIO_CFG0's OUT_DIS/TX_EN/RX_EN bits, identified by its board signal `name`."""
    pin = _serializer_gpio_pin_by_name(name)
    cfg0_reg = _serializer_gpio_cfg0_reg(pin)
    cfg0 = _read_serializer_reg(bus, serializer_addr, cfg0_reg)
    out_dis = bool(cfg0 & SERIALIZER_GPIO_CFG0_OUT_DIS_BIT)
    tx_en = bool(cfg0 & SERIALIZER_GPIO_CFG0_TX_EN_BIT)
    rx_en = bool(cfg0 & SERIALIZER_GPIO_CFG0_RX_EN_BIT)
    if not out_dis and not tx_en and not rx_en:
        direction = "OUTPUT"
    elif out_dis and tx_en and not rx_en:
        direction = "INPUT"
    elif out_dis and not tx_en and not rx_en:
        direction = "HIZ"
    else:
        direction = "UNKNOWN (cfg0=0x{:02X})".format(cfg0)
    logger.info(">>> read_serializer_gpio_direction(name=%s) = %s (GPIO_CFG0_%d=0x%02X, OUT_DIS=%s TX_EN=%s RX_EN=%s)",
                 name, direction, pin, cfg0, out_dis, tx_en, rx_en)
    return direction


def select_fsync_target(bus: SMBus, serializer_addr: int, target: str) -> None:
    """Select which camera/IMU's FSYNC line drives the shared GMSL_FSYNC net
    (deserializer MFP4): `target` (one of FSYNC_TARGETS) is configured as OUTPUT,
    the other two are forced to HIZ (tri-stated) to avoid bus contention on the
    shared net - e.g. select_fsync_target(bus, addr, "GMSL_RGB_FSYNC") drives RGB's
    FSYNC and tri-states GMSL_TOF_FSYNC/GMSL_IMU_FSYNC."""
    if target not in FSYNC_TARGETS:
        raise GmslConfigError("Unknown FSYNC target '{}' - expected one of {}".format(target, FSYNC_TARGETS))
    logger.info(">>> select_fsync_target(target=%s)", target)
    for name in FSYNC_TARGETS:
        pin = _serializer_gpio_pin_by_name(name)
        configure_serializer_gpio_pin(bus, serializer_addr, pin, name, "OUTPUT" if name == target else "HIZ")


def _configure_deserializer_link(bus: SMBus) -> None:
    """Bring up the deserializer's GMSL3 Link D (disable CSI out, set rate/mode, reset, relock)."""
    logger.info(">>> _configure_deserializer_link()")
    logger.info("Deserializer:")

    backtop4 = _read_deserializer_reg(bus, DESERIALIZER_BACKTOP4_REG)
    backtop4 &= ~DESERIALIZER_CSI_OUT_EN_BIT
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_BACKTOP4_REG + [backtop4],
               "\tBACKTOP4 | CSI_OUT_EN: CSI output disabled")

    logger.info("Link Initialization for Deserializer:")

    reg16 = _read_deserializer_reg(bus, DESERIALIZER_REG16)
    reg16 = (reg16 & ~DESERIALIZER_REG16_RX_RATE_MASK) | DESERIALIZER_REG16_RX_RATE_12GBPS_GMSL3
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_REG16 + [reg16],
               "\tREG16 | RX_RATE_PHYD: 12Gbps/GMSL3")

    reg7 = _read_deserializer_reg(bus, DESERIALIZER_REG7)
    reg7 |= DESERIALIZER_REG7_GMSL3_D_BIT | DESERIALIZER_REG7_LINK_EN_D_BIT
    reg7 &= ~DESERIALIZER_REG7_LINK_ABC_BITS
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_REG7 + [reg7],
               "\tREG7 | GMSL3_D: Enabled | LINK_EN_D: Enabled | GMSL3/LINK_EN_A/B/C: Disabled")

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_FEC_MODE_D_REG + [DESERIALIZER_FEC_MODE_D_RX_FEC_EN_VALUE],
               "\tFEC_MODE_D | RX_FEC_EN (Link D): Enabled")

    _i2c_write(bus, DESERIALIZER_ADDR,
               DESERIALIZER_CTRL1_REG + [DESERIALIZER_CTRL1_RESET_ONESHOT_D_BIT],
               "\tCTRL1 | RESET_ONESHOT_D: Activated (self-clearing)")

    time.sleep(0x78 / 1000.0)
    logger.info("\t120 msec delay")

    logger.info("Link Initialization for Deserializer:")

    time.sleep(0x01 / 1000.0)
    logger.info("\tWarning: the actual recommended delay is 5 usec")


def _configure_serializer_mipi_input(bus: SMBus, serializer_addr: int) -> None:
    """Configure the serializer's CSI-2 inputs (Port A: ADSD3500 ToF, Port B: RGB), 2 lanes each."""
    logger.info(">>> _configure_serializer_mipi_input()")
    logger.info("Instructions for GMSL serializer MAX96723A:")
    logger.info("MIPI D-PHY Configuration:")

    mipi_rx0 = _read_serializer_reg(bus, serializer_addr, SERIALIZER_MIPI_RX0_REG)
    mipi_rx0 = (mipi_rx0 & ~SERIALIZER_MIPI_RX0_LANE_COUNT_MASK) | SERIALIZER_MIPI_RX0_LANE_COUNT_2LANE
    if SERIALIZER_MIPI_INPUT_DESKEW_ENABLED:
        mipi_rx0 |= SERIALIZER_MIPI_RX0_DESKEW_EN_BIT
    else:
        mipi_rx0 &= ~SERIALIZER_MIPI_RX0_DESKEW_EN_BIT
    _i2c_write(bus, serializer_addr, SERIALIZER_MIPI_RX0_REG + [mipi_rx0],
               "\tCSI_RX_CTRL_0__MIPI_RX0 (Port A, ToF) | LANE_COUNT: 2 Lane | DESKEW_EN: {} (required >= {} Mbps/lane)".format(
                   "Enabled" if SERIALIZER_MIPI_INPUT_DESKEW_ENABLED else "Disabled",
                   SERIALIZER_MIPI_DESKEW_REQUIRED_THRESHOLD_MBPS))

    mipi_rx0_ctrl1 = _read_serializer_reg(bus, serializer_addr, SERIALIZER_MIPI_RX0_CTRL1_REG)
    mipi_rx0_ctrl1 = (mipi_rx0_ctrl1 & ~SERIALIZER_MIPI_RX0_LANE_COUNT_MASK) | SERIALIZER_MIPI_RX0_LANE_COUNT_2LANE
    if SERIALIZER_MIPI_INPUT_DESKEW_ENABLED_RGB:
        mipi_rx0_ctrl1 |= SERIALIZER_MIPI_RX0_DESKEW_EN_BIT
    else:
        mipi_rx0_ctrl1 &= ~SERIALIZER_MIPI_RX0_DESKEW_EN_BIT
    _i2c_write(bus, serializer_addr, SERIALIZER_MIPI_RX0_CTRL1_REG + [mipi_rx0_ctrl1],
               "\tCSI_RX_CTRL_1__MIPI_RX0 (Port B, RGB) | LANE_COUNT: 2 Lane | DESKEW_EN: {} (required >= {} Mbps/lane)".format(
                   "Enabled" if SERIALIZER_MIPI_INPUT_DESKEW_ENABLED_RGB else "Disabled",
                   SERIALIZER_MIPI_DESKEW_REQUIRED_THRESHOLD_MBPS))

    video_tx = _read_serializer_reg(bus, serializer_addr, SERIALIZER_VIDEO_TX_REG)
    video_tx |= SERIALIZER_VIDEO_TX_LIMITED_HEARTBEAT_BIT
    _i2c_write(bus, serializer_addr, SERIALIZER_VIDEO_TX_REG + [video_tx],
               "\tVIDEO_TX_0__VIDEO_TX (Port A, ToF) | LIMITED_HEARTBEAT: Disabled (heartbeat disabled during blanking)")

    video_tx_ctrl1 = _read_serializer_reg(bus, serializer_addr, SERIALIZER_VIDEO_TX_CTRL1_REG)
    video_tx_ctrl1 |= SERIALIZER_VIDEO_TX_LIMITED_HEARTBEAT_BIT
    _i2c_write(bus, serializer_addr, SERIALIZER_VIDEO_TX_CTRL1_REG + [video_tx_ctrl1],
               "\tVIDEO_TX_1__VIDEO_TX (Port B, RGB) | LIMITED_HEARTBEAT: Disabled (heartbeat disabled during blanking)")


def _configure_deserializer_mipi_output(bus: SMBus) -> None:
    """Configure the deserializer's CSI-2 outputs: Controller 1/PHY1/Port A (ToF,
    Pipe 0) and Controller 2/PHY2/Port B (RGB, Pipe 1), 2 lanes each, tunnel routing."""
    logger.info(">>> _configure_deserializer_mipi_output()")
    logger.info("Instructions for deserializer MAX96726A:")
    logger.info("Video Pipes And Routing Configuration:")

    pipe_en = _read_deserializer_reg(bus, DESERIALIZER_VIDEO_PIPE_EN_REG)
    pipe_en |= DESERIALIZER_VIDEO_PIPE_EN_PIPE0_BIT | DESERIALIZER_VIDEO_PIPE_EN_PIPE1_BIT
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_VIDEO_PIPE_EN_REG + [pipe_en],
               "\tVIDEO_PIPE_EN | Pipe 0 (ToF) and Pipe 1 (RGB): forced Enabled")

    video_rx0_pipe0 = _read_deserializer_reg(bus, DESERIALIZER_VIDEO_RX0_PIPE0_REG)
    video_rx0_pipe0 &= ~DESERIALIZER_VIDEO_RX0_SEQ_MISS_EN_BIT
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_VIDEO_RX0_PIPE0_REG + [video_rx0_pipe0],
               "\tVIDEO_RX0 (Pipe 0, ToF) | SEQ_MISS_EN: Disabled")

    video_rx0_pipe1 = _read_deserializer_reg(bus, DESERIALIZER_VIDEO_RX0_PIPE1_REG)
    video_rx0_pipe1 &= ~DESERIALIZER_VIDEO_RX0_SEQ_MISS_EN_BIT
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_VIDEO_RX0_PIPE1_REG + [video_rx0_pipe1],
               "\tVIDEO_RX0 (Pipe 1, RGB) | SEQ_MISS_EN: Disabled")

    lim_heart = _read_deserializer_reg(bus, DESERIALIZER_LIM_HEART_REG)
    lim_heart |= DESERIALIZER_LIM_HEART_PIPE0_BIT | DESERIALIZER_LIM_HEART_PIPE1_BIT
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_LIM_HEART_REG + [lim_heart],
               "\tLIM_HEART (Pipe 0, Pipe 1) | Heartbeat: Disabled")

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_HEARTBEAT_TIMEOUT_REG + [DESERIALIZER_HEARTBEAT_TIMEOUT_MAX],
               "\tHeartbeat timeout threshold: Max (0xFF)")

    pipe_sel = _read_deserializer_reg(bus, DESERIALIZER_VIDEO_PIPE_SEL_0_REG)
    pipe_sel = (pipe_sel & ~DESERIALIZER_VIDEO_PIPE_SEL_0_MASK) | DESERIALIZER_VIDEO_PIPE_SEL_0_LINKD_STREAM0
    pipe_sel = (pipe_sel & ~DESERIALIZER_VIDEO_PIPE_SEL_1_MASK) | DESERIALIZER_VIDEO_PIPE_SEL_1_LINKD_STREAM1
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_VIDEO_PIPE_SEL_0_REG + [pipe_sel],
               "\tVIDEO_PIPE_SEL_0 | Pipe 0 (ToF): Link D Stream 0 | Pipe 1 (RGB): Link D Stream 1")

    logger.info("MIPI D-PHY Configuration:")

    phy0 = _read_deserializer_reg(bus, DESERIALIZER_MIPI_PHY0_REG)
    phy0 |= DESERIALIZER_MIPI_PHY0_PHY1_EN_BIT | DESERIALIZER_MIPI_PHY0_PHY2_EN_BIT
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_MIPI_PHY0_REG + [phy0],
               "\tMIPI_PHY0 | phy_Stdby_n: PHY1 Enabled (Port A, ToF), PHY2 Enabled (Port B, RGB)")

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_MIPI_TX10_CTRL1_REG + [DESERIALIZER_MIPI_TX10_2LANE_DPHY],
               "\tMIPI_TX10 (Controller 1) | CSI2_LANE_CNT: 2 lanes, D-PHY mode")
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_MIPI_TX10_REG + [DESERIALIZER_MIPI_TX10_2LANE_DPHY],
               "\tMIPI_TX10 (Controller 2) | CSI2_LANE_CNT: 2 lanes, D-PHY mode")

    def _configure_dpll_and_freq(dpll_reg, freq_reg, output_freq, controller_label):
        _i2c_write(bus, DESERIALIZER_ADDR, dpll_reg + [DESERIALIZER_DPLL0_SOFT_RESET_ASSERT],
                   "\tDPLL_0 ({}) | config_soft_rst_n: 0x0".format(controller_label))
        logger.info("\tSet predefined (coarse) CSI output frequency: %s is %s Mbps/lane",
                     controller_label, DESERIALIZER_MIPI_FREQ_MBPS.get(output_freq, "unknown"))
        _i2c_write(bus, DESERIALIZER_ADDR, freq_reg + [DESERIALIZER_MIPI_FREQ_PREDEF_EN_BIT | output_freq],
                   "\t{} frequency config | predef_freq: {} Mbps/lane".format(
                       controller_label, DESERIALIZER_MIPI_FREQ_MBPS.get(output_freq, "unknown")))
        _i2c_write(bus, DESERIALIZER_ADDR, dpll_reg + [DESERIALIZER_DPLL0_SOFT_RESET_RELEASE],
                   "\tDPLL_0 ({}) | config_soft_rst_n: 0x1".format(controller_label))
        return DESERIALIZER_MIPI_FREQ_MBPS.get(output_freq, 0)

    output_freq_mbps = _configure_dpll_and_freq(
        DESERIALIZER_DPLL0_CTRL1_REG, DESERIALIZER_MIPI_FREQ_CTRL1_REG, DESERIALIZER_MIPI_OUTPUT_FREQ,
        "Controller 1 / PHY1 (ToF)")
    output_freq_mbps_rgb = _configure_dpll_and_freq(
        DESERIALIZER_DPLL0_REG, DESERIALIZER_MIPI_FREQ_REG, DESERIALIZER_MIPI_OUTPUT_FREQ_RGB,
        "Controller 2 / PHY2 (RGB)")

    _i2c_write(bus, DESERIALIZER_ADDR,
               DESERIALIZER_MIPI_PHY0_REG + [DESERIALIZER_MIPI_PHY0_PHY1_EN_BIT | DESERIALIZER_MIPI_PHY0_PHY2_EN_BIT],
               "\tMIPI_PHY0 | phy_Stdby_n: PHY1 Enabled (Port A, ToF), PHY2 Enabled (Port B, RGB), reserved bits cleared")

    def _configure_deskew(init_reg, per_reg, output_freq_mbps, controller_label):
        periodic_enabled = DESERIALIZER_DESKEW_PERIODIC_ENABLED
        deskew_per_value = ((DESERIALIZER_DESKEW_ENABLE_BIT
                             | (DESERIALIZER_DESKEW_PERIOD_BITS << 3)
                             | DESERIALIZER_DESKEW_WIDTH_WIDEST)
                            if periodic_enabled else DESERIALIZER_DESKEW_DISABLE)
        deskew_period_frames = next((k for k, v in DESERIALIZER_DESKEW_PERIOD_CHOICES.items()
                                      if v == DESERIALIZER_DESKEW_PERIOD_BITS), "?")
        _i2c_write(bus, DESERIALIZER_ADDR, init_reg + [DESERIALIZER_DESKEW_AUTO_ENABLE_WIDEST],
                   "\tDESKEW_INIT ({}): auto-enabled (output is {} Mbps/lane)".format(
                       controller_label, output_freq_mbps))
        _i2c_write(bus, DESERIALIZER_ADDR, per_reg + [deskew_per_value],
                   "\tDESKEW_PER ({}): {}".format(
                       controller_label,
                       "enabled, every {} frame(s)".format(deskew_period_frames) if periodic_enabled else "disabled"))

    _configure_deskew(DESERIALIZER_DESKEW_INIT_CTRL1_REG, DESERIALIZER_DESKEW_PER_CTRL1_REG,
                       output_freq_mbps, "Controller 1 (ToF)")
    _configure_deskew(DESERIALIZER_DESKEW_INIT_REG, DESERIALIZER_DESKEW_PER_REG,
                       output_freq_mbps_rgb, "Controller 2 (RGB)")

    logger.info("Tunnel Mode Configuration:")

    config_0 = _read_deserializer_reg(bus, DESERIALIZER_PIPE0_CONFIG_0_REG)
    config_0 = (config_0 & ~DESERIALIZER_CONFIG_0_CON_DEST_MASK) | DESERIALIZER_CONFIG_0_CON_DEST_CONTROLLER1
    config_0 |= DESERIALIZER_CONFIG_0_DPHY_MODE_BIT
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_PIPE0_CONFIG_0_REG + [config_0],
               "\tCONFIG_0 (Pipe 0) | CON_DEST: Controller 1 (Port A, ToF) | D-PHY mode bit: Set")

    config_1 = _read_deserializer_reg(bus, DESERIALIZER_PIPE1_CONFIG_0_REG)
    config_1 = (config_1 & ~DESERIALIZER_CONFIG_0_CON_DEST_MASK) | DESERIALIZER_CONFIG_0_CON_DEST_CONTROLLER2
    config_1 |= DESERIALIZER_CONFIG_0_DPHY_MODE_BIT
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_PIPE1_CONFIG_0_REG + [config_1],
               "\tCONFIG_0 (Pipe 1) | CON_DEST: Controller 2 (Port B, RGB) | D-PHY mode bit: Set")

    _i2c_write(bus, DESERIALIZER_ADDR,
               DESERIALIZER_MIPI_TX54_CTRL1_REG + [DESERIALIZER_MIPI_TX54_DESKEW_TUN_SRC_PIPE0],
               "\tMIPI_TX54 (Controller 1) | DESKEW_TUN_SRC: Pipe 0")
    _i2c_write(bus, DESERIALIZER_ADDR,
               DESERIALIZER_MIPI_TX54_REG + [DESERIALIZER_MIPI_TX54_DESKEW_TUN_SRC_PIPE1],
               "\tMIPI_TX54 (Controller 2) | DESKEW_TUN_SRC: Pipe 1")

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_DEC_EN_REG + [DESERIALIZER_DEC_EN_DISABLE_VALUE],
               "\tDEC_EN | legacy GMSL2 video decoder: Disabled")

    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_VC_CTRL_PIPE0_REG + [DESERIALIZER_VC_CTRL_OVERRIDE_ENABLE_VALUE],
               "\tVC_CTRL (Pipe 0, ToF) | SRC/DST VC override: Enabled")
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_SRC_VC_PIPE0_REG + [DESERIALIZER_VC0_VALUE],
               "\tSRC_VC (Pipe 0, ToF): VC0")
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_DST_VC_PIPE0_REG + [DESERIALIZER_VC0_VALUE],
               "\tDST_VC (Pipe 0, ToF): VC0")

    # Link D would otherwise remap the RGB camera's VC0 to VC12; keep the original CSI VC instead.
    vc_mode = _read_deserializer_reg(bus, DESERIALIZER_VC_CTRL_PIPE1_REG)
    _i2c_write(bus, DESERIALIZER_ADDR,
               DESERIALIZER_VC_CTRL_PIPE1_REG + [vc_mode & ~DESERIALIZER_VC_OVERRIDE_MODE_MASK],
               "\tVC_CTRL (Pipe 1, RGB) | SRC/DST VC override: Disabled (preserve input VC)")

    backtop4 = _read_deserializer_reg(bus, DESERIALIZER_BACKTOP4_REG)
    backtop4 |= DESERIALIZER_CSI_OUT_EN_BIT
    _i2c_write(bus, DESERIALIZER_ADDR, DESERIALIZER_BACKTOP4_REG + [backtop4],
               "\tBACKTOP4 | CSI_OUT_EN: CSI output enabled (shared, both controllers)")


def _wait_for_deserializer_link_lock(bus: SMBus, timeout_s: float = 2.0, poll_interval_s: float = 0.05) -> bool:
    """Poll CTRL3.LOCK_PIN after a link reset until it asserts or `timeout_s` elapses."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        ctrl3 = _read_deserializer_reg(bus, DESERIALIZER_CTRL3_REG)
        if ctrl3 & DESERIALIZER_CTRL3_LOCK_PIN_BIT:
            logger.info("\tLink D relocked after reset")
            return True
        time.sleep(poll_interval_s)
    logger.warning(
        "\tLink D did not relock within %.1fs after reset - subsequent serializer-side "
        "I2C transactions may fail with a Remote I/O error", timeout_s)
    return False


def bring_up_gmsl_link(bus_number: int) -> None:
    """Bring up the MAX96723A/MAX96726A GMSL3 tunnel-mode link over I2C, configuring
    BOTH camera paths: ADSD3500 ToF (serializer Port A -> deserializer Port A/J21)
    and RGB (serializer Port B -> deserializer Port B/J20)."""
    logger.info(">>> bring_up_gmsl_link()")
    with SMBus(bus_number) as bus:
        logger.info("Deserializer detected at address %s", hex(DESERIALIZER_ADDR))
        read_deserializer_revision(bus)

        serializer_addr = _detect_serializer_addr(bus, SERIALIZER_ADDR_CANDIDATES)
        logger.info("Serializer detected at address %s", hex(serializer_addr))
        read_serializer_revision(bus, serializer_addr)
        logger.info("Configuration started")

        _configure_deserializer_link(bus)
        _wait_for_deserializer_link_lock(bus)
        for tunnel_name, (deser_mfp, ser_pin, channel_id, direction) in GPIO_TUNNELS.items():
            configure_gpio_tunnel(bus, serializer_addr, deser_mfp=deser_mfp, ser_mfp=ser_pin,
                                  channel_id=channel_id, direction=direction)
        configure_serializer_gpio_pins(bus, serializer_addr)
        _configure_serializer_mipi_input(bus, serializer_addr)
        _configure_deserializer_mipi_output(bus)

        logger.info("Configuration completed")
        read_deserializer_link_status(bus)
        read_serializer_link_status(bus, serializer_addr)
        enable_serializer_i2c_passthrough(bus, serializer_addr)
        read_serializer_i2c_passthrough(bus, serializer_addr)


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    print("gmsl3_init_max96723a_max96726a.py version {}".format(SCRIPT_VERSION))
    parser = argparse.ArgumentParser(
        description="Bring up the MAX96723A/MAX96726A GMSL2/3 tunnel-mode link over I2C.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  Full GMSL bring-up (default, bus 2):
    python3 gmsl3_init_max96723a_max96726a.py

  Full GMSL bring-up on a specific I2C bus, verbose DEBUG logging:
    python3 gmsl3_init_max96723a_max96726a.py 2 --log-level DEBUG

  Drive a named board-specific serializer GPIO HIGH (e.g. enable the RGB camera):
    python3 gmsl3_init_max96723a_max96726a.py --set-gpio GMSL_EN_RGB HIGH

  Read back a named board-specific serializer GPIO's current programmed level:
    python3 gmsl3_init_max96723a_max96726a.py --get-gpio GMSL_EN_RGB

  Read back a named board-specific serializer GPIO's actual configured direction (OUTPUT/INPUT/HIZ):
    python3 gmsl3_init_max96723a_max96726a.py --get-gpio-direction GMSL_EN_RGB

  Select which target's FSYNC line drives the shared GMSL_FSYNC net:
    python3 gmsl3_init_max96723a_max96726a.py --select-fsync-target GMSL_RGB_FSYNC

  Configure only the board-specific serializer GPIO pins (skip full bring-up):
    python3 gmsl3_init_max96723a_max96726a.py --configure-serializer-gpios

  Override the ToF CSI output speed for this run only:
    python3 gmsl3_init_max96723a_max96726a.py --mipi-freq-tof 2000

  Override the RGB CSI output speed for this run only:
    python3 gmsl3_init_max96723a_max96726a.py --mipi-freq-rgb 1500

  Enable periodic lane-deskew recalibration every 32 frames (requires >=1500Mbps):
    python3 gmsl3_init_max96723a_max96726a.py --mipi-freq-tof 1500 --deskew-period 32
""")
    parser.add_argument("bus", nargs="?", type=int, default=2,
                        help="I2C bus number (default: 2)")
    parser.add_argument("--log-level", default="ALL",
                        choices=["ALL", "DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging verbosity (default: ALL, i.e. show every log level)")
    parser.add_argument("--set-gpio", nargs=2, metavar=("NAME", "VALUE"), default=None,
                        help="Skip GMSL bring-up; drive a board-specific serializer GPIO (by its "
                             "SERIALIZER_GPIO_PIN_TABLE signal name, e.g. GMSL_EN_TOF) HIGH or LOW. "
                             "VALUE is HIGH/LOW/1/0. Only works on pins configured as OUTPUT "
                             "(not GMSL_RGBISP_RST/GMSL_TOFISP_RST_L, which are tunnel-driven - "
                             "toggle the Jetson host GPIO PP.00 (ToF)/PP.01 (RGB) directly instead).")
    parser.add_argument("--get-gpio", metavar="NAME", default=None,
                        help="Skip GMSL bring-up; read back a board-specific serializer GPIO's "
                             "current programmed level (by its SERIALIZER_GPIO_PIN_TABLE signal "
                             "name, e.g. GMSL_EN_TOF) and print HIGH/LOW. Only works on pins "
                             "configured as OUTPUT.")
    parser.add_argument("--get-gpio-direction", metavar="NAME", default=None,
                        help="Skip GMSL bring-up; read back a board-specific serializer GPIO's "
                             "actual configured direction straight off the GPIO_CFG0 hardware bits "
                             "(by its SERIALIZER_GPIO_PIN_TABLE signal name, e.g. GMSL_EN_TOF) and "
                             "print OUTPUT/INPUT/HIZ/UNKNOWN. Unlike --get-gpio, works regardless "
                             "of what SERIALIZER_GPIO_PIN_TABLE assumes.")
    parser.add_argument("--select-fsync-target", choices=FSYNC_TARGETS, default=None,
                        help="Skip GMSL bring-up; select which target's FSYNC line drives the "
                             "shared GMSL_FSYNC net (deserializer MFP4) - the other two FSYNC_TARGETS "
                             "are forced to HIZ to avoid bus contention on the shared net.")
    parser.add_argument("--configure-serializer-gpios", action="store_true",
                        help="Skip GMSL bring-up; configure only the board-specific serializer GPIO "
                             "pins (SERIALIZER_GPIO_PIN_TABLE), not GPIO0/GPIO1/GPIO2's tunnels")
    parser.add_argument("--mipi-freq-tof", choices=sorted(DESERIALIZER_MIPI_FREQ_CHOICES, key=int),
                        default=None,
                        help="Override DESERIALIZER_MIPI_OUTPUT_FREQ (ToF, Mbps/lane) for this run "
                             "only, without editing the script")
    parser.add_argument("--mipi-freq-rgb", choices=sorted(DESERIALIZER_MIPI_FREQ_CHOICES, key=int),
                        default=None,
                        help="Override DESERIALIZER_MIPI_OUTPUT_FREQ_RGB (RGB, Mbps/lane) for this "
                             "run only, without editing the script")
    parser.add_argument("--deskew-period", choices=sorted(DESERIALIZER_DESKEW_PERIOD_CHOICES, key=int),
                        default=None,
                        help="Opt in to periodic lane-deskew recalibration every N frames for "
                             "this run only (off by default - the Jetson only needs the one-time "
                             "initial deskew before the first frame, not per-frame recalibration). "
                             "Only applies when deskew is enabled, i.e. --mipi-freq-tof >= 1500")
    args = parser.parse_args(argv)

    logging.getLogger().setLevel(logging.DEBUG if args.log_level == "ALL" else args.log_level)
    logger.info("Parsed arguments: %s", vars(args))

    if args.mipi_freq_tof is not None:
        global DESERIALIZER_MIPI_OUTPUT_FREQ
        DESERIALIZER_MIPI_OUTPUT_FREQ = DESERIALIZER_MIPI_FREQ_CHOICES[args.mipi_freq_tof]

    if args.mipi_freq_rgb is not None:
        global DESERIALIZER_MIPI_OUTPUT_FREQ_RGB
        DESERIALIZER_MIPI_OUTPUT_FREQ_RGB = DESERIALIZER_MIPI_FREQ_CHOICES[args.mipi_freq_rgb]

    if args.deskew_period is not None:
        global DESERIALIZER_DESKEW_PERIODIC_ENABLED, DESERIALIZER_DESKEW_PERIOD_BITS
        DESERIALIZER_DESKEW_PERIODIC_ENABLED = True
        DESERIALIZER_DESKEW_PERIOD_BITS = DESERIALIZER_DESKEW_PERIOD_CHOICES[args.deskew_period]

    try:
        if args.configure_serializer_gpios:
            with SMBus(args.bus) as bus:
                serializer_addr = _detect_serializer_addr(bus, SERIALIZER_ADDR_CANDIDATES)
                configure_serializer_gpio_pins(bus, serializer_addr)
        elif args.set_gpio is not None:
            gpio_name, gpio_value_str = args.set_gpio
            value_choices = {"HIGH": GPIO_HIGH, "LOW": GPIO_LOW, "1": GPIO_HIGH, "0": GPIO_LOW}
            if gpio_value_str.upper() not in value_choices:
                logger.error("--set-gpio VALUE must be HIGH/LOW/1/0, got '%s'", gpio_value_str)
                return 1
            with SMBus(args.bus) as bus:
                serializer_addr = _detect_serializer_addr(bus, SERIALIZER_ADDR_CANDIDATES)
                set_serializer_gpio_output(bus, serializer_addr, gpio_name, value_choices[gpio_value_str.upper()])
        elif args.get_gpio is not None:
            with SMBus(args.bus) as bus:
                serializer_addr = _detect_serializer_addr(bus, SERIALIZER_ADDR_CANDIDATES)
                value = get_serializer_gpio_output(bus, serializer_addr, args.get_gpio)
                print("HIGH" if value else "LOW")
        elif args.get_gpio_direction is not None:
            with SMBus(args.bus) as bus:
                serializer_addr = _detect_serializer_addr(bus, SERIALIZER_ADDR_CANDIDATES)
                print(read_serializer_gpio_direction(bus, serializer_addr, args.get_gpio_direction))
        elif args.select_fsync_target is not None:
            with SMBus(args.bus) as bus:
                serializer_addr = _detect_serializer_addr(bus, SERIALIZER_ADDR_CANDIDATES)
                select_fsync_target(bus, serializer_addr, args.select_fsync_target)
        else:
            bring_up_gmsl_link(args.bus)
    except GmslConfigError as exc:
        logger.error("GMSL configuration failed: %s", exc)
        return 1
    except OSError as exc:
        logger.error("I2C bus error on bus %s: %s", args.bus, exc)
        return 1

    logger.info("GMSL configuration succeeded")
    return 0

if __name__ == "__main__":
    sys.exit(main())

