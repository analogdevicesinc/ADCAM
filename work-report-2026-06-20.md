# Work Report — Week of 2026-06-16 to 2026-06-20

## 1. v1.0.0 Release Preparation

**Files modified:**
- `README.md`
- `ToF-drivers` (submodule → rel-7.0.0)
- `libaditof` (submodule → rel-7.1.0)
- `doc/user-guide/readme.md`
- `doc/user-guide/ADCAM-CameraKit-100.html` *(new)*
- `doc/user-guide/ADCAM-CameraKit-100.md` *(new)*
- `doc/user-guide/ADCAM-CameraKit-020.html` *(removed)*
- `doc/user-guide/ADCAM-CameraKit-020.md` *(removed)*

**Changes:**
- Bumped README to reflect 1.0.0 release.
- Removed the v0.2.0 user guide; replaced with new v1.0.0 user guide (1,695-line Markdown + HTML mirror).
- Pinned submodules: `ToF-drivers` → `rel-7.0.0`, `libaditof` → `rel-7.1.0`.

---

## 2. User Guide and Example Help Text Improvements

**Files modified:**
- `doc/user-guide/ADCAM-CameraKit-100.html`
- `doc/user-guide/ADCAM-CameraKit-100.md`
- `examples/bindings/python/streaming/depth-image-animation-pygame.py`

**Changes:**
- Rewrote the `depth-image-animation-pygame.py` usage instructions to clearly distinguish between:
  - **On-device** (Jetson Orin Nano / Raspberry Pi 5): `python depth-image-animation-pygame.py <mode>`
  - **Network-connected host**: `python depth-image-animation-pygame.py <mode> <ip>`
- Mirrored the same clarification in both the HTML and Markdown versions of the v1.0.0 user guide.

---

## 3. Feature: RGB Camera Support (AR0234 Sensor)

**Branch / commit:** `adcfa371` in `libaditof`

**New files added:**
| File | Purpose |
|------|---------|
| `sdk/include/aditof/ar0234_sensor.h` | `RGBSensor` interface for the AR0234 |
| `sdk/src/connections/target/ar0234_sensor.cpp/.h` | AR0234 GStreamer capture implementation |
| `sdk/src/connections/target/gstreamer_frame_grabber.cpp/.h` | GStreamer pipeline wrapper |
| `sdk/src/connections/target/nv12_to_rgb.cpp/.h` | NV12 → BGR color-space conversion |

**Surgical modifications (RGB-only, no regression to existing paths):**
- `sdk/CMakeLists.txt` — added `WITH_RGB_CAMERA` CMake option + GStreamer dependency detection.
- `sdk/include/aditof/aditof.h` — conditional `#include <aditof/ar0234_sensor.h>`.
- `sdk/include/aditof/camera.h` — added `getRecordedFrameCount()` pure virtual.
- `sdk/include/aditof/sensor_enumerator_interface.h` — added `getRGBSensorStatus()` pure virtual.
- `sdk/src/cameras/itof-camera/camera_itof.cpp/.h` — `m_rgbEnabled`, `m_rgbSensor`, `m_rgbStatus` members; `setRGBSensorInfo()`.
- `sdk/src/cameras/itof-frame/frame_handler_impl.cpp` — optional AB/depth + RGB frame save.
- `sdk/src/cameras/itof-frame/frame_impl.cpp` — NV12 buffer sizing for `'rgb'` frame type.
- `sdk/src/connections/network/…` / `offline/…` enumerators — stub `getRGBSensorStatus()`.
- `sdk/src/connections/target/adsd3500/adsd3500_chip_config_manager.cpp` — `rgb` frameContent + AB mutual exclusion logic.
- `sdk/src/connections/target/adsd3500/adsd3500_sensor.h` — added `getBufferProcessor()`, `getRecordedFrameCount()`.
- `sdk/src/connections/target/frame_pipeline/buffer_processor.cpp/.h` — added `captureRGBFrameThread`, `m_frames_written`.
- `sdk/src/cameras/itof-camera/soc/nvidia/sensor_enumerator_nvidia.cpp` — AR0234 device detection.
- `sdk/src/connections/target/target_sensor_enumerator.h` — `getRGBSensorStatus()`.
- `sdk/src/system_impl.cpp` — `getRGBSensorStatus()` + `setRGBSensorInfo()` propagation through system layer.
- `sdk/src/connections/target/config/sensor-tables/device_parameters.h` — mode tables extended with `rgbCameraEnable` field.

---

## 4. Bug Fix: Frame Loss False Positive on Stream Restart

**File modified:**
- `examples/tof-viewer/src/ADIController.cpp`

**Root cause:** On `StartCapture()`, `m_prev_frame_number` retained the last ISP frame number from the previous streaming session. When the new session began with a lower ISP frame number the delta was interpreted as a large frame-loss event.

**Fix:** Reset both counters at the top of `StartCapture()`:

```cpp
m_prev_frame_number = static_cast<uint32_t>(-1);  // sentinel: "no previous frame"
m_current_frame_number = 0;
```

This ensures the first-frame guard fires correctly and no false gap is computed on restart.

---

## 5. Build Fix: Missing `<cstdint>` Include

**File modified:**
- `libaditof/sdk/src/cameras/itof-camera/managers/camera_configuration.h`

**Fix:** Added `#include <cstdint>` to resolve implicit dependency on integer-type definitions pulled in transitively by other headers (exposed by stricter toolchains / newer GCC defaults).

---

## 6. Firmware Update Tool Enhancements *(carries over from Jun 12)*

**Files modified:**
- `tools/nvm_tools/adsd3500_fw_update` — dual-slot `.bin` support with CRC verification and downgrade protection.
- `sdcard-images-utils/` — chip ID `0x59` 32-byte read added to `ctrl_app` for dual-ISP boot verification; new `firmware_update` utility executable for both NVIDIA and RPI platforms; updated README.

---

## Summary

| Item | Status |
|------|--------|
| v1.0.0 release: README, submodule pins, doc | ✅ Complete |
| v1.0.0 user guide (HTML + MD) | ✅ Complete |
| pygame example help text clarification | ✅ Complete |
| RGB camera support (AR0234, GStreamer pipeline) | ✅ Complete |
| Frame loss false positive fix on stream restart | ✅ Complete |
| `<cstdint>` include fix in `camera_configuration.h` | ✅ Complete |
| Firmware update: dual-slot `.bin` + CRC + NVIDIA/RPI executables | ✅ Complete |
