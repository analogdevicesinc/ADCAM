# first-frame sample code

## Overview

The first-frame is a cross platform sample code that shows how to use the aditof sdk to configure a camera so that frames can be captured from it.

```
first-frame [-ip | --ip <ip>] [-m | --m <mode>] [-config | --config <config_file.json>]
first-frame [-m | --m <mode>] [-lens-scatter | --lens-scatter] [-config | --config <config_file.json>]
first-frame [-fuse | --fuse <firstMode>[,<secondMode>]] [-fusion-method | --fusion-method <srlr|lrinval|twolr>] [-lrinval-type | --lrinval-type <1-4>] [-config | --config <config_file.json>]
```

`-m` selects the mode by index or name (e.g. `0` or `sr-native`, default 0); `./first-frame -h` lists the modes.

For example, the run command could look like:
`./first-frame -m 0`

The first-frame can talk to a remote ToF camera over the network.

For example if the ip address of the remote camera is `192.168.56.1` the run command could look like:

`./first-frame -ip 192.168.56.1 -m 0`

## Mode fusion

`-fuse <firstMode>,<secondMode>` fuses a short-range mode with a long-range mode into one depth frame (ADTF3066: short-range 0, 1, 3, 6, long-range 7, 8; other imagers: 2-frequency short-range, 3-frequency long-range). The first mode leads the sequence, so the SR frame comes first when the first mode is short-range. No JSON config is required. It overrides `-m` and is not supported with `-ip`. Output files are named `mode_<firstMode>_<secondMode>`, e.g. `out_depth_mode_0_7.bin`.

`./first-frame -fuse 0,7`

`-fusion-method` chooses how the frames are fused (default `srlr`):

| Method | Modes | Example |
|---|---|---|
| `srlr` | one short-range + one long-range mode (HDR depth) | `./first-frame -fuse 0,7` |
| `lrinval` | one short- or long-range mode, invalidates pixels by the `-lrinval-type` criterion: 1 AB, 2 edge confidence, 3 confidence, 4 radial (default 1) | `./first-frame -fuse 7 -fusion-method lrinval -lrinval-type 1` |
| `twolr` | two long-range modes of the same resolution (flying-pixel rejection) | `./first-frame -fuse 7,7 -fusion-method twolr` |

## Lens scatter compensation

`-lens-scatter` captures the `-m` mode with lens scatter compensation (non-PCM modes): the ADSD3500 outputs raw frames and depth is computed on the GPU by the lens scatter depth compute library. It is not supported with `-fuse` or `-ip`.

`./first-frame -m 0 -lens-scatter`
