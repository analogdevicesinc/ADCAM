# Work Report — Week of 2026-06-09 to 2026-06-12

## 1. Bug Fix: `abAveraging` Mode-Awareness

**Files modified:**
- `libaditof/sdk/src/connections/target/config/sensor-tables/device_parameters.h`
- `libaditof/sdk/src/cameras/itof-camera/helpers/sensor_config_helper.cpp`

**Root cause:** `abAveraging` was hardcoded to `"0"` for all modes, breaking QMP modes (2–6) which require `"1"`.

**Fix:** Added `abAveraging` as a per-mode INI field in all 7 parameter maps. Updated `sensor_config_helper.cpp` to read the value from INI instead of hardcoding.

| Mode group | Imager type | `abAveraging` value |
|------------|-------------|---------------------|
| MP (modes 0–1) | `adsd3100_dual_fullDepth`, `adsd3100_partialDepth`, `adsd_PCM` | `"0"` |
| QMP (modes 2–6) | `adsd3100_fullDepth`, `adsd3030_fullDepth`, `adtf3080_fullDepth`, `adtf3066_fullDepth` | `"1"` |

---

## 2. Bug Fix: `dualPulsatrixSystemEnabled` Unsupported Control Warning

**File modified:**
- `libaditof/sdk/src/connections/target/config/sensor_control_registry.cpp`

**Root cause:** Control was handled in `adsd3500_sensor.cpp` dispatch (line 1253) but rejected earlier by `m_controlRegistry.setControl()` guard at line 1113 with "Unsupported control" LOG(WARNING) and early return.

**Fix:** Registered `dualPulsatrixSystemEnabled` in the control registry alongside related controls.

---

## 3. Driver Configuration Table Updates

**File modified:**
- `libaditof/sdk/src/connections/target/config/sensor-tables/driver_configuration_table.h`

Added **10 new hardware-validated entries** to `m_adsd3500standard`:

### 8 new entries: `D=12, C=4` (all AB values, both noOfFreqs)

| noOfFreqs | Depth | AB | Conf | driverWidth | driverHeight |
|-----------|-------|----|------|-------------|--------------|
| 2 | 12 | 16 | 4 | 2048 | 2048 |
| 2 | 12 | 12 | 4 | 2048 | 1792 |
| 2 | 12 | 8  | 4 | 2048 | 1536 |
| 2 | 12 | 0  | 4 | 2048 | 1024 |
| 3 | 12 | 16 | 4 | 2048 | 2048 |
| 3 | 12 | 12 | 4 | 2048 | 1792 |
| 3 | 12 | 8  | 4 | 2048 | 1536 |
| 3 | 12 | 0  | 4 | 2048 | 1024 |

### 2 new entries: `D=16, AB=0, C=0` (landscape orientation fix)

| noOfFreqs | Depth | AB | Conf | driverWidth | driverHeight |
|-----------|-------|----|------|-------------|--------------|
| 2 | 16 | 0 | 0 | 2048 | 1024 |
| 3 | 16 | 0 | 0 | 2048 | 1024 |

> **Note:** Previous table had `1024×2048` for this combination. Hardware requires landscape `2048×1024`.

---

## 4. Bit Combination Hardware Validation (V4L2 Level)

**Tool:** `~/ADI/Robotics/Camera/ADCAM/1.0.0/tools/v4l2_scripts/ADTF3175DUAL/processed/test_bit_combinations.sh`

Tested all combinations where `(depth + conf) % 8 == 0` via direct V4L2 capture. Results confirmed across 3 independent runs.

| Combination | Resolution | Result |
|-------------|------------|--------|
| D=16, AB=16, C=8 | 3072×1707 | ✅ PASS |
| D=16, AB=12, C=8 | 3072×1536 | ✅ PASS |
| D=16, AB=8,  C=8 | 3072×1366 | ✅ PASS |
| D=16, AB=0,  C=8 | 3072×1024 | ✅ PASS |
| D=16, AB=16, C=0 | 1024×4096 | ✅ PASS |
| D=16, AB=12, C=0 | 1024×3584 | ✅ PASS |
| D=16, AB=0,  C=0 | 2048×1024 | ✅ PASS |
| D=12, AB=16, C=4 | 2048×2048 | ✅ PASS |
| D=12, AB=12, C=4 | 2048×1792 | ✅ PASS |
| D=12, AB=8,  C=4 | 2048×1536 | ✅ PASS |
| D=12, AB=0,  C=4 | 2048×1024 | ✅ PASS |
| D=16, AB=8,  C=0 | 1024×3072 | ❌ FAIL — `1024×3072` absent from V4L2 driver enum |

---

## 5. End-to-End SDK Validation

**Tool:** `sdk_test_bit_combinations.sh` using `data_collect` with `-d`/`-a`/`-c` bit override flags

All 11 active SDK-supported combinations validated through full camera pipeline:
`initialize()` → `setControl()` → `setMode()` → `start()` → `requestFrame()`

**Result: 11/11 PASS**

| Combination | SDK Result |
|-------------|------------|
| D=16, AB=16, C=8 | ✅ PASS |
| D=16, AB=12, C=8 | ✅ PASS |
| D=16, AB=8,  C=8 | ✅ PASS |
| D=16, AB=0,  C=8 | ✅ PASS |
| D=16, AB=16, C=0 | ✅ PASS |
| D=16, AB=12, C=0 | ✅ PASS |
| D=16, AB=0,  C=0 | ✅ PASS |
| D=16, AB=8,  C=0 | ⏭ SKIP — `1024×3072` not in V4L2 driver enum |
| D=12, AB=16, C=4 | ✅ PASS |
| D=12, AB=12, C=4 | ✅ PASS |
| D=12, AB=8,  C=4 | ✅ PASS |
| D=12, AB=0,  C=4 | ✅ PASS |

---

## Summary

| Item | Status |
|------|--------|
| `abAveraging` mode-aware fix | ✅ Complete |
| `dualPulsatrixSystemEnabled` warning fix | ✅ Complete |
| Driver table: 8 new D=12/C=4 entries | ✅ Complete |
| Driver table: D=16/AB=0/C=0 landscape correction | ✅ Complete |
| V4L2-level bit combination validation | ✅ 11/12 pass (1 known V4L2 driver limitation) |
| SDK end-to-end bit combination validation | ✅ 11/11 pass |

### Known Limitation
- **D=16, AB=8, C=0** (`1024×3072`): Resolution is absent from the V4L2 driver's enumerated format list (`v4l2-ctl --list-formats-ext`). This is a firmware/driver constraint, not an SDK issue. `2048×3072` exists in the enum but `1024×3072` does not.
