#
# MIT License
#
# Copyright (c) 2026 Analog Devices, Inc.
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
import numpy as np
import sys
import argparse
import time
import os
from dataclasses import dataclass

minV = 0
maxV = 7000

VALID_MODES_BY_IMAGER = {
    "mp": [0, 2, 5],
    "vga": [0, 2, 5, 8],
}


@dataclass
class AppConfig:
    imager: str
    mode_a: int
    mode_b: int
    fps: int
    ip: str
    config_path: str
    dry_run: bool


def positive_int(value):
    fps_value = int(value)
    if fps_value <= 0:
        raise argparse.ArgumentTypeError("fps must be a positive integer")
    return fps_value


def build_parser():
    parser = argparse.ArgumentParser(
        description="Dynamic mode switch viewer",
        usage="%(prog)s <imager>,<mode> [--ip <ip>] [--config <config.json>] [--fps <fps>] [--dry-run]"
    )
    parser.add_argument(
        "imager_mode",
        help="Imager and mode in format: imager,mode\n"
             "  Valid MP: mp,0 mp,2 mp,5\n"
             "  Valid VGA: vga,0 vga,2 vga,5 vga,8\n"
    )
    parser.add_argument("--ip", "--ipconfig", dest="ip", default="",
                        help="Optional camera IP address (e.g., 192.168.1.10)")
    parser.add_argument("--config", dest="config", default="",
                        help="Optional config JSON file path")
    parser.add_argument("--fps", type=positive_int, default=20,
                        help="Frame rate in fps (default: 20, must be a positive integer)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate arguments and camera setup without opening the pygame window")
    return parser


def parse_imager_mode(parser, imager_mode_value):
    imager_mode_parts = imager_mode_value.split(',')
    if len(imager_mode_parts) != 2:
        parser.error("imager_mode must be in format: imager,mode (e.g., mp,2)")

    imager = imager_mode_parts[0]
    if imager not in VALID_MODES_BY_IMAGER:
        parser.error(f"Invalid imager '{imager}'. Must be one of: {', '.join(VALID_MODES_BY_IMAGER)}")

    try:
        mode_a = int(imager_mode_parts[1])
    except ValueError:
        parser.error(f"Invalid mode '{imager_mode_parts[1]}'. Mode must be an integer")

    valid_modes = VALID_MODES_BY_IMAGER[imager]
    if mode_a not in valid_modes:
        parser.error(
            f"Invalid mode {mode_a} for imager '{imager}'. "
            f"Valid modes: {', '.join(map(str, valid_modes))}"
        )

    return imager, mode_a


def parse_args():
    parser = build_parser()
    args = parser.parse_args()
    imager, mode_a = parse_imager_mode(parser, args.imager_mode)

    config_path = ""
    if args.config:
        print(f"Including config file {args.config}.")
        if not os.path.exists(args.config):
            parser.error(f"Config file {args.config} does not exist")
        config_path = os.path.abspath(args.config)
        print(f"Using config file: {config_path}")

    return AppConfig(
        imager=imager,
        mode_a=mode_a,
        mode_b=mode_a + 1,
        fps=args.fps,
        ip=args.ip,
        config_path=config_path,
        dry_run=args.dry_run,
    )


def get_mode_mapping(config):
    imager = config.imager
    if imager == 'vga':
        modemapping = {
            3: {"height": 256, "width": 320},
            5: {"height": 256, "width": 320},
            6: {"height": 256, "width": 320},
            8: {"height": 256, "width": 320},
            9: {"height": 256, "width": 320},
            0: {"height": 512, "width": 640},
            1: {"height": 512, "width": 640},
            7: {"height": 512, "width": 640},
        }
    else:
        modemapping = {
            2: {"height": 512, "width": 512},
            3: {"height": 512, "width": 512},
            5: {"height": 512, "width": 512},
            6: {"height": 512, "width": 512},
            0: {"width": 1024, "height": 1024},
            1: {"width": 1024, "height": 1024},
        }

    if config.mode_a not in modemapping:
        print(f"Error: Mode {config.mode_a} is not available for imager '{config.imager}'")
        print(f"Available modes: {', '.join(sorted(map(str, modemapping.keys())))}")
        sys.exit(1)

    return modemapping


def get_camera_list(system, ip, tof_module):
    cameras = []
    ip_target = ""
    if ip:
        print(f"Looking for camera on network @ {ip}.")
        ip_target = "ip:" + ip
    else:
        print("Looking for locally connected camera.")

    status = system.getCameraList(cameras, ip_target)
    print("system.getCameraList()", status)
    if status != tof_module.Status.Ok or not cameras:
        sys.exit("Could not find any camera!")
    return cameras


def configure_camera(camera, config, tof_module):
    status = camera.initialize()
    if status != tof_module.Status.Ok:
        sys.exit("Could not initialize camera!")

    cam_details = tof_module.CameraDetails()
    status = camera.getDetails(cam_details)
    if status != tof_module.Status.Ok:
        sys.exit("Could not get camera details!")
    print("camera1.getDetails()", status)
    print('SD card image version: ', cam_details.sdCardImageVersion)
    print("Kernel version: ", cam_details.kernelVersion)
    print("U-Boot version: ", cam_details.uBootVersion)
    print("serial number: ", repr(cam_details.serialNumber))
    serial_number = cam_details.serialNumber.replace('\x00', '').replace(' ', '')
    print("folder serial number: ", serial_number)

    available_modes = []
    if config.config_path:
        print("Loading configuration from JSON file: ", config.config_path)
        status = camera.loadDepthParamsFromJsonFile(config.config_path, int(config.mode_a))
        if status != tof_module.Status.Ok:
            sys.exit("Could not load depth parameters from JSON file!")
    else:
        status = camera.adsd3500SetABinvalidationThreshold(5)
        if status != tof_module.Status.Ok:
            sys.exit("Could not set AB invalidation threshold!")
        status = camera.adsd3500SetConfidenceThreshold(25)
        if status != tof_module.Status.Ok:
            sys.exit("Could not set confidence threshold!")
        status = camera.adsd3500SetRadialThresholdMin(50)
        if status != tof_module.Status.Ok:
            sys.exit("Could not set radial threshold min!")
        status = camera.adsd3500SetRadialThresholdMax(7000)
        if status != tof_module.Status.Ok:
            sys.exit("Could not set radial threshold max!")

    status = camera.getAvailableModes(available_modes)
    if status != tof_module.Status.Ok or len(available_modes) == 0:
        sys.exit('Could not acquire available modes')

    status = camera.setMode(config.mode_a)
    if status != tof_module.Status.Ok:
        sys.exit("Could not set camera mode!")

    # Enable embedded header in AB frame
    status = camera.adsd3500SetEnableMetadatainAB(1)
    if status != tof_module.Status.Ok:
        sys.exit("Could not set embedded header in AB frame!")

    # Set desired frame rate
    status = camera.adsd3500SetFrameRate(config.fps)
    if status != tof_module.Status.Ok:
        sys.exit("Could not set FPS!")

    # Enable dynamic mode switching
    status = camera.adsd3500setEnableDynamicModeSwitching(True)
    if status != tof_module.Status.Ok:
        sys.exit("Error setting dynamic mode switching!")

    sequence = [
        (config.mode_a, 0x01), # Mode A repeat 1 time
        (config.mode_b, 0x01), # Mode B repeat 1 time
    ]
    status = camera.adsds3500setDynamicModeSwitchingSequence(sequence)
    if status != tof_module.Status.Ok:
        sys.exit("Error setting dynamic mode switching!")

    status, dynamic_mode_switch_status = camera.adsd3500GetGenericTemplate(0x0085)
    if status != tof_module.Status.Ok:
        sys.exit("Error setting dynamic mode switching!")
    print('Dynamic Mode Status: ', dynamic_mode_switch_status)


def start_camera(camera, tof_module):
    status = camera.start()
    print("camera1.start()", status)
    if status != tof_module.Status.Ok:
        sys.exit("Could not start camera!")


def stop_camera(camera):
    try:
        camera.stop()
    except Exception:
        pass


def load_tof():
    try:
        import aditofpython as tof
    except ModuleNotFoundError as exc:
        sys.exit(f"Could not import aditofpython: {exc}")
    return tof

def normalize(min_depth, max_depth, image_scalar):
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    original_cmap = plt.cm.turbo
    colors = original_cmap(np.linspace(0, 1, 256))
    colors[0] = [0, 0, 0, 0]  # RGBA for red
    modified_cmap = ListedColormap(colors)

    visualization_depth_range_max = max_depth
    min_value = min_depth

    image_scalar = (image_scalar - min_value)
    visualization_depth_range_max = visualization_depth_range_max - min_value

    image_scalar_norm = image_scalar / visualization_depth_range_max

    # Apply the colormap to the scalar image to obtain an RGB image
    image_rgb = modified_cmap(image_scalar_norm)
        
    surface = (image_rgb[:, :, :3] * 255).astype(np.uint8)
    return surface


def animate(camera, frame, config, modemapping, pygame, tof_module, min_depth, max_depth):
    frame_A_loaded = False
    frame_B_loaded = False
    tries = 0
    while ((not frame_A_loaded) or (not frame_B_loaded)):
        status = camera.requestFrame(frame)
        if status != tof_module.Status.Ok:
            raise RuntimeError("Could not request frame")

        image_temp = np.array(frame.getData("depth"), copy=True)
        status, metadata = frame.getMetadataStruct()
        if status != tof_module.Status.Ok:
            raise RuntimeError("Could not read frame metadata")

        mode_temp = metadata.imagerMode
        laser_temp = metadata.laserTemperature
        sensor_temp = metadata.sensorTemperature

        if mode_temp == config.mode_a:
            image1 = image_temp
            frame_A_loaded = True
        
        if mode_temp == config.mode_b:
            image2 = image_temp
            frame_B_loaded = True

        tries = tries + 1
        if tries > 10:
            print('10 Tries to get consecutive frames')
            raise RuntimeError('Could not get consecutive frames for both modes')

    final_image = np.ones((modemapping[config.mode_a]["width"] * 2, modemapping[config.mode_a]["height"]))
    final_image[0:modemapping[config.mode_a]["width"], :] = image1
    final_image[modemapping[config.mode_a]["width"]:modemapping[config.mode_a]["width"] * 2, :] = image2
    surface = pygame.surfarray.make_surface(normalize(min_depth, max_depth, final_image))
    return surface, laser_temp, sensor_temp
    

def run_viewer(camera, config, modemapping, tof_module, min_depth, max_depth):
    import pygame

    pygame.init()

    window_size = (modemapping[config.mode_a]["width"] * 2, modemapping[config.mode_a]["height"])

    screen = pygame.display.set_mode(window_size)
    frame = tof_module.Frame()

    done = False
    fc = 0
    start_time = time.time()
    try:
        while not done:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    done = True
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    done = True

            pygame_surface, laser_temp, sensor_temp = animate(camera, frame, config, modemapping, pygame, tof_module, min_depth, max_depth)
            screen.blit(pygame_surface, (0, 0))
            fc = fc + 1.0
            elapsed_time = time.time() - start_time
            if elapsed_time > 2:
                measured_fps = fc / elapsed_time
                fc = 0
                start_time = time.time()
                print(f'Frame Rate: {int(measured_fps)} fps, Laser Temp: {laser_temp} C, Sensor Temp: {sensor_temp} C')

            pygame.display.flip()
    finally:
        pygame.quit()


def main():
    config = parse_args()
    modemapping = get_mode_mapping(config)
    tof_module = load_tof()
    system = tof_module.System()
    cameras = get_camera_list(system, config.ip, tof_module)
    camera = cameras[0]

    try:
        configure_camera(camera, config, tof_module)
        if config.dry_run:
            print("Dry run completed successfully.")
            return

        start_camera(camera, tof_module)
        run_viewer(camera, config, modemapping, tof_module, minV, maxV)
    finally:
        stop_camera(camera)


if __name__ == "__main__":
    main()