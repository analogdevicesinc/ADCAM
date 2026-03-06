#### Network Build

*Jetson Orin Nano Dev Kit or Raspberry Pi* <-----at least 1 Gbps Ethernet-----> *Windows WSL2 Ubuntu 22.04 w/GPU Acceleration*

While this is skewed towards WSL2 aspects of this can be applied to another Linux host system in general. Where we currently recommend Ubuntu 22.04 as the host to avoid dependency and build issue due to differing tools versions.

##### Jetson Orin Nano Dev Kit or Raspberry Pi as a Network Device

```console
git clone https://github.com/analogdevicesinc/ADCAM.git
cd ADCAM
git submodule update --init
git checkout <branch or tag>
cd libaditof
git checkout <branch or tag>
cd ..
mkdir build
cd build
cmake -DWITH_NETWORK=ON -DCMAKE_BUILD_TYPE=Release ..
cmake --build . -j 6
cd apps/server
sudo ./aditof-server
```

##### Windows WSL2 Host

```console
sudo apt update
sudo apt install cmake g++ \
     libopencv-dev \
     libgl1-mesa-dev libglfw3-dev \
     doxygen graphviz \
     libxinerama-dev \
     libxcursor-dev \
     libxi-dev \
     libxrandr-dev \
     python3.10-dev \
     mesa-utils
```

```console
git clone https://github.com/analogdevicesinc/ADCAM.git
cd ADCAM
git submodule update --init
git checkout <branch or tag>
cd libaditof
git checkout <branch or tag>
cd ..
mkdir build
cd build
cmake -DWITH_PLATFORM=WSL2 -DWSL2_GL_VERSION=4.6 -DWITH_NETWORK=ON ..
cmake --build . -j 6
```

For the best performance:
1. Use a direct Ethernet connection.
2. For ADIToFGUI, enable GPU usage in WSL2 and use a high-performance GPU. The instructions below may help, if not Google Search AI can assist.

On Windows 11, enable GPU for WSL2, add the following *%UserProfile%\.wslconfig*.
```
[wsl2]
gpu=true
```
Add the following to the bottom of *~./bashrc*.
```
export LIBGL_ALWAYS_SOFTWARE=0
export MESA_GL_VERSION_OVERRIDE=4.6
export MESA_GLSL_VERSION_OVERRIDE=460
export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
```

Before you get started:

1. Set the Ethernet IP Address on the NVIDIA or Raspberry Pi.
2. Set the IP address on Windows. See [here](/tools/host/powershell/README.md).
3. Update tof-tools.config in the ADIToFGUI folder. See *ADIToFGUI (C++) -> Configuring ADIToFGUI* section of [ADCAM-CameraKit-020.md](/doc/user-guide/ADCAM-CameraKit-020.md#configuring-aditofgui).
