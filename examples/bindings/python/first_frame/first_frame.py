#
# BSD 3-Clause License
#
# Copyright (c) 2019, Analog Devices, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
import aditofpython as tof
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import sys
import os
import struct

def help():
    print(f"{sys.argv[0]} usage:")
    print(f"Target: {sys.argv[0]} <mode number> <show frames(0/1)>")
    print(f"Network connection: {sys.argv[0]} <mode number> <ip> <show frames (0/1)>")
    print()
    print("For example:")
    print(f"python {sys.argv[0]} 0 192.168.56.1 0")
    exit(1)

if len(sys.argv) < 3 or len(sys.argv) > 4 or sys.argv[1] == "--help" or sys.argv[1] == "-h" :
    help()
    exit(-1)

system = tof.System()

print("SDK version: ", tof.getApiVersion(), " | branch: ", tof.getBranchVersion(), " | commit: ", tof.getCommitVersion())

mode = 0
cameras = []
isdisplay = 1
ip = ""
if len(sys.argv) == 4:
    mode = sys.argv[1]
    ip = sys.argv[2]
    print (f"Looking for camera on network @ {ip}.")
    ip = "ip:" + ip
    isdisplay = sys.argv[3]
elif len(sys.argv) == 3:
    mode = sys.argv[1]
    isdisplay = sys.argv[2]
    print (f"Looking for camera on Target.")
else :
    print("Too many arguments provided!")
    exit(-2)
if ip:
    status = system.getCameraList(cameras, ip)
else:
    status = system.getCameraList(cameras)
print("system.getCameraList()", status)

camera1 = cameras[0]

#create callback and register it to the interrupt routine
def callbackFunction(callbackStatus):
    print("Running the python callback for which the status of ADSD3500 has been forwarded. ADSD3500 status = ", callbackStatus)

sensor = camera1.getSensor()
status = sensor.adsd3500_register_interrupt_callback(callbackFunction)

status = camera1.initialize()
print("camera1.initialize()", status)

modes = []
status = camera1.getAvailableModes(modes)
print("camera1.getAvailableModes()", status)
print(modes)

if int(mode) not in modes:
    print(f"Error: Unknown mode - {mode}")
    exit(-3)

camDetails = tof.CameraDetails()
status = camera1.getDetails(camDetails)
print("camera1.getDetails()", status)
print("camera1 details:", "id:", camDetails.cameraId, "connection:", camDetails.connection)

status = camera1.setMode(int(mode))
print("camera1.setMode(",mode,")", status)

# Example of getting/modifying/setting the current ADSD3500 parameters
# status, currentFrameProcessParams = camera1.getFrameProcessParams()
# currentFrameProcessParams["ab_thresh_min"] = "4"
# camera1.setFrameProcessParams(currentFrameProcessParams)

# Example of configuring the Dynamic Mode Switching
# The expected sequence of frame is: mode2, mode2, mode2, mode3, mode2, ...
# camera1.adsd3500setEnableDynamicModeSwitching(True)
# camera1.adsds3500setDynamicModeSwitchingSequence([(2, 3), (3, 1)])

status = camera1.start()
print("camera1.start()", status)

frame = tof.Frame()

status = camera1.requestFrame(frame)
print("camera1.requestFrame()", status)

frameDataDetails = tof.FrameDataDetails()
status = frame.getDataDetails("depth", frameDataDetails)
print("frame.getDataDetails()", status)
print("depth frame details:", "width:", frameDataDetails.width, "height:", frameDataDetails.height, "type:", frameDataDetails.type)

status = camera1.stop()
print("camera1.stop()", status)

# Get the depth frame
image_depth = np.array(frame.getData("depth"), copy=False)
# Get the AB frame
image_ab = np.array(frame.getData("ab"), copy=False)
# Get the confidence frame
image_conf = np.array(frame.getData("conf"), copy=False)

image_xyz= np.array(frame.getData("xyz"), copy=False)

if ((frameDataDetails.width != 1024 and frameDataDetails.height != 1024)):
    image_conf2 = image_conf.flatten()
    count = 0
    final_conf = np.zeros(frameDataDetails.width*frameDataDetails.height*4)
    for i in range(frameDataDetails.width*(frameDataDetails.height // 2)):
        packed_float = struct.pack('f', image_conf2[i])

    # Unpack the bytes into four uint8 values
        uint8_values = struct.unpack('2H', packed_float)
        array_data = np.array(uint8_values)
        for j in range(2):
            final_conf[count+j] = array_data[j]
            #print(j)
        count = count + 2
    image_conf = np.reshape(final_conf[frameDataDetails.width*frameDataDetails.height*0:frameDataDetails.width*frameDataDetails.height*1], \
                            [frameDataDetails.height,frameDataDetails.width])

metadata = tof.Metadata
status, metadata = frame.getMetadataStruct()

#Unregister callback
status = sensor.adsd3500_unregister_interrupt_callback(callbackFunction)

# Metadata values
sensor_temp = metadata.sensorTemperature
laser_temp = metadata.laserTemperature
frame_num = metadata.frameNumber
imager_mode = metadata.imagerMode

print("Sensor temperature from metadata: ", sensor_temp)
print("Laser temperature from metadata: ", laser_temp)
print("Frame number from metadata: ", frame_num)
print("Mode from metadata: ", imager_mode)

if int(isdisplay)==1:
    # Create a figure with 5 subplots (3 images + 1 metadata text + 1 point cloud)
    fig = plt.figure(figsize=(20, 8))
    
    # Plot the depth image
    ax1 = fig.add_subplot(2, 3, 1)
    im1 = ax1.imshow(image_depth, cmap='jet')
    ax1.set_title("Depth Image")
    ax1.axis("off")
    fig.colorbar(im1, ax=ax1)

    # Plot the AB image
    ax2 = fig.add_subplot(2, 3, 2)
    im2 = ax2.imshow(image_ab, cmap='gray')
    ax2.set_title("AB Image")
    ax2.axis("off")
    fig.colorbar(im2, ax=ax2)

    # Plot the Confidence image
    ax3 = fig.add_subplot(2, 3, 3)
    im3 = ax3.imshow(image_conf, cmap='gray')
    ax3.set_title("Confidence Image")
    ax3.axis("off")
    fig.colorbar(im3, ax=ax3)

    # Metadata as text in the fourth subplot
    ax4 = fig.add_subplot(2, 3, 4)
    ax4.axis("off")  # Hide axes
    metadata_text = (
        f"Sensor Temp: {sensor_temp}°C\n"
        f"Laser Temp: {laser_temp}°C\n"
        f"Frame #: {frame_num}\n"
        f"Mode: {imager_mode}"
    )
    ax4.text(0.1, 0.5, metadata_text, fontsize=12, verticalalignment='center')

    # Point cloud visualization
    ax5 = fig.add_subplot(2, 3, (5, 6), projection='3d')
    
    # Reshape XYZ data - assuming it's in format [x, y, z, x, y, z, ...]
    # XYZ data is int16 (signed 16-bit), with each coordinate being one int16 value
    print(f"XYZ data shape: {image_xyz.shape}, dtype: {image_xyz.dtype}")
    
    # Ensure data is interpreted as signed int16
    if image_xyz.dtype != np.int16:
        image_xyz = image_xyz.view(np.int16)
    
    xyz_reshaped = image_xyz.reshape(-1, 3)
    
    # Extract X, Y, Z coordinates
    x = xyz_reshaped[:, 0].astype(np.int16)
    y = xyz_reshaped[:, 1].astype(np.int16)
    z = xyz_reshaped[:, 2].astype(np.int16)
    
    print(f"X range: [{x.min()}, {x.max()}], Y range: [{y.min()}, {y.max()}], Z range: [{z.min()}, {z.max()}]")
    
    # Filter out invalid points (z == 0)
    valid_mask = z != 0
    x_valid = x[valid_mask]
    y_valid = y[valid_mask]
    z_valid = z[valid_mask]
    
    # Downsample for better performance (every 10th point)
    downsample_factor = 10
    x_display = x_valid[::downsample_factor]
    y_display = y_valid[::downsample_factor]
    z_display = z_valid[::downsample_factor]
    
    # Create point cloud scatter plot colored by depth (Z)
    scatter = ax5.scatter(x_display, y_display, z_display, 
                         c=z_display, cmap='jet', 
                         s=1, marker='.')
    
    ax5.set_xlabel('X')
    ax5.set_ylabel('Y')
    ax5.set_zlabel('Z (Depth)')
    ax5.set_title("Point Cloud")
    fig.colorbar(scatter, ax=ax5, shrink=0.5)
    
    # Set equal aspect ratio for better visualization
    max_range = np.array([x_display.max()-x_display.min(), 
                         y_display.max()-y_display.min(), 
                         z_display.max()-z_display.min()]).max() / 2.0
    mid_x = (x_display.max()+x_display.min()) * 0.5
    mid_y = (y_display.max()+y_display.min()) * 0.5
    mid_z = (z_display.max()+z_display.min()) * 0.5
    ax5.set_xlim(mid_x - max_range, mid_x + max_range)
    ax5.set_ylim(mid_y - max_range, mid_y + max_range)
    ax5.set_zlim(mid_z - max_range, mid_z + max_range)

    plt.tight_layout()
    plt.show()
else:
    # dump the files
    image_depth.tofile("depth_mode_" + str(mode) + ".bin")
    image_ab.tofile("ab_mode_" + str(mode) + ".bin")
    image_conf.tofile("conf_mode_" + str(mode) + ".bin")
    image_xyz.tofile("xyz_mode_" + str(mode) + ".bin")


