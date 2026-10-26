# Which detector ChakraV trains for the ESP32-S31

Research note, 26.10.2026. Nothing was installed or trained for it. Numbers are Espressif's own
measurements (ESP-DL v3.3.14 model READMEs, int8, `CONFIG_COMPILER_OPTIMIZATION_PERF`) unless marked
**est.** (scaled by input pixels from a measured pair; ESPDet latency grows linearly with pixels:
224² to 416² is 3.45x the pixels and 3.49x the time).

## Recommendation

| | Choice | S31 time per detection | Notes |
|---|---|---|---|
| **Model** | **ESPDet-Pico** (esp-detection), one multi-class model | | 0.36 M params, ReLU, ESP-DL native, S31 listed |
| **Classes** | bowl, crystal_bowl, mallet, hand, gong | | crystal bowls look nothing like metal ones; keep them apart |
| **Input** | **320 x 320** from the 720 x 720 centre square | **~170 ms est.** (162 model + ~8 pre) | mallet heads stay ~15 px; 3 fps = ~51 % of the SIMD core |
| Speed step | same model at 256 x 256 | ~110 ms est. | for 4 fps, or when audio needs more |
| Full upright frame | same model, `rect=True`, 448 x 256 (h x w) | ~190 ms est. | only if instruments outside the view matter; smaller scale (0.36) |
| Quantisation | int8 (w8a8), per-channel; w8a16 if int8 loses boxes | | mn05 matched float in 103 of 133 windows at w8a8, 124 at w8a16 |
| **Fallback** | **PicoDet-XS 320** (PaddleDetection, Apache-2.0) | ~310 ms est. (256: ~200) | if the AGPL licence is a blocker or ESPDet underfits; no ESP-DL port yet |
| Not this | YOLO11n 320 / YOLO26n 512 | 544 ms / 1587 ms measured | under 2 fps on the S31 |
| Which bowl | sound plus tracker (already in `tools/bowl_tracker.py`), not the detector | | optional crop embedding later, ~45 ms per crop |

**Open decision for Alexander: the licence.** esp-detection is AGPL-3.0 and built on Ultralytics,
whose licence page says the AGPL covers models trained with it "even if you train your own model
from scratch", weights included. ChakraV is public under Apache-2.0. Either publish the detector
(training scripts, weights) under AGPL-3.0 and accept Ultralytics' reading for the firmware, buy an
Enterprise licence, or take the PicoDet-XS fallback. This is a legal path: worth a `review` second
opinion before the first trained model ships in the repo.

## Why ESPDet-Pico

Measured on the ESP32-S31 (320 MHz, PSRAM 250 MHz), preprocess + model + postprocess:

| Model (ESP-DL model zoo) | Input | S31 total | P4 total | S3 total | mAP50-95 |
|---|---|---|---|---|---|
| espdet_pico cat | 224² | 84.3 ms | 48.6 ms | 129.9 ms | 0.663 (COCO cat) |
| espdet_pico cat | 416² | 289.5 ms | 182.1 ms | 444.2 ms | 0.724 |
| espdet_pico hand | 224² | 83.4 ms | 48.1 ms | 128.6 ms | 0.409 (custom) |
| espdet_pico face | 416² | 291.5 ms | 183.6 ms | 445.0 ms | 0.597 |
| yolo11n | 320² | 543.8 ms | 321.9 ms | 991.8 ms | 0.278 (COCO 80) |
| yolo11n | 640² | 2242.7 ms | 1395.9 ms | 4005.8 ms | 0.373 |
| yolo26n | 512² | 1586.5 ms | 948.7 ms | 2406.3 ms | 0.365 |
| MobileNetV2-0.5 classifier | 128² | 45.3 ms | 25.4 ms | 73.9 ms | (gestures) |

- **S31 sits between S3 and P4**: ESPDet is 0.65x the S3 time and 1.7x the P4 time. Only one S31 core
  has the 128-bit SIMD; ESP-DL's multi-core mode is *slower* on the S31 (MobileNetV2: 302 ms vs 292 ms
  single core). Plan the detector and mn05 on the SIMD core, audio DSP, LVGL and the camera on the other.
- **Budget at 3 fps, 320²**: 3 x 170 = 510 ms/s, plus mn05 30 to 60 ms/s: about 55 to 57 % of the SIMD
  core. At 4 fps 320² would take 74 % before audio; that is what 256² is for. `bowl_tracker.py` already
  asks for a detection only when needed (every 4th frame in a still scene), so the average is lower.
- **Our case suits a small model**: few classes, large objects (a bowl is 150 to 400 px of the 720 px
  square, 65 to 180 px at 320). The thin mallet is the hard class; 320 keeps its head at about 15 px
  where 224 would leave about 10.
- **Size**: an ESPDet-Pico 320 `.espdl` is about 0.55 MB (esp-vision's example: 574,864 bytes); with
  mn05 (1.8 to 1.9 MB) well inside 16 MB flash. Activations go to PSRAM; YOLO11n needs 6 MB for its
  memory manager, ESPDet-Pico far less (**not measured**: check on the board). One 1280 x 720 UYVY
  frame is 1.84 MB.
- **ESP-DL 3.3.14** (the version `s31_dl_test` already builds) supports the S31, reworked Conv for
  speed, and its image preprocessor takes YUV422 directly, so the UYVY crop needs no RGB copy.
- **The S31 target works in our toolchain**: esp-ppq 1.3.12 exported mn04/mn05 with target `esp32s31`
  on 25.10.2026 (`esp_dl_work/README.md`). esp-detection's scripts only name `esp32p4`/`esp32s3`, and
  `espdet_run.py` copies any non-P4 model into `models/s3`: call the quantiser with `esp32s31` and skip
  its deploy step.

Why not the others: YOLO11n/YOLO26n are 3x to 10x too slow (above). PicoDet-XS (0.70 M params,
0.67 GFLOPs at 320, COCO 23.5) and NanoDet-Plus-m (1.17 M, 0.9 GFLOPs, COCO 27.0) are permissive but
need about 2x and 2.6x ESPDet-Pico's ~0.35 GFLOPs at 320 (est. from 0.17 at 224 and 0.60 at 416), and
neither has an ESP-DL port or S31 measurement; their operators must be checked against
`operator_support_state.md`. FOMO gives centroids without box sizes and measured 0.66 to 1.7 s at
96 x 96 on the old ESP32 (ESP-EYE); ChakraV draws boxes.

## Training recipe

- **Format**: YOLO detection (`class cx cy w h`, normalised), a dataset YAML with `names`; the order of
  `names` is the class id on the board. `tools/make_detector_data.py` already writes this.
- **esp-detection defaults** (`train.py`): epochs 1200, batch 128, imgsz 224, mosaic 1.0,
  close_mosaic 30, copy_paste 0.1, mixup 0; for `rect=True` fine-tune 30 to 50 epochs after a square
  pre-train. The esp-vision guide trains at `--size 320 320` and quantises with
  `deploy.quantize_aligned` (percentile calibration, bias correction), branch
  `YanKE01/esp-detection@feat/esp-vision-train`.
- **Pre-training**: only single-class ESPDet checkpoints are public (cat .pt at 224, 416, 160x288).
  Stage 1: train ESPDet-Pico at 320 on public boxes (below), about 300 epochs. Stage 2: fine-tune on
  our frames, 100 to 300 epochs, `patience` 50, watching val for overfitting.
- **Dim rooms**: the dark test video averaged luma 6 of 255. Put dark and flash-lit frames in train and
  in the **calibration set** (esp-vision warns that a narrow calibration set gives good simulator mAP
  but missing boxes on the board); strengthen `hsv_v` and add sensor noise; measure with and without
  the flash LED.
- **Background frames**: 5 to 10 % without instruments (empty room, people, feet: OWL-ViT took a foot
  for a bowl).

## Training data

**How many**: Ultralytics recommends at least 1500 images and 10,000 instances per class for full
accuracy from scratch; Roboflow's team starts a first model at about 50 representative images per
class. With pre-training, aim for **150 to 300 reviewed images per class from at least 10 sessions or
rooms**, at least 1000 bowl boxes and 300 of each other class, split by video.

**What we have** (`detector_data/`, OWLv2 proposals, 26.10.2026 08:22, before review): 104 train and
13 val images; boxes: bowl 562 + 93, mallet 104 + 8, hand 5 + 0, gong 7 + 6. Bowls are fine for a
first model; **hands and gongs are far too few**, crystal bowls are not a class yet.

**Bootstrapping with OWLv2** (bowls at 0.3 to 0.44 on bright frames, 2 or 3 of many in a dim session):
1. Low per-class thresholds, then a person accepts or fixes boxes on the review sheets (as now).
2. Image-guided OWLv2 (one-shot query with a crop of one of the owner's bowls) for frames where the text
   prompt fails; the HF OWLv2 docs show zero- and one-shot detection.
3. Propagate reviewed boxes along each video with the tracker (or SAM 2/SAM 3) instead of labelling
   every frame; SAM 3 also takes text concepts and is a second teacher to compare.
4. Train a first model on the Mac, let it propose the next batch, review only where it and OWLv2
   disagree. All of it stays local (own videos show people).

**Public sets**: no Roboflow Universe dataset for singing bowls was found (only kitchen bowls, e.g.
628 images). Useful classes: Open Images V7 boxable *Bowl*, *Mixing bowl*, *Drum*, *Human hand*,
*Chime*, *Musical instrument*; LVIS v1 *bowl*, *chime/gong*, *mallet*, *drumstick*, *drum*, *cymbal*.
Espressif's hand_detect model shows hands work at 224 (mAP 0.409); Open Images hands fill that class.

## Which bowl it is

**Sound first, the detector only finds "a bowl".** Bowls of one set look alike and their size in the
picture changes with distance, so per-bowl detector classes would be weak. The pitch says which chakra
sounds, and `bowl_tracker.py` already ties a note to the bowl a hand or mallet covered at the onset
(after a few votes the box reads "Bowl C"). That works in the dark too.

- **Crop classifier or embedding** (optional, later): MobileNetV2-0.5 at 128² takes 45 ms on the S31;
  run it once per new track, not per frame, enrolled on the owner's own bowls (as ESP-DL's face
  recognition matches embeddings). Helps when two bowls sound alike or before the first strike.
- **The chakra symbol inside the bowl**: visible only from above, small (at 320 input a few pixels), low
  contrast when engraved, gone in dim light, and missing on many bowls; it also names the seller's
  chakra, which can differ from the one the pitch gives. A bonus reader on a full-resolution crop at
  best, not the way to identify.

## Sources

- esp-detection README, train.py, espdet_pico.yaml, rect tutorial, LICENSE (AGPL-3.0):
  https://github.com/espressif/esp-detection
- ESP-DL README and news (10/2026 operator rework, w8a16 from v3.3.11, YOLO26): https://github.com/espressif/esp-dl
- ESP-DL v3.3.14 release (S31 support, YUV422 preprocessing): https://github.com/espressif/esp-dl/releases
- Model zoo: https://github.com/espressif/esp-dl/blob/master/models/README.md ; per model:
  `models/cat_detect`, `hand_detect`, `human_face_detect`, `pedestrian_detect`, `coco_detect`, `yolo26`,
  `imagenet_cls` (S31 single vs multi core), `hand_gesture_recognition` (README.md each)
- ESP-VISION, Train an ESPDet Pico Model: https://docs.espressif.com/projects/esp-vision/en/latest/esp32p4/how-to/train-espdet-pico.html
- ESP32-S31 (SIMD on one core, 512 KB SRAM, 250 MHz PSRAM): https://www.espressif.com/news/ESP32_S31_Release
- Ultralytics licence FAQ: https://www.ultralytics.com/license
- PicoDet benchmark: https://github.com/PaddlePaddle/PaddleDetection/blob/release/2.8/configs/picodet/README_en.md
- NanoDet: https://github.com/RangiLyu/nanodet
- FOMO on ESP-EYE (Edge Impulse public project): https://studio.edgeimpulse.com/public/346631/live/tuner/16332111
- Dataset size: https://docs.ultralytics.com/yolov5/tutorials/tips_for_best_training_results/ ;
  https://discuss.roboflow.com/t/roboflow-3-0-and-yolo-8-11-transfer-learning-advice-needed/10152
- Open Images V7 boxable classes: https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions-boxable.csv
- LVIS class names: https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/lvis.yaml
- Roboflow bowl set: https://universe.roboflow.com/jamal-ykucp/bowl-detection-2
- OWLv2 (one-shot, image-guided): https://huggingface.co/docs/transformers/model_doc/owlv2
- SAM 3: https://github.com/facebookresearch/sam3
- Local: `tools/detect_owl.py`, `tools/make_detector_data.py`, `tools/bowl_tracker.py`,
  `~/Library/Application Support/LeopardCode/chakra/esp_dl_work/README.md`
