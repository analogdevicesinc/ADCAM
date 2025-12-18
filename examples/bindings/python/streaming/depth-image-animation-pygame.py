#
# MIT License
#
# Copyright (c) 2025 Analog Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

import aditofpython as tof
import numpy as np
import pygame
import sys
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import os

mode = 3

def help():
    print(f"{sys.argv[0]} usage:")
    print(f"Target: {sys.argv[0]} <mode number>")
    print(f"Network connection: {sys.argv[0]} <mode number> <ip>")
    print()
    print("For example:")
    print(f"python {sys.argv[0]} 0 192.168.56.1")
    exit(1)

if len(sys.argv) < 2 or len(sys.argv) > 3 or sys.argv[1] == "--help" or sys.argv[1] == "-h" :
    help()
    exit(-1)

jet_colormap = plt.get_cmap('jet')

system = tof.System()

print("SDK version: ", tof.getApiVersion(), " | branch: ", tof.getBranchVersion(), " | commit: ", tof.getCommitVersion())

cameras = []
ip = ""
if len(sys.argv) == 3:
    mode = sys.argv[1]
    ip = sys.argv[2]
    print (f"Looking for camera on network @ {ip}.")
    ip = "ip:" + ip
elif len(sys.argv) == 2:
    mode = sys.argv[1]
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

status = camera1.initialize()
print("camera1.initialize()", status)

modes = []
status = camera1.getAvailableModes(modes)
print("camera1.getAvailableModes()", status)
print(modes)

if int(mode) not in modes:
    print(f"Error: Unknown mode - {mode}")
    help()
    exit(-3)

camDetails = tof.CameraDetails()
status = camera1.getDetails(camDetails)
print("camera1.getDetails()", status)
print("camera1 details:", "id:", camDetails.cameraId, "connection:", camDetails.connection)

status = camera1.setMode(int(mode))
print("camera1.setMode()", status)

status = camera1.start()
print("camera1.start()", status)

sensor = camera1.getSensor()
modeDetails = tof.DepthSensorModeDetails()
status = sensor.getModeDetails(int(mode),modeDetails)
    
def normalize(image_scalar, width, height):
    image_scalar_norm = image_scalar / image_scalar.max()

    # Apply the colormap to the scalar image to obtain an RGB image
    image_rgb = jet_colormap(image_scalar_norm)
        
    surface = (image_rgb[:, :, :3] * 255).astype(np.uint8)
    return surface

def animate():
    frame = tof.Frame()
    status = camera1.requestFrame(frame)
    frameDataDetails = tof.FrameDataDetails()
    status = frame.getDataDetails("depth", frameDataDetails)
    image = np.asarray(frame.getData("depth"))
    image = np.rot90(image)
    return pygame.surfarray.make_surface(normalize(image, frameDataDetails.width, frameDataDetails.height))
    
def main():
    pygame.init()
    window_size = (modeDetails.baseResolutionWidth, modeDetails.baseResolutionHeight)
    screen = pygame.display.set_mode(window_size)

    # display the animation
    done = False
    i = 0
    while not done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                done = True

        screen.blit(animate(), (0, 0))
        pygame.display.flip()

    # quit Pygame
    pygame.quit()

    status = camera1.stop()
    
main()
