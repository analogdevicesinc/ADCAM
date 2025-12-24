/*
 * MIT License
 *
 * Copyright (c) 2025 Analog Devices, Inc.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
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

    /** Image type RGB.
	 *
	 * \details
	 * Each pixel of RGB data is three bytes representing Red, Green, Blue components.
	 * The value of the data represents color information.
	 *
	 * \details
	 * This format represents visible light and is captured by the RGB camera.
	 *
	 * \details
	 * Stride indicates the length of each line in bytes and should be used to determine the start location of each
	 * line of the image in memory.
	 */
    ADI_IMAGE_FORMAT_RGB,

} ADI_Image_Format_t;

#ifdef __cplusplus
}
#endif

#endif //ADITYPES_H
