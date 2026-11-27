# 3D Time of Flight : Python examples

Refer to the eval kit [documentation](../../../doc/user-guide/ADTF3175D-EvalKit-610.md#python-tools) for more details.

## Setting up the Virtual Environment

After building the code:

1. cd build/examples/bindings/python

### Create and setup the virtual environment

1. source ./adcam_virtual_env.sh

### Activating the built virtual environment

1. source ./adcam_virtual_env/bin/activate
2. echo "$VIRTUAL_ENV"
   * This should point to the virtual environment in use

### Activating the built virtual environment

1. deactivate

## first_frame

`first_frame/first_frame.py` captures one frame and shows (`-o show`), snapshots (`-o snap`) or dumps (`-o bin`) it. `python first_frame.py -h` lists all options.

| Option | Meaning |
|---|---|
| `-m <mode>` | Mode to capture; required unless `--fuse` is given |
| `-i <ip>` | Camera on the network; omit on the target |
| `--fuse FIRST[,SECOND]` | Mode fusion; overrides `-m`, not with `--ip` |
| `--fusion-method srlr\|lrinval\|twolr` | `srlr`: one short-range + one long-range mode, e.g. `--fuse 0,7` (default); `lrinval`: one mode, e.g. `--fuse 7`; `twolr`: two long-range modes of the same resolution, e.g. `--fuse 7,7` |
| `--lrinval-type 1-4` | `lrinval` criterion: 1 AB, 2 edge confidence, 3 confidence, 4 radial (default 1) |
| `--lens-scatter` | Lens scatter compensation (non-PCM modes); not with `--fuse` or `--ip` |

```
python first_frame.py -m 0 -o show
python first_frame.py --fuse 0,7
python first_frame.py --fuse 7 --fusion-method lrinval --lrinval-type 1
python first_frame.py -m 0 --lens-scatter
```

## Streaming (pygame)

`streaming/depth-image-animation-pygame.py` opens a configuration window before streaming. There, the depth feature button cycles through None, the mode fusion methods (SR/LR, LR Invalidation, Two LR Frames) and Lens Scatter; only the features the installed depth compute libraries support are offered. Fusion methods that need a second mode show a drop-down for it.