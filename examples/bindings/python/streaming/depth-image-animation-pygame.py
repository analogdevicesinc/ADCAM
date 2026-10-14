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
import json


def apply_param_overrides(camera):
    """Apply optional per-mode depth-param overrides from
    pygame_param_overrides.json (next to this script), e.g.
    {"7": {"radialThreshMax": 5000}, "0": {"confThresh": 30}}.
    Written to each mode's config before setMode() so fusion/DMS picks them up.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "pygame_param_overrides.json")
    if not os.path.exists(path):
        return
    try:
        with open(path) as f:
            overrides = json.load(f)
    except Exception as e:  # noqa: BLE001 - optional file, just warn
        print("param overrides: could not read", path, ":", e)
        return
    for mode_str, params in overrides.items():
        try:
            mode = int(mode_str)
        except (TypeError, ValueError):
            continue
        strparams = {k: str(v) for k, v in params.items()}
        status = camera.setFrameProcessParams(strparams, mode)
        print(f"param override mode {mode}: {strparams} -> {status}")


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

if not cameras:
    where = f"network @ {sys.argv[1]}" if len(sys.argv) >= 2 else "the target"
    print(f"No camera found on {where}.")
    print("Run with no arguments for the on-board camera, or pass a valid "
          "network camera IP (e.g. 10.42.0.1).")
    sys.exit(1)

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


# Key depth params exposed for live tuning in the config window.
PARAM_KEYS = ["confThresh", "abThreshMin", "radialThreshMin", "radialThreshMax"]


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
    height = 720

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

    # Depth-param editor: one text field per key, reused as the edited mode
    # changes. Values per mode live in param_by_mode; edit_mode is the mode the
    # fields currently show (switchable during fusion).
    y_params = 452
    param_inputs = {
        k: TextInput((230, y_params + 56 + i * 34, 110, 30), 0)
        for i, k in enumerate(PARAM_KEYS)
    }
    param_by_mode = {}
    edit_mode = None
    edit_toggle_btn = pygame.Rect(30, y_params + 22, width - 60, 28)

    def load_params_into_inputs(mode):
        vals = param_by_mode.get(mode, {})
        for k in PARAM_KEYS:
            param_inputs[k].text = str(vals.get(k, "0"))

    def save_inputs_into(mode):
        if mode is None:
            return
        d = param_by_mode.setdefault(mode, {})
        for k in PARAM_KEYS:
            d[k] = str(param_inputs[k].value(0))

    start_btn = pygame.Rect(width // 2 - 80, 662, 160, 44)

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
            if loaded:
                for k in PARAM_KEYS:
                    param_inputs[k].handle_event(e)
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
                        # Seed each mode's editable params from its config.
                        for m in available_modes:
                            _, pm = camera1.getDepthParamtersMap(m)
                            param_by_mode[m] = {
                                k: pm.get(k, "0") for k in PARAM_KEYS}
                        edit_mode = start_mode
                        load_params_into_inputs(edit_mode)
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
                if fusion and edit_toggle_btn.collidepoint(p):
                    save_inputs_into(edit_mode)
                    edit_mode = (second_dd.selected
                                 if edit_mode == primary_dd.selected
                                 else primary_dd.selected)
                    load_params_into_inputs(edit_mode)
                    continue
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
                    # Commit edited params into each involved mode's config so
                    # main()'s setMode()/fusion flow applies them.
                    save_inputs_into(edit_mode)
                    involved = {sel_mode}
                    if fusion:
                        involved.add(second_mode)
                    for m in involved:
                        vals = param_by_mode.get(m)
                        if vals:
                            camera1.setFrameProcessParams(vals, m)
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
            screen.blit(small.render("Depth Range (mm) - visualization only",
                                     True, (255, 255, 255)), (30, y_range))
            screen.blit(small.render("Min", True, (255, 255, 255)),
                        (110, min_input.rect.y + 7))
            min_input.draw(screen, small)
            screen.blit(small.render("Max", True, (255, 255, 255)),
                        (110, max_input.rect.y + 7))
            max_input.draw(screen, small)

            # Depth-param editor: keep edit_mode valid, then draw the fields for
            # the currently edited mode.
            valid_modes = [primary_dd.selected]
            if fusion and second_dd.selected != primary_dd.selected:
                valid_modes.append(second_dd.selected)
            if edit_mode not in valid_modes:
                edit_mode = valid_modes[0]
                load_params_into_inputs(edit_mode)
            screen.blit(small.render("Depth Params", True, (255, 255, 255)),
                        (30, y_params))
            if fusion:
                draw_button(
                    screen, small, edit_toggle_btn,
                    f"Editing Mode {edit_mode} ({range_label(edit_mode)})"
                    "  - click to switch",
                    active=True)
            for k in PARAM_KEYS:
                screen.blit(small.render(k, True, (200, 200, 200)),
                            (30, param_inputs[k].rect.y + 6))
                param_inputs[k].draw(screen, small)

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
    depth = np.rot90(np.asarray(frame.getData("depth")))
    surf = pygame.surfarray.make_surface(normalize(depth, dmin, dmax))
    return surf, depth


def dump_frame(depth, surface, title, dmin, dmax, font):
    """Save the current frame: raw depth as .bin and the colorized depth (with
    the colorbar) as .png, into the working directory. Returns the base name."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    tag = "".join(c for c in str(title) if c.isalnum() or c in "+_")
    base = f"pygame_frame_{tag}_{ts}"
    depth.astype(np.uint16).tofile(base + "_depth.bin")
    sw, sh = surface.get_width(), surface.get_height()
    cbar_w = 76
    comp = pygame.Surface((sw + cbar_w, sh))
    comp.fill((0, 0, 0))
    comp.blit(surface, (0, 0))
    draw_colorbar(comp, font, (sw + 12, 24, 16, max(20, sh - 40)), dmin, dmax)
    pygame.image.save(comp, base + "_depth.png")
    print(f"Saved {base}_depth.bin/.png  ({depth.shape[1]}x{depth.shape[0]})")
    return base


def draw_colorbar(surface, font, rect, dmin, dmax):
    """Vertical depth colorbar: top = dmax, bottom = dmin, using the same jet
    map as the image, with min/mid/max labels in mm."""
    x, y, w, h = rect
    fr = np.linspace(1.0, 0.0, h, dtype=np.float32)  # top=max, bottom=min
    rgb = (jet_colormap(fr)[:, :3] * 255).astype(np.uint8)  # (h, 3)
    strip = np.repeat(rgb[:, None, :], w, axis=1)  # (h, w, 3)
    bar = pygame.surfarray.make_surface(np.transpose(strip, (1, 0, 2)))
    surface.blit(bar, (x, y))
    pygame.draw.rect(surface, (200, 200, 200), pygame.Rect(x, y, w, h), 1)
    surface.blit(font.render("mm", True, (220, 220, 220)), (x - 2, y - 20))
    for frac, val in ((0.0, dmax), (0.5, (dmin + dmax) // 2), (1.0, dmin)):
        ty = int(y + frac * h)
        lbl = font.render(str(int(val)), True, (220, 220, 220))
        surface.blit(lbl, (x + w + 4, ty - lbl.get_height() // 2))


def run_window(title, modeDetails, dmin, dmax):
    """Running window: live depth stream scaled to fit a resizable window, with
    an adjustable depth range."""
    res_label = (f"{modeDetails.baseResolutionWidth}"
                 f"x{modeDetails.baseResolutionHeight}")
    panel_h = 104
    min_w = 520

    first = animate(dmin, dmax)[0]
    win_w = max(first.get_width(), min_w)
    win_h = first.get_height() + panel_h
    screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
    pygame.display.set_caption(f"ADCAM Depth - Mode {title} ({res_label})")
    font = pygame.font.SysFont("Arial", 16)

    min_input = TextInput((60, 0, 90, 30), dmin)
    max_input = TextInput((280, 0, 90, 30), dmax)
    save_btn = pygame.Rect(0, 0, 100, 34)

    def place_inputs():
        # Inputs + Save button live in the bottom panel; repositioned on resize.
        py = win_h - panel_h
        min_input.rect.topleft = (60, py + 44)
        max_input.rect.topleft = (280, py + 44)
        save_btn.topleft = (win_w - 120, py + 42)

    place_inputs()

    rng = [dmin, dmax]
    save_msg = ""
    save_until = 0.0
    clock = pygame.time.Clock()
    done = False
    while not done:
        # Grab this iteration's frame first so a save uses the current frame.
        surf, depth = animate(rng[0], rng[1])
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                done = True
            elif e.type == pygame.VIDEORESIZE:
                win_w = max(e.w, min_w)
                win_h = max(e.h, panel_h + 120)
                screen = pygame.display.set_mode((win_w, win_h),
                                                 pygame.RESIZABLE)
                place_inputs()
            elif (e.type == pygame.MOUSEBUTTONDOWN
                  and save_btn.collidepoint(e.pos)):
                base = dump_frame(depth, surf, title, rng[0], rng[1], font)
                save_msg = "Saved " + base
                save_until = time.time() + 2.5
            # Typed range is applied on Enter.
            if min_input.handle_event(e):
                rng[0] = max(0, min_input.value(rng[0]))
                if rng[1] <= rng[0]:
                    rng[1] = rng[0] + 1
                    max_input.text = str(rng[1])
            if max_input.handle_event(e):
                rng[1] = max(rng[0] + 1, max_input.value(rng[1]))

        # Scale the frame to fill the image area, preserving aspect ratio.
        # A strip on the right is reserved for the depth colorbar.
        cbar_w = 76
        area_w, area_h = win_w - cbar_w, win_h - panel_h
        scale = min(area_w / surf.get_width(), area_h / surf.get_height())
        sw = max(1, int(surf.get_width() * scale))
        sh = max(1, int(surf.get_height() * scale))
        scaled = pygame.transform.smoothscale(surf, (sw, sh))
        ox = (area_w - sw) // 2
        oy = (area_h - sh) // 2

        panel_y = win_h - panel_h
        screen.fill((0, 0, 0))
        screen.blit(scaled, (ox, oy))
        cb_h = max(20, area_h - 40)
        draw_colorbar(screen, font, (area_w + 12, 24, 16, cb_h),
                      rng[0], rng[1])
        pygame.draw.rect(screen, (30, 30, 30),
                         pygame.Rect(0, panel_y, win_w, panel_h))
        screen.blit(font.render(
            f"Mode {title}   Res: {res_label}   "
            f"Min/Max (mm) = visualization only",
            True, (200, 200, 200)), (20, panel_y + 12))
        screen.blit(font.render("Min", True, (255, 255, 255)),
                    (20, min_input.rect.y + 7))
        min_input.draw(screen, font)
        screen.blit(font.render("Max", True, (255, 255, 255)),
                    (240, max_input.rect.y + 7))
        max_input.draw(screen, font)
        draw_button(screen, font, save_btn, "Save", active=True)
        if save_msg and time.time() < save_until:
            screen.blit(font.render(save_msg, True, (150, 220, 150)),
                        (20, panel_y + 80))
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    camera1.stop()


def main():
    # 1) Configuration window: load a config file, choose mode, optional
    #    fusion, depth range. The camera is initialized inside this window.
    sel_mode, dmin, dmax, fusion, second_mode = config_window()

    # Optional per-mode param overrides, applied before any setMode() so each
    # mode's config (and thus its fusion context) reflects them.
    apply_param_overrides(camera1)

    if fusion:
        # The primary (active/first) mode must be fixed by IsSRFrameFirst, not
        # by which mode the user picked: IsSRFrameFirst=0 -> LR primary (SR
        # second), =1 -> SR primary (LR second). Resolve it here so the capture
        # is identical regardless of the selection order. ADTF3066 (hardcoded):
        # modes 7, 8 are Long Range; all others are Short Range.
        def is_lr(m):
            return m == 7 or m == 8

        lr_mode = sel_mode if is_lr(sel_mode) else second_mode
        sr_mode = second_mode if is_lr(sel_mode) else sel_mode

        _, sr_params = camera1.getDepthParamtersMap(sr_mode)
        sr_first = sr_params.get("IsSRFrameFirst", "0") == "1"

        sel_mode = sr_mode if sr_first else lr_mode
        second_mode = lr_mode if sr_first else sr_mode

        # Warm up both fused modes by running the full setMode() path on each
        # (secondary first, primary last so it stays active). This mirrors the
        # console example's two-mode discovery and leaves each mode's compute
        # context in the same "built twice" state, so fusion output no longer
        # depends on which mode was visited first.
        status = camera1.setMode(second_mode)
        print("camera1.setMode(second warm-up)", status)

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
