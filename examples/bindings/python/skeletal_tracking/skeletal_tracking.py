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
import cv2 as cv
import argparse
from enum import Enum
import sys
import mediapipe as mp

ip = "" # Set to "192.168.56.1" if networking is used.
mode = 2

inWidth = 300
inHeight = 300
WHRatio = inWidth / float(inHeight)
inScaleFactor = 0.007843
meanVal = 127.5
thr = 0.2
WINDOW_NAME = "Display Objects"
WINDOW_NAME_DEPTH = "Display Objects Depth"


# Initialize Mediapipe
mp_pose = mp.solutions.pose
pose = mp_pose.Pose()

mp_hands = mp.solutions.hands
hands = mp_hands.Hands()

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description='Script to run Skeletal tracking ')
    parser.add_argument("--ip", default=ip, help="IP address of ToF Device")

    args = parser.parse_args()

    system = tof.System()

    cameras = []
    if args.ip:
        status = system.getCameraList(cameras, "ip:"+ args.ip)
    else:
        status = system.getCameraList(cameras)
    if not status:
        print("system.getCameraList(): ", status)

    camera1 = cameras[0]

    status = camera1.initialize()
    if not status:
        print("camera1.initialize() failed with status: ", status)

    modes = []
    status = camera1.getAvailableModes(modes)
    if not status:
        print("system.getAvailableModes() failed with status: ", status)
        
    status = camera1.setMode(mode)
    if not status:
        print("camera1.setMode() failed with status:", status)
    
    status = camera1.start()
    if not status:
        print("camera1.start() failed with status:", status)
   
    camDetails = tof.CameraDetails()
    status = camera1.getDetails(camDetails)
    if not status:
        print("system.getDetails() failed with status: ", status)

    # Enable noise reduction for better results
    smallSignalThreshold = 100

    camera_range = 5000
    bitCount = 9
    frame = tof.Frame()

    max_value_of_IR_pixel = 2 ** bitCount - 1
    distance_scale_ir = 255.0 / max_value_of_IR_pixel
    distance_scale = 255.0 / camera_range

    while True:
            
        # Capture frame-by-frame
        status = camera1.requestFrame(frame)
        if not status:
            print("camera1.requestFrame() failed with status: ", status)

        ab_map = np.asarray(frame.getData("ab"), dtype="uint16")

        # Creation of the IR image
        ab_map = distance_scale_ir * ab_map
        ab_map = np.uint8(ab_map)
        ab_map = cv.flip(ab_map, 1)
        ab_map_rgb = cv.cvtColor(ab_map, cv.COLOR_GRAY2RGB)  
        ab_map_bgr = cv.cvtColor(ab_map_rgb, cv.COLOR_RGB2BGR)
        
        # Process the frame with Mediapipe Pose and Hands
        results_pose = pose.process(ab_map_rgb)
        results_hands = hands.process(ab_map_rgb)
        
        # Check if any pose is detected
        if results_pose.pose_landmarks:
            # Draw connections between landmarks
            mp.solutions.drawing_utils.draw_landmarks(ab_map_bgr, results_pose.pose_landmarks, mp_pose.POSE_CONNECTIONS)
        
        # Check if any hand is detected
        if results_hands.multi_hand_landmarks:
            for hand_landmarks in results_hands.multi_hand_landmarks:
                for landmark in hand_landmarks.landmark:
                    x = int(landmark.x * ab_map_bgr.shape[1])
                    y = int(landmark.y * ab_map_bgr.shape[0])
                    z = cv.circle(ab_map_bgr, (x, y), 4, (0, 255, 0), -1)

        cv.namedWindow(WINDOW_NAME, cv.WINDOW_AUTOSIZE)
        cv.imshow(WINDOW_NAME, ab_map_bgr)

        if cv.waitKey(1) >= 0:
            break
            
    camera1.stop()
