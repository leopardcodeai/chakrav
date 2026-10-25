"""ChakraV detect: open-vocabulary instrument boxes on a ZeroGPU slot.

What: one Gradio function, detect(image, model, prompts), that runs the chosen open detector on the
      GPU and returns the boxes normalised to the image, with the model time in ms. Models load once
      on the CPU and move to the GPU inside @spaces.GPU, as ZeroGPU asks.
Why:  the ChakraV app (github.com/leopardcodeai/chakrav) compares these models against OWL-ViT on a
      Mac and, later, a small detector on the ESP32-S31; this is the free GPU path instead of a
      paid API.
Privacy: frames are processed in memory; nothing is written or kept.
"""
import time

import gradio as gr
import spaces
import torch
from transformers import (AutoModelForZeroShotObjectDetection, AutoProcessor, OwlViTForObjectDetection,
                          OwlViTProcessor, Owlv2ForObjectDetection, Owlv2Processor)

DEFAULT_PROMPTS = ("a metal singing bowl, a large gong hanging in a frame, a hand drum, a felt mallet, "
                   "a tuning fork, wind chimes, a rainstick")
MODELS = {
    "owlvit-b32": ("google/owlvit-base-patch32", OwlViTProcessor, OwlViTForObjectDetection),
    "owlv2-b16": ("google/owlv2-base-patch16-ensemble", Owlv2Processor, Owlv2ForObjectDetection),
    "gdino-tiny": ("IDEA-Research/grounding-dino-tiny", AutoProcessor, AutoModelForZeroShotObjectDetection),
}
# ZeroGPU lets models move to "cuda" at start; the GPU is attached only inside @spaces.GPU calls.
LOADED = {name: (proc.from_pretrained(repo), model.from_pretrained(repo).eval().to("cuda"))
          for name, (repo, proc, model) in MODELS.items()}


@spaces.GPU(duration=20)
def detect(image, model: str = "owlv2-b16", prompts: str = DEFAULT_PROMPTS, threshold: float = 0.1):
    if image is None:
        return {"boxes": [], "ms": 0, "model": model}
    proc, net = LOADED[model]
    labels = [p.strip() for p in prompts.split(",") if p.strip()]
    w, h = image.size
    t0 = time.perf_counter()
    with torch.no_grad():
        if model == "gdino-tiny":
            inputs = proc(images=image, text=[labels], return_tensors="pt").to("cuda")
            out = net(**inputs)
            res = proc.post_process_grounded_object_detection(out, inputs.input_ids, threshold=threshold,
                                                              text_threshold=threshold, target_sizes=[(h, w)])[0]
            names = res.get("text_labels", res.get("labels"))
            triples = zip(res["scores"].tolist(), names, res["boxes"].tolist())
        else:
            inputs = proc(text=[labels], images=image, return_tensors="pt").to("cuda")
            out = net(**inputs)
            res = proc.image_processor.post_process_object_detection(
                out, threshold=threshold, target_sizes=torch.tensor([[h, w]], device="cuda"))[0]
            triples = zip(res["scores"].tolist(), [labels[i] for i in res["labels"].tolist()], res["boxes"].tolist())
    torch.cuda.synchronize()
    ms = (time.perf_counter() - t0) * 1000
    boxes = [[str(lab), round(x0 / w, 3), round(y0 / h, 3), round((x1 - x0) / w, 3), round((y1 - y0) / h, 3),
              round(float(s), 3)] for s, lab, (x0, y0, x1, y1) in sorted(triples, key=lambda t: -t[0])][:8]
    return {"boxes": boxes, "ms": round(ms, 1), "model": model}


demo = gr.Interface(
    fn=detect,
    inputs=[gr.Image(type="pil"), gr.Dropdown(list(MODELS), value="owlv2-b16"),
            gr.Textbox(value=DEFAULT_PROMPTS), gr.Slider(0.01, 0.5, value=0.1)],
    outputs=gr.JSON(), api_name="detect", title="ChakraV detect",
    description="Open-vocabulary instrument boxes for ChakraV (OWL-ViT, OWLv2, Grounding DINO) on ZeroGPU.")
demo.launch()
