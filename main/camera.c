// SPDX-License-Identifier: Apache-2.0
// ChakraV's camera on the board: the ESP-Mosaico camera module as the app's 16:9 view.
//
// What: one task opens the module through the BSP's mosaico_module_camera (it claims the left
// slot, reads the slot EEPROM, detects the sensor by its ID and registers /dev/video2), asks the
// sensor for its PID itself (camera_sensor_pid) to name the module, takes a UYVY frame every
// 1000 / fps ms, measures its mean luma (Rec. 601 Y, read straight from the UYVY bytes), and turns
// the centre 16:9 band into the view: the PPA crops it (view_crop), scales it by the largest exact
// 1/16 step that makes CHAKRA_CAM_W x CHAKRA_CAM_H (400 x 224), into RGB565, turned and mirrored as
// the mount needs (view_transform). The hardware JPEG encoder makes the frame that
// chakra_core_set_frame() shows. Three JPEG buffers: one being written, the newest finished one,
// and the one the UI task is reading. The flash LED follows camera_board_light().
//
// Modules (Espressif user_guide_camera, BSP components/mosaico_module_camera):
//   V1.4  SC101IOT, 1 MP, 1280 x 720 UYVY (CONFIG_CAMERA_SC101IOT_DVP_DEFAULT_FMT_YUV422_1280X720_15FPS,
//         the sensor's Kconfig default), 2.9 um pixels, 3.1 mm F1.8 lens with manual focus,
//         73 x 42 degrees; XCLK from the module's 20 MHz oscillator. The expected module.
//   V1.2  OV3640, 1024 x 768 UYVY (CONFIG_CAMERA_OV3640_DVP_DEFAULT_FMT_YUV422_UYVY_1024X768_25FPS),
//         68 degrees diagonal.
//   The module is told apart by its sensor's PID (SC101IOT 0xDA4A, OV3640 0x364C or 0x3641), read
//   through a second reference to /dev/video2 the way the BSP reads it (camera_sensor_pid; esp_video
//   counts references, so the BSP's own fd stays open). The size the sensor opens with is only the
//   fallback when that read fails: the config asks for width and height 0, each sensor's Kconfig
//   default, and the OV3640 lines in sdkconfig.defaults must stay (its own default is RGB565
//   640 x 480; the OV3640 driver also has a 1280 x 720 mode). The slot EEPROM (24C02 at 0x50) is
//   logged once (log_module_info); it cannot tell V1.2 from V1.4: Espressif's programmer writes
//   hw 1.2 into every profile (docs/CAMERA_BOARD_QUESTIONS.md, question 3).
//   Mounted for landscape (CHAKRA_CAM_LANDSCAPE, default) the picture stays 1280 x 720 and the view is
//   all of it (owner 26.10.2026: "Bildausschnitt wie bei Zielkamera 16:9"):
//     V1.4  1280 x 717 at 5/16 = 400 x 224, the whole frame, 73 x 42 degrees (one view row of 225 left out)
//     V1.2  the centre 916 x 512 at 7/16 = 400 x 224, about 51 x 30 degrees (6/16 of its whole 16:9 band,
//           1024 x 576, would be 384 x 216: a frame of another size, and the view shows only one size)
//   Sideways (CHAKRA_CAM_LANDSCAPE 0) the picture is turned to portrait and the view is a 16:9 band
//   across it: raw 400 x 712 at 9/16, turned to 400 x 225, of which the encoder takes 224 rows; about
//   42 x 26 degrees on V1.4. tools/camera_live.py view_crop() emulates the same.
//
// Orientation (docs/CAMERA_BOARD_QUESTIONS.md, question 2): the sensor reads out unmirrored. The PPA
// scales, then rotates counter-clockwise, then mirrors (mirror_x left-right, mirror_y top-bottom).
//   Landscape: rotation 0, no mirror; CHAKRA_CAM_TURN_180 turns it (mirror_x and mirror_y together)
//   when the module sits the other way up.
//   Sideways: 90 degrees counter-clockwise, no mirror, the true (rear-facing) picture. The camera kit's
//   preview (camera_lcd_preview) uses 270 + mirror_y, which is the same picture mirrored left to right,
//   the selfie view for the folded, front-facing lens: CHAKRA_CAM_MIRROR gives that look (it flips
//   mirror_x in either mount, rotate first, mirror after).
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
//   * The PPA scales in steps of 1/16 (ESP-IDF ppa.rst) and its output size is the block times the
//     step, rounded down (ppa_srm.c): view_crop() picks the block so that the width comes out exactly
//     CHAKRA_CAM_W. UYVY input needs an even block width and x offset (ppa_srm.c).
//   * The view is 400 x 224, not 1280 x 5/16 = 400 x 225: with JPEG_DOWN_SAMPLING_YUV420 the encoder
//     works in 16 x 16 blocks (jpeg_encode.c: mcux = mcuy = 16), and 400 = 25 x 16, 224 = 14 x 16 are
//     whole blocks. 225 rows would end in a block of one row; Espressif's encoder table only shows
//     partial blocks of 8 rows (1920 x 1080, jpeg.rst), and the driver checks no size, so an odd height
//     would be a guess. The width was never the question: 400 is a multiple of 16, as 320 would be.
//   * GPIO14 is DVP D4 while the camera runs. The slot EEPROM stays readable: the camera's EEPROM is
//     fixed at 0x50 with no address pin, the BSP claims the slot with PROBE_WHILE_CLAIMED, and
//     mosaico_module_mgr_get_info() returns the descriptor before, during and after streaming.
//     GPIO33 is DVP D2 and shares the USB Serial/JTAG D- pad (the BSP takes the pad; ChakraV's
//     console is the UART).
//   * CAM_PWDN (GPIO48) is the BSP's since 7cbfb39 (b60f5d8, "fix: update camera app"): low = run,
//     high = sleep, also for the SC101IOT; open and start wake the sensor, stop and close put it to
//     sleep. The PID read runs between open and start, while the sensor is awake.
//   * Return every frame before stopping or deleting the camera (BSP README); the task does.
//   * CHECK ON THE BOARD, the orientation (two minutes, docs/CAMERA_BOARD_QUESTIONS.md question 2):
//     mount the module for landscape, lens facing away, and point it at a printed sheet with large
//     text and an arrow pointing up. Text readable, arrow up: nothing to set. Upside down (arrow
//     down): CHAKRA_CAM_TURN_180. Mirrored text (reads right to left) should not happen with the lens
//     rear-facing: note fold state and mount, then try CHAKRA_CAM_MIRROR. Cross-check: a hand moved to
//     your right moves to the picture's right. Once more with the lens folded to front-facing, to
//     decide whether the selfie mirror is wanted. Expected (inference): turning the module 90 degrees
//     clockwise from the kit's mount, seen from behind the camera, lands upright.
//   * CHECK ON THE BOARD: the log lines agree on the module ("sc101iot: Detected Camera sensor
//     PID=0xda4a", "mosaico_camera: Camera opened: sensor=SC101IOT pid=0xDA4A", ours "PID 0xDA4A"),
//     what the slot EEPROM of the real V1.4 says (write it down here), that the PPA writes exactly 400 x 224 from V1.4's 1280 x 717
//     at 5/16 and V1.2's 916 x 512 at 7/16 (and 400 x 225 sideways into the extra row), RGB565 byte
//     order into the JPEG encoder (swapped colours: set pixel_reverse), how long the flash may stay on
//     (heat), and Auto's LUMA_DARK with the SC101IOT's larger pixels (chakra_core.c).
#include "camera.h"

#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include "chakra_core.h"
#include "driver/jpeg_encode.h"
#include "driver/ppa.h"
#include "esp_cache.h"
#include "esp_cam_sensor_types.h"  // esp_cam_sensor_id_t, ESP_CAM_SENSOR_IOC_G_CHIP_ID
#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_video_device.h"      // ESP_VIDEO_DVP_DEVICE_NAME ("/dev/video2")
#include "esp_video_ioctl.h"       // V4L2_CTRL_CLASS_ESP_CAM_IOCTL
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "linux/videodev2.h"
#include "mosaico_module_camera.h"
#include "mosaico_module_mgr.h"

/* How the module is mounted (owner 26.10.2026: "Querformat, die Kamera kann seitlich angeordnet werden").
 * 1: landscape, the sensor's 1280 x 720 stays upright (73 x 42 degrees on V1.4) and is the whole view,
 *    rotation 0, no mirror;
 * 0: sideways (as in the camera kit), turned 90 degrees counter-clockwise to an unmirrored portrait
 *    picture, the view a 16:9 band across it.
 * CHECK ON THE BOARD with the text sheet and the arrow (header comment, Pitfalls). */
#ifndef CHAKRA_CAM_LANDSCAPE
#define CHAKRA_CAM_LANDSCAPE 1
#endif
/* 1: the picture comes out upside down (the module sits the other way up): turn it 180 degrees,
 * mirror_x and mirror_y together. */
#ifndef CHAKRA_CAM_TURN_180
#define CHAKRA_CAM_TURN_180 0
#endif
/* 1: mirror left to right, the selfie view for the lens folded to face the viewer (sideways this is
 * the kit preview's 270 + mirror_y). */
#ifndef CHAKRA_CAM_MIRROR
#define CHAKRA_CAM_MIRROR 0
#endif
#define JPEG_SLOTS 3             // writing, newest, being read
#define VIEW_ROWS (CHAKRA_CAM_H + 1)  // the PPA's output: sideways the 9/16 step gives 225 rows, 224 are kept
#define JPEG_MAX (96 * 1024)     // a 400 x 224 frame at quality 80 is about 20 to 40 KB
#define JPEG_QUALITY 80
#define RETRY_MS 5000            // no module: try again
#define LUMA_STEP 8              // every 8th pixel and row of the view's crop for the mean luma

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

/* The part of the sensor frame (raw, as it comes) that becomes the view, and its PPA step. */
typedef struct {
    uint32_t x, y, w, h;
    float scale;  // n / 16, exact in float
} view_crop_t;

/* The smallest step n/16 (the widest view) whose centred block fits the frame and scales to exactly
 * CHAKRA_CAM_W (the PPA rounds down: out = block * n / 16). Landscape: V1.4 1280 x 720 gives 1280 x 717
 * at 5/16, V1.2 1024 x 768 gives 916 x 512 at 7/16. Sideways (turned 90 degrees) the view's width comes
 * from the raw rows and its height from the raw columns: 400 x 712 at 9/16 on both, 225 rows out.
 * tools/camera_live.py view_crop() emulates it. */
static bool view_crop(uint32_t width, uint32_t height, view_crop_t *c)
{
    for (uint32_t n = 1; n <= 16; ++n) {
        const uint32_t along = (CHAKRA_CAM_W * 16U + n - 1) / n;  // the raw side that becomes the width
        uint32_t across = (CHAKRA_CAM_H * 16U + n - 1) / n;       // the raw side that becomes the height
        uint32_t bw = CHAKRA_CAM_LANDSCAPE ? along : across, bh = CHAKRA_CAM_LANDSCAPE ? across : along;
        bw += bw & 1U;  // UYVY: an even block width
        const uint32_t out_w = (CHAKRA_CAM_LANDSCAPE ? bw : bh) * n / 16U;
        const uint32_t out_h = (CHAKRA_CAM_LANDSCAPE ? bh : bw) * n / 16U;
        if (out_w != CHAKRA_CAM_W || out_h < CHAKRA_CAM_H || out_h > VIEW_ROWS || bw > width || bh > height) {
            continue;
        }
        *c = (view_crop_t){.x = ((width - bw) / 2U) & ~1U, .y = (height - bh) / 2U, .w = bw, .h = bh,
                           .scale = (float)n / 16.0f};
        return true;
    }
    return false;
}

/* The PPA's turn and mirrors for the mount (header comment, Orientation). */
typedef struct {
    ppa_srm_rotation_angle_t rotation;
    bool mirror_x, mirror_y;
} view_transform_t;

static view_transform_t view_transform(void)
{
    return (view_transform_t){
        .rotation = CHAKRA_CAM_LANDSCAPE ? PPA_SRM_ROTATION_ANGLE_0    // landscape: upright as it comes
                                         : PPA_SRM_ROTATION_ANGLE_90,  // sideways: 90 CCW, unmirrored
        .mirror_x = (CHAKRA_CAM_TURN_180 != 0) != (CHAKRA_CAM_MIRROR != 0),
        .mirror_y = CHAKRA_CAM_TURN_180 != 0,
    };
}

/* Sensor PIDs (BSP mosaico_camera.c; esp_cam_sensor sc101iot.h, ov3640.h). */
#define PID_SC101IOT 0xDA4A
#define PID_OV3640_1 0x364C
#define PID_OV3640_2 0x3641

/* The sensor's product ID, read the way the BSP does it (mosaico_camera.c camera_get_sensor_id); 0 if
 * unknown. Call after mosaico_camera_open(): it opens a second reference to the video device, which
 * esp_video counts (esp_video.c esp_video_open), so closing it leaves the BSP's fd as it was. */
static uint16_t camera_sensor_pid(void)
{
    const int fd = open(ESP_VIDEO_DVP_DEVICE_NAME, O_RDWR);
    if (fd < 0) {
        return 0;
    }
    esp_cam_sensor_id_t id = {0};
    struct v4l2_ext_control c = {.id = ESP_CAM_SENSOR_IOC_G_CHIP_ID, .size = sizeof(id), .p_u8 = (uint8_t *)&id};
    struct v4l2_ext_controls cs = {.ctrl_class = V4L2_CTRL_CLASS_ESP_CAM_IOCTL, .count = 1, .controls = &c};
    const int r = ioctl(fd, VIDIOC_G_EXT_CTRLS, &cs);
    close(fd);
    return r == 0 ? id.pid : 0;
}

typedef enum { MODULE_UNKNOWN, MODULE_V14, MODULE_V12 } module_kind_t;

/* The module from the sensor PID; the opened size only when the PID could not be read. */
static module_kind_t module_kind(uint16_t pid, uint32_t width, uint32_t height)
{
    if (pid == PID_SC101IOT) {
        return MODULE_V14;
    }
    if (pid == PID_OV3640_1 || pid == PID_OV3640_2) {
        return MODULE_V12;
    }
    if (pid) {
        return MODULE_UNKNOWN;  // a sensor the BSP would have rejected; do not guess from the size
    }
    return width == 1280 && height == 720 ? MODULE_V14 : width == 1024 && height == 768 ? MODULE_V12 : MODULE_UNKNOWN;
}

/* The slot EEPROM descriptor, once per open (docs/CAMERA_BOARD_QUESTIONS.md, question 3). It is read at
 * discovery and stays readable while the camera holds GPIO14; after mosaico_camera_open() the loop
 * returns at once (a claim needs a VALID descriptor). After a failed open it says why the claim
 * failed (CRC or magic wrong, no module), once until a valid descriptor is seen again. */
static void log_module_info(void)
{
    static bool told_invalid;
    mosaico_module_mgr_info_t m = {0};
    for (int i = 0; i < 20 && (mosaico_module_mgr_get_info(MOSAICO_MODULE_MGR_SLOT_LEFT, &m) != ESP_OK ||
                               m.descriptor_state == MOSAICO_MODULE_DESCRIPTOR_UNKNOWN);
         ++i) {
        vTaskDelay(pdMS_TO_TICKS(100));
    }
    if (m.descriptor_state != MOSAICO_MODULE_DESCRIPTOR_VALID) {
        if (told_invalid) {
            return;
        }
        told_invalid = true;
        ESP_LOGW(TAG, "slot EEPROM 0x%02x: presence %d, descriptor state %d, %s", m.eeprom_addr, m.presence,
                 m.descriptor_state, esp_err_to_name(m.last_error));
        return;
    }
    told_invalid = false;
    const mosaico_module_mgr_eeprom_v1_t *e = &m.eeprom;
    ESP_LOGI(TAG,
             "slot EEPROM 0x%02x: type 0x%02x id 0x%04x hw %u.%u sw %u.%u vendor 0x%04x flags 0x%08" PRIx32
             " serial %" PRIu32 " name %.32s date 0x%08" PRIx32 " batch %u factory %u param v%u len %u",
             m.eeprom_addr, e->board_type, e->board_id, e->hw_version >> 8, e->hw_version & 0xFF, e->sw_version >> 8,
             e->sw_version & 0xFF, e->vendor_id, e->board_flags, e->serial_number, e->board_name, e->manufacture_date,
             e->batch_number, e->factory_id, e->param_version, e->param_length);
}

/* Opens the module; the source line names it, or says there is none. */
static esp_err_t open_camera(pipeline_t *p)
{
    mosaico_camera_config_t cfg = MOSAICO_CAMERA_DEFAULT_CONFIG();  // UYVY, the sensor's Kconfig default size
    esp_err_t err = mosaico_camera_new(&cfg, &p->cam);
    if (err == ESP_OK) {
        err = mosaico_camera_open(p->cam);
    }
    uint16_t pid = 0;
    if (err == ESP_OK) {
        pid = camera_sensor_pid();  // open and awake (the BSP wakes CAM_PWDN on open)
        err = mosaico_camera_start_stream(p->cam);
    }
    if (err != ESP_OK) {
        if (p->cam) {
            log_module_info();  // why the claim failed, if it was the descriptor
            mosaico_camera_del(p->cam);
            p->cam = NULL;
        }
        ESP_LOGW(TAG, "no camera module in the left slot: %s", esp_err_to_name(err));
        set_source(CHAKRA_SOURCE_NONE, "No camera module");
        return err;
    }
    mosaico_camera_info_t info = {0};
    mosaico_camera_get_info(p->cam, &info);
    log_module_info();
    const module_kind_t kind = module_kind(pid, info.width, info.height);
    const bool v14 = kind == MODULE_V14, v12 = kind == MODULE_V12;
    ESP_LOGI(TAG, "camera %" PRIu32 " x %" PRIu32 " at %" PRIu32 " fps: %s (%s 0x%04X)", info.width, info.height,
             info.frame_rate, v14 ? "V1.4 SC101IOT" : v12 ? "V1.2 OV3640" : "unknown module",
             pid ? "PID" : "PID unread, by frame size;", pid);
    if (pid && module_kind(0, info.width, info.height) != kind) {
        ESP_LOGW(TAG, "frame %" PRIu32 " x %" PRIu32 " is not this module's usual size (sdkconfig.defaults?)",
                 info.width, info.height);
    }
    const view_transform_t tr = view_transform();
    ESP_LOGI(TAG, "mount %s: rotation %d CCW, mirror x %d y %d", CHAKRA_CAM_LANDSCAPE ? "landscape" : "sideways",
             CHAKRA_CAM_LANDSCAPE ? 0 : 90, tr.mirror_x, tr.mirror_y);
    view_crop_t crop;
    if (info.pixel_format != V4L2_PIX_FMT_UYVY || !view_crop(info.width, info.height, &crop)) {
        set_source(CHAKRA_SOURCE_NONE, "Camera format not supported");
        close_camera(p);
        return ESP_ERR_NOT_SUPPORTED;
    }
    ESP_LOGI(TAG, "view: %" PRIu32 " x %" PRIu32 " at (%" PRIu32 ", %" PRIu32 "), scale %d/16 to %d x %d", crop.w, crop.h,
             crop.x, crop.y, (int)(crop.scale * 16.0f + 0.5f), CHAKRA_CAM_W, CHAKRA_CAM_H);
    char text[48];
    snprintf(text, sizeof(text), "%s · %" PRIu32 " × %" PRIu32, v14 ? "SC101IOT v1.4" : v12 ? "OV3640 v1.2" : "Camera",
             info.width, info.height);
    set_source(CHAKRA_SOURCE_CAMERA, text);
    return ESP_OK;
}

/* The mean Y of the view's crop, from the UYVY bytes (U Y0 V Y1: Y at odd offsets). */
static int frame_luma(const mosaico_camera_frame_t *f, uint32_t stride, const view_crop_t *c)
{
    const uint8_t *px = f->data;
    uint32_t sum = 0, n = 0;
    for (uint32_t y = c->y; y < c->y + c->h; y += LUMA_STEP) {
        const uint8_t *row = px + (size_t)y * stride;
        for (uint32_t x = c->x; x < c->x + c->w; x += LUMA_STEP) {
            sum += row[2 * x + 1];
            ++n;
        }
    }
    return n ? (int)(sum / n) : -1;
}

/* One frame: luma, the PPA's view, the JPEG. */
static esp_err_t take_frame(pipeline_t *p)
{
    mosaico_camera_frame_t f = {0};
    ESP_RETURN_ON_ERROR(mosaico_camera_get_frame(p->cam, &f), TAG, "no frame");
    esp_err_t err = ESP_OK;
    const uint32_t stride = f.bytes_per_line ? f.bytes_per_line : f.width * 2U;
    view_crop_t c;
    if (f.pixel_format != V4L2_PIX_FMT_UYVY || !view_crop(f.width, f.height, &c)) {
        err = ESP_ERR_INVALID_SIZE;
        goto done;
    }
    esp_cache_msync((void *)f.data, f.size, ESP_CACHE_MSYNC_FLAG_DIR_M2C | ESP_CACHE_MSYNC_FLAG_INVALIDATE);
    const int luma = frame_luma(&f, stride, &c);
    const view_transform_t tr = view_transform();
    const ppa_srm_oper_config_t op = {
        .in = {.buffer = f.data, .pic_w = stride / 2U, .pic_h = f.height, .block_w = c.w, .block_h = c.h,
               .block_offset_x = c.x, .block_offset_y = c.y,
               .srm_cm = PPA_SRM_COLOR_MODE_YUV422_UYVY, .yuv_range = PPA_COLOR_RANGE_LIMIT,
               .yuv_std = PPA_COLOR_CONV_STD_RGB_YUV_BT601},
        /* VIEW_ROWS: room for the 225th row the sideways step makes; the encoder reads the first
         * CHAKRA_CAM_H rows, which lie in one piece at the buffer's start (pic_w = CHAKRA_CAM_W). */
        .out = {.buffer = p->rgb, .buffer_size = p->rgb_size, .pic_w = CHAKRA_CAM_W, .pic_h = VIEW_ROWS,
                .srm_cm = PPA_SRM_COLOR_MODE_RGB565},
        .rotation_angle = tr.rotation,  // landscape 0, sideways 90 CCW (view_transform)
        .scale_x = c.scale,  // an exact 1/16 step (view_crop)
        .scale_y = c.scale,
        .mirror_x = tr.mirror_x,
        .mirror_y = tr.mirror_y,
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
    p->rgb = jpeg_alloc_encoder_mem(CHAKRA_CAM_W * VIEW_ROWS * 2, &in, &p->rgb_size);
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
