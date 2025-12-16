
#!/usr/bin/env python3
"""
MAX7327 SMBus/I2C helper (function-style API)

Addresses (per your setup):
- 0x68 controls outputs O0..O7 (port bits 0..7)
- 0x58 controls outputs O8..O15 (port bits 8..15)

Pin connection: AD2 and AD0 are grounded.

Function API examples:
    set_port_expander(0x68, EN_1P8, LOW)
    set_port_expander(0x58, EN_VSYS, HIGH)

Labels (O0..O15 in order provided):
O0  -> EN_1P8
O1  -> EN_0P8
O2  -> P2
O3  -> I2CM_SEL
O4  -> ISP_BS3
O5  -> NET_HOST_IO_SEL
O6  -> ISP_BS0
O7  -> ISP_BS1
O8  -> HOST_IO_DIR
O9  -> ISP_BS4
O10 -> ISP_BS5
O11 -> FSYNC_DIR
O12 -> EN_VAUX
O13 -> EN_VAUX_LS
O14 -> EN_VSYS      # renamed from EN_SYS to EN_VSYS
O15 -> O15          # placeholder; rename if you have a proper label
"""

import os
import time

# Try smbus2 first, fall back to smbus
try:
    from smbus2 import SMBus
except ImportError:  # pragma: no cover
    from smbus import SMBus


# === SoC gpio ===
GPIO_CAM_RESET_N = "PAC.00"
EXPORT_GPIO_NUM = "486"

# ==== I2C configuration ===
I2C_BUS_NUM = 2        # Adjust if your board uses a different bus
ADDR_LOW = 0x68        # O0..O7
ADDR_HIGH = 0x58       # O8..O15

# ==== Level constants ====
LOW = 0
HIGH = 1

# ==== Label constants (map to pin indices 0..15) ====
EN_1P8          = 0   # O0
EN_0P8          = 1   # O1
P2              = 2   # O2
I2CM_SEL        = 3   # O3
ISP_BS3         = 4   # O4
NET_HOST_IO_SEL = 5   # O5
ISP_BS0         = 6   # O6
ISP_BS1         = 7   # O7
HOST_IO_DIR     = 8   # O8
ISP_BS4         = 9   # O9
ISP_BS5         = 10  # O10
FSYNC_DIR       = 11  # O11
EN_VAUX         = 12  # O12
EN_VAUX_LS      = 13  # O13
EN_VSYS         = 14  # O14
O15_LABEL       = 15  # O15 (rename if needed)

# Name list for formatted snapshot
LABELS = [
    "EN_1P8",
    "EN_0P8",
    "P2",
    "I2CM_SEL",
    "ISP_BS3",
    "NET_HOST_IO_SEL",
    "ISP_BS0",
    "ISP_BS1",
    "HOST_IO_DIR",
    "ISP_BS4",
    "ISP_BS5",
    "FSYNC_DIR",
    "EN_VAUX",
    "EN_VAUX_LS",
    "EN_VSYS",
    "O15",
]


class _Max7327Bus:
    """Internal bus manager for MAX7327 banks"""
    def __init__(self, bus_num=I2C_BUS_NUM, addr_low=ADDR_LOW, addr_high=ADDR_HIGH):
        self.bus = SMBus(bus_num)
        self.addr_low = addr_low
        self.addr_high = addr_high

    def close(self):
        try:
            self.bus.close()
        except Exception:
            pass

    # ---- Primitive ops ----
    def write_byte(self, addr, value8):
        if not (0 <= value8 <= 0xFF):
            raise ValueError("Byte out of range 0..255")
        self.bus.write_byte(addr, value8)

    def read_byte(self, addr):
        return self.bus.read_byte(addr)

    # ---- Bank helpers ----
    def _bank_for_pin(self, pin):
        """Return (addr, mask) for the pin"""
        if not (0 <= pin <= 15):
            raise ValueError("Pin must be in 0..15")
        if pin < 8:
            addr = self.addr_low
            mask = 1 << pin
        else:
            addr = self.addr_high
            mask = 1 << (pin - 8)
        return addr, mask

    def set_pin(self, pin, level):
        """Read-modify-write the proper bank to set pin to level (0/1)"""
        addr, mask = self._bank_for_pin(pin)
        current = self.read_byte(addr)
        newval = (current | mask) if level == HIGH else (current & ~mask)
        self.write_byte(addr, newval)

    def get_pin(self, pin):
        """Read the output image bit (0/1)"""
        addr, mask = self._bank_for_pin(pin)
        current = self.read_byte(addr)
        return 1 if (current & mask) else 0

    def write_all(self, value16):
        """Write O0..O15 in one shot."""
        if not (0 <= value16 <= 0xFFFF):
            raise ValueError("16-bit value out of range 0..65535")
        low = value16 & 0xFF
        high = (value16 >> 8) & 0xFF
        self.write_byte(self.addr_low, low)
        self.write_byte(self.addr_high, high)

    def read_all(self):
        """Read O0..O15 as a 16-bit value"""
        low = self.read_byte(self.addr_low)
        high = self.read_byte(self.addr_high)
        return low | (high << 8)


# Single module-level bus (create once)
_bus = _Max7327Bus()


# ===== Public function API =====

def set_port_expander(addr, label_pin, level):
    """
    Set a labeled pin to LOW/HIGH on the specified bank address.

    Example:
        set_port_expander(0x68, EN_1P8, LOW)
        set_port_expander(0x58, EN_VSYS, HIGH)
    """
    if addr not in (ADDR_LOW, ADDR_HIGH):
        raise ValueError(f"addr must be {hex(ADDR_LOW)} or {hex(ADDR_HIGH)}")
    if level not in (LOW, HIGH):
        raise ValueError("level must be LOW or HIGH")
    if not (0 <= label_pin <= 15):
        raise ValueError("label_pin must map to 0..15")

    # Ensure the label belongs to the chosen bank
    if addr == ADDR_LOW and label_pin >= 8:
        raise ValueError("label_pin belongs to high bank but addr is low (0x68)")
    if addr == ADDR_HIGH and label_pin < 8:
        raise ValueError("label_pin belongs to low bank but addr is high (0x58)")

    _bus.set_pin(label_pin, level)


def get_port_expander(addr, label_pin):
    """Read a labeled pin bit (0/1) from the specified bank address."""
    if addr not in (ADDR_LOW, ADDR_HIGH):
        raise ValueError(f"addr must be {hex(ADDR_LOW)} or {hex(ADDR_HIGH)}")
    if not (0 <= label_pin <= 15):
        raise ValueError("label_pin must map to 0..15")

    # Bank consistency
    if addr == ADDR_LOW and label_pin >= 8:
        raise ValueError("label_pin belongs to high bank but addr is low (0x68)")
    if addr == ADDR_HIGH and label_pin < 8:
        raise ValueError("label_pin belongs to low bank but addr is high (0x58)")

    return _bus.get_pin(label_pin)


def write_port_byte(addr, value8):
    """Write an entire bank byte."""
    if addr not in (ADDR_LOW, ADDR_HIGH):
        raise ValueError(f"addr must be {hex(ADDR_LOW)} or {hex(ADDR_HIGH)}")
    _bus.write_byte(addr, value8 & 0xFF)


def read_port_byte(addr):
    """Read an entire bank byte."""
    if addr not in (ADDR_LOW, ADDR_HIGH):
        raise ValueError(f"addr must be {hex(ADDR_LOW)} or {hex(ADDR_HIGH)}")
    return _bus.read_byte(addr)


def write_all(value16):
    """Write both banks in one call."""
    _bus.write_all(value16 & 0xFFFF)

def export_and_configure_gpio(gpio_dir_name, export_gpio_num):
    gpio_path = f"/sys/class/gpio/{gpio_dir_name}"

    # If GPIO directory doesn't exist → export it
    if not os.path.isdir(gpio_path):
        # Export the GPIO
        with open("/sys/class/gpio/export", "w") as f:
            f.write(export_gpio_num)

        # Set direction to "out"
        direction_path = os.path.join(gpio_path, "direction")
        with open(direction_path, "w") as f:
            f.write("out")

def write_gpio_value(gpio_number, value):
    gpio_path = os.path.join('/sys/class/gpio/{}/value'.format(gpio_number))
    with open(gpio_path, 'w') as f:
        f.write(str(value))

def snapshot_by_labels():
    """
    Print the current output image, each label on a new line.
    """
    val16 = _bus.read_all()
    for pin, name in enumerate(LABELS):
        state = 1 if (val16 >> pin) & 1 else 0
        print(f"{name} = {state}")


def close_bus():
    """Close the SMBus (optional for cleanup)."""
    _bus.close()


# ===== Main sequence (updated per your earlier request) =====
if __name__ == "__main__":
    try:
        # Optional: start from all LOW
        write_all(0x0000)

        export_and_configure_gpio(GPIO_CAM_RESET_N, EXPORT_GPIO_NUM)
        print("Starting ToF power sequence...")
        #Pull ADSD3500 reset low
        write_gpio_value(GPIO_CAM_RESET_N, LOW)

        # --- Initial configuration ---
        # Set NET_HOST_IO_SEL = 1
        set_port_expander(ADDR_LOW, NET_HOST_IO_SEL, HIGH)

        # Set HOST_IO_DIR = 1
        set_port_expander(ADDR_HIGH, HOST_IO_DIR, HIGH)

        # Set FSYNC_DIR = 1
        set_port_expander(ADDR_HIGH, FSYNC_DIR, HIGH)

        # EN_1P8 = 0
        set_port_expander(ADDR_LOW, EN_1P8, LOW)

        # EN_0P8 = 0
        set_port_expander(ADDR_LOW, EN_0P8, LOW)

        time.sleep(0.2)

        # I2CM_SEL = 0
        set_port_expander(ADDR_LOW, I2CM_SEL, LOW)

        # ISP_BS0 = 0
        set_port_expander(ADDR_LOW, ISP_BS0, LOW)

        # ISP_BS1 = 0
        set_port_expander(ADDR_LOW, ISP_BS1, LOW)

        # ISP_BS4 = 0
        set_port_expander(ADDR_HIGH, ISP_BS4, LOW)

        # ISP_BS5 = 0
        set_port_expander(ADDR_HIGH, ISP_BS5, LOW)

        # EN_1P8 = 1
        set_port_expander(ADDR_LOW, EN_1P8, HIGH)

        time.sleep(0.2)

        # EN_0P8 = 1
        set_port_expander(ADDR_LOW, EN_0P8, HIGH)

        time.sleep(0.2)

        # EN_VSYS = 1 (renamed from EN_SYS)
        set_port_expander(ADDR_HIGH, EN_VSYS, HIGH)

        # EN_VAUX_LS = 1
        set_port_expander(ADDR_HIGH, EN_VAUX_LS, HIGH)

        # EN_VAUX = 1
        set_port_expander(ADDR_HIGH, EN_VAUX, HIGH)

        time.sleep(0.2)

        #Pull ADSD3500 reset high
        write_gpio_value(GPIO_CAM_RESET_N, HIGH)
        print("ToF power sequence completed.")
        print()

        # Read back states
        low_val = read_port_byte(ADDR_LOW)
        high_val = read_port_byte(ADDR_HIGH)

        print(f"Slave Address 0x{ADDR_LOW:02X} -> Data: 0x{low_val:02X}")
        print(f"Slave Address 0x{ADDR_HIGH:02X} -> Data: 0x{high_val:02X}")
        print()

        # Print final snapshot (each on a new line)
        print("Final Port Expander State:")
        snapshot_by_labels()

    finally:
        close_bus()

