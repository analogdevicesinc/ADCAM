# ADCAM System Test Implementation - Quick Reference

## What Was Implemented

A complete GoogleTest-based system test framework for ADCAM that runs in Docker containers, based on the system_test_agent.md template.

## Files Created

### Test Infrastructure
- `tests/sdk/include/test_utils.h` - Test utility header with TestRunner class
- `tests/sdk/src/test_utils.cpp` - Test utility implementations
- `tests/sdk/system/system-first_frame_test.cpp` - Sample system tests for camera initialization and frame capture

### Build Configuration
- `tests/sdk/CMakeLists.txt` - Updated with GoogleTest integration
- Added test utilities library and test executable registration

### Test Configuration
- `tests/test_csvs/system_test_list.csv` - CSV-based test suite configuration
  - Basic system tests (camera discovery, initialization)
  - Frame capture tests (single, multiple frames)
  - Frame mode tests (all MP and QMP modes 0-6)
  - Stress tests (repeated captures)

### Docker Infrastructure
- `tests/docker/Dockerfile.test` - Ubuntu 22.04-based test container with all ADCAM dependencies
- `tests/docker/docker-compose.yml` - Service configuration for test environment
- `tests/docker/build.sh` - Build script with ToFi library handling
- `tests/docker/run_tests.sh` - CSV-driven test executor
- `tests/docker/cleanup.sh` - Docker resource cleanup

### Test Execution
- `tests/start_tests.sh` - Main wrapper script with options for build, repeat, cleanup

### Documentation
- `tests/README.md` - Comprehensive testing guide with examples

## Quick Start Commands

### 1. Build Docker Image
```bash
cd tests/docker
bash ./build.sh
```

**Requirements**:
- Docker installed and running
- ToFi libraries at `../libs/` (libtofi_compute.so, libtofi_config.so)

### 2. Run All System Tests
```bash
cd tests
bash ./start_tests.sh -f test_csvs/system_test_list.csv -o ./test-results
```

### 3. Run with Options
```bash
# Force rebuild Docker image
bash ./start_tests.sh -f test_csvs/system_test_list.csv -o ./results -b

# Run tests 3 times
bash ./start_tests.sh -f test_csvs/system_test_list.csv -o ./results -r 3

# Use 8 parallel jobs, cleanup after
bash ./start_tests.sh -f test_csvs/system_test_list.csv -o ./results -j 8 -c
```

## Test Configuration (CSV)

Edit `tests/test_csvs/system_test_list.csv` to customize tests:

```csv
TestID,Execute,TestName,TestParameters
SY000001,Y,system-first_frame_test,
SY000002,Y,system-first_frame_test,--gtest_filter=FirstFrameTest.CaptureFrame
SY000030,Y,system-first_frame_test,--mode=0 --gtest_repeat=3
```

**Columns**:
- `TestID`: Unique identifier (SY=System, UN=Unit, FN=Functional)
- `Execute`: Y to run, N to skip
- `TestName`: Executable name (without path)
- `TestParameters`: GoogleTest flags + ADCAM custom args

**Common Flags**:
- `--gtest_filter=<pattern>`: Run specific tests
- `--gtest_repeat=N`: Repeat N times
- `--mode=<0-6>`: Frame mode (0-1=MP 1024×1024, 2-6=QMP 512×512)
- `--device=<addr>`: Device address
- `--config=<path>`: Config file path

## Test Output

Results saved to `<output_path>_<timestamp>/`:
```
test-results_20260202_120000/
├── test_summary.txt          # Overall summary
├── SY000001_run1.log        # Individual test logs
├── SY000001_run1.json       # GoogleTest JSON results
└── ...
```

## Key Features

✅ **Isolated Environment**: Docker container with all dependencies  
✅ **Reproducible Builds**: Clean build each time  
✅ **CSV Configuration**: Easy test suite management  
✅ **Multiple Runs**: Stress testing with --repeat  
✅ **GoogleTest Integration**: Standard test framework  
✅ **Frame Mode Testing**: All ADCAM modes (0-6)  
✅ **Detailed Results**: JSON + logs for each test  
✅ **Exit Codes**: 0=pass, 1=fail for CI integration  

## Frame Modes Reference

| Mode | Type | Resolution | ISP Behavior |
|------|------|------------|--------------|
| 0-1  | MP   | 1024×1024  | ISP computes depth on-chip |
| 2-6  | QMP  | 512×512    | ISP pre-computed depth + confidence |

## Adding New Tests

1. **Create test file**: `tests/sdk/system/system-my_test.cpp`
2. **Update CMakeLists.txt**: Add `add_adcam_test(system-my_test ...)`
3. **Add to CSV**: `SY100001,Y,system-my_test,`
4. **Rebuild Docker**: `cd tests/docker && bash ./build.sh`
5. **Run**: `cd tests && bash ./start_tests.sh -f test_csvs/system_test_list.csv -o ./results`

## Troubleshooting

### Docker Build Fails
- Check ToFi libraries at `../libs/`
- Ensure sufficient disk space
- Try `--no-cache` option

### Test Hangs
- Check hardware connection
- Use `GTEST_SKIP()` for hardware-unavailable cases
- Increase timeout in CMakeLists.txt

### Library Not Found
- Verify ToFi libraries copied to Docker
- Check `LD_LIBRARY_PATH` includes `/workspace/libs`
- Mount libs at runtime: `-v $(pwd)/../../libs:/workspace/libs:ro`

## Next Steps

1. **Run Initial Tests**: Verify setup with basic test suite
2. **Add Hardware Tests**: Create tests requiring actual ADSD3500 hardware
3. **Extend CSV**: Add more test scenarios (stress, performance, edge cases)
4. **CI Integration**: Add to azure-pipelines.yml for automated testing
5. **Custom Tests**: Create domain-specific tests for your use cases

## References

- Full documentation: [tests/README.md](tests/README.md)
- System test template: [.github/agents/system_test_agent.md](.github/agents/system_test_agent.md)
- GoogleTest: https://google.github.io/googletest/
- ADCAM architecture: [libaditof/README.md](libaditof/README.md)
