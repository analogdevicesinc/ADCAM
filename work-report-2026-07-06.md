# Work Report — Week of 2026-06-30 to 2026-07-06

## 1. RGB Pipeline Alignment with rgb_support Architecture

**Branch / commit:** `22343d91` in `libaditof` (`rgb_update`)

**Files modified:**
- `sdk/src/cameras/itof-camera/camera_itof.cpp`
- `sdk/src/connections/target/frame_pipeline/buffer_processor.cpp/.h`

**Changes:**
- `start()`: depth streaming begins first (`STREAMON`), 500 ms delay, then RGB
  start; `BufferProcessor` wired (`setRGBSensor` + `enableRGBCapture`) only
  after Argus reaches PLAYING state.
- `setRGBSensorInfo()`: deferred `BufferProcessor` wiring to `start()`.
- `requestFrame()`: switched to `bufferProc->getLatestRGBFrame()` instead of
  direct `m_rgbSensor->getFrame()` to avoid dual appsink consumers.
- `captureRGBFrameThread`: NV12 → BGR conversion (3 bytes/pixel) before pushing
  to `m_rgb_frame_Q`; self-gates on `m_rgbCaptureEnabled` flag.
- `startThreads()`: `captureRGBFrameThread` always started; thread self-gates.
- `stopThreads()`: added 5 s queue-drainage wait before thread join.
- `captureFrameThread`: requeue V4L2 buffer on `nullptr` to prevent starvation.
- `setMode()`: RGB frame buffer sized at 3 bytes/pixel (BGR, not BGRA).

---

## 2. Bug Fix: QMP Modes ISP MIPI Silence with RGB Enabled

**Branch / commit:** `9822d76b` in `libaditof` (`rgb_update`)

**File modified:**
- `sdk/src/cameras/itof-camera/helpers/sensor_config_helper.cpp`

**Root cause (confirmed by hardware bit-combination test):**
The ADSD3500 ISP in QMP modes (2–6, 512×512) requires `ab_bits > 0` in the MIPI
stream or it outputs **no frames at all**.  The only passing combinations for
mode 2 are `{D=16, AB∈{8,12,16}, C=8}`.

When RGB is enabled the original code unconditionally zeroed `abBits` to free the
AB output slot for RGB data.  For MP modes (0–1, 1024×1024) this is correct
(ISP can output depth+conf without AB).  For QMP modes it causes ISP silence,
resulting in a 1536×512 V4L2 format (depth+conf only) instead of the correct
2560×512.

**Fix:** Added a separate `else if (rgbOn && isQMPMode)` branch:
- Sets `abEnabled = false` so the AB slot in the output frame is available for
  RGB data (same user-visible behaviour as MP+RGB).
- Keeps `abBitsPerPixel = 16` and calls `setControl("abBits", "6")` so the ISP
  continues to output AB in the MIPI stream, maintaining the 2560×512 V4L2
  format.

```cpp
} else if (rgbOn && isQMPMode) {
    abEnabled = false;          // slot freed for RGB in output frame
    // abBitsPerPixel=16 preserved — ISP requires AB in MIPI stream
    m_depthSensor->setControl("abBits", convertBitsToSensorValue(value, true));
}
```

---

## 3. Bug Investigation: modeDetailsCache Initialization Ordering

**File:** `sdk/src/cameras/itof-camera/camera_itof.cpp`

**Root cause identified:**
`configureSensorModeDetails()` is called at line 522 **before**
`getModeDetails()` at line 597, so `modeDetailsCache.baseResolutionWidth` is
either 0 (first launch) or stale from the previous mode (e.g., 1024 when
switching from mode 0 → mode 2).  This caused `isQMPMode` to evaluate `false`
for QMP modes on first launch, incorrectly zeroing `abBits` and producing the
1536×512 bug even after the fix in §2.

**Fix (pending commit):**
Pre-populate `modeDetailsCache` from the already-found `modeIt` entry before the
first `configureSensorModeDetails()` call:

```cpp
// Pre-populate so configureSensorModeDetails() sees correct width/height
// before getModeDetails() is called below.
m_modeDetailsCache.baseResolutionWidth  = modeIt->baseResolutionWidth;
m_modeDetailsCache.baseResolutionHeight = modeIt->baseResolutionHeight;
configureSensorModeDetails();
```

---

## 4. Feature: RGB Colour Mode for Point Cloud in tof-viewer

**Branch / commit:** `83903c38` in `merge-rgb_support-to-main-pr`

**Files modified:**
- `examples/tof-viewer/src/ADIMainControl.cpp`
- `examples/tof-viewer/src/ADIView.cpp`
- `examples/tof-viewer/src/ADIView_neon.cpp`

**Changes:**
- Added **RGB Colour** radio button (`m_pccolour=3`) in the Point Cloud colour
  selector, visible only when `m_rgbThreadCreated` is true; auto-resets to Depth
  colour if RGB thread stops.
- Scalar path (`ADIView.cpp`) and NEON/Jetson path (`ADIView_neon.cpp`): waits on
  `rgb_data_ready_cv` before entering per-frame loop when `m_pccolour==3`;
  nearest-neighbour ToF→RGB pixel scale lookup
  (`tof_col * rgbW / tofW`, `tof_row * rgbH / tofH`); BGR→RGB channel swap for
  correct shader output. Falls back to HSV depth colour when RGB data unavailable.

---

## 5. Feature: RGBD Coregistration Python Example

**Branch / commit:** `26db74bc` in `merge-rgb_support-to-main-pr`

**New files added:**
- `examples/bindings/python/coregistration/coregistration.py`

**Changes:**
- End-to-end RGB-Depth coregistration using pure NumPy.
- Supports file mode (`--depth`, `--rgb`, `--calib`) and live camera mode.
- Uses `RGBDCoregistration` SDK class for depth-to-RGB pixel mapping.

---

## 6. Build Fix: Missing `<cstring>` Include in tof-viewer

**Branch / commit:** `ea21c506` in `merge-rgb_support-to-main-pr`

**File modified:**
- `examples/tof-viewer/src/ADIView.cpp`

**Fix:** Added `#include <cstring>` to resolve implicit dependency on
`std::memcpy` (exposed by stricter toolchains / newer GCC defaults).

---

## 7. Git Branch Management

- Rebased `merge-rgb_support-to-main-pr` onto `origin/merge-rgb_support-to-main-pr`
  (resolved `libaditof` submodule pointer conflicts throughout; kept `rgb_update`
  HEAD `9822d76b`).
- Rebased `merge-rgb_support-to-main-pr` onto `origin/main` (same conflict
  resolution pattern; all RGB feature commits verified present after rebase).
- Force-pushed both times with `--force-with-lease`.
- Restored accidentally deleted `sdk/src/connections/target/sensor-tables/device_parameters.h`
  (stash artifact from a previous session).

---

## Summary

| Item | Status |
|------|--------|
| RGB pipeline alignment (start order, BGR sizing, thread gating) | ✅ Committed (`22343d91`) |
| QMP ISP MIPI silence fix — `abBits=16` kept in hardware for QMP+RGB | ✅ Committed (`9822d76b`) |
| `modeDetailsCache` ordering fix in `camera_itof.cpp` | ⏳ Pending commit |
| RGB Colour point-cloud mode in tof-viewer | ✅ Committed (`83903c38`) |
| RGBD coregistration Python example | ✅ Committed (`26db74bc`) |
| `<cstring>` include fix in `ADIView.cpp` | ✅ Committed (`ea21c506`) |
| Branch rebase onto `origin/main` + force-push | ✅ Complete |
