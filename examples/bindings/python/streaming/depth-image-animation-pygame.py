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
import cv2
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

# Jet sampled at full 8-bit precision: 1020 distinct colours (cv2.COLORMAP_JET has 256).
_JET_T = np.linspace(0.0, 1.0, 4096)[:, None]
JET_LUT_RGB = (np.clip(1.5 - 4.0 * np.abs(_JET_T - [0.75, 0.5, 0.25]), 0.0, 1.0) * 255 + 0.5).astype(np.uint8)


def jet_rgb(norm):
    """Map values in [0, 1] to RGB uint8 using the 1020-colour jet."""
    return JET_LUT_RGB.take((np.clip(norm, 0.0, 1.0) * 4095 + 0.5).astype(np.uint16), axis=0)


# Weight of the newest frame when smoothing the auto colours (lower = steadier).
AUTO_RANGE_ALPHA = 0.2


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


def cdf_ticks(cdf):
    """(colour position, mm) colorbar labels for an equalised scale."""
    return [(f, float(np.searchsorted(cdf, max(f, 1e-6))))
            for f in (1.0, 0.75, 0.5, 0.25, 0.0)]

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
        # Installed package: eval/Python -> eval/C++/ADIToFGUI
        os.path.join(here, "..", "C++", "ADIToFGUI"),
        # Build tree: examples/bindings/python/streaming -> examples/tof-viewer
        os.path.join(here, "..", "..", "..", "tof-viewer"),
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
    optional mode fusion + second mode (drop-downs), and the depth colours (auto
    equalised by default, or a manual Min/Max). The camera is initialized here
    (once) using the chosen config so a Load Config selection is applied
    without a second initialize()."""
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
    auto_btn = pygame.Rect(320, y_range + 24, 200, 32)
    auto = True
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
            # Text fields consume focus (mouse) and typing (keys); committing
            # a value switches to a manual range.
            if min_input.handle_event(e) or max_input.handle_event(e):
                auto = False
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
                if auto_btn.collidepoint(p):
                    auto = not auto
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
                    return sel_mode, dmin, dmax, auto, fusion, second_mode

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
            draw_button(screen, small, auto_btn,
                        f"Auto Range: {'ON' if auto else 'OFF'}", active=auto)
            if auto:
                screen.blit(small.render("Min/Max ignored while Auto is ON",
                                         True, (170, 170, 170)),
                            (320, max_input.rect.y + 7))

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
    return jet_rgb(norm)


def colorbar_ticks(view):
    """(colour position, mm) labels for the current colour mapping."""
    if view["auto"]:
        return [] if view["cdf"] is None else cdf_ticks(view["cdf"])
    dmin, dmax = view["rng"]
    return [(1.0, dmax), (0.5, (dmin + dmax) / 2), (0.0, dmin)]


def animate(view):
    """Grab a frame and colorize it. view = {"auto", "rng", "cdf"}: auto uses
    equalised colours smoothed across frames ("cdf"), otherwise the manual
    linear range "rng" = [min, max] mm."""
    frame = tof.Frame()
    camera1.requestFrame(frame)
    frameDataDetails = tof.FrameDataDetails()
    frame.getDataDetails("depth", frameDataDetails)
    depth = np.rot90(np.asarray(frame.getData("depth")))
    if view["auto"]:
        new = equalize_cdf(depth)
        if new is not None:
            old = view["cdf"]
            view["cdf"] = new if old is None else old + AUTO_RANGE_ALPHA * (new - old)
    if view["auto"] and view["cdf"] is not None:
        # One depth(mm) -> colour table per frame, then one lookup per pixel.
        table = jet_rgb(view["cdf"])
        table[0] = 0  # invalid depth: black, not the nearest-depth colour
        rgb = table.take(depth.astype(np.uint16, copy=False), axis=0)
    else:
        rgb = normalize(depth, *view["rng"])
    return pygame.surfarray.make_surface(rgb), depth


def dump_frame(depth, surface, title, ticks, font):
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
    draw_colorbar(comp, font, (sw + 12, 24, 16, max(20, sh - 40)), ticks)
    pygame.image.save(comp, base + "_depth.png")
    print(f"Saved {base}_depth.bin/.png  ({depth.shape[1]}x{depth.shape[0]})")
    return base


def draw_colorbar(surface, font, rect, ticks):
    """Vertical depth colorbar using the same jet map as the image, labelled
    in mm at the given (colour position 0=bottom..1=top, mm) ticks."""
    x, y, w, h = rect
    fr = np.linspace(1.0, 0.0, h, dtype=np.float32)  # top=max, bottom=min
    rgb = jet_rgb(fr)  # (h, 3)
    strip = np.repeat(rgb[:, None, :], w, axis=1)  # (h, w, 3)
    bar = pygame.surfarray.make_surface(np.transpose(strip, (1, 0, 2)))
    surface.blit(bar, (x, y))
    pygame.draw.rect(surface, (200, 200, 200), pygame.Rect(x, y, w, h), 1)
    surface.blit(font.render("mm", True, (220, 220, 220)), (x - 2, y - 20))
    for frac, val in ticks:
        ty = int(y + (1.0 - frac) * (h - 1))
        lbl = font.render(str(int(val)), True, (220, 220, 220))
        surface.blit(lbl, (x + w + 4, ty - lbl.get_height() // 2))


def run_window(title, modeDetails, dmin, dmax, auto):
    """Running window: live depth stream scaled to fit a resizable window, with
    auto (equalised) or manual linear depth colours."""
    res_label = (f"{modeDetails.baseResolutionWidth}"
                 f"x{modeDetails.baseResolutionHeight}")
    panel_h = 104
    min_w = 640

    view = {"auto": auto, "rng": [float(dmin), float(dmax)], "cdf": None}
    first = animate(view)[0]
    win_w = max(first.get_width(), min_w)
    win_h = first.get_height() + panel_h
    screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
    pygame.display.set_caption(f"ADCAM Depth - Mode {title} ({res_label})")
    font = pygame.font.SysFont("Arial", 16)

    min_input = TextInput((60, 0, 90, 30), dmin)
    max_input = TextInput((280, 0, 90, 30), dmax)
    auto_btn = pygame.Rect(0, 0, 120, 34)
    save_btn = pygame.Rect(0, 0, 100, 34)

    def place_inputs():
        # Inputs + buttons live in the bottom panel; repositioned on resize.
        py = win_h - panel_h
        min_input.rect.topleft = (60, py + 44)
        max_input.rect.topleft = (280, py + 44)
        auto_btn.topleft = (390, py + 42)
        save_btn.topleft = (win_w - 120, py + 42)

    place_inputs()

    save_msg = ""
    save_until = 0.0
    clock = pygame.time.Clock()
    done = False
    while not done:
        # Grab this iteration's frame first so a save uses the current frame.
        surf, depth = animate(view)
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
                base = dump_frame(depth, surf, title, colorbar_ticks(view), font)
                save_msg = "Saved " + base
                save_until = time.time() + 2.5
            elif (e.type == pygame.MOUSEBUTTONDOWN
                  and auto_btn.collidepoint(e.pos)):
                view["auto"] = not view["auto"]
                view["cdf"] = None  # re-seed from the next frame
            # Typed range is applied on Enter and switches to manual.
            rng = view["rng"]
            if min_input.handle_event(e):
                view["auto"] = False
                rng[0] = max(0, min_input.value(int(rng[0])))
                if rng[1] <= rng[0]:
                    rng[1] = rng[0] + 1
                    max_input.text = str(int(rng[1]))
            if max_input.handle_event(e):
                view["auto"] = False
                rng[1] = max(rng[0] + 1, max_input.value(int(rng[1])))
        if view["auto"] and view["cdf"] is not None:
            # Fields show the live depth extent, so switching to manual starts from it.
            ticks = cdf_ticks(view["cdf"])
            view["rng"][:] = [ticks[-1][1], ticks[0][1]]
            if not min_input.active:
                min_input.text = str(int(view["rng"][0]))
            if not max_input.active:
                max_input.text = str(int(view["rng"][1]))

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
                      colorbar_ticks(view))
        pygame.draw.rect(screen, (30, 30, 30),
                         pygame.Rect(0, panel_y, win_w, panel_h))
        screen.blit(font.render(
            f"Mode {title}   Res: {res_label}   Colours: "
            f"{'Auto (equalised)' if view['auto'] else 'Manual'} - visualization only",
            True, (200, 200, 200)), (20, panel_y + 12))
        screen.blit(font.render("Min", True, (255, 255, 255)),
                    (20, min_input.rect.y + 7))
        min_input.draw(screen, font)
        screen.blit(font.render("Max", True, (255, 255, 255)),
                    (240, max_input.rect.y + 7))
        max_input.draw(screen, font)
        draw_button(screen, font, auto_btn,
                    f"Auto: {'ON' if view['auto'] else 'OFF'}",
                    active=view["auto"])
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
    sel_mode, dmin, dmax, auto, fusion, second_mode = config_window()

    # Optional per-mode param overrides, applied before any setMode() so each
    # mode's config (and thus its fusion context) reflects them.
    apply_param_overrides(camera1)

    if fusion:
        # The camera configures Dynamic Mode Switching for the pair; the first
        # selected mode leads (IsSRFrameFirst=1 when it is short-range).
        status = camera1.setModeFusion(sel_mode, second_mode)
        print("camera1.setModeFusion()", status)
    else:
        status = camera1.setMode(sel_mode)
        print("camera1.setMode()", status)

    status = camera1.start()
    print("camera1.start()", status)

    sensor = camera1.getSensor()
    modeDetails = tof.DepthSensorModeDetails()
    sensor.getModeDetails(sel_mode, modeDetails)

    # 2) Running window: live stream with the depth-range selector.
    title = f"{sel_mode} + {second_mode} (fused)" if fusion else f"{sel_mode}"
    run_window(title, modeDetails, dmin, dmax, auto)


main()
