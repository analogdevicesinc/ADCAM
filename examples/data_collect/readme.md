# Data collect Example

## Requirements
* Default Configuration and calibration files are in "sdk/config" folder

## Command Line Options

```
Usage:
      data_collect
      data_collect [--f <folder>] [--fps <frame rate>] [--n <ncapture>] [--m <mode>] [--ccb FILE] [--ip <ip>] [-scf <save-configuration-file>] [-lcf <load-configuration-file>]
      data_collect [--f <folder>] [--fps <frame rate>] [--n <ncapture>] [--m <mode>] [--lens-scatter] [-lcf <load-configuration-file>]
      data_collect [--f <folder>] [--fps <frame rate>] [--n <ncapture>] [--fuse <firstMode>[,<secondMode>]] [--fusion-method <srlr|lrinval|twolr>] [--lrinval-type <1-4>] [-lcf <load-configuration-file>]
      data_collect (-h | --help)

    Options:
      -h --help          Show this screen.
      --f <folder>       Output folder (max name 512) [default: ./]
      --fps <frame rate>   Frame rate in frames per second [default: 10]
      --n <ncapture>     Capture frame num. [default: 1]
      --m <mode>         Mode to capture data in. [default: 0]
      --lens-scatter     Lens scatter compensation (non-PCM mode).
                         Not with --fuse or --ip.
      --fuse <firstMode>[,<secondMode>]
                         Start mode fusion. Overrides --m.
                         Not supported with --ip.
      --fusion-method <srlr|lrinval|twolr>
                         srlr: one SR (0, 1, 3, 6) + one LR (7, 8) mode,
                               e.g. --fuse 0,7; frames arrive at fps/2
                         lrinval: one SR or LR mode, e.g. --fuse 7
                         twolr: two LR modes (7, 8) of equal
                                resolution, e.g. --fuse 7,7; frames
                                arrive at fps/2
                         [default: srlr]
      --lrinval-type <1-4>
                         lrinval criterion: 1 AB, 2 edge conf, 3 conf,
                         4 radial. [default: 1]
      --ccb <FILE>       The path to store CCB content
      --ip <ip>          Camera IP
      --scf <save-configuration-file>    Save current configuration to json file
      --lcf <load-configuration-file>    Load configuration from json file

    Note: --m argument supports index (0, 1, etc.)

    Valid mode (--m) options are:
        0: short-range native
        1: long-range native
        2: short-range Qnative
        3: long-range Qnative
        4: pcm-native
        5: long-range mixed
        6: short-range mixed
```

## Run
To run the example, run data_collect with the options above. Some example commands can be seen below.

```
./data_collect
./data_collect --f ../data_output
./data_collect --f ../data_output --m 1
./data_collect --f ../data_output --n 50
./data_collect --f ../data_output --m 1 --n 4 --fps 30
```

## Mode fusion
`--fuse <firstMode>,<secondMode>` fuses a short-range mode with a long-range mode (ADTF3066: short-range 0, 1, 3, 6, long-range 7, 8; other imagers: 2-frequency short-range, 3-frequency long-range). The first mode leads the sequence, so the SR frame comes first when the first mode is short-range. No JSON config is required. It overrides `--m` and is not supported with `--ip`. `--fps` is the sensor rate, so fused frames arrive at fps/2; the recording header stores the fusion pair so tof-viewer playback shows it.

```
./data_collect --fuse 0,7 --fps 20 --n 100 --f ../data_output
```

`--fusion-method` chooses how the frames are fused (default `srlr`):

| Method | Modes | Example |
|---|---|---|
| `srlr` | one short-range + one long-range mode (HDR depth); frames arrive at fps/2 | `./data_collect --fuse 0,7 --fps 20 --n 100` |
| `lrinval` | one short- or long-range mode, invalidates pixels by the `--lrinval-type` criterion: 1 AB, 2 edge confidence, 3 confidence, 4 radial (default 1) | `./data_collect --fuse 7 --fusion-method lrinval --lrinval-type 1 --n 100` |
| `twolr` | two long-range modes of the same resolution (flying-pixel rejection); frames arrive at fps/2 | `./data_collect --fuse 7,7 --fusion-method twolr --fps 20 --n 100` |

## Lens scatter compensation
`--lens-scatter` captures the `--m` mode with lens scatter compensation (non-PCM modes): the ADSD3500 outputs raw frames and depth is computed on the GPU by the lens scatter depth compute library. It is not supported with `--fuse` or `--ip`.

```
./data_collect --m 0 --lens-scatter --n 100 --f ../data_output
```

## Known Issues
None

## Troubleshooting
* If you see the error "Could not initialize camera!" it could because the USB device could not be opened. Check the USB device connection. If the USB connection is proper then, it is because of the config file path passed is incorrect. Check the config file passed in camera->initialize() function.
* If you see the error "Could not start camera!" it is because of depth compute initialization failed or may be due to setting calibration parameters, check the camera calibration file passed is correct.
* If you see the error "config Json file is not provided.." pass the --c option with valid json file.
