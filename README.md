# ChakraV

**Chakra with video: hear the bowl, see the room, light it in the chakra's colour.**

ChakraV is the experimental sibling of **[Chakra Detection](https://github.com/leopardcodeai/chakra-detection)**,
for Espressif's [ESP-Mosaico](https://mosaico.espressif.com) (ESP32-S31, 2.16" 480 x 480 touch screen,
microphone, camera slot). Chakra hears a singing bowl and colours the room. ChakraV adds a camera to see
what is possible: a thick frame around the screen glows in the colour of the chakra it hears, the live
picture sits in the middle, boxes mark the instruments, and two pills say what it hears and what it sees.
German: [README.de.md](README.de.md).

## Which one?

There are two apps, from the same code. In yoga and sound healing many people want no AI at all, or only
AI that stays in the room: **[Chakra Detection](https://github.com/leopardcodeai/chakra-detection) is built
for that.** It works without any AI, its one AI feature runs locally on the device, and it has no camera and
no cloud. **ChakraV is explicitly the experimental one**: it tries what a camera and bigger models can add.

| | [Chakra Detection](https://github.com/leopardcodeai/chakra-detection) | ChakraV (this one) |
|---|---|---|
| Listens | microphone | microphone and camera |
| AI | none needed; an optional local AI sound gate, on the device only | as much on the device as the ESP32-S31 runs, plus optional cloud models with your own API key |
| For | rooms where a camera is not wanted: the classic, private choice | experiments: what can it see and mark? |
| Maturity | tested against real recordings | v0 |

If you do not need the camera, or want no AI beyond the device, take Chakra.

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
| Chakra detection, lamps, screen lamp, local AI sound gate | as in Chakra Detection (676670f) |
| Frame in the chakra's colour, fading, kicked by strikes | works in the simulator |
| Live camera view, Mac camera, 1, 2 or 4 fps | works in the simulator (`tools/camera_live.py`) |
| Instrument boxes with label pills, up to 4 | the overlay works; the boxes come from a **stub** (`--demo-boxes`) |
| Heard and seen pills, small spectrum | work |
| Settings: Settings, Connections, **Camera** (on, boxes, fps, Cloud AI) | work; stored as settings version 5 on the board |
| Cloud AI (experimental) | a **stub**: the setting and `tools/cloud_vision.py` exist, nothing is sent in v0 |
| Camera on the board | **not yet**: the Mosaico camera driver is not wired in (`main/main.c`, TODO camera) |

**There is no real detector yet.** The boxes in the screenshots are the demo scene's own positions; over
the real camera, `--demo-boxes` sends boxes that drift plausibly and mark nothing. Without it no boxes are
sent and the seen pill says "Nothing".

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
python3 tools/screens.py /tmp/chakrav-shots       # the four screenshots above (demo sources only)
```

Ports: audio on 8710 (`CHAKRA_FEED_PORT`), lines on 8711 (`CHAKRA_AI_PORT`: the AI gate's verdicts and the
camera's frames and boxes), so ChakraV and Chakra never share a port. The preview takes 3222 or the next
free port; `sim.sh` prints it.

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
| `frame\t<path>` | a JPEG of exactly 368 x 276, read at once |
| `boxes\tclear` then `box\t<label>\t<x>\t<y>\t<w>\t<h>\t<conf>` | a frame's marks, normalised 0..1, at most 4 |
| `source\t<text>` | the Camera page's source line |
| `sound\t<bowl\|other\|none>\t<strike>` | the local AI sound gate (`tools/ai_gate.py`); while none has spoken for 5 s the detection leads alone |
| `camera\t<on>\t<boxes>\t<fps>\t<cloud>` | back to every client: the Camera settings |

## Design

Per our Mosaico design rules (DESIGN.md in the workspace): top bar with title, clock, dot and gear; Inter; pills h/2; little text;
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
   fork", "gong", "chimes", "drum") in `camera_live.py`, replacing the stub.
2. **On the board**: wire in the Mosaico camera (esp_video, see `apps/camera`), then a trained
   ESPDet-Pico on the ESP32-S31 for the instruments; a Canvas target instead of JPEG frames.
3. Measure the on-device AI on the board: the audio gate and the detector, latency and memory.
4. The real cloud call behind Cloud AI, to compare its boxes with the on-device ones.
5. Join what is heard and what is seen: a strike on the bowl that is marked lights its box.

## How it is built

| Part | File |
|---|---|
| Detection: FFT, harmonics, steadiness, mappings | `components/app_chakra/chakra_detect.c` |
| Screen: frame, camera view, boxes, pills, settings, hold to close | `components/app_chakra/chakra_core.c`, scene `ui/make_scene.py` |
| Board: microphone, Wi-Fi, lamps, settings in NVS (key `chakrav`, version 5) | `main/main.c` |
| Simulator side and feeders | `components/app_chakra/host/platform_pc.c`, `tools/chakra_feed.py`, `tools/camera_live.py` |
| Screenshots | `tools/screens.py`, `tools/sim_shot.py` |

The internal names stay `app_chakra` and `gsp_chakra_*`, as in the chakra app.

## Licence

Apache-2.0. Made by [LeopardCode.AI](https://leopardcode.ai). A light and sound tool, not a medical device.
