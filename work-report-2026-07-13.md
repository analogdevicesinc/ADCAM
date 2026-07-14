# Work Report — Week of 2026-07-07 to 2026-07-13

## 1. Root Cause Investigation: QMP→MP Mode Switch — Zero Frames After STREAMON

**Date:** 2026-07-09 / 2026-07-10

### Investigation

Created a standalone C++ test binary (`examples/test-mode-switch/`) to isolate
the failure from the tof-viewer.  The test confirmed: after 5 successful QMP
frames (512×512), switching to MP mode (1024×1024) via `stop()` → `setMode(0)`
→ `start()` produced a V4L2 `select timeout` after 20 seconds — zero frames
delivered to `captureFrameThread`.

Key observations from test logs:
- `configureMediaPipeline` correctly re-issued for 12-bit MP format.
- `initTargetDepthCompute` completed in ~2 s (chip had 3+ s to settle).
- STREAMON succeeded — yet no V4L2 buffers were dequeued.
- For comparison, the first `setMode(QMP=2)` after `initialize()` always worked.

### Root Cause Confirmed

MIPI output speed and deskew-at-stream-on are written to the ADSD3500 chip
**once**, inside `CameraInitializationManager::applyHardwareConfiguration()`
during `initialize()`.  On every subsequent `setMode()` call, the sensor's
`CTRL_SET_MODE` ioctl triggers an internal ISP reconfiguration on the chip.
That reconfiguration resets the chip's transport registers (MIPI speed, deskew)
back to hardware defaults.  The Tegra VI/CSI pipeline then loses MIPI sync and
delivers zero frames after STREAMON.

The first `setMode(QMP)` always worked because it ran on a chip that had just
been GPIO-reset and was still in a "fresh" state; no full ISP reconfiguration
was triggered.  The second `setMode(MP)` — transitioning from a running QMP
stream — triggered the full ISP reset and wiped those registers.

---

## 2. Fix: Restore MIPI/Deskew and Reset Chip on Camera Stop

**Branches:**
- `libaditof`: `fix/mode-switch-mipi-reset` (commit `16250aae`)
- `ADCAM`: `fix/mode-switch-fps-config-load` (commit `80d190e1`)

**Files modified:**
- `libaditof/sdk/src/cameras/itof-camera/camera_itof.cpp`
- `libaditof/sdk/src/cameras/itof-camera/managers/camera_initialization_manager.h`

### Architecture decision

Several placement options for the re-apply were evaluated:

| Location | Decision | Reason |
|----------|----------|--------|
| `setMode()` (after DMS) | ❌ Rejected | Violates `setMode()` contract — mode config, not transport setup |
| `start()` (before STREAMON) | ❌ Rejected | `start()` should be a clean STREAMON; chip config not its responsibility |
| `stop()` + `CameraInitializationManager::applyHardwareConfiguration()` | ✅ Accepted | `stop()` owns teardown; leaving chip in a consistent ready-state is its job |

`applyHardwareConfiguration()` was already the correct method (owned by
`CameraInitializationManager`, called at init time).  It was promoted from
`private` to `public` so `camera_itof::stop()` could call it.

### Changes

**`camera_itof::stop()`** — after `m_depthSensor->stop()`:
```cpp
if (!m_isOffline && m_adsd3500Hardware) {
    aditof::Status resetStatus = m_adsd3500Hardware->adsd3500_reset();
    if (resetStatus == Status::OK)
        m_initManager->applyHardwareConfiguration();
}
```

**`camera_itof::setMode()`** — at start of online path:
```cpp
if (m_devStreaming) {
    stop();   // ensures GPIO reset + hardware config run before CTRL_SET_MODE
}
```

### Test result

```
[QMP] frame 1/5  depth 512x512   bytes=524288   ✓
[QMP] frame 5/5  depth 512x512   bytes=524288   ✓
QMP capture OK
=== Switching to MP mode 0 ===
stop() OK  →  GPIO reset  →  MIPI speed=1  →  deskew enabled
setMode(MP) OK
start() OK
[MP] frame 1/5  depth 1024x1024  bytes=2097152  ✓
[MP] frame 5/5  depth 1024x1024  bytes=2097152  ✓
MP capture OK
PASS: QMP→MP mode switch successful
```

---

## 3. Fix: Current FPS Showing Higher Than Expected FPS After Mode Switch

**File:** `examples/tof-viewer/src/ADIController.cpp`
**Branch:** `fix/mode-switch-fps-config-load`

**Root cause:** `StartCapture()` seeded `m_fps_ema` but did not update
`m_framerate`.  After a QMP(40 fps)→MP(10 fps) switch, `m_framerate` held the
old 40 fps value until the first MP frame arrived — "Current fps" (40) was
displayed higher than "Expected fps" (10).

**Fix (one line):**
```cpp
m_fps_ema    = static_cast<float>(frameRate); // seed EMA at configured rate
m_framerate  = m_fps_ema;                     // show correct rate immediately ← added
```

---

## 4. Fix: Absurd Frame Lost / Temperature Values After Loading Config File

**File:** `examples/tof-viewer/src/ADIMainCore.cpp`
**Branch:** `fix/mode-switch-fps-config-load`

**Root cause (two issues):**

1. `ShowLoadAdsdParamsMenu()` called `camera->stop()` then `camera->start()`
   directly, bypassing `ADIController::StartCapture()`.  This left
   `m_frames_lost` and `m_prev_frame_number` stale.  When streaming resumed
   the wrapped/reset frame numbers produced absurd "Frames Lost" counts.

2. After our GPIO-reset fix, `camera->stop()` resets the chip.  Calling
   `camera->start()` without a preceding `setMode()` issued STREAMON on an
   uninitialized chip → garbage metadata bytes → absurd Laser/Sensor Temp.

**Fix:** Replaced raw `camera->stop()` + `camera->start()` with:
```cpp
m_view_instance->m_ctrl->StopCapture();  // resets all counters cleanly
// ... file dialog + loadDepthParamsFromJsonFile() ...
if (wasStreaming)
    m_capture_separate_enabled = true;   // triggers PrepareCamera() next frame
```
`m_capture_separate_enabled = true` causes `CameraPlay()` to run the full
`PrepareCamera()` path (stop → GPIO reset → setMode → StartCapture) on the
next render frame, ensuring correct chip state and reset counters.

---

## 5. Branch / PR Summary

| Repo | Branch | Base | Status |
|------|--------|------|--------|
| `libaditof` | `fix/mode-switch-mipi-reset` | `rel-7.1.0` | Pushed, PR ready |
| `ADCAM` | `fix/mode-switch-fps-config-load` | `rel-1.0.0` | Pushed, PR ready |

### Pending merges to main (pre-existing, confirmed via commit search)

| Repo | Branch | In main? |
|------|--------|----------|
| `libaditof` | `add_missing_bits_support` | ✅ already in main |
| `libaditof` | `add_reset_before_set_mode` | ✅ already in main |
| `libaditof` | `fix_rpi_issue` | ✅ already in main |
| `ADCAM` | `fix/pygame-depth-colormap` | ❌ not yet in main |
| `ADCAM` | `update_nvm_tools_release` | ✅ already in main |
