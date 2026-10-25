// SPDX-License-Identifier: Apache-2.0
// ChakraV's camera on the board: the ESP-Mosaico camera module in the left slot, V1.4 (SC101IOT)
// or V1.2 (OV3640), as the square view's JPEG frames, their mean luma and the module's flash LED.
// The task runs on its own; the UI side only takes finished frames (camera.c, header comment).
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Starts the camera task; the camera stays closed until camera_board_set(true, ...). */
esp_err_t camera_board_start(void);
/** The Camera settings: on or off, frames a second (1, 2 or 4). Any task; does not block. */
void camera_board_set(bool on, int fps);
/** The flash LED (Off, On, Auto's verdict from chakra_core). Any task; applied by the camera task. */
void camera_board_light(bool on);
/** UI task: the newest finished frame, if there is one not taken yet: a JPEG of exactly
 *  CHAKRA_CAM_W x CHAKRA_CAM_H and its mean luma 0..255. The buffer stays valid until
 *  camera_board_release(); chakra_core_set_frame copies it, so release right after. */
bool camera_board_take(const uint8_t **jpeg, size_t *size, int *luma);
void camera_board_release(void);
/** UI task: the source line and its kind (CHAKRA_SOURCE_*), when it changed since the last call. */
bool camera_board_source(char *text, size_t len, int *kind);

#ifdef __cplusplus
}
#endif
