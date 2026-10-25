// SPDX-License-Identifier: Apache-2.0
// ChakraV's camera on the board: the ESP-Mosaico camera module as the app's square view.
//
// What: one task opens the module through the BSP's mosaico_module_camera (it claims the left
// slot, reads the slot EEPROM, detects the sensor by its ID and registers /dev/video2), takes a
// UYVY frame every 1000 / fps ms, measures its mean luma (Rec. 601 Y, read straight from the UYVY
// bytes), and turns the centre square into the view: the PPA crops 720 x 720, scales it by 6/16 to
// CHAKRA_CAM_W x CHAKRA_CAM_H (270), rotates it 270 degrees and mirrors it as the camera kit's
// preview does (camera_lcd_preview), into RGB565; the hardware JPEG encoder makes the frame that
// chakra_core_set_frame() shows. Three JPEG buffers: one being written, the newest finished one,
// and the one the UI task is reading. The flash LED follows camera_board_light().
//
// Modules (Espressif user_guide_camera, BSP components/mosaico_module_camera):
//   V1.4  SC101IOT, 1 MP, 1280 x 720 UYVY (CONFIG_CAMERA_SC101IOT_DVP_DEFAULT_FMT_YUV422_1280X720_15FPS,
//         the sensor's Kconfig default), 2.9 um pixels, 3.1 mm F1.8 lens with manual focus,
//         73 x 42 degrees; XCLK from the module's 20 MHz oscillator. The expected module.
//   V1.2  OV3640, 1024 x 768 UYVY (CONFIG_CAMERA_OV3640_DVP_DEFAULT_FMT_YUV422_UYVY_1024X768_25FPS),
//         68 degrees diagonal.
//   The module is told apart by the format its sensor opens with (the config asks for width and
//   height 0: each sensor's Kconfig default, sdkconfig.defaults), which the BSP chose after reading
//   the sensor's PID (it logs "Camera opened: sensor=SC101IOT pid=0xDA4A"). The slot EEPROM
//   (24C02 at 0x50) is logged too: its hw_version for V1.2 and V1.4 is not documented.
//   Both mount sideways: the upright picture is portrait, and the 720 x 720 centre square is all of
//   V1.4's short side (about 42 x 42 degrees) and the centre 720 of V1.2's 768.
//
// Flash: two LEDs on GPIO34, LOW = on, through a high-side P-MOS. The BSP drives GPIO34 as an
// open-drain output, presets it high (off) before configuring it and disables its sleep select,
// so the LEDs stay off when the host powers down (mosaico_camera.c camera_flash_force_off); here
// only mosaico_camera_flash_trigger() and mosaico_camera_flash_stop() are called.
//
// Why: owner 25.10.2026, "ich glaub der Mosaico kommt mit dem SC101IoT ... bau alles um"; "Kamera
// soll wie bei der Camera-Kit-Kamera sein".
//
// Pitfalls (none of this has run on a board yet; the board is on order):
//   * The PPA scales in steps of 1/16 (ESP-IDF ppa.rst): 720 x 6/16 = 270 exactly. Another view size
//     needs another crop (chakra_core.h CHAKRA_CAM_W).
//   * GPIO14 is DVP D4 while the camera runs, which suspends the slot EEPROM; GPIO33 is DVP D2 and
//     shares the USB Serial/JTAG D- pad (the BSP takes the pad; ChakraV's console is the UART).
//   * Return every frame before stopping or deleting the camera (BSP README); the task does.
//   * CHECK ON THE BOARD: the orientation (the kit preview's 270 + mirror_y is copied, so the view
//     matches the kit's screen), RGB565 byte order into the JPEG encoder (swapped colours:
//     set pixel_reverse), the encoder with a 270 px width (not a multiple of 16; else use 272 with
//     a 726 crop on V1.2 only, or YUV444), how long the flash may stay on (heat), and Auto's
//     LUMA_DARK with the SC101IOT's larger pixels (chakra_core.c).
#include "camera.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "chakra_core.h"
#include "driver/jpeg_encode.h"
#include "driver/ppa.h"
#include "esp_cache.h"
#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "linux/videodev2.h"
#include "mosaico_module_camera.h"
#include "mosaico_module_mgr.h"

#define CROP 720                 // the upright square the view is made from (720 x 6/16 = 270)
#define JPEG_SLOTS 3             // writing, newest, being read
#define JPEG_MAX (96 * 1024)     // a 270 x 270 frame at quality 80 is about 15 to 30 KB
#define JPEG_QUALITY 80
#define RETRY_MS 5000            // no module: try again
#define LUMA_STEP 8              // every 8th pixel and row of the square for the mean luma

static const char *TAG = "chakrav_cam";

static struct {
    TaskHandle_t task;
    volatile bool on, light;
    volatile int fps;
    portMUX_TYPE lock;
    uint8_t *jpeg[JPEG_SLOTS];
    size_t jpeg_len[JPEG_SLOTS];
    int luma[JPEG_SLOTS];
    int ready, busy;             // slot indices, -1 none
    char source[48];
    int source_kind;
    bool source_dirty;
} s = {.lock = portMUX_INITIALIZER_UNLOCKED, .ready = -1, .busy = -1, .fps = 2};

static void set_source(int kind, const char *text)
{
    portENTER_CRITICAL(&s.lock);
    snprintf(s.source, sizeof(s.source), "%s", text);
    s.source_kind = kind;
    s.source_dirty = true;
    portEXIT_CRITICAL(&s.lock);
}

void camera_board_set(bool on, int fps)
{
    s.fps = fps == 1 || fps == 4 ? fps : 2;
    s.on = on;
    if (s.task) {
        xTaskNotifyGive(s.task);
    }
}

void camera_board_light(bool on)
{
    s.light = on;
    if (s.task) {
        xTaskNotifyGive(s.task);
    }
}

bool camera_board_take(const uint8_t **jpeg, size_t *size, int *luma)
{
    bool got = false;
    portENTER_CRITICAL(&s.lock);
    if (s.ready >= 0 && s.busy < 0) {
        s.busy = s.ready;
        s.ready = -1;
        *jpeg = s.jpeg[s.busy];
        *size = s.jpeg_len[s.busy];
        *luma = s.luma[s.busy];
        got = true;
    }
    portEXIT_CRITICAL(&s.lock);
    return got;
}

void camera_board_release(void)
{
    portENTER_CRITICAL(&s.lock);
    s.busy = -1;
    portEXIT_CRITICAL(&s.lock);
}

bool camera_board_source(char *text, size_t len, int *kind)
{
    bool changed = false;
    portENTER_CRITICAL(&s.lock);
    if (s.source_dirty) {
        s.source_dirty = false;
        snprintf(text, len, "%s", s.source);
        *kind = s.source_kind;
        changed = true;
    }
    portEXIT_CRITICAL(&s.lock);
    return changed;
}

/* A slot that is neither the newest finished frame nor the one being read. */
static int free_slot(void)
{
    int slot = -1;
    portENTER_CRITICAL(&s.lock);
    for (int i = 0; i < JPEG_SLOTS && slot < 0; ++i) {
        if (i != s.ready && i != s.busy) {
            slot = i;
        }
    }
    portEXIT_CRITICAL(&s.lock);
    return slot;
}

static void publish(int slot, size_t len, int luma)
{
    portENTER_CRITICAL(&s.lock);
    s.jpeg_len[slot] = len;
    s.luma[slot] = luma;
    s.ready = slot;
    portEXIT_CRITICAL(&s.lock);
}

typedef struct {
    mosaico_camera_handle_t cam;
    ppa_client_handle_t ppa;
    jpeg_encoder_handle_t jpeg;
    uint16_t *rgb;               // the PPA's RGB565 view, the JPEG encoder's input
    size_t rgb_size;
    bool lit;
} pipeline_t;

static void close_camera(pipeline_t *p)
{
    if (!p->cam) {
        return;
    }
    mosaico_camera_flash_stop(p->cam);
    p->lit = false;
    mosaico_camera_stop_stream(p->cam);
    mosaico_camera_close(p->cam);
    mosaico_camera_del(p->cam);  // releases the slot and the flash GPIO
    p->cam = NULL;
}

/* Opens the module; the source line names it, or says there is none. */
static esp_err_t open_camera(pipeline_t *p)
{
    mosaico_camera_config_t cfg = MOSAICO_CAMERA_DEFAULT_CONFIG();  // UYVY, the sensor's Kconfig default size
    esp_err_t err = mosaico_camera_new(&cfg, &p->cam);
    if (err == ESP_OK) {
        err = mosaico_camera_open(p->cam);
    }
    if (err == ESP_OK) {
        err = mosaico_camera_start_stream(p->cam);
    }
    if (err != ESP_OK) {
        if (p->cam) {
            mosaico_camera_del(p->cam);
            p->cam = NULL;
        }
        ESP_LOGW(TAG, "no camera module in the left slot: %s", esp_err_to_name(err));
        set_source(CHAKRA_SOURCE_NONE, "No camera module");
        return err;
    }
    mosaico_camera_info_t info = {0};
    mosaico_camera_get_info(p->cam, &info);
    const bool v14 = info.width == 1280 && info.height == 720;
    const bool v12 = info.width == 1024 && info.height == 768;
    mosaico_module_mgr_info_t slot = {0};
    if (mosaico_module_mgr_get_info(MOSAICO_MODULE_MGR_SLOT_LEFT, &slot) == ESP_OK &&
        slot.descriptor_state == MOSAICO_MODULE_DESCRIPTOR_VALID) {
        ESP_LOGI(TAG, "slot EEPROM: board %.32s, type 0x%02x, hw %u, sw %u", slot.eeprom.board_name,
                 slot.eeprom.board_type, slot.eeprom.hw_version, slot.eeprom.sw_version);
    }
    ESP_LOGI(TAG, "camera %" PRIu32 " x %" PRIu32 " at %" PRIu32 " fps: %s", info.width, info.height, info.frame_rate,
             v14 ? "V1.4 SC101IOT" : v12 ? "V1.2 OV3640" : "unknown module");
    if (info.pixel_format != V4L2_PIX_FMT_UYVY || info.width < CROP || info.height < CROP) {
        set_source(CHAKRA_SOURCE_NONE, "Camera format not supported");
        close_camera(p);
        return ESP_ERR_NOT_SUPPORTED;
    }
    char text[48];
    snprintf(text, sizeof(text), "%s · %" PRIu32 " × %" PRIu32, v14 ? "SC101IOT v1.4" : v12 ? "OV3640 v1.2" : "Camera",
             info.width, info.height);
    set_source(CHAKRA_SOURCE_CAMERA, text);
    return ESP_OK;
}

/* The mean Y of the centre square, from the UYVY bytes (U Y0 V Y1: Y at odd offsets). */
static int frame_luma(const mosaico_camera_frame_t *f, uint32_t stride)
{
    const uint8_t *px = f->data;
    const uint32_t x0 = (f->width - CROP) / 2, y0 = (f->height - CROP) / 2;
    uint32_t sum = 0, n = 0;
    for (uint32_t y = y0; y < y0 + CROP; y += LUMA_STEP) {
        const uint8_t *row = px + (size_t)y * stride;
        for (uint32_t x = x0; x < x0 + CROP; x += LUMA_STEP) {
            sum += row[2 * x + 1];
            ++n;
        }
    }
    return n ? (int)(sum / n) : -1;
}

/* One frame: luma, the PPA's square, the JPEG. */
static esp_err_t take_frame(pipeline_t *p)
{
    mosaico_camera_frame_t f = {0};
    ESP_RETURN_ON_ERROR(mosaico_camera_get_frame(p->cam, &f), TAG, "no frame");
    esp_err_t err = ESP_OK;
    const uint32_t stride = f.bytes_per_line ? f.bytes_per_line : f.width * 2U;
    if (f.pixel_format != V4L2_PIX_FMT_UYVY || f.width < CROP || f.height < CROP) {
        err = ESP_ERR_INVALID_SIZE;
        goto done;
    }
    esp_cache_msync((void *)f.data, f.size, ESP_CACHE_MSYNC_FLAG_DIR_M2C | ESP_CACHE_MSYNC_FLAG_INVALIDATE);
    const int luma = frame_luma(&f, stride);
    const ppa_srm_oper_config_t op = {
        .in = {.buffer = f.data, .pic_w = stride / 2U, .pic_h = f.height, .block_w = CROP, .block_h = CROP,
               .block_offset_x = ((f.width - CROP) / 2U) & ~1U, .block_offset_y = ((f.height - CROP) / 2U) & ~1U,
               .srm_cm = PPA_SRM_COLOR_MODE_YUV422_UYVY, .yuv_range = PPA_COLOR_RANGE_LIMIT,
               .yuv_std = PPA_COLOR_CONV_STD_RGB_YUV_BT601},
        .out = {.buffer = p->rgb, .buffer_size = p->rgb_size, .pic_w = CHAKRA_CAM_W, .pic_h = CHAKRA_CAM_H,
                .srm_cm = PPA_SRM_COLOR_MODE_RGB565},
        .rotation_angle = PPA_SRM_ROTATION_ANGLE_270,  // as camera_lcd_preview: upright, like the kit's screen
        .scale_x = (float)CHAKRA_CAM_W / CROP,         // 6/16, exact in the PPA's 1/16 steps
        .scale_y = (float)CHAKRA_CAM_H / CROP,
        .mirror_y = true,
        .mode = PPA_TRANS_MODE_BLOCKING,
    };
    err = ppa_do_scale_rotate_mirror(p->ppa, &op);
    if (err != ESP_OK) {
        goto done;
    }
    const int slot = free_slot();
    if (slot < 0) {
        goto done;  // cannot happen with three slots; skip the frame rather than overwrite
    }
    const jpeg_encode_cfg_t enc = {.width = CHAKRA_CAM_W, .height = CHAKRA_CAM_H,
                                   .src_type = JPEG_ENCODE_IN_FORMAT_RGB565, .sub_sample = JPEG_DOWN_SAMPLING_YUV420,
                                   .image_quality = JPEG_QUALITY};
    uint32_t len = 0;
    err = jpeg_encoder_process(p->jpeg, &enc, (const uint8_t *)p->rgb, CHAKRA_CAM_W * CHAKRA_CAM_H * 2, s.jpeg[slot],
                               JPEG_MAX, &len);
    if (err == ESP_OK) {
        publish(slot, len, luma);
    }
done:
    mosaico_camera_return_frame(p->cam, &f);
    return err;
}

static esp_err_t make_pipeline(pipeline_t *p)
{
    const ppa_client_config_t ppa = {.oper_type = PPA_OPERATION_SRM, .max_pending_trans_num = 1};
    ESP_RETURN_ON_ERROR(ppa_register_client(&ppa, &p->ppa), TAG, "PPA client");
    const jpeg_encode_engine_cfg_t eng = {.timeout_ms = 100};
    ESP_RETURN_ON_ERROR(jpeg_new_encoder_engine(&eng, &p->jpeg), TAG, "JPEG encoder");
    const jpeg_encode_memory_alloc_cfg_t in = {.buffer_direction = JPEG_ENC_ALLOC_INPUT_BUFFER};
    const jpeg_encode_memory_alloc_cfg_t out = {.buffer_direction = JPEG_ENC_ALLOC_OUTPUT_BUFFER};
    p->rgb = jpeg_alloc_encoder_mem(CHAKRA_CAM_W * CHAKRA_CAM_H * 2, &in, &p->rgb_size);
    ESP_RETURN_ON_FALSE(p->rgb, ESP_ERR_NO_MEM, TAG, "view buffer");
    for (int i = 0; i < JPEG_SLOTS; ++i) {
        size_t got = 0;
        s.jpeg[i] = jpeg_alloc_encoder_mem(JPEG_MAX, &out, &got);
        ESP_RETURN_ON_FALSE(s.jpeg[i] && got >= JPEG_MAX, ESP_ERR_NO_MEM, TAG, "JPEG buffer");
    }
    return ESP_OK;
}

static void camera_task(void *arg)
{
    (void)arg;
    pipeline_t p = {0};
    if (make_pipeline(&p) != ESP_OK) {
        set_source(CHAKRA_SOURCE_NONE, "No camera pipeline");
        vTaskDelete(NULL);
        return;
    }
    TickType_t retry_at = 0;
    for (;;) {
        if (!s.on) {
            close_camera(&p);
            ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
            continue;
        }
        if (!p.cam) {
            if (retry_at && (int32_t)(xTaskGetTickCount() - retry_at) < 0) {
                ulTaskNotifyTake(pdTRUE, retry_at - xTaskGetTickCount());
                continue;
            }
            if (open_camera(&p) != ESP_OK) {
                retry_at = xTaskGetTickCount() + pdMS_TO_TICKS(RETRY_MS);
                continue;
            }
            retry_at = 0;
        }
        if (s.light != p.lit) {
            p.lit = s.light;
            if (p.lit) {
                mosaico_camera_flash_trigger(p.cam);
            } else {
                mosaico_camera_flash_stop(p.cam);
            }
        }
        const TickType_t t0 = xTaskGetTickCount();
        const esp_err_t err = take_frame(&p);
        if (err == ESP_ERR_TIMEOUT || err == ESP_FAIL) {
            ESP_LOGW(TAG, "frame failed (%s); reopening the camera", esp_err_to_name(err));
            close_camera(&p);
            continue;
        }
        const TickType_t period = pdMS_TO_TICKS(1000 / s.fps), spent = xTaskGetTickCount() - t0;
        ulTaskNotifyTake(pdTRUE, spent < period ? period - spent : 1);  // woken early by a setting
    }
}

esp_err_t camera_board_start(void)
{
    set_source(CHAKRA_SOURCE_NONE, "Waiting for camera");
    return xTaskCreate(camera_task, "chakrav_cam", 6144, NULL, 5, &s.task) == pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}
