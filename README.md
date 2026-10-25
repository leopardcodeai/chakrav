# ChakraV

<img src="docs/icon.svg" width="72" align="right" alt="ChakraV icon: a singing bowl with a camera">

**Chakra with video: hear the bowl, see the room, light it in the chakra's colour.**

ChakraV is the experimental sibling of **[ChakraA](https://github.com/leopardcodeai/chakraa)**, the audio app,
for Espressif's [ESP-Mosaico](https://mosaico.espressif.com) (ESP32-S31, 2.16" 480 x 480 touch screen,
microphone, camera slot). Chakra hears a singing bowl and colours the room. ChakraV adds a camera to see
what is possible: a thick frame around the screen glows in the colour of the chakra it hears, the live
picture sits in the middle, boxes mark the instruments, and two pills say what it hears and what it sees.
German: [README.de.md](README.de.md).

## Which one?

There are two apps, from the same code. In yoga and sound healing many people want no AI at all, or only
AI that stays in the room: **[ChakraA](https://github.com/leopardcodeai/chakraa) is built for
that.** It works without any AI, its one AI feature runs locally on the device, and it has no camera and
no cloud. **ChakraV is explicitly the experimental one**: it tries what a camera and bigger models can add.

| | [ChakraA](https://github.com/leopardcodeai/chakraa) (audio) | ChakraV (this one) |
|---|---|---|
| Listens | microphone | microphone and camera |
| AI | none needed; an optional local AI sound gate, on the device only | as much on the device as the ESP32-S31 runs, plus optional cloud models with your own API key |
| For | rooms where a camera is not wanted: the classic, private choice | experiments: what can it see and mark? |
| Maturity | tested against real recordings | v0 |

If you do not need the camera, or want no AI beyond the device, take ChakraA.

**The light is the same in both.** Glow, strike kick, fades, the screen lamp, the colour settings and
every lamp setting come from the same core code (`chakra_core.c`: `animate()`, `light()`, the colour and
lamp pages), and a change to them is made in both apps.

| Live view | Settings | Camera | Connections |
|---|---|---|---|
| ![Frame in the Heart's green, the demo scene with three marked instruments, Heart F3 174.6 Hz, heard Tone, seen Singing bowl](docs/screen_main.png) | ![Colour, brightness, sensitivity, afterglow, mapping, language, local AI sound gate](docs/screen_settings.png) | ![Camera on or off, boxes on or off, 1, 2 or 4 fps, the source](docs/screen_camera.png) | ![The screen lamp ticked, the other lamps not paired](docs/screen_connections.png) |

All screenshots use the drawn demo scene (`tools/camera_live.py --demo`), never a real camera picture.

## Status: v0 (25.10.2026)

| Part | State |
|---|---|
| Chakra detection, lamps, screen lamp, local AI sound gate | as in ChakraA (1cbd13c): strikes are found by the spectral flux, so a loud ringing bowl no longer masks the next ones (7 of 7 strikes in a round where Flow showed Root alone before; 0.4 s in Flow, 0.1 s in Strike) |
| Frame in the chakra's colour, fading, kicked by strikes | works in the simulator |
| Live camera view: a square like the camera kit's preview, 270 x 270, from the Mac camera or a video, 1, 2 or 4 fps | works in the simulator (`tools/camera_live.py`, emulating the V1.4 or V1.2 module) |
| Instrument boxes with short label pills ("Bowl", "Bowl C"), up to 7, one a chakra bowl | the overlay works; the boxes come from a **stub** (`--demo-boxes`) |
| Heard pill (orange dot while it hears), seen pill (green dot while it sees) | work |
| Spectrum: one band a semitone, the locked tone's octave and three semitones either side (A2 to D4 for octave 3), its band in its chakra's colour; the seven chakra dots under their notes | works |
| Indicator dot beside the gear, as on iOS: green while a camera or a video feeds the view, orange while only the microphone listens, grey for the demo scene; the connection is the Wi-Fi glyph between dot and gear | works |
| Camera light: Off, On, Auto (default; on while the picture is dark) | works in the simulator (the Mac's camera has no light, so it is reported); on the board the module's flash LEDs (GPIO34), written, not yet run |
| Settings: Settings, Connections, **Camera** (on, boxes, fps, Cloud AI) | work; stored as settings version 5 on the board |
| Cloud AI (experimental) | a **stub**: the setting and `tools/cloud_vision.py` exist, nothing is sent in v0 |
| Camera on the board | **written, builds, not yet run** (the board is on order): `main/camera.c` opens the module, tells V1.4 from V1.2, makes the square view and its luma, switches the flash |

**There is no real detector yet.** The boxes in the screenshots are the demo scene's own positions; over
the real camera, `--demo-boxes` sends boxes that drift plausibly and mark nothing. Without it no boxes are
sent and the seen pill says "Nothing".

## Hardware: the camera module

The ESP-Mosaico is expected with the **camera module V1.4 (SC101IOT)**; the older **V1.2 (OV3640)**
works too. Both sit in the **left slot** only. The app finds out which one it has from the format its
sensor opens with (the BSP reads the sensor's ID first) and names it on the Camera page
("SC101IOT v1.4 · 1280 × 720").

| Camera modules | V1.4 (expected) | V1.2 |
|---|---|---|
| Sensor | SC101IOT, 1 MP, 2.9 µm pixels (better in a dim room) | OV3640, 3 MP, 1.75 µm pixels |
| Frame | 1280 x 720 UYVY, 15 fps | 1024 x 768 UYVY, 25 fps |
| Lens | 3.1 mm F1.8, **manual focus**, 73 x 42 degrees | 68 degrees diagonal |
| Upright picture (the module sits sideways) | 720 x 1280, portrait 9:16 | 768 x 1024, portrait 3:4 |
| The app's square | the whole 720 px width, about 42 x 42 degrees | the centre 720 of 768, about 42 x 42 degrees |
| Flash | two LEDs on GPIO34, LOW = on, open drain (off when the host sleeps) | same |

- **The view is square**, the centre of the upright picture, as the camera kit's preview shows it:
  270 x 270 on the screen (720 x 6/16; the board's PPA scales in 1/16 steps).
- **Focus once.** The V1.4 lens has manual focus: turn it once to the distance of the bowls, with the
  live view open, then leave it.
- **Light.** The flash LEDs are the camera light (Off, On, Auto). How long they may stay on (heat)
  and Auto's dark threshold with the brighter V1.4 sensor are still to be measured on the board.

## AI: on the device first, the cloud to compare

1. **On the device.** As much as the ESP32-S31 can run itself, through ESP-DL: the local AI sound gate (EfficientAT
   mn05, w8a16, the same one `tools/ai_gate.py` runs on the Mac) and an instrument detector such as
   ESPDet-Pico. Both are **estimates so far**: the board is on order, nothing is measured on hardware.
2. **In the cloud, optional.** Vision and audio models with your own API key (for example OpenAI or
   Gemini), to compare with what runs on the device. **Off by default** (Camera page, Cloud AI). It runs
   only when it is switched on **and** a key is present. Keys come only from the device's secure storage
   (encrypted NVS; `tools/provision.py` is to write them, not yet in v0) or, on the Mac, from the keychain through the
   environment (`OPENAI_API_KEY`, `GEMINI_API_KEY`); never from a file in this repository. A cloud call
   would send a picture of the room to the provider: switch it on only where that is fine. In v0,
   `tools/cloud_vision.py` builds the request and sends nothing.

## Run it in the simulator

You need macOS, Python 3, ffmpeg (`brew install ffmpeg`) and Pillow for the demo scene, and the Mosaico
workspace next to this folder (`../../workspace`).

```sh
./sim.sh --demo     # browser preview (the address it prints): demo bowls, the drawn scene with its boxes
./sim.sh --live     # the Mac's microphone with the local AI sound gate, and the Mac's camera
./sim.sh            # the app alone; feed it yourself:
python3 tools/chakra_feed.py tone 174.6           # one tone (Heart)
python3 tools/camera_live.py --demo --demo-boxes  # the demo scene
python3 tools/camera_live.py --video FILE --detect  # a video as the V1.4 module would see it (--module v1.2)
python3 tools/screens.py /tmp/chakrav-shots       # the four screenshots above (demo sources only)
```

Ports: audio on 8710 (`CHAKRA_FEED_PORT`), lines on 8711 (`CHAKRA_AI_PORT`: the AI gate's verdicts and the
camera's frames and boxes), so ChakraV and Chakra never share a port. The preview takes 3222 or the next
free port; `sim.sh` prints it.

**The module, emulated.** `camera_live.py --module v1.4` (default) or `v1.2` turns a video into the
module's upright picture (scaled to cover it, centred; portrait 9:16 videos fit V1.4 exactly), then
takes its centre square for the app, and the same square at twice the size (540 x 540) for the
detector, which scores bowls far better there. From the Mac camera it takes the centre square of the
Mac's picture at the module's angle. The Camera page's source line says what is emulated
("Video · SC101IOT v1.4 emulated").

**Camera and privacy.** macOS asks once for the camera permission of the app that starts
`camera_live.py`; if it is refused, the script says so and waits, it never works around it. Frames exist
only in one temp file in a private folder, overwritten by each next frame and deleted at the end. With
the camera set to Off, ffmpeg stops, so the Mac's camera is off too.

## In the Ideas launcher

Our Vibe Mode launcher simulation (`tools/mosaico_launcher.py` in the Mosaico workspace, http://127.0.0.1:3300,
not part of this repository) has a ChakraV tile:

- **Live** (default): `chakra_feed.py mic --ai` (microphone and the local AI sound gate, when its venv exists; colours to the screen lamp)
  and `camera_live.py` (the Mac's camera, no boxes).
- **Demo** (`--demo chakrav`): demo bowls and `camera_live.py --demo --demo-boxes`.
- Hold the top bar 3 s to close it, as every app.

## The line protocol (port 8711)

| Line | Meaning |
|---|---|
| `frame\t<path>\t<luma>` | a JPEG of exactly 270 x 270, read at once; its mean luma drives the light's Auto |
| `boxes\tclear` then `box\t<label>\t<x>\t<y>\t<w>\t<h>\t<conf>` | a frame's marks, normalised 0..1, at most 7 |
| `source\t<text>\t<camera\|video\|demo>` | the Camera page's source line and the indicator dot |
| `sound\t<bowl\|other\|none>\t<strike>` | the local AI sound gate (`tools/ai_gate.py`); while none has spoken for 5 s the detection leads alone |
| `camera\t<on>\t<boxes>\t<fps>\t<cloud>` | back to every client: the Camera settings |
| `camlight\t<on>\t<dark>` | back to every client: the camera light should be on or off |

## Design

Per our Mosaico design rules (DESIGN.md in the workspace): top bar with title, clock, the camera and microphone dot and gear; Inter; pills h/2; little text;
English first, German in the settings. The frame is 28 px (20 px was the other variant; 28 reads more as
light). Its inner edge runs at the screen's radius minus the frame, at least 8 px; two dark veils make it
fade softly inward, because ESP-GSP has no blur. The camera view keeps the screen's 20 px radius through
the ring mask from DESIGN.md "Media". Boxes are four thin fills each, because a dynamic width resizes a
container's fill but not its border.

Design references (25.10.2026):

- [Philips Ambilight](https://www.philips.ca/c-p/42PDL7906T_12): the light extends the picture onto the
  wall; here the frame extends the sound into the room.
- [Apple Intelligence edge glow](https://vp0.com/blogs/apple-intelligence-glow-border-effect-code-ios-free-ios-template-vibe-coding-gui):
  an edge glow is a state, not decoration; it comes with the tone and leaves with it.
- [Material Design, object detection in a live camera](https://m2.material.io/design/machine-learning/object-detection-live-camera.html):
  mark a found object with a continuous rectangle and a short label.
- [Google Nest Hub ambient mode](https://www.techadvisor.com/article/732792/how-to-change-ambient-mode-on-google-nest-hub.html):
  a calm screen that adapts to the room's light.
- [Framer Border Glow Pro](https://www.framer.com/marketplace/components/border-glow-pro/): a soft diffused
  edge instead of a hard outline.

## Next

1. **Real detection on the Mac**: an open-vocabulary detector such as OWL-ViT ("singing bowl", "tuning
   fork", "gong", "chimes", "drum") in `camera_live.py`, replacing the stub. Test it where it is hard:
   - **Low light.** Sound healing rooms are dim. `tools/check_frames.py` on two freely licensed test videos
     (25.10.2026): a floating gong in a dark room averaged a luma of 6 of 255 with a contrast of 19, flat 59 %
     of the time; a gong and drum session was bright (luma 109, contrast 84). Measure the detector on both.
   - **Changing backgrounds.** The gong and drum video changed by 8.4 luma levels a frame on average (up to
     12), the dark one by 0.5: moving people and light. Check that boxes stay on the instrument and do not
     jump with the background.
   - **Does the light help?** The camera light's Auto switched on after 2 s in the dark video and stayed on.
     On the board, measure the detector with and without the flash LED, and its heat when left on.
2. **On the board**: run `main/camera.c` on the real module and check what it marks as CHECK ON THE
   BOARD (orientation, colours, the encoder at 270 px, the flash's heat, Auto's dark threshold); then a
   trained ESPDet-Pico on the ESP32-S31 for the instruments; a Canvas target instead of JPEG frames.
3. Measure the on-device AI on the board: the audio gate and the detector, latency and memory.
4. The real cloud call behind Cloud AI, to compare its boxes with the on-device ones.
5. Join what is heard and what is seen: a strike on the bowl that is marked lights its box.

## How it is built

| Part | File |
|---|---|
| Detection: FFT, harmonics, steadiness, strikes (spectral flux), mappings | `components/app_chakra/chakra_detect.c` |
| Screen: frame, camera view, boxes, pills, settings, hold to close | `components/app_chakra/chakra_core.c`, scene `ui/make_scene.py` |
| Board: microphone, Wi-Fi, lamps, settings in NVS (key `chakrav`, version 6) | `main/main.c` |
| Board: the camera module, the square view, its luma, the flash | `main/camera.c`, camera block in `sdkconfig.defaults` |
| Simulator side and feeders | `components/app_chakra/host/platform_pc.c`, `tools/chakra_feed.py`, `tools/camera_live.py` |
| Screenshots; brightness, contrast, change and the light's Auto over a video | `tools/screens.py`, `tools/sim_shot.py`, `tools/check_frames.py` |

The internal names stay `app_chakra` and `gsp_chakra_*`, as in the chakra app.

## Licence

Apache-2.0. Made by [LeopardCode.AI](https://leopardcode.ai). A light and sound tool, not a medical device.
