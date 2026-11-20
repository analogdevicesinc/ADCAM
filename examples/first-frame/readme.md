# first-frame sample code

## Overview

The first-frame is a cross platform sample code that shows how to use the aditof sdk to configure a camera so that frames can be captured from it.

For example, the run command could look like:
`./first-frame config/config_adsd3500_adsd3100.json`

The first-frame can talk to a remote ToF camera over the network.

For example if the ip address of the remote camera is `192.168.56.1` the run command could look like:

`./first-frame 192.168.56.1 config/config_adsd3500_adsd3100.json`

In addition please ensure the correct mode is selected. This is done by manually editing the code. In the future this will move to a comamnd line option.

See https://github.com/analogdevicesinc/ToF/blob/e551cab2e470f3743a01a49ef4c22fe663d7715e/examples/first-frame/main.cpp#L127

## Mode fusion

`-fuse <firstMode>,<secondMode>` fuses a short-range mode with a long-range mode into one depth frame (ADTF3066: short-range 0, 1, 3, 6, long-range 7, 8; other imagers: 2-frequency short-range, 3-frequency long-range). The first mode leads the sequence, so the SR frame comes first when the first mode is short-range. No JSON config is required. It overrides `-m` and is not supported with `-ip`. Output files are named `mode_<firstMode>_<secondMode>`, e.g. `out_depth_mode_0_7.bin`.

`./first-frame -fuse 0,7`

## Lens scatter compensation

`-lens-scatter` captures the `-m` mode with lens scatter compensation (non-PCM modes): the ADSD3500 outputs raw frames and depth is computed on the GPU by the lens scatter depth compute library. It is not supported with `-fuse` or `-ip`.

`./first-frame -m 0 -lens-scatter`
