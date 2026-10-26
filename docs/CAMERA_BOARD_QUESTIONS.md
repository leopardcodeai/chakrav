# Camera module: three questions answered before the board arrives

Date: 26.10.2026. Scope: ESP-Mosaico (ESP32-S31), camera module V1.4 (SC101IOT) or V1.2 (OV3640) in the
left slot H2, apps `apps/chakrav/main/camera.c` and `apps/camera/main/camera.c`. Nothing here has run on
a board. Applied 26.10.2026 to both `camera.c` files (PID, orientation switches, EEPROM log, comments);
the BSP submodule now stands at master `7cbfb39` (22.10.2026), past `b60f5d8`. Each answer says where it comes from: **code** (read in the sources we build), **docs**
(Espressif pages), **inference** (reasoned from code and docs, to be confirmed on the board).

Sources read:

- BSP, local submodule `workspace/submodule/esp-mosaico-bsp` at `5f88b91` (16.10.2026). GitHub master is
  three merges ahead (`b60f5d8`, 19.10.2026, "fix: update camera app": PWDN polarity and the Front/Rear
  label swap, both relevant below). Paths below are relative to the submodule unless absolute.
- `esp_cam_sensor` 2.6.0 and `esp_video` 2.5.0 as managed in `apps/chakrav/managed_components`
  (the SC101IOT driver there carries the BSP's PCLK delay patch, so its line numbers are one higher than
  upstream from line 29 on).
- ESP-IDF in `toolchain/esp-idf-mosaico` (PPA driver).
- Espressif camera module user guide:
  <https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s31/esp-mosaico/user_guide_camera.html>
- ESP32-P4 TRM, chapter 39 PPA (the S31 PPA has the same SRM register layout,
  `components/soc/esp32s31/register/soc/ppa_struct.h:524-543`):
  <https://www.espressif.com/sites/default/files/documentation/esp32-p4_technical_reference_manual_en.pdf>
- GitHub `esp-mosaico/esp-mosaico-bsp` commits and PRs (via `gh api`). A web search for Mosaico camera
  orientation, mirroring or EEPROM contents on the esp32.com forum, Reddit and issues found nothing
  beyond the user guide; the BSP repo has no camera issues on these topics.

---

## 1. Do the modules open at 1280 x 720 (SC101IOT) and 1024 x 768 (OV3640), and can the app tell them apart by that?

**Answer.** Yes, with our `sdkconfig.defaults`: SC101IOT opens at 1280 x 720 UYVY 15 fps, OV3640 at
1024 x 768 UYVY 25 fps. The size is set by each sensor's Kconfig default, not by the BSP and not by
`S_FMT`. But the size is only a proxy: the OV3640 driver also has a 1280 x 720 mode (the BSP builds it), and
the OV3640's own Kconfig default is RGB565 640 x 480. The authoritative signal is the sensor PID, which the
BSP reads but does not expose. Use the PID; keep the size as a fallback.

**How sure.** Code, certain.

**Evidence.**

- How the size is chosen:
  - Each sensor driver starts with `cur_format = format_info[CONFIG_..._IF_FORMAT_INDEX_DEFAULT]`
    (`sc101iot.c:37`, `:159-166`, `:527`; `ov3640.c:50`, `:213`, `:770`).
  - `esp_video` copies that as the capture format at init (`src/device/esp_video_device_common.c:970`).
  - `VIDIOC_S_FMT` only accepts the current width and height. It rejects any other size
    (`esp_video_device_common.c:563-586`) and can change only the pixel format. Changing resolution would
    need `VIDIOC_S_SENSOR_FMT`, which the BSP never calls.
  - The BSP, with width = height = 0 (`MOSAICO_CAMERA_DEFAULT_CONFIG`, `include/mosaico_module_camera.h:20-30`),
    does `G_FMT` and then `S_FMT` with the same size in UYVY (`mosaico_camera.c:590-612`).
- Kconfig defaults:
  - SC101IOT: the choice defaults to `..._DEFAULT_FMT_YUV422_1280X720_15FPS`, index 0
    (`sensors/sc101iot/Kconfig.sc101iot:63-65`, `:97-99`).
  - OV3640: the choice defaults to `..._DEFAULT_FMT_RGB565_LE_640X480_7FPS`
    (`sensors/ov3640/Kconfig.ov3640:78-79`). 1024 x 768 UYVY 25 fps (index 3, `:125`) comes only from our
    `sdkconfig.defaults` (chakrav lines 80-83; the kit's `examples/camera_lcd_preview/sdkconfig.defaults`
    does the same).
  - The BSP's `components/mosaico_module_camera/Kconfig:1-18` only `select`s the formats it needs (OV3640
    1024 x 768 25 fps and 1280 x 720 15 fps, SC101IOT 1280 x 720 25 fps). It never sets a default choice.
- Built configs agree (`apps/chakrav/build/sdkconfig:4758`, `:4761`, `:4792`, `:4795`):
  - OV3640: `DEFAULT_FMT_YUV422_UYVY_1024X768_25FPS`, index 3.
  - SC101IOT: `DEFAULT_FMT_YUV422_1280X720_15FPS`, index 0. The 25 fps entry is also built, because the
    BSP selects it.
- The user guide states the same defaults: V1.2 "1024 × 768 UYVY", V1.4 "1280 × 720 UYVY".
- Sensor ID in the BSP:
  - `open_video_device()` reads the chip ID with `VIDIOC_G_EXT_CTRLS` and `ESP_CAM_SENSOR_IOC_G_CHIP_ID`
    (`mosaico_camera.c:262-276`, `:586`).
  - It rejects anything other than OV3640 PID 0x364C/0x3641 or SC101IOT PID 0xDA4A (`:40-42`, `:587-588`).
  - It logs `Camera opened: sensor=SC101IOT pid=0xDA4A format=1280x720` (`:685-686`).
  - The ID is kept in a private field (`:100`). `mosaico_camera_info_t` has no sensor field
    (`include/mosaico_module_camera.h:71-80`).
- 15 vs 25 fps:
  - `mosaico_camera_get_info().frame_rate` comes from `VIDIOC_G_PARM` (`mosaico_camera.c:622-632`), which
    reports the sensor format's fps (`esp_video_device_common.c:786-800`): 15 on V1.4, 25 on V1.2.
  - The SC101IOT 15 fps table notes that 720p at 20 MHz XCLK gives 15 fps with PCLK 37.5 MHz, marked
    "warning" (`private_include/sc101iot_dvp_8bit_20Minput_1280x720_yuv422_uyvy_15fps.h:7-17`).
  - The BSP had to add a PCLK edge delay patch for SC101IOT (`patches/esp-cam-sensor-sc101iot-pclk-delay.patch`,
    commit `e110720`) and a DVP frame capture patch to ESP-IDF (commit `e0b97e8`). It drops invalid frames
    (commit `f629a8e`). Its README says the SC101IOT workarounds are inactive if the IDF patch fails to apply.
  - The guide's "1280 × 720 @ 30 FPS" is the sensor maximum; no Espressif example uses 25 fps on SC101IOT.
  - For us: we take 1 to 4 frames per second, so 15 fps is the safer choice and costs nothing. `S_PARM`
    could reduce it further by skipping frames (`esp_video_device_common.c:774-780`). We do not need that,
    because we only dequeue at our pace.
- Second open of `/dev/video2` is allowed: `esp_video` counts references (`src/esp_video.c:524-527`, close
  `:598-606`). An app can therefore ask the sensor itself without a BSP change.

**What camera.c should do.**

1. Identify the module by PID: after `mosaico_camera_open()`, open `/dev/video2` a second time, read the
   chip ID, close it (code below). Map 0xDA4A to V1.4 SC101IOT and 0x364C/0x3641 to V1.2 OV3640. Fall back
   to the size only if the ioctl fails. Longer term, ask upstream for a `sensor_pid` field in
   `mosaico_camera_info_t`; it is a two-line change in `mosaico_camera_get_info()`.
2. Keep the four OV3640 and SC101IOT lines in `sdkconfig.defaults`. Without the OV3640 `DEFAULT_FMT` line
   the V1.2 opens at 640 x 480 RGB565, and the UYVY `S_FMT` then fails or converts.
3. Keep SC101IOT at 15 fps.
4. Update the BSP submodule to GitHub master (`b60f5d8`) before the first flash. It moves CAM_PWDN control
   into the BSP with the board's polarity (low = run, high = sleep, "including SC101IOT"), passes
   `pwdn_pin = GPIO_NUM_NC` to `esp_video`, and leaves the sensor asleep after close.

```c
#include <fcntl.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include "esp_cam_sensor_types.h"   // esp_cam_sensor_id_t, ESP_CAM_SENSOR_IOC_G_CHIP_ID
#include "esp_video_device.h"       // ESP_VIDEO_DVP_DEVICE_NAME ("/dev/video2")
#include "esp_video_ioctl.h"        // V4L2_CTRL_CLASS_ESP_CAM_IOCTL
#include "linux/videodev2.h"

/* The sensor's product ID, read the way the BSP does it (mosaico_camera.c:262-276); 0 if unknown.
 * Call after mosaico_camera_open(): it opens a second reference to the video device. */
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
```

If the build cannot find `esp_cam_sensor_types.h` or `esp_video_ioctl.h`, add `esp_video` and
`esp_cam_sensor` to `PRIV_REQUIRES` in `main/CMakeLists.txt`. `esp_video` already reaches us publicly
through `mosaico_module_camera`.

**Board check (idf.py monitor, UART console).** Look for these lines:

- `sc101iot: Detected Camera sensor PID=0xda4a`
- `mosaico_camera: Camera opened: sensor=SC101IOT pid=0xDA4A format=1280x720`
- our `camera 1280 x 720 at 15 fps`
- the PID from `camera_sensor_pid()` printed beside them. They must agree.

---

## 2. Does the picture need a flip or mirror when mounted for landscape?

**Answer.**

- **The sensor output is not mirrored. It is rotated by 90 degrees relative to the kit's mount.**
  - In the kit's mount (module in H2 per the silkscreen, rear-facing), the true upright picture is the raw
    frame turned 90 degrees counter-clockwise, with no mirror.
  - The `camera_lcd_preview` transform (270 + `mirror_y`) is that same upright picture mirrored left to
    right: the selfie view for the folded, front-facing lens.
- **Landscape mount (sensor's long side horizontal).**
  - The raw 1280 x 720 frame is either already upright or upside down, depending on which way the module
    is turned. It is never mirrored.
  - Transform: rotation 0, no mirror (what `camera.c` does now).
  - If it comes out upside down, set both `mirror_x` and `mirror_y` (a 180 degree turn).
  - Set `mirror_x` alone only if a mirrored selfie view is wanted, for example with the lens folded to
    face the viewer.

**How sure.**

- PPA order and semantics: certain (TRM).
- Front/Rear meaning: code plus upstream commit, high.
- That the SC101IOT module has the same readout orientation as the OV3640 module the examples were written
  for: inference, medium.
- Which way the owner's turn lands (0 or 180 degrees): unknown until the board is here.

**Evidence.**

- **The PPA does scale, then rotate counter-clockwise, then mirror, with mirror X horizontal and mirror Y
  vertical** (TRM 39.5.3.1: it "first scales ..., then rotates it ..., and finally mirrors it
  horizontally and vertically"). `driver/ppa.h:174-178` confirms counter-clockwise rotation.
- **What the kit preview does to the raw frame.** `camera_lcd_preview` turns it 270 degrees CCW, then
  mirrors vertically (`examples/camera_lcd_preview/main/main.c:188-213`). That equals 90 degrees CCW
  followed by a left-right mirror: an upright, mirrored image.
- **The upright view without a mirror is 90 degrees CCW.**
  - `mosaico_camera_jpeg_decode_rgb888_ccw90()` rotates 90 degrees CCW "into the model-upright orientation"
    (`components/mosaico_module_camera/README.md:36-39`, `mosaico_camera_jpeg.c:165-204`).
  - The AI gallery feeds face detection a 90 degree CCW frame with no mirror "so an upright portrait face
    matches the detector" (`examples/ai_model_gallery/main/app_main.cpp:302`, README lines 15-19).
  - The same app's LCD preview uses 270 + `mirror_y` (`app_main.cpp:179-182`). Both views are upright, so
    they differ by exactly one left-right mirror.
- **Which of the two is the true picture.** The module has a flip design: folding the lens section
  switches between front-facing and rear-facing (user guide, "Module Overview").
  - `camera_photo_app` offers a Flip button that adds `mirror_x` to 270 + `mirror_y`
    (`examples/camera_photo_app/main/main.c:454-458`). With both mirrors the result is a pure 90 degree CCW
    turn.
  - In our local copy the default was labelled "Rear" (`main/camera_ui.c:265-273`, `:575`).
  - Upstream PR #28 (`b60f5d8`, merged 21.10.2026) "Correct front/rear camera labels": the default
    (270 + `mirror_y`, mirrored) is now "Front". "Rear" is the flipped setting (pure 90 degree CCW, not
    mirrored).
  - This matches the phone convention: rear camera true, front camera mirrored like a mirror. It is
    consistent with the AI path.
  - Hence the raw sensor frame is unmirrored. In the kit's mount it shows the scene rotated 90 degrees
    clockwise: scene "up" points to the frame's right edge, column 1279.
  - Nothing in the BSP, the commits or the docs explains the 270 + `mirror_y` choice beyond these labels.
    It came with the first import of the examples (`1415812`, 26.08.2026) without a comment.
- **Sensor controls exist for both sensors.**
  - `esp_video` maps `V4L2_CID_VFLIP` to `ESP_CAM_SENSOR_VFLIP` and `V4L2_CID_HFLIP` to
    `ESP_CAM_SENSOR_HMIRROR` (`src/esp_video_cam.c:84-93`). They are set through `VIDIOC_S_EXT_CTRLS`
    (`:280-361`).
  - SC101IOT: mirror is register 0x3221 bits [2:1], flip is 0x3221 bits [6:5] (`sc101iot.c:279-287`). Both
    are 0..1, default 0 (`:289-307`). Reading them back is not supported (`get_para_value` returns
    `ESP_ERR_NOT_SUPPORTED`, `:310-313`). The init tables never write 0x3221 (page 0x32 is written only at
    0x41, 0x43, 0x48 and 0x0C-0x0F), so the power-on default holds.
  - OV3640: mirror is 0x307C bit 1, flip is 0x307C bit 0 (`ov3640.c:420-428`). The tables do not write
    0x307C either.
  - The BSP does not expose its file descriptor and has no flip API. Its README offers no orientation
    setting.
- **Sensor flip vs PPA.** A sensor mirror on a Bayer sensor can shift the colour phase. Neither driver
    documents that it compensates. The settings are also lost whenever the sensor re-initialises
    (`mosaico_camera_restart()`, reopen after an error). The PPA mirror is free: same SRM pass, no state.
    Use the PPA.

**What camera.c should do.**

- **Landscape (`CHAKRA_CAM_LANDSCAPE 1`)**: keep rotation 0 and add two build-time switches. Neither is a
  run-time setting yet:
  - `CHAKRA_CAM_TURN_180`: sets `.mirror_x = .mirror_y = true`.
  - `CHAKRA_CAM_MIRROR`: toggles `.mirror_x` only, for a selfie view.

  With rotation 0, `mirror_x` is a plain left-right mirror.
- **Sideways (`CHAKRA_CAM_LANDSCAPE 0`)**: do not copy the kit preview. For a true (rear-facing) picture use
  `PPA_SRM_ROTATION_ANGLE_90` with no mirror; for the kit's front-facing selfie look use 270 + `mirror_y`.
  `view_crop()` is unchanged, because both swap the axes the same way. The current code
  (`main/camera.c:330-334`) uses 270 + `mirror_y`, the mirrored view.
- The same applies to `apps/camera/main/camera.c` (`CAMERA_LANDSCAPE`).
- Prediction for the landscape mount, to be confirmed: with the lens rear-facing, turning the module or
  the device 90 degrees clockwise from the kit's mount, as seen by the person behind the camera, makes the
  raw frame upright. Counter-clockwise needs `CHAKRA_CAM_TURN_180`.
- If the PPA ever cannot be used, the sensor route is a second `open("/dev/video2")` after
  `mosaico_camera_start_stream()`, then `VIDIOC_S_EXT_CTRLS` with `ctrl_class = V4L2_CTRL_CLASS_USER`,
  `V4L2_CID_HFLIP` and/or `V4L2_CID_VFLIP` = 1. Discard two frames afterwards and repeat after every
  reopen.

**Board test (two minutes, no code beyond the switches).**

1. Mount the module for landscape, lens facing away from you. Point it at a printed page with large text
   and an arrow pointing up.
2. Open the ChakraV camera view (or `apps/camera` `/view.jpg`):
   - Text readable and arrow up: no transform (current code).
   - Text readable but upside down (arrow down): `CHAKRA_CAM_TURN_180`.
   - Text mirrored (reads right to left): this should not happen when the lens is rear-facing. Note the
     fold state and the mount, then try `CHAKRA_CAM_MIRROR`.
3. Cross-check: move your hand to your right. In a rear-facing true picture it moves to the picture's
   right.
4. Run the same once with the lens folded to front-facing, and decide whether the selfie mirror is wanted.

---

## 3. What does the slot EEPROM report, and how do we read it before the camera claims GPIO14?

**Answer.**

- **Layout (code, certain):** EEPROM V1 image of 0x86 bytes, three CRC16-protected sections.

  | Offset | Field |
  |---|---|
  | 0x00 | magic "ESP" |
  | 0x03 | board_type (0x07 = camera) |
  | 0x04 | board_id |
  | 0x06 | hw_version |
  | 0x08 | sw_version |
  | 0x0A | vendor_id |
  | 0x0C | board_flags |
  | 0x10 | serial_number |
  | 0x14 | board_name[32] |
  | 0x34 | descriptor CRC |
  | 0x36 | manufacture_date |
  | 0x3A | batch_number |
  | 0x3C | factory_id |
  | 0x3E | manufacturing CRC |
  | 0x40 | param_version |
  | 0x42 | param_length |
  | 0x44 | param_data[64] |
  | 0x84 | parameter CRC |

- **Values on V1.2 and V1.4:** not documented anywhere. The guide only says the EEPROM "stores module
  identification information", board type 0x07 at 0x50.
  - The only known image is Espressif's `module_eeprom_programmer` camera profile: type 0x07, board_id 1,
    name "CameraBoard", hw_version 0x0102, sw_version 0x0100, vendor_id 1, serial 1, param_version 1,
    param_length 0, date, batch and factory 0.
  - Its README states that every profile uses hardware version V1.2 "independent of the core board
    revision". If the factory used this tool, a V1.4 module also reports hw 0x0102. **Do not use the
    EEPROM to tell V1.2 from V1.4; use the sensor PID (question 1).**
- **When it can be read:** any time the module manager runs; GPIO14 does not matter for the camera.
  - The camera EEPROM has no address pin and sits fixed at 0x50.
  - The manager reads the descriptor at discovery. A claim requires it to be VALID.
  - The camera claims with `USE_SLOT_CONTROL_GPIO | PROBE_WHILE_CLAIMED`, so probing continues while DVP
    D4 is driven.
  - `mosaico_module_mgr_get_info()` returns the last decoded descriptor before, during and after streaming.
  - The user guide says EEPROM access is "suspended" while the camera is open. That is older than this
    code. Our `camera.c` comment (line 50) repeats it and should be corrected.

**How sure.** Layout and read path: code, certain. Factory contents: unknown until read on the board.

**Evidence.**

- Decode: `components/mosaico_module_mgr/mosaico_module_mgr.c:22-26` (offsets), `:209-218` (CRC16, poly
  0xA001, init 0xFFFF), `:221-259` (`parse_descriptor`).
- Struct: `include/mosaico_module_mgr.h:23-25` (magic, size 0x86), `:43-58` (board types), `:86-105`
  (`mosaico_module_mgr_eeprom_v1_t`), `:107-117` (`mosaico_module_mgr_info_t`), `:261`
  (`mosaico_module_mgr_get_info`).
- Log line on discovery: `Module identified: slot=left type=Camera(0x07) id=0x0001 name=CameraBoard`
  (`mosaico_module_mgr.c:436-442`).
- Probing while claimed: `slot_probe_allowed_locked()` (`mosaico_module_mgr.c:363-371`). Camera claim flags:
  `components/mosaico_module_camera/mosaico_camera.c:733-741`. Manager README, section 硬件约束 (hardware
  constraints): the camera EEPROM is fixed at 0x50 with no address line, and probing at 0x50 continues
  while the camera runs. Also `components/esp-mosaico-bsp/include/bsp/subboard.h:19-39`.
- GPIO14 as D4: `mosaico_camera.c:154-160` (`data_io[4] = slot_config.address_select_gpio`).
- Programmer image: `examples/module_eeprom_programmer/main/eeprom_program.c:23` (camera profile), `:62-78`
  (`build_image`); README "Profiles use module hardware version V1.2 ...". Added in PR #23
  (10.10.2026), CI firmware in PR #24.
- EEPROM parts differ by version: AT24C02BS SOP-8 on V1.2, 24C02S SOT23-5 on V1.4 (user guide). Both are
  2 Kbit at 0x50; no part-specific behaviour is visible to software.

**What camera.c should do.**

1. Keep reading `mosaico_module_mgr_get_info(MOSAICO_MODULE_MGR_SLOT_LEFT, ...)`; it is already correct, and
   reading it after `mosaico_camera_open()` is fine.
2. Print `hw_version` and `sw_version` as major.minor (`hw >> 8`, `hw & 0xFF`), so 0x0102 shows as 1.2
   rather than 258.
3. Also log `board_id`, `vendor_id`, `serial_number`, `board_flags` and `manufacture_date` once.
4. If `descriptor_state` is not VALID, log `last_error` (`ESP_ERR_INVALID_CRC`, `ESP_ERR_INVALID_RESPONSE`
   for a wrong magic). The claim then fails, unless `allow_unidentified` is set (`mosaico_module_camera.h:45-48`).
5. Name the module in the UI from the PID, not from `hw_version`.
6. Correct the GPIO14 comments in both `camera.c` files: GPIO14 is D4, but the EEPROM stays readable.

**Board check.** Paste into `open_camera()` after the existing EEPROM log, or run once at start. It needs
no camera claim; with only `mosaico_module_mgr_init(NULL)` it waits up to 2 s for the descriptor.

```c
mosaico_module_mgr_info_t m = {0};
for (int i = 0; i < 20 && (mosaico_module_mgr_get_info(MOSAICO_MODULE_MGR_SLOT_LEFT, &m) != ESP_OK ||
                           m.descriptor_state == MOSAICO_MODULE_DESCRIPTOR_UNKNOWN); ++i) {
    vTaskDelay(pdMS_TO_TICKS(100));
}
const mosaico_module_mgr_eeprom_v1_t *e = &m.eeprom;
ESP_LOGI(TAG, "EEPROM 0x%02x presence %d state %d err %s", m.eeprom_addr, m.presence, m.descriptor_state,
         esp_err_to_name(m.last_error));
ESP_LOGI(TAG, "type 0x%02x id 0x%04x hw %u.%u sw %u.%u vendor 0x%04x flags 0x%08" PRIx32 " serial %" PRIu32
         " name %.32s date 0x%08" PRIx32 " batch %u factory %u param v%u len %u",
         e->board_type, e->board_id, e->hw_version >> 8, e->hw_version & 0xFF, e->sw_version >> 8,
         e->sw_version & 0xFF, e->vendor_id, e->board_flags, e->serial_number, e->board_name,
         e->manufacture_date, e->batch_number, e->factory_id, e->param_version, e->param_length);
```

Expected if the factory used Espressif's programmer:
`type 0x07 id 0x0001 hw 1.2 sw 1.0 vendor 0x0001 flags 0x00000000 serial 1 name CameraBoard ...`.
Write down what the real V1.4 module reports here and in `camera.c`'s header comment.

---

## Summary for camera.c (both apps)

| Item | Now | Change |
|---|---|---|
| Module identity | from the opened size | sensor PID via a second `/dev/video2` fd; size as fallback |
| Landscape transform | rotation 0, no mirror | keep; add build switches for 180 and selfie mirror |
| Sideways transform | 270 + `mirror_y` (kit "Front", mirrored) | 90 CCW, no mirror, for a true picture |
| EEPROM log | hw/sw as decimal | major.minor, plus id, vendor, serial, error state |
| GPIO14 comment | "suspends the slot EEPROM" | EEPROM stays readable (fixed 0x50, probe while claimed) |
| BSP submodule | `5f88b91` | update to `b60f5d8` (PWDN polarity) before the first flash |
| sdkconfig | OV3640 and SC101IOT defaults set | keep, they decide the opened size |
