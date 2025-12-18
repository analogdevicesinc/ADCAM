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
import sys
import time
import os

ccb_dir = 'ccb_directory'
ccb_prefix = 'ccb_'

if __name__ == "__main__":

    if len(sys.argv) > 1 :
        if sys.argv[1] in ["--help", "-h"]: 
            print("save_ccb.py usage:")
            print("USB / Local connection: save_ccb.py")
            print("Network connection: save_ccb.py <ip>")
            exit(1)

    cameras = []
    ip = ""
    if len(sys.argv) == 2 :
        ip = sys.argv[1]
        print (f"Looking for camera on network @ {ip}.")
        ip = "ip:" + ip
    elif len(sys.argv) == 1 :
        print (f"Looking for camera on UVC.")
    else :
        print("Too many arguments provided!")
        exit(1)

    dir_path = os.path.join(os.path.dirname( os.path.abspath(__file__)), ccb_dir)
    if os.path.exists(dir_path):
        print(f"The directory {dir_path} already exists.")
    else:
        # Create the directory
        os.makedirs(dir_path)
        print(f"The directory {dir_path} was created.")

    system = tof.System()

    print("SDK version: ", tof.getApiVersion(), " | branch: ", tof.getBranchVersion(), " | commit: ", tof.getCommitVersion())

    status = system.getCameraList(cameras, ip)
    print("system.getCameraList()", status)

    camera1 = cameras[0]

    status = camera1.initialize()
    print(f"camera1.initialize()", status)
    serial_no=''
    status = camera1.readSerialNumber(serial_no, False)
    serial_no = status[1].rstrip('\x00')
    print('Module serial number is: %s' %(serial_no))
    ccb_prefix = ccb_prefix+serial_no+'_'

    camDetails = tof.CameraDetails()
    status = camera1.getDetails(camDetails)
    print("camera1.getDetails()", status)
    print("camera1 details:", "id:", camDetails.cameraId )
    print("connection: ", camDetails.connection)
    print("mode: ", camDetails.mode)
    print("mindepth: ", camDetails.minDepth)
    print("maxdepth: ", camDetails.maxDepth)

    print("Intrinsic Parameters: ")
    # Get intrinsic parameters from camera
    intrinsicParameters = camDetails.intrinsics
    print("fx: ",intrinsicParameters.fx)
    print("fy: ",intrinsicParameters.fy)
    print("cx: ",intrinsicParameters.cx)
    print("cy: ",intrinsicParameters.cy)
    print("codx: ",intrinsicParameters.codx)
    print("cody: ",intrinsicParameters.cody)
    print("k1: ",intrinsicParameters.k1)
    print("k2: ",intrinsicParameters.k2)
    print("k3: ",intrinsicParameters.k3)
    print("k4: ",intrinsicParameters.k4)
    print("k5: ",intrinsicParameters.k5)
    print("k6: ",intrinsicParameters.k6)
    print("p2: ",intrinsicParameters.p2)
    print("p1: ",intrinsicParameters.p1)

    ccb_filename = ccb_prefix + time.strftime('%y%m%d%H%M') + '.ccb'
    
    status = camera1.saveModuleCCB(os.path.join(dir_path,ccb_filename))
    print("camera1.saveModuleCCB()", status)

    file_exists = os.path.isfile(os.path.join(dir_path, ccb_filename))
    if (file_exists):
        print(f"{ccb_filename} saved in {dir_path}")
    else:
        print("ccb not saved")
        
