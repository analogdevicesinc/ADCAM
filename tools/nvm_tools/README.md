# nvm_tools

This project contains utilities for NVM and CCB read/write operations, along with firmware update support for the ADSD3500 device.

## Prerequisites

- CMake version 3.0 or later
- GNU Make
- A supported Linux environment
- Required development libraries and headers for your target platform

## Directory Structure

- `NVM_WRITE/` – NVM write utility
- `NVM_READ/` – NVM read utility
- `CCB_WRITE/` – CCB write utility
- `CCB_READ/` – CCB read utility
- `adsd3500_fw_update/` – ADSD3500 firmware update tool

## Build Instructions (NVIDIA Platform)

Follow the steps below to build the project for the NVIDIA Jetson Orin nano platform.

```bash
mkdir build
cd build
cmake -DNVIDIA=ON ..
make
```

## Build Instructions (RPI Platform)

Follow the steps below to build the project for the Raspberry Pi 5 platform.

```bash
mkdir build
cd build
cmake -DRPI=ON ..
make
```

## Clean Build (Recommended)

Before switching platforms or rebuilding from scratch, perform a clean build:

```bash
rm -rf build
```
