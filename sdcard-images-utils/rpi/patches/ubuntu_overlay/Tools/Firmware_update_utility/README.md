1) firmware_update executable will be available at this path.

	Usage: ./firmware_update <ADCAM_Fw_Update_X.Y.Z.bin> [--force]

        Note:
          i)  Copy the latest ADCAM_Fw_Update_X.Y.Z.bin dual-slot file to Firmware_update_utility.
              The .bin file must be at least 262144 bytes (2 x 128 KB slots):
                Slot 0 (offset 0x00000): master firmware (chunkType=0x54)
                Slot 1 (offset 0x20000): slave  firmware (chunkType=0x60)
         ii)  Single-device (master only) and dual-device (master + slave) configurations
              are detected automatically at runtime — no separate slave argument required.
        iii)  --force is optional and only required when intentionally downgrading firmware.

	$ cd Workspace/Tools/Firmware_update_utility
	$ ./firmware_update ADCAM_Fw_Update_8.1.0.bin
	$ ./firmware_update ADCAM_Fw_Update_8.1.0.bin --force   # downgrade only
