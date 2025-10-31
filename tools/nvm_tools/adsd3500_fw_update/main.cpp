/****************************************************************************
# Copyright (c) 2024 - Analog Devices Inc. All Rights Reserved.
# This software is proprietary & confidential to Analog Devices, Inc.
# and its licensors.
# *****************************************************************************
# *****************************************************************************/

#include <iostream>
#include "Adsd3500.h"

int main(int argc, char *argv[]) {

#ifdef NXP
	int user;
	user = getuid();
	if (user != 0)
	{
		std::cout << "Please run the application with sudo" << std::endl;
		return 1;
	}
#endif

	if (argc != 3) {
		fprintf(stderr, "Usage: %s <file> <master|slave>\n", argv[0]);
		fprintf(stderr, "       .bin file for master target\n");
		fprintf(stderr, "       .stream file for slave target\n");
		return 1;
	}

	const char *filename = argv[1];
	const char *target   = argv[2];

	if (strcmp(target, "master") != 0 && strcmp(target, "slave") != 0) {
		fprintf(stderr, "Error: Second argument must be 'master' or 'slave'.\n");
		return 1;
	}

	if (!validate_ext(filename, target)) {
		fprintf(stderr, "Error: For '%s' target, file must have a '%s' extension.\n",
				target, strcmp(target, "master") == 0 ? ".bin" : ".stream");
		return 1;
	}

	auto adsd = Adsd3500(filename, target);
}
