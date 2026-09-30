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
import time
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import os


def help():
    print(f"{sys.argv[0]} usage:")
    print()
    print("Run with no arguments and pick the mode in the configuration window.")
    print()
    print("**On the Jetson Orin Nano Dev Kit or Raspberry Pi 5**")
    print(f"python {sys.argv[0]}")
    print()
    print("**For a network connected device (pass the camera IP)**")
    print(f"python {sys.argv[0]} <ip>")
    print("For example:")
    print(f"python {sys.argv[0]} 192.168.56.1")
    exit(1)

if "--help" in sys.argv or "-h" in sys.argv:
    help()
    exit(-1)

jet_colormap = plt.get_cmap('jet')

system = tof.System()

print("SDK version: ", tof.getApiVersion(), " | branch: ", tof.getBranchVersion(), " | commit: ", tof.getCommitVersion())

cameras = []
ip = ""
# Optional single argument = camera IP (network camera). The capture mode is
# chosen in the configuration window, so no mode argument is required.
if len(sys.argv) >= 2:
    ip = sys.argv[1]
    print(f"Looking for camera on network @ {ip}.")
    ip = "ip:" + ip
else:
    print("Looking for camera on Target.")
if ip:
    status = system.getCameraList(cameras, ip)
else:
    status = system.getCameraList(cameras)
print("system.getCameraList()", status)

camera1 = cameras[0]

# NOTE: the camera is initialized inside the configuration window (once) after
# the user picks a config file, so an "Update Config" selection can be applied
# without re-initializing (a second initialize() resets/locks the device).


def find_configs():
    """Discover selectable config JSON files near this script and the install
    tree. Returns a sorted list of absolute paths."""
    here = os.path.dirname(os.path.abspath(__file__))
    search_dirs = [
        here,
        os.path.join(here, "config"),
        os.path.join(here, "..", "..", "..", "..", "eval", "C++", "ADIToFGUI"),
        os.path.expanduser(
            "~/ADI/Robotics/Camera/ADCAM/1.0.0/eval/C++/ADIToFGUI"),
    ]
    found = []
    seen = set()
    for d in search_dirs:
        d = os.path.abspath(d)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.lower().endswith(".json"):
                path = os.path.join(d, name)
                if path not in seen:
                    seen.add(path)
                    found.append(path)
    return found


def range_label(m):
    # ADTF3066 (hardcoded): Long Range = modes 7, 8; others are Short Range.
    return "Long Range" if m in (7, 8) else "Short Range"


def draw_button(surface, font, rect, text, active=False):
    pygame.draw.rect(surface, (70, 130, 180) if active else (60, 60, 60), rect)
    pygame.draw.rect(surface, (200, 200, 200), rect, 1)
    label = font.render(text, True, (255, 255, 255))
    surface.blit(label, (rect.x + (rect.width - label.get_width()) // 2,
                         rect.y + (rect.height - label.get_height()) // 2))


class Dropdown:
    """Minimal pygame drop-down: a collapsed header that expands a click list."""

    def __init__(self, rect, options, label_fn):
        self.rect = pygame.Rect(rect)
        self.options = list(options)
        self.label_fn = label_fn
        self.selected = self.options[0] if self.options else None
        self.open = False

    def option_rect(self, i):
        return pygame.Rect(self.rect.x,
                           self.rect.y + self.rect.height * (i + 1),
                           self.rect.width, self.rect.height)

    def handle(self, pos):
        """Process a click at pos. Returns True if the selection changed."""
        if self.open:
            changed = False
            for i, opt in enumerate(self.options):
                if self.option_rect(i).collidepoint(pos):
                    self.selected = opt
                    changed = True
                    break
            self.open = False  # any click collapses the list
            return changed
        if self.rect.collidepoint(pos):
            self.open = True
        return False

    def draw_header(self, surface, font):
        text = self.label_fn(self.selected) if self.selected is not None else ""
        draw_button(surface, font, self.rect, text + "   v")

    def draw_list(self, surface, font):
        if not self.open:
            return
        for i, opt in enumerate(self.options):
            draw_button(surface, font, self.option_rect(i),
                        self.label_fn(opt), active=(opt == self.selected))


class TextInput:
    """Minimal numeric text field: click to focus, type digits, Enter commits."""

    def __init__(self, rect, value):
        self.rect = pygame.Rect(rect)
        self.text = str(value)
        self.active = False

    def handle_event(self, event):
        """Returns True when the value is committed (Enter pressed)."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.active = False
                return True
            elif event.unicode.isdigit() and len(self.text) < 6:
                self.text += event.unicode
        return False

    def value(self, default=0):
        try:
            return int(self.text) if self.text else default
        except ValueError:
            return default

    def draw(self, surface, font):
        pygame.draw.rect(surface, (90, 90, 110) if self.active else (60, 60, 60),
                         self.rect)
        pygame.draw.rect(surface,
                         (120, 180, 240) if self.active else (200, 200, 200),
                         self.rect, 1)
        shown = self.text + ("|" if self.active else "")
        label = font.render(shown, True, (255, 255, 255))
        surface.blit(label, (self.rect.x + 6,
                             self.rect.y +
                             (self.rect.height - label.get_height()) // 2))


def config_window():
    """First window: optionally load a config file, then pick the primary mode,
    optional mode fusion + second mode (drop-downs), and the initial depth
    range. The camera is initialized here (once) using the chosen config so a
    Load Config selection is applied without a second initialize()."""
    pygame.init()
    font = pygame.font.SysFont("Arial", 20)
    small = pygame.font.SysFont("Arial", 16)
    width = 560
    height = 520

    mode_res = {}  # mode -> (width, height), filled after the config loads

    def mode_label(m):
        base = f"Mode {m}  ({range_label(m)})"
        if m in mode_res:
            base += f"  {mode_res[m][0]}x{mode_res[m][1]}"
        return base

    # Config File drop-down: "Default (no config)" plus any discovered *.json.
    config_options = [("Default (no config)", "")]
    config_options += [(os.path.basename(p), p) for p in find_configs()]
    config_dd = Dropdown((30, 75, width - 60, 34), config_options,
                         lambda o: o[0])
    config_dd.selected = config_options[0]
    load_btn = pygame.Rect(30, 122, width - 60, 34)

    loaded = False
    load_msg = "Pick a config file (optional), then click Load."
    available_modes = []
    primary_dd = None
    second_dd = None

    fusion = False  # fusion is off by default
    y_range = 340
    min_input = TextInput((160, y_range + 24, 140, 32), 0)
    max_input = TextInput((160, y_range + 64, 140, 32), 5000)
    fusion_btn = pygame.Rect(30, 210, width - 60, 34)
    start_btn = pygame.Rect(width // 2 - 80, y_range + 118, 160, 44)

    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("ADCAM Depth - Configuration")

    clock = pygame.time.Clock()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            # Text fields consume focus (mouse) and typing (keys).
            min_input.handle_event(e)
            max_input.handle_event(e)
            if e.type == pygame.MOUSEBUTTONDOWN:
                p = e.pos
                # Open drop-downs take click priority so the list is clickable.
                if config_dd.open:
                    config_dd.handle(p)
                    continue
                if loaded and primary_dd.open:
                    primary_dd.handle(p)
                    continue
                if loaded and fusion and second_dd.open:
                    second_dd.handle(p)
                    continue
                if config_dd.rect.collidepoint(p):
                    config_dd.handle(p)
                    continue
                if not loaded:
                    if load_btn.collidepoint(p):
                        cfg = config_dd.selected[1]
                        status = (camera1.initialize(cfg) if cfg
                                  else camera1.initialize())
                        print("camera1.initialize(%s)" %
                              (config_dd.selected[0]), status)
                        available_modes = []
                        camera1.getAvailableModes(available_modes)
                        if not available_modes:
                            load_msg = "No modes available - check the config."
                            continue
                        sensor = camera1.getSensor()
                        for m in available_modes:
                            md = tof.DepthSensorModeDetails()
                            sensor.getModeDetails(m, md)
                            mode_res[m] = (md.baseResolutionWidth,
                                           md.baseResolutionHeight)
                        start_mode = available_modes[0]
                        primary_dd = Dropdown((30, 158, width - 60, 34),
                                              available_modes, mode_label)
                        primary_dd.selected = start_mode
                        others = [m for m in available_modes
                                  if m != start_mode]
                        second_dd = Dropdown((30, 280, width - 60, 34),
                                             available_modes, mode_label)
                        second_dd.selected = (others[0] if others
                                              else start_mode)
                        load_msg = "Loaded: " + config_dd.selected[0]
                        loaded = True
                    continue
                # Loaded: mode / fusion / range / start interactions.
                if primary_dd.rect.collidepoint(p):
                    primary_dd.handle(p)
                    continue
                if fusion and second_dd.rect.collidepoint(p):
                    second_dd.handle(p)
                    continue
                if fusion_btn.collidepoint(p):
                    fusion = not fusion
                if start_btn.collidepoint(p):
                    dmin = max(0, min_input.value(0))
                    dmax = max_input.value(dmin + 1)
                    if dmax <= dmin:
                        dmax = dmin + 1
                    sel_mode = primary_dd.selected
                    second_mode = second_dd.selected
                    if second_mode == sel_mode:
                        alt = [m for m in available_modes if m != sel_mode]
                        second_mode = alt[0] if alt else sel_mode
                    return sel_mode, dmin, dmax, fusion, second_mode

        screen.fill((30, 30, 30))
        screen.blit(font.render("Configuration", True, (255, 255, 255)),
                    (30, 20))
        screen.blit(small.render("Config File", True, (200, 200, 200)),
                    (30, 55))
        config_dd.draw_header(screen, small)
        if not loaded:
            draw_button(screen, font, load_btn, "Load", active=True)
        screen.blit(small.render(load_msg, True, (170, 200, 170)),
                    (30, 170))
        if loaded:
            screen.blit(small.render("Primary Mode", True, (200, 200, 200)),
                        (30, 140))
            primary_dd.draw_header(screen, small)
            draw_button(screen, small, fusion_btn,
                        f"Mode Fusion: {'ON' if fusion else 'OFF'}",
                        active=fusion)
            if fusion:
                screen.blit(small.render("Second Mode", True, (200, 200, 200)),
                            (30, second_dd.rect.y - 18))
                second_dd.draw_header(screen, small)
            screen.blit(small.render("Depth Range (mm)", True,
                                     (255, 255, 255)), (30, y_range))
            screen.blit(small.render("Min", True, (255, 255, 255)),
                        (110, min_input.rect.y + 7))
            min_input.draw(screen, small)
            screen.blit(small.render("Max", True, (255, 255, 255)),
                        (110, max_input.rect.y + 7))
            max_input.draw(screen, small)
            draw_button(screen, font, start_btn, "Start", active=True)
        # Draw open drop-down lists last so they overlay the widgets below.
        if loaded:
            primary_dd.draw_list(screen, small)
            if fusion:
                second_dd.draw_list(screen, small)
        config_dd.draw_list(screen, small)
        pygame.display.flip()
        clock.tick(30)


def normalize(image_scalar, dmin, dmax):
    # Map the user-selected depth range [dmin, dmax] mm across the colormap.
    if dmax <= dmin:
        dmax = dmin + 1
    norm = np.clip((image_scalar.astype(np.float32) - dmin) / (dmax - dmin),
                   0.0, 1.0)
    norm[image_scalar == 0] = 0.0  # invalid pixels -> colormap floor
    image_rgb = jet_colormap(norm)
    return (image_rgb[:, :, :3] * 255).astype(np.uint8)


def animate(dmin, dmax):
    frame = tof.Frame()
    camera1.requestFrame(frame)
    frameDataDetails = tof.FrameDataDetails()
    frame.getDataDetails("depth", frameDataDetails)
    image = np.asarray(frame.getData("depth"))
    image = np.rot90(image)
    return pygame.surfarray.make_surface(normalize(image, dmin, dmax))


def run_window(title, modeDetails, dmin, dmax):
    """Running window: live depth stream scaled to fit a resizable window, with
    an adjustable depth range."""
    res_label = (f"{modeDetails.baseResolutionWidth}"
                 f"x{modeDetails.baseResolutionHeight}")
    panel_h = 92
    min_w = 520

    first = animate(dmin, dmax)
    win_w = max(first.get_width(), min_w)
    win_h = first.get_height() + panel_h
    screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
    pygame.display.set_caption(f"ADCAM Depth - Mode {title} ({res_label})")
    font = pygame.font.SysFont("Arial", 16)

    min_input = TextInput((60, 0, 90, 30), dmin)
    max_input = TextInput((280, 0, 90, 30), dmax)

    def place_inputs():
        # Inputs live in the bottom panel; repositioned on every resize.
        py = win_h - panel_h
        min_input.rect.topleft = (60, py + 50)
        max_input.rect.topleft = (280, py + 50)

    place_inputs()

    rng = [dmin, dmax]
    clock = pygame.time.Clock()
    done = False
    while not done:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                done = True
            elif e.type == pygame.VIDEORESIZE:
                win_w = max(e.w, min_w)
                win_h = max(e.h, panel_h + 120)
                screen = pygame.display.set_mode((win_w, win_h),
                                                 pygame.RESIZABLE)
                place_inputs()
            # Typed range is applied on Enter.
            if min_input.handle_event(e):
                rng[0] = max(0, min_input.value(rng[0]))
                if rng[1] <= rng[0]:
                    rng[1] = rng[0] + 1
                    max_input.text = str(rng[1])
            if max_input.handle_event(e):
                rng[1] = max(rng[0] + 1, max_input.value(rng[1]))

        # Scale the frame to fill the image area, preserving aspect ratio.
        surf = animate(rng[0], rng[1])
        area_w, area_h = win_w, win_h - panel_h
        scale = min(area_w / surf.get_width(), area_h / surf.get_height())
        sw = max(1, int(surf.get_width() * scale))
        sh = max(1, int(surf.get_height() * scale))
        scaled = pygame.transform.smoothscale(surf, (sw, sh))
        ox = (area_w - sw) // 2
        oy = (area_h - sh) // 2

        panel_y = win_h - panel_h
        screen.fill((0, 0, 0))
        screen.blit(scaled, (ox, oy))
        pygame.draw.rect(screen, (30, 30, 30),
                         pygame.Rect(0, panel_y, win_w, panel_h))
        screen.blit(font.render(f"Mode {title}    Resolution: {res_label}",
                                True, (200, 200, 200)), (20, panel_y + 14))
        screen.blit(font.render("Min", True, (255, 255, 255)),
                    (20, panel_y + 56))
        min_input.draw(screen, font)
        screen.blit(font.render("Max", True, (255, 255, 255)),
                    (240, panel_y + 56))
        max_input.draw(screen, font)
        screen.blit(font.render("mm  Enter=apply", True, (150, 150, 150)),
                    (384, panel_y + 56))
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    camera1.stop()


def main():
    # 1) Configuration window: load a config file, choose mode, optional
    #    fusion, depth range. The camera is initialized inside this window.
    sel_mode, dmin, dmax, fusion, second_mode = config_window()

    status = camera1.setMode(sel_mode)
    print("camera1.setMode()", status)

    if fusion:
        # Mirror the SDK/DMS setup: opt into fusion (off by default at the SDK
        # level), metadata-in-AB on, reapply MIPI (setMode clears it), settle,
        # enable Dynamic Mode Switching, then load the primary+second sequence
        # so the chip fuses the pair.
        camera1.setModeFusionEnabled(True)
        camera1.adsd3500SetEnableMetadatainAB(1)
        camera1.adsd3500SetMIPIOutputSpeed(1)
        time.sleep(0.3)
        status = camera1.adsd3500setEnableDynamicModeSwitching(True)
        print("enable Dynamic Mode Switching", status)
        sequence = [(sel_mode, 0x01), (second_mode, 0x01)]
        status = camera1.adsds3500setDynamicModeSwitchingSequence(sequence)
        print("set Dynamic Mode Switching sequence", status)
        time.sleep(0.3)

    status = camera1.start()
    print("camera1.start()", status)

    sensor = camera1.getSensor()
    modeDetails = tof.DepthSensorModeDetails()
    sensor.getModeDetails(sel_mode, modeDetails)

    # 2) Running window: live stream with the depth-range selector.
    title = f"{sel_mode} + {second_mode} (fused)" if fusion else f"{sel_mode}"
    run_window(title, modeDetails, dmin, dmax)


main()
