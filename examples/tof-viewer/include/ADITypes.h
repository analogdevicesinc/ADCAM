/*
 * BSD 3-Clause License
 *
 * Copyright (c) 2019, Analog Devices, Inc.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice, this
 *    list of conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 *
 * 3. Neither the name of the copyright holder nor the names of its
 *    contributors may be used to endorse or promote products derived from
 *    this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 * CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#ifndef ADITYPES_H
#define ADITYPES_H

#ifdef __cplusplus
#include <cinttypes>
#include <cstddef>
#include <cstring>
#else
#include <inttypes.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    /** Depth image type DEPTH16.
	 *
	 * \details
	 * Each pixel of DEPTH16 data is two bytes of little endian unsigned depth data. The unit of the data is in
	 * millimeters from the origin of the camera.
	 *
	 * \details
	 * Stride indicates the length of each line in bytes and should be used to determine the start location of each
	 * line of the image in memory.
	 */
    ADI_IMAGE_FORMAT_DEPTH16 = 0,

    /** Image type AB16.
	 *
	 * \details
	 * Each pixel of AB16 data is two bytes of little endian unsigned depth data. The value of the data represents
	 * brightness.
	 *
	 * \details
	 * This format represents infrared light and is captured by the depth camera.
	 *
	 * \details
	 * Stride indicates the length of each line in bytes and should be used to determine the start location of each
	 * line of the image in memory.
	 */
    ADI_IMAGE_FORMAT_AB16,

} ADI_Image_Format_t;

#ifdef __cplusplus
}
#endif

#endif //ADITYPES_H
