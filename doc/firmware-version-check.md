# Firmware Version Check Configuration

## Overview

The SDK uses a **dedicated firmware version configuration file** (`firmware_version_config.json`) to manage firmware version validation during camera initialization. This keeps firmware version settings separate from the main camera configuration.

## Configuration File Location

The SDK automatically searches for `firmware_version_config.json` in:

1. **Binary directory** (development/examples): Same directory as executable
2. **System installation** (production): `/usr/local/share/aditof/firmware_version_config.json`

## Configuration File Structure

**File:** `firmware_version_config.json`

```json
{
  "expectedFirmwareVersion": "4.0.1.0",
  "skipFirmwareVersionCheck": false
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `expectedFirmwareVersion` | string | Expected firmware version. Empty string = disabled |
| `skipFirmwareVersionCheck` | boolean | If true, skips version check and 10s delay |

## Behavior Scenarios

The check compares the **major version** of the actual firmware against the major version declared in `expectedFirmwareVersion`.

### ✅ Firmware Matches (exact)
```
I20260520 Loaded expected firmware version: 8.1.0.0
I20260520 Skip firmware version check: false
I20260520 Current adsd3500 firmware version is: 8.1.0.0
I20260520 Firmware version matches expected version
```
**Result:** Initialization continues immediately.

### ❌ Actual Major < Expected Major (abort)
```
E20260520 Firmware version is too old to proceed!
E20260520   Expected: 8.1.0.0
E20260520   Actual:   7.3.2.0
E20260520   Actual major (7) < required major (8)
E20260520 Please update the ADSD3500 firmware before using this SDK version
```
**Result:** `initializeOnlineMode` returns `GENERIC_ERROR`; initialization is aborted. The firmware **must** be updated.

### ⏱️ Actual Major ≥ Expected Major, Version Mismatch (10s delay)
```
W20260520 Firmware version mismatch!
W20260520   Expected: 8.1.0.0
W20260520   Actual:   8.2.0.0
W20260520 Delaying 10 seconds before proceeding...
I20260520 To skip this delay, add "skipFirmwareVersionCheck": true
I20260520 Waiting... 10 seconds remaining
...
I20260520 Waiting... 1 seconds remaining
I20260520 Continuing initialization with mismatched firmware version
```
**Result:** 10-second countdown, then continues.

### ⚡ Skip Check Override
**Config:**
```json
{
  "expectedFirmwareVersion": "4.0.1.0",
  "skipFirmwareVersionCheck": true
}
```
**Result:** No delay, initialization continues immediately

### 🔓 No Config File
```
W20260520 Firmware version config file not found
I20260520 Firmware version check will be disabled
```
**Result:** No version checking performed

## Use Cases

### Development/Testing
```json
{
  "skipFirmwareVersionCheck": true
}
```

### Production Enforcement
```json
{
  "expectedFirmwareVersion": "4.0.1.0",
  "skipFirmwareVersionCheck": false
}
```

### Disable Check
Delete or rename `firmware_version_config.json`, or set:
```json
{
  "expectedFirmwareVersion": ""
}
```

## Modifying Configuration

### During Development
```bash
# Edit source and rebuild
nano libaditof/sdk/src/cameras/itof-camera/config/firmware_version_config.json
cd build && make -j8
```

### At Runtime
```bash
# Edit in binary directory
nano build/examples/first-frame/firmware_version_config.json
# Changes take effect on next camera.initialize()
```

## Integration Examples

### C++ (first-frame)
```bash
cd build/examples/first-frame
./first-frame
# Automatically loads firmware_version_config.json
```

### Python
```python
import aditofpython as tof
system = tof.System()
camera = system.getCameraList()[0]
camera.initialize()  # Firmware check happens here
```

## Implementation Details

- **Loading:** During `CameraInitializationManager::initializeOnlineMode()`
- **Check Timing:** After reading actual firmware version from hardware
- **Delay:** 10 seconds with countdown displayed every second
- **Non-Fatal:** SDK continues initialization after delay

## Files Modified

- [firmware_version_config.json](../libaditof/sdk/src/cameras/itof-camera/config/firmware_version_config.json) - Source config
- [camera_configuration.h](../libaditof/sdk/src/cameras/itof-camera/managers/camera_configuration.h) - Added loadFirmwareVersionConfig()
- [camera_configuration.cpp](../libaditof/sdk/src/cameras/itof-camera/managers/camera_configuration.cpp) - Implementation
- [camera_initialization_manager.cpp](../libaditof/sdk/src/cameras/itof-camera/managers/camera_initialization_manager.cpp) - Version check logic
- [examples/*/CMakeLists.txt](../examples/) - Copy config to build dirs
