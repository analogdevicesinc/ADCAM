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
import argparse
import numpy as np
import matplotlib.pyplot as plt
import sys
import os
import time

def help():
    print(f"{sys.argv[0]} usage:")
    print(f"Target: {sys.argv[0]} <mode number>")
    print(f"Network connection: {sys.argv[0]} <mode number> <ip>")
    print()
    print("For example:")
    print(f"python {sys.argv[0]} 0 192.168.56.1")
    exit(1)

mode_help_message = """Valid mode (-m) options are:
        0: short-range native;
        1: long-range native;
        2: short-range Qnative;
        3: long-range Qnative
        4: pcm-native;
        5: long-range mixed;
        6: short-range mixed;
        
        Note: --m argument supports index (Default: 0) """
Ip = ''
imager_configurations = ["standard", "standard-raw", "custom", "custom-raw"]
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Script to run data collect python script')
    parser.add_argument('-f', dest='folder', default='./',
                        help='output folder [default: ./]', metavar = '<folder>')
    parser.add_argument('-n', dest='ncapture', type=int, default=1,
                        help='number of frame captured[default: 1]', metavar = '<ncapture>')
    parser.add_argument('-m', dest='mode',  default='0',
                        help=mode_help_message, metavar = '<mode>')
    parser.add_argument('-wt', dest='warmup_time', type=int,
                        default=0, help='warmup time in seconds[default: 0]', metavar = '<warmup>')
    parser.add_argument('-ccb', type=str, 
                        help='The path to store CCB content', metavar='<FILE>')                    
    parser.add_argument('-ip', default=Ip, help='camera IP[default: 192.168.56.1]', metavar = '<ip>')
    parser.add_argument('-fw', dest='firmware', help='Adsd3500 firmware file', metavar = '<firmware>')
    parser.add_argument('-s', '--split', action="store_true", dest='split', 
                        help='Save each frame into a separate file (Debug)')
    parser.add_argument('-t', '--netlinktest', action="store_true", 
                        dest='netlinktest', help='Puts server on target in test mode (Debug)')
    parser.add_argument('-st', '--singlethread', action="store_true", 
                        dest='singlethread', help='Store the frame to file using same thread')
    parser.add_argument('-ic', type=str, help='Select imager configuration. By default is standard.',
                        metavar='<imager-configuration>', default = "standard", 
                        choices=imager_configurations)  
    parser.add_argument('-scf', type=str, help='Save current configuration to json file', 
                        metavar='<save-configuration-file>')  
    parser.add_argument('-lcf', type=str, help='Load custom configuration to json file', 
                        metavar='<load-configuration-file>')  
    args = parser.parse_args()


    print("SDK version: ", tof.getApiVersion(), " | branch: ", tof.getBranchVersion(), " | commit: ", tof.getCommitVersion())

    #check if directory output folder exist, if not, create one
    if (args.folder):
        if not os.path.isdir(args.folder):
            os.mkdir(args.folder)
            print("output folder created")

    saveToSingleFile = True
    if (args.split):
        saveToSingleFile = False
        
    samethread = False
    if (args.singlethread):
        samethread = True
    
    saveconfigurationFile = False
    saveConfigFileName = args.scf
    if(saveConfigFileName):
        if not saveConfigFileName.endswith(".json"):
            saveConfigFileName = saveConfigFileName + ".json"
        saveconfigurationFile = True 

    loadconfigurationFile = False
    loadConfigFileName = args.lcf
    if(loadConfigFileName):
        if not loadConfigFileName.endswith(".json"):
            loadConfigFileName = loadConfigFileName + ".json"
        loadconfigurationFile = True 

    print ("Output folder: ", args.folder)
    print ("Mode: ", args.mode )
    print ("Number of frames: ", args.ncapture)
    print ("Warm Up time is: ", args.warmup_time, "seconds")
    print ("Configuration is: ", args.ic)
    
    if (args.ip):
        print("Ip address is: ", args.ip)
    
    if (args.firmware):
        print("Firmware file is: ", args.firmware)
    
    if (args.ccb):
        print("Path to store CCB content: " , args.ccb)

    try:
        system = tof.System()
    except:
        print("Failed to create system")

    cameras = []


    if args.ip:
        ip = "ip:" + args.ip
        if args.netlinktest:
            ip += ":netlinktest"
        status = system.getCameraList(cameras, args.ip)
    else:
        status = system.getCameraList(cameras)

    print("system.getCameraList(): ", status)
    if status != tof.Status.Ok:
        sys.exit("No cameras found")


    camera1 = cameras[0]
    mode = args.mode

    #create callback and register it to the interrupt routine
    def callbackFunction(callbackStatus):
        print("Running the python callback for which the status of ADSD3500 has been forwarded. ADSD3500 status = ", callbackStatus)

    sensor = camera1.getSensor()
    status = sensor.adsd3500_register_interrupt_callback(callbackFunction)

    status = camera1.initialize()
    if status != tof.Status.Ok:
        sys.exit("Could not initialize camera!")

    status = camera1.setSensorConfiguration(args.ic)
    if status != tof.Status.Ok:
        print("Could not configure camera with ", args.ic)
    else:
        print("Configure camera with ", args.ic)  
    
    if saveconfigurationFile:
        status = camera1.saveDepthParamsToJsonFile(saveConfigFileName)
        if status != tof.Status.Ok:
            print("Could not save current configuration info to ", saveConfigFileName)
        else:
            print("Current configuration info saved to file ", saveConfigFileName)

    if loadconfigurationFile:
        status = camera1.loadDepthParamsFromJsonFile(loadConfigFileName, int(args.mode))
        if status != tof.Status.Ok:
            print("Could not load configuration info from ", loadConfigFileName)
        else:
            print("Current configuration loaded from ", loadConfigFileName)

    cam_details = tof.CameraDetails()
    status = camera1.getDetails(cam_details)
    print('camera1.getDetails()', status)
    
    print ('SD card image version: ', cam_details.sdCardImageVersion)
    print ("Kernel version: ", cam_details.kernelVersion)
    print ("U-Boot version: ", cam_details.uBootVersion)

    if (args.firmware):
        if not os.path.isfile(args.firmware):
            sys.exit(f"{args.firmware} does not exists")
        status = camera1.adsd3500UpdateFirmware(args.firmware)
        if status != tof.Status.Ok:
            print('Could not update the Adsd3500 firmware')
        else:
            print('Please reboot the board')

    # Get frame type
    modes = []
    status = camera1.getAvailableModes(modes)
    if status != tof.Status.Ok or len(modes) == 0:
        sys.exit('Could not acquire available modes')

    #check mode, accepts both string and index
    if (args.mode):
        if int(args.mode) not in modes:
            sys.exit(f'{args.mode} is not a valid mode')
        else:
            mode = int(args.mode)
            print(f'Mode: {mode}')


    status = camera1.setMode(int(mode))
    if status != tof.Status.Ok:
        sys.exit("Could not set camera mode!")

    if (args.ccb):
        status = camera1.saveModuleCCB(args.ccb)
        print("camera1.saveModuleCCB()", status)

    status = camera1.start()
    if status != tof.Status.Ok:
        sys.exit("Could not start camera!")
   
    frame = tof.Frame()
    frameDetails = tof.FrameDetails()
    
    warmup_start = time.monotonic()
    
    warmup_time = args.warmup_time
    #Wait until the warmup time is finished
    if warmup_time > 0:
        while time.monotonic() - warmup_start < warmup_time:
            #Request a frame from the camera object
            status = camera1.requestFrame(frame)
            if status != tof.Status.Ok:
                sys.exit("Could not request frame!")

    saveToSingleFile = not args.split
    
    frameSaver = tof.FrameHandler()
    frameSaver.storeFramesToSingleFile(saveToSingleFile)
    frameSaver.setOutputFilePath(args.folder)

    print(f'Requesting {args.ncapture} frames!')
    
    #start high resolution timer
    start_time = time.perf_counter_ns()
    
    #Request the frames for the respective mode
    for loopcount in range(args.ncapture):
        
        status = camera1.requestFrame(frame)
        if status != tof.Status.Ok:
            sys.exit("Could not request frame!")
        
        if args.netlinktest:
            continue
        
        if not samethread:
            frameSaver.saveFrameToFileMultithread(frame)
        else:
            frameSaver.saveFrameToFile(frame)
        
    end_time = time.perf_counter_ns()
    total_time = (end_time - start_time) / 1e9
    
    if total_time > 0:
        measured_fps = args.ncapture / total_time
        print("Measured FPS: ", format(measured_fps, '.5f'))    

    status = camera1.stop()
    if status != tof.Status.Ok:
        sys.exit("Error stopping camera!")