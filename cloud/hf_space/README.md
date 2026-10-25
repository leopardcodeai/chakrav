---
title: ChakraV detect
colorFrom: purple
colorTo: indigo
sdk: gradio
app_file: app.py
pinned: false
license: apache-2.0
short_description: Open-vocabulary instrument marks for ChakraV, on ZeroGPU
---

# ChakraV detect

A small API for [ChakraV](https://github.com/leopardcodeai/chakrav): send one camera frame, get back the
instruments it sees (singing bowl, gong, drum, mallet ...) as boxes, from open models on a ZeroGPU slot:
OWL-ViT, OWLv2 and Grounding DINO. Frames are processed in memory and not stored.

`POST /detect` through the Gradio API: image, model name, prompts (comma separated). Returns
`{"boxes": [[label, x, y, w, h, score], ...], "ms": model time, "model": ...}`, boxes normalised 0..1.
