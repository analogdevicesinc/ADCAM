1) Firmware_update executable will be available at this path and it takes three argument.

	Usage: ./firmware_update <bin|stream file> <master|slave>

        Note:
          i) Copy the latest Fw_Update_X.X.X.bin and ADSD3500_Second_Firmware_Host_Boot_X_X_X.stream file to Firmware_update_utility.
         ii) Below mentioned file, which is passed as an argument to executable file is just an example bin or stream file.

	$ cd Workspace/Tools/Firmware_update_utility
	$ ./firmware_update Fw_Update_x.x.x.bin master
	$ ./firmware_update ADSD3500_Second_Firmware_Host_Boot_X_X_X.stream slave
