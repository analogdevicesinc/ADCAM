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
import json
import tempfile
import time
import os
from dataclasses import dataclass

# Weight of the newest frame when smoothing the auto colours (lower = steadier).
AUTO_RANGE_ALPHA = 0.2
CBAR_W = 80


@dataclass
class AppConfig:
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
        usage="%(prog)s <modeA>,<modeB> [--ip <ip>] [--config <config.json>] [--fps <fps>] [--dry-run]"
    )
    parser.add_argument(
        "modes",
        help="Two modes of the same resolution to alternate, e.g. 0,1 or 3,6\n"
    )
    parser.add_argument("--ip", "--ipconfig", dest="ip", default="",
                        help="Optional camera IP address (e.g., 192.168.1.10)")
    parser.add_argument("--config", dest="config", default="",
                        help="Optional config JSON file path")
    parser.add_argument("--fps", type=positive_int, default=None,
                        help="Frame rate in fps for both modes (default: mode setting)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate arguments and camera setup without opening the pygame window")
    return parser


def parse_modes(parser, modes_value):
    mode_parts = modes_value.split(',')
    if len(mode_parts) != 2:
        parser.error("modes must be in format: modeA,modeB (e.g., 0,1)")

    try:
        mode_a, mode_b = (int(m) for m in mode_parts)
    except ValueError:
        parser.error(f"Invalid modes '{modes_value}'. Modes must be integers")

    if mode_a == mode_b:
        parser.error("modeA and modeB must be different")

    return mode_a, mode_b


def parse_args():
    parser = build_parser()
    args = parser.parse_args()
    mode_a, mode_b = parse_modes(parser, args.modes)

    config_path = ""
    if args.config:
        print(f"Including config file {args.config}.")
        if not os.path.exists(args.config):
            parser.error(f"Config file {args.config} does not exist")
        config_path = os.path.abspath(args.config)
        print(f"Using config file: {config_path}")

    return AppConfig(
        mode_a=mode_a,
        mode_b=mode_b,
        fps=args.fps,
        ip=args.ip,
        config_path=config_path,
        dry_run=args.dry_run,
    )


def write_configs(camera, config, tof_module):
    """Writes temporary config JSONs: depth params only, and params + DMS sequence.

    Without --config, the camera's own depth parameters are used as the base.
    """
    params_path = tempfile.mkstemp(suffix=".json")[1]
    dms_path = tempfile.mkstemp(suffix=".json")[1]
    if config.config_path:
        with open(config.config_path) as f:
            params = json.load(f)
    else:
        if camera.saveDepthParamsToJsonFile(params_path) != tof_module.Status.Ok:
            sys.exit("Could not read the camera depth parameters!")
        with open(params_path) as f:
            params = json.load(f)

    params.pop("dynamicModeSwitching", None)
    if config.fps:
        for mode in (config.mode_a, config.mode_b):
            params.setdefault(str(mode), {}).setdefault(
                "configuration-parameters", {})["fps"] = config.fps
    with open(params_path, "w") as f:
        json.dump(params, f, indent=4)

    params["dynamicModeSwitching"] = [
        {"mode": config.mode_a, "repeat": 1},
        {"mode": config.mode_b, "repeat": 1},
    ]
    with open(dms_path, "w") as f:
        json.dump(params, f, indent=4)
    return params_path, dms_path


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
    status = camera.getAvailableModes(available_modes)
    if status != tof_module.Status.Ok or len(available_modes) == 0:
        sys.exit('Could not acquire available modes')

    sensor = camera.getSensor()
    resolutions = []
    for mode in (config.mode_a, config.mode_b):
        if mode not in available_modes:
            sys.exit(f"Mode {mode} is not available. Available modes: {available_modes}")
        details = tof_module.DepthSensorModeDetails()
        sensor.getModeDetails(mode, details)
        resolutions.append((details.baseResolutionWidth, details.baseResolutionHeight))
    if resolutions[0] != resolutions[1]:
        sys.exit(f"Modes {config.mode_a} and {config.mode_b} must have the same resolution")

    # Embedded metadata identifies which mode produced each frame
    status = camera.adsd3500SetEnableMetadatainAB(1)
    if status != tof_module.Status.Ok:
        sys.exit("Could not set embedded header in AB frame!")

    # setMode() writes only its own mode's params to the ADSD3500, so set mode B
    # before the sequence is loaded; setMode(mode A) then enables DMS.
    params_path, dms_path = write_configs(camera, config, tof_module)
    try:
        status = camera.loadDepthParamsFromJsonFile(params_path, -1)
        if status != tof_module.Status.Ok:
            sys.exit("Could not load depth parameters!")
        status = camera.setMode(config.mode_b)
        if status != tof_module.Status.Ok:
            sys.exit(f"Could not set mode {config.mode_b}!")
        status = camera.loadDepthParamsFromJsonFile(dms_path, -1)
        if status != tof_module.Status.Ok:
            sys.exit("Could not load the dynamic mode switching sequence!")
    finally:
        os.remove(params_path)
        os.remove(dms_path)

    status = camera.setMode(config.mode_a)
    if status != tof_module.Status.Ok:
        sys.exit("Error setting dynamic mode switching!")
    print(f"Dynamic mode switching: mode {config.mode_a} <-> mode {config.mode_b}")

    # The ADSD3500 needs a moment to apply the sequence before streaming
    time.sleep(0.3)


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

# Jet sampled at full 8-bit precision: 1020 distinct colours (cv2.COLORMAP_JET has 256).
_JET_T = np.linspace(0.0, 1.0, 4096)[:, None]
JET_LUT_RGB = (np.clip(1.5 - 4.0 * np.abs(_JET_T - [0.75, 0.5, 0.25]), 0.0, 1.0) * 255 + 0.5).astype(np.uint8)


EQ_TRIM = 0.005  # ignore this fraction of valid pixels at each end (stray / flying pixels)
EQ_BLEND = 0.75  # 1 = fully equalised (most detail), 0 = linear (colour tracks distance)
MM_RANGE = np.arange(65536, dtype=np.float32)


def equalize_cdf(depth):
    """Auto colour scale: clip-limited histogram equalisation of valid depth.

    Returns a 65536-entry table mapping depth (mm) to its colour position in
    [0, 1], or None if no pixel is valid. Colours go where the pixels are, but no
    single mm value may take more than 1/256 of them, so a large flat surface
    (e.g. a wall) can't swallow the colormap. The outer EQ_TRIM of pixels at each
    end are clamped, and the result is blended with a linear scale (EQ_BLEND).
    """
    hist = np.bincount(depth[::2, ::2].astype(np.uint16, copy=False).ravel(),
                       minlength=65536).astype(np.float32)
    hist[0] = 0  # invalid depth
    total = hist.sum()
    if total == 0:
        return None
    cum = np.cumsum(hist)
    lo = int(np.searchsorted(cum, EQ_TRIM * total))
    hi = int(np.searchsorted(cum, (1 - EQ_TRIM) * total))
    hist[:lo] = 0
    hist[hi + 1:] = 0
    np.minimum(hist, max(1.0, hist.sum() / 256), out=hist)
    eq = np.cumsum(hist)
    eq /= eq[-1]
    lin = np.clip((MM_RANGE - lo) / max(hi - lo, 1), 0.0, 1.0)
    cdf = EQ_BLEND * eq + (1 - EQ_BLEND) * lin
    cdf[0] = 0.0
    return cdf


def colorize(depth, cdf):
    """Equalised jet colours via one depth(mm) -> colour table; invalid pixels black."""
    table = JET_LUT_RGB.take((cdf * 4095 + 0.5).astype(np.uint16), axis=0)
    table[0] = 0
    return table.take(depth.astype(np.uint16, copy=False), axis=0)


def draw_colorbar(screen, pygame, font, x, height, cdf):
    """Vertical colorbar labelled with the depth in mm at each tick."""
    if cdf is None:
        return
    top, bar_w = 24, 16
    bar_h = max(20, height - 2 * top)
    ramp = np.linspace(4095, 0, bar_h).astype(np.uint16)
    strip = np.repeat(JET_LUT_RGB.take(ramp, axis=0)[:, None, :], bar_w, axis=1)
    screen.blit(pygame.surfarray.make_surface(np.transpose(strip, (1, 0, 2))), (x + 8, top))
    pygame.draw.rect(screen, (200, 200, 200), pygame.Rect(x + 8, top, bar_w, bar_h), 1)
    screen.blit(font.render("mm", True, (220, 220, 220)), (x + 6, top - 18))
    for frac in (1.0, 0.75, 0.5, 0.25, 0.0):
        label = font.render(f"{np.searchsorted(cdf, max(frac, 1e-6))}", True, (220, 220, 220))
        y = top + int((1.0 - frac) * (bar_h - 1))
        screen.blit(label, (x + 8 + bar_w + 4, y - label.get_height() // 2))


def animate(camera, frame, config, pygame, tof_module, state):
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

    final_image = np.concatenate((image1, image2), axis=0)
    new = equalize_cdf(final_image)
    if new is not None:
        old = state["cdf"]
        state["cdf"] = new if old is None else old + AUTO_RANGE_ALPHA * (new - old)
    if state["cdf"] is None:
        rgb = np.zeros(final_image.shape + (3,), dtype=np.uint8)
    else:
        rgb = colorize(final_image, state["cdf"])
    surface = pygame.surfarray.make_surface(rgb)
    return surface, laser_temp, sensor_temp
    

def run_viewer(camera, config, tof_module):
    import pygame

    frame = tof_module.Frame()
    status = camera.requestFrame(frame)
    if status != tof_module.Status.Ok:
        sys.exit("Could not request frame!")
    rows, cols = np.array(frame.getData("depth"), copy=False).shape

    pygame.init()
    font = pygame.font.Font(None, 20)

    screen = pygame.display.set_mode((rows * 2 + CBAR_W, cols))
    pygame.display.set_caption(f"Mode {config.mode_a} | Mode {config.mode_b}")

    state = {"cdf": None}
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

            pygame_surface, laser_temp, sensor_temp = animate(camera, frame, config, pygame, tof_module, state)
            screen.fill((0, 0, 0))
            screen.blit(pygame_surface, (0, 0))
            draw_colorbar(screen, pygame, font, rows * 2, cols, state["cdf"])
            fc = fc + 1.0
            elapsed_time = time.time() - start_time
            if elapsed_time > 2:
                measured_fps = fc / elapsed_time
                fc = 0
                start_time = time.time()
                cdf = state["cdf"]
                extent = (f"{np.searchsorted(cdf, 1e-6)}-{np.searchsorted(cdf, 1.0)} mm"
                          if cdf is not None else "n/a")
                print(f'Frame Rate: {int(measured_fps)} fps, Laser Temp: {laser_temp} C, Sensor Temp: {sensor_temp} C, '
                      f'Depth colours (auto, equalised): {extent}')

            pygame.display.flip()
    finally:
        pygame.quit()


def main():
    config = parse_args()
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
        run_viewer(camera, config, tof_module)
    finally:
        stop_camera(camera)


if __name__ == "__main__":
    main()