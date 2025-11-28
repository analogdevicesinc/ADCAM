## Quick orientation for AI coding agents

This repo implements the **ADCAM Camera Kit** — an ADI Time-of-Flight SDK + host applications for the NVIDIA Jetson Orin Nano with dual ADSD3500 Depth ISPs. The guidance below covers the minimal knowledge needed to be immediately productive.

### Big picture architecture
- **Major components**: `libaditof/` (SDK core + driver integration), `apps/` (server & target apps), `bindings/` (Python via pybind11), `examples/` (reference apps), `ToF-drivers/` (V4L2 kernel driver, git submodule), `tests/` (CMake-driven test suite)
- **Hardware**: **ADTF3175D** Time-of-Flight imager + **ADSD3500** Dual Depth ISP (on NVIDIA Jetson Orin Nano). Key difference from earlier eval kits: depth computation is **fully hardware-handled** by dual ISPs; SDK only needs to format/copy output.
- **Data flow**: ADTF3175D → ADSD3500 ISP → V4L2 kernel driver → `libaditof` SDK (`BufferProcessor` multi-threaded pipeline) → host applications or Python bindings. See diagram in `libaditof/README.md` and top-level `README.md`.
- **Frame modes** (set via `-m <mode>` flag in examples): each mode produces different V4L2 payload structure, ISP behavior, and resolution:
  - **Modes 0-1 (MP, Megapixel, 1024×1024)**: Raw mode; ISP outputs raw sensor data; payload = depth (2B) + AB (2B) per pixel; `processThread()` **just copies** V4L2 payload (no TofiCompute needed; ISP does depth computation on-chip)
  - **Modes 2-6 (QMP, Quarter Megapixel, 512×512)**: ISP pre-computes depth + confidence; payload = depth (2B) + confidence (4B); `processThread()` calls `TofiCompute()` to perform deinterleaving only
  - All QMP modes (2-6) are ISP pre-computed; exact payload and frame content depend on specific mode (pcm-native, long-range mixed, etc.); inspect `buffer_processor.cpp:processThread()` for layout

**Memory layout in buffers**: Raw V4L2 frame → raw buffer → (after optional TofiCompute) → output: Depth [W×H×uint16] | AB [W×H×uint16] | Confidence [W×H×float] = W×H×8B
- MP modes (0-1): W=1024, H=1024 → 8.4 MB per frame
- QMP modes (2-6): W=512, H=512 → 2.1 MB per frame

### Build and run — exact commands
```bash
# Submodules required
git submodule update --init

# Out-of-source build (project root)
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DNVIDIA=ON ..  # NVIDIA=ON for Jetson target
cmake --build . -j$(nproc)

# Key flags
# -DNVIDIA=ON|OFF (default ON): Jetson target vs. host-only testing
# -DWITH_PYTHON=ON|OFF: Python bindings (requires libpython headers)
# -DWITH_EXAMPLES=ON|OFF: C++ examples (requires OpenGL, OpenCV)
# -DWITH_NETWORK=ON|OFF: ZMQ server (requires libzmq, protobuf, glog)
# -WITH_OFFLINE=ON|OFF: Offline replay mode (no hardware)
```

Run tests: `cd build && ctest --output-on-failure`

### Core architecture: Multi-threaded frame pipeline
**File**: `libaditof/sdk/src/connections/target/buffer_processor.cpp`

Two worker threads communicate via lock-free queues; critical for understanding memory flow:

1. **`captureFrameThread()`**: 
   - Dequeues empty V4L2 buffers from pre-allocated pool (`m_v4l2_input_buffer_Q`)
   - Blocks on `VIDIOC_DQBUF` to wait for ISP-filled frames
   - Copies V4L2 payload into heap buffer (shared_ptr<uint8_t>)
   - Pushes to `m_capture_to_process_Q`; on error, **must requeue buffer immediately** to avoid deadlock

2. **`processThread()`**:
   - Pops raw V4L2 frame from `m_capture_to_process_Q`
   - Pops preallocated processing buffer (shared_ptr<uint16_t>) from `m_tofi_io_Buffer_Q`
   - **For MP modes (0-1)**: Just copies V4L2 payload to output buffer (ISP already computed depth)
   - **For QMP modes (2-6)**: Calls `TofiCompute()` for deinterleaving and output formatting
   - Pushes processed frame to `m_process_done_Q`; must restore original context pointers before returning buffer

**Critical invariant**: Buffer offsets calculated in `uint16_t*` units, NOT bytes; stride mismatch → heap corruption.

### Project-specific patterns
- **Code style & formatting**: Run `scripts/format.sh` before commit; ClangFormat 14.0 enforced by CI (`doc/code-formatting.md`)
- **Logging**: `#ifdef USE_GLOG` for glog, fallback to `aditof/log.h`; avoid stdout/stderr in SDK core
- **Depth compute library**: Closed-source `libtofi_compute.so` + `libtofi_config.so`; placed in `../libs/` (one level above repo); wrapped with `#ifdef DUAL` for dual-ISP vs. fallback logic
- **CMake organization**: Avoid in-source builds (enforced); SDK flags in `libaditof/cmake/readme.md`; top-level CMake glues submodules + apps
- **Naming convention**: SDK core under `libaditof/sdk/src/cameras/itof-*`; sensor/driver integration under `libaditof/sdk/src/connections/target/` (e.g., `adsd3500_sensor.cpp`, `v4l_buffer_access_interface.h`)

### Integration points
- **V4L2 kernel driver**: `ToF-drivers/` submodule; payload sizes depend on ISP firmware + frame mode
- **Network/IPC**: `libzmq` + `cppzmq` + `protobuf` (all vendored in `libaditof/`) used by `apps/server`; protocol in `apps/server/buffer.proto`
- **Python bindings**: pybind11 wrapper in `bindings/python/aditofpython.cpp`; exposed to `bindings/python/examples/first_frame.py`
- **Reproducible Python**: Bundled `adcam_env/` provides Python 3.10 + numpy + OpenCV; use for CI/examples: `source adcam_env/bin/activate`

### Key files to reference
| Purpose | File(s) |
|---------|---------|
| Frame pipeline logic | `libaditof/sdk/src/connections/target/buffer_processor.cpp` (capture + process threads) |
| Frame data layout | `libaditof/sdk/src/cameras/itof-frame/frame_impl.cpp` (getData, getDataDetails) |
| Sensor driver interface | `libaditof/sdk/src/connections/target/adsd3500_sensor.cpp`, `v4l_buffer_access_interface.h` |
| Example: all modes | `examples/first-frame/main.cpp` (use `-m <mode>` to set frame mode) |
| Build configuration | `CMakeLists.txt` (top-level), `libaditof/cmake/readme.md` |
| Code style | `doc/code-formatting.md` (run `scripts/format.sh` pre-commit) |
| Tests | `tests/README.md` (log format: `@@,binary,PASS/FAIL,LN<line>`) |

### Critical memory & safety gotchas
- **Payload bounds-checking**: Always validate `process_frame.size` before memcpy; V4L2 delivers different payload sizes per mode. See `buffer_processor.cpp` processThread for safe pattern with confidence frame (lines ~570-600).
- **Offset arithmetic**: Offsets in `uint16_t*` units when indexing depth/AB; `reinterpret_cast<float*>()` only for confidence region. Mixing uint16 stride with byte offsets → silent corruption.
- **Queue error recovery**: On `pop()` timeout or memcpy failure, **immediately push buffer back** to source queue to avoid permanent deadlock in multi-threaded pipeline.
- **ToFi context pointers**: `processThread()` modifies `m_tofiComputeContext->p_depth_frame`, etc.; **must restore original pointers before pushing buffer back** (see lines ~550-570 for safe pattern).
- **NVIDIA build flag**: Defaults to `ON` (Jetson target). Host-only builds require `-DNVIDIA=OFF`; some frame modes or ISP features may not work. Check `CMakeLists.txt` for ON_TARGET guard.
- **Vendored libraries**: libzmq, glog, protobuf inside `libaditof/` take precedence; avoid linking system versions.
- **Submodule state**: `ToF-drivers` and `libaditof` are git submodules; always run `git submodule update --init` after clone/checkout.

### Minimal agent contract
When editing:
- **Inputs**: Specific file path + desired behavior (or error log with line number)
- **Outputs**: Focused diffs, preserve existing style/formatting, update examples/tests if behavior changes
- **Validation**: After frame/memory changes, verify no crashes during mode-switching or buffer operations; after CMake changes, confirm build commands in README still valid

