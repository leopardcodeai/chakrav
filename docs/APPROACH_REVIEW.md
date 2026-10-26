# Approach review: are ChakraA and ChakraV on the right track?

Research note, 26.10.2026. Question from the owner: check online, with sources, whether the way both
apps hear, see and light is the right approach, and what to change. No code was changed for this note.
It reads the code as it is (`components/app_chakra/chakra_detect.c`, `chakra_light.c`, `tools/ai_gate.py`,
`tools/detect_owl.py`, `tools/bowl_tracker.py`, `../chakrav_detector`) and the evaluation in ChakraA
(`docs/evaluation/report.md`, run 2026-10-26_103325). "Est." marks our own estimates; everything else
has a source.

## Verdicts

| # | Part | Verdict | Reason | Source |
|---|---|---|---|---|
| 1 | 16 kHz, 4096-point FFT, 1024 hop (3.9 Hz bins, 256 ms window, 64 ms hop) | **keep** | bowl fundamentals sit at roughly 140 to 430 Hz and their strong partials below 2 to 3 kHz; 2 bins a semitone at C3 plus parabolic interpolation is enough; doublets (beats of a few Hz) are not resolved in 256 ms and need not be, the peak-hold envelope bridges them | [Terwagne, Bush: fundamentals 187 to 428 Hz](https://arxiv.org/pdf/1106.6348); [Imbery et al., DAGA 2014: partials 80 to 2000 Hz, modal pairs](https://pub.dega-akustik.de/DAGA_2014/data/articles/000254.pdf) |
| 2 | Harmonic sum (weights at 1x, 2x, 3x, 4x) for the fundamental, and the harmonic-share confidence | **adjust** | a bowl has no 2x and 4x partial; its second and third modes sit near 2.7 to 3.0x and 5.2 to 5.4x, so the sum works on bowls only where the second mode happens to fall near 3x, and the confidence under-rates bowls whose mode ratio is lower; the code already patches this with the 2.5 to 3.1x partial rule. Score candidates with a bowl-mode template (or, better, with learned templates, row 4) | [Wilkerson, Serafin, Ng, ICMC 2002: 186, 551, 1007, 1627 Hz](https://ccrma.stanford.edu/~carmenng/250b/icmc2002.pdf); [Terwagne, Bush: only (n,0) modes, frequency grows with n²](https://arxiv.org/pdf/1106.6348); [pYIN is built for monophonic harmonic sources](https://code.soundsoftware.ac.uk/projects/pyin) |
| 3 | Spectral-flux onsets with a running-median threshold | **keep, adjust the flux** | flux with an adaptive threshold is the standard online onset detector; for ringing, beating sounds add a maximum filter over frequency (SuperFlux) and log-spaced bands, which cut false onsets from wobbling partials by up to 60 % in the paper; bell transcription uses a delta spectrogram for the same reason (beating suppressed, onsets kept) | [Böck, Widmer, DAFx 2013](https://dafx.de/paper-archive/details/0oee-99Z88WL7pSo749gcA); [madmom: 24 bands an octave](https://madmom.readthedocs.io/en/v0.16/modules/features/onsets.html); [Marolt, bell chiming, delta spectrogram](https://lgm.fri.uni-lj.si/papers/8992340.pdf) |
| 4 | "New tone over a ringing one" by subtracting the held spectrum, and "learned bowls" as one frequency per chakra | **replace (in learned-bowls mode)** | this is a hand-made, one-template version of what the literature does with non-negative decomposition onto fixed templates learned beforehand: each bowl's whole spectrum (all partials and their levels) is learned once, every hop is decomposed onto the 7 templates, and a bowl's activation rising is its strike. Bell transcription with NMF works only when initialised with each bell's spectrum; real-time decomposition onto fixed templates runs per frame | [Marolt, bell chiming NMF](https://lgm.fri.uni-lj.si/papers/8992340.pdf); [Dessein, Cont, Lemaitre, ISMIR 2010](https://hal.archives-ouvertes.fr/hal-00708682); [Rigaud et al., inharmonic NMF needs good initialisation](https://hal.archives-ouvertes.fr/hal-00856734) |
| 5 | Lock, switch hysteresis, hold (Flow 384 ms, Strike 128 ms) | **keep** | the light needs a stable state; this is the hand-tuned form of the HMM path smoothing that pYIN uses (high self-transition probability); an HMM would be cleaner but gives the same behaviour | [pYIN / Essentia PitchYinProbabilitiesHMM, self-transition 0.99](https://essentia.upf.edu/reference/std_PitchYinProbabilitiesHMM.html) |
| 6 | AI gate: EfficientAT mn05 (AudioSet) embedding plus a logistic head | **keep the backbone, adjust the head** | mn05 is the best size for the S31 (1.43 M params, 0.16 G MACs at 10 s, mAP 44.3; our export 18.5 M MACs for 1 s, 1.9 MB w8a16); MobileNet embeddings rank well on HEAR; AudioSet has a "Singing bowl" class. But our own numbers show the trained head does not beat the pretrained rule and costs bowls (91 to 84 %, own segments 69 to 63 %). Add prototypes of the owner's own bowls and decide per strike | [EfficientAT](https://github.com/fschmid56/EfficientAT); [Schmid et al., Low-Complexity Audio Embedding Extractors, EUSIPCO 2023](https://arxiv.org/html/2303.01879v2); [AudioSet singing bowl](https://research.google.com/audioset/dataset/singing_bowl.html); ChakraA report.md |
| 7 | Alternatives to mn05: PANNs, YAMNet, BEATs, a tiny CNN from scratch | **do not switch** | CNN14 has about 81 M params, its MobileNet variant only 0.383 mAP; BEATs about 90 M (a teacher, not a device model); YAMNet measured here at 69 M MACs and 4 MB for less AudioSet skill; a tiny CNN needs a teacher and far more data than our 79 clips (DCASE low-complexity students are distilled from PaSST/BEATs) | [PANNs summary, IEEE SPS](https://signalprocessingsociety.org/newsletter/2024/05/panns-large-scale-pretrained-audio-neural-networks-audio-pattern-recognition); [codesota leaderboard](https://codesota.com/audio/classification); [DCASE 2025 task 1 reports](https://arxiv.org/html/2509.09262v1); `esp_dl_work/README.md` |
| 8 | Vision: OWLv2 teacher, ESPDet-Pico student on pseudo-labels | **keep, add human review** | distilling an open-vocabulary detector into an edge detector is standard (OWLv2 itself is trained by self-training on pseudo-boxes); auto-labels reach 90 to 95 % of human-label performance on common classes but collapse on rare, specialised ones (LVIS: under 0.10 mAP), which is our case (singing bowl, mallet, rainstick); moderate thresholds (0.2 to 0.5) train better than strict ones | [Minderer et al., Scaling Open-Vocabulary Object Detection](https://arxiv.org/pdf/2306.09683); [Voxel51, auto-labeling benchmark](https://voxel51.com/blog/zero-shot-auto-labeling-rivals-human-performance); [DART pipeline](https://arxiv.org/pdf/2407.09174) |
| 9 | Detector classes bowl, mallet, hand, gong, rattle, rainstick | **adjust** | AP50 today: gong 0.68, bowl 0.29, hand 0.10, mallet, rattle, rainstick about 0; the fusion rule needs bowls, the gong and "someone plays here", and the mallet head is already found by colour. Fewer classes, each with enough reviewed boxes | `../chakrav_detector/README.md`; [Ultralytics data tips](https://docs.ultralytics.com/yolov5/tutorials/tips_for_best_training_results/) |
| 10 | "Audio decides, vision confirms" (late fusion, camera may veto, rescue, break a tie) | **keep** | late fusion is robust to a missing modality and is the usual choice for small systems; for several instruments of one kind, motion tells which one is played; drum transcription used visual hit detection plus an assignment to improve the audio result | [Slizovskaia et al., ICMR 2017](https://repositori.upf.edu/items/3903024a-0627-48dd-bab7-b3cce1dcf5b2); [Gan et al., Music Gesture, CVPR 2020](https://arxiv.org/abs/2004.09476); [McGuinness et al., EUSIPCO 2007](https://researchportal.ip-paris.fr/en/publications/visual-analysis-for-drum-sequence-transcription/) |
| 11 | Light rules (SOUND_LIGHT_EXPERIENCE.md) | **keep; two wording fixes** | nothing found contradicts them. The WCAG red flash counts any opposing transition involving saturated red, at any luminance, so a kick on Root is a red flash however small (still inside 3 a second at 1 per 2 s); and WCAG's area rule is for screens: a room lamp fills the field, so the rate limit, not the amplitude, is what keeps us safe | [W3C Understanding SC 2.3.1](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html); [Epilepsy Society](https://epilepsysociety.org.uk/sites/default/files/2025-04/PhotosensitiveepilepsyApril2025.pdf) |
| 12 | Evaluation (per-strike accuracy, bootstrap over recordings, latency, changes a minute, flicker) | **keep, extend** | the unit of resampling (recordings) is right and better than most blogs; a reviewer will ask for precision (false colour changes), a confusion matrix, standard event metrics, baselines, ablations, a held-out test set never used for tuning, and more than one bowl set and room | [mir_eval onset, 50 ms window](https://mir-eval.readthedocs.io/latest/api/onset.html); [sed_eval event metrics](https://tut-arg.github.io/sed_eval/sound_event.html); [Ebbers et al., threshold-independent SED evaluation](https://arxiv.org/pdf/2201.13148) |

## 1. Pitch and onsets for singing bowls

### What bowls are, acoustically

- **Modes, not harmonics.** A struck or rubbed bowl vibrates in (n,0) shell modes; their frequencies grow
  roughly with n², not n ([Terwagne, Bush](https://arxiv.org/pdf/1106.6348)). One measured 21 cm bowl:
  186, 551, 1007, 1627, 2337 Hz, i.e. 1 : 2.96 : 5.41 : 8.75 : 12.6, each partial with a long, separate decay
  ([Wilkerson, Serafin, Ng, ICMC 2002](https://ccrma.stanford.edu/~carmenng/250b/icmc2002.pdf)). Our
  code's 2.5 to 3.1x window for the second mode matches this; the third mode near 5.2 to 5.4x is not used.
- **Doublets and beats.** Every mode is a pair of slightly different frequencies (the bowl is never
  perfectly round); their difference is the beat, and its depth depends on direction
  ([Imbery, Jensen, Weber, DAGA 2014](https://pub.dega-akustik.de/DAGA_2014/data/articles/000254.pdf);
  [Inácio, Henrique, Antunes, Acta Acustica 2006](https://www.ingentaconnect.com/contentone/dav/aaua/2006/00000092/00000004/art00017)).
  Beats of 0.5 to a few Hz cannot be resolved in a 256 ms window and need not be: they show as amplitude
  modulation, which `env[]` (peak hold, 8 dB a second) already bridges.
- **Pitch is the fundamental.** Tuners and sellers name a bowl by its lowest mode; the evaluation's
  failure case (-ar9vsmFhJU's "root" bowl rings at G#3) shows sellers' chakra labels follow the set, not the
  note.

### Harmonic sum and confidence: adjust

`harmonic_peak()` sums the spectrum at k, 2k, 3k, 4k. For a bowl, 2k and 4k hold nothing, and 3k holds the
second mode only when its ratio is near 3 (2.96 above: within 7 Hz, 2 bins). For a bowl with ratio 2.7 at
300 Hz, the second mode is 90 Hz (23 bins) away from 3k, and `tone_confidence()` (energy on harmonics
over all energy, ±2 bins) then sees most of the bowl's energy as "not the tone". That plausibly explains
part of the low colour share of bells (43 % in Flow) and part of the strikes lost in u1KjQTAHSlo (3 to 4 of
7). Harmonic models are the wrong prior for this instrument; pYIN-type estimators are explicitly built for
monophonic, harmonic sources ([pYIN](https://code.soundsoftware.ac.uk/projects/pyin)), and NMF work on
inharmonic instruments uses inharmonic partial templates, with relaxed constraints, because a strict
model fails ([Rigaud et al.](https://hal.archives-ouvertes.fr/hal-00856734);
[Vincent, Bertin, Badeau, harmonic and inharmonic NMF](https://researchportal.ip-paris.fr/en/publications/harmonic-and-inharmonic-nonnegative-matrix-factorization-for-poly/)).

Change for the Notes and Solfeggio mappings (no learned bowls): score a candidate fundamental k by
`m[k] + w2 * max(m[2.5k .. 3.1k]) + w3 * max(m[5.0k .. 5.7k])`, and compute the confidence over those
three windows plus the harmonics (voices and tuning forks stay harmonic; take the better of the two
models). Est.: a few hundred extra operations a hop.

### Onsets: keep the flux, filter it

The flux with a median threshold is the standard online method. Two refinements from the literature fit
bowls:

- **Maximum filter over frequency (SuperFlux):** compare each bin with the maximum of its neighbours in the
  earlier frame, so a partial that drifts or wobbles by a bin does not count as new energy. Up to 60 % fewer
  false positives on vibrato material, causal, real-time ([Böck, Widmer, DAFx 2013](https://dafx.de/paper-archive/details/0oee-99Z88WL7pSo749gcA)).
- **Log-spaced bands** (24 an octave, as madmom recommends for SuperFlux) instead of linear bins 100 to
  1500 Hz, so high partials do not outvote the fundamental region
  ([madmom docs](https://madmom.readthedocs.io/en/v0.16/modules/features/onsets.html)).
- Bell transcription uses a delta spectrogram for exactly our problem: "emphasizes fast and big changes,
  such as onsets, and deemphasizes slower and smaller changes, such as beating"
  ([Marolt](https://lgm.fri.uni-lj.si/papers/8992340.pdf)).

### Several bowls ringing: learned spectral templates

Today "learned bowls" stores one frequency per chakra (`bowl_hz`, matched within 150 cents), and the
strike path subtracts the held spectrum (×2) to find what is new. The established method for "which of a
known set of inharmonic sounds is playing, several at once" is non-negative decomposition onto fixed
templates:

1. **Learn**: during the existing "strike each bowl once" flow, store each bowl's spectrum 0.3 to 1.5 s after
   the strike (normalised; in about 100 to 200 log bands it is 0.4 to 0.8 KB a bowl). That is all the bowl's
   partials, so its second mode can no longer be mistaken for another bowl's fundamental.
2. **Run**: every hop, solve `v ≈ W h` with h ≥ 0 for the 7 templates plus one or two free templates
   (broadband noise, a gong) by a few multiplicative updates, warm-started from the previous hop
   ([Dessein, Cont, Lemaitre, ISMIR 2010](https://hal.archives-ouvertes.fr/hal-00708682): real time,
   fixed templates learned offline, beta-divergence). Est.: 9 templates × 200 bands × 20 iterations,
   about 36 k multiply-adds a hop, under 1 % of a core.
3. **Decide**: a strike is a bowl whose activation jumps (flux on h, not on the spectrum); the colour is
   that bowl's chakra; a bowl rings while its activation stays above its own decay line. The louder
   ringing bowl no longer masks the quieter new one, because both are explained at once.

Marolt's bell work shows the key condition: NMF on inharmonic bells gives meaningful parts only when
initialised with each bell's spectrum ([Marolt](https://lgm.fri.uni-lj.si/papers/8992340.pdf)); we have
better than an initialisation, since the owner strikes every bowl alone once. It also handles bowls that
are not tuned to a note (the G#3 "root"), which the Notes mapping cannot.

### Sample rate and FFT size: keep

16 kHz keeps everything up to 8 kHz; the bowls' strong partials are below 2 to 3 kHz
([DAGA 2014](https://pub.dega-akustik.de/DAGA_2014/data/articles/000254.pdf)). 4096 points give 3.9 Hz
bins: at C3 (130.8 Hz) a semitone is 7.8 Hz, two bins, and parabolic interpolation gives a few cents. Only
below about G2 (98 Hz, 1.5 bins a semitone) is it tight; `F_MIN` is 90 Hz. A longer window would cost
latency for nothing the light needs. Keep. If low bowls (below C3) matter, zero-pad to 8192 for the
interpolation only.

### Existing datasets

The closest public data is "Acoustic Sounds for Wellbeing" (88 h from YouTube: gongs, drumming, singing
bowls, chanting; MFCC + SVM baseline 57.4 % UAR, with a dedicated gong vs bowl task because the two are
acoustically close) ([Baird, Schuller 2019](https://arxiv.org/pdf/1908.01671)); AudioSet has 895 "Singing
bowl" videos rated medium quality ([AudioSet](https://research.google.com/audioset/dataset/singing_bowl.html)).
Both are worth using for the gate's "other" class and to compare against, with their licences checked.

## 2. The AI sound gate

### Keep mn05

- **Size and skill.** mn05_as: 1.43 M params, mAP 44.3 on AudioSet
  ([EfficientAT](https://github.com/fschmid56/EfficientAT)); our export: 18.5 M MACs for one second,
  1.91 MB at w8a16, 124 of 133 windows equal to float (`esp_dl_work/README.md`). PANNs CNN14 (0.431 mAP)
  is about 81 M params; its MobileNetV1 variant gets 0.383
  ([IEEE SPS on PANNs](https://signalprocessingsociety.org/newsletter/2024/05/panns-large-scale-pretrained-audio-neural-networks-audio-pattern-recognition));
  BEATs is about 90 M ([codesota](https://codesota.com/audio/classification)); YAMNet measured here at
  69 M MACs and 4 MB. None of them buys more per millisecond on the S31.
- **As an embedding.** The EfficientAT authors show the MobileNets are good general embedding extractors
  on the HEAR benchmark, best when mid-level block features (B5, B11, B13, B15, pooled) are concatenated
  with the final ones ([Schmid et al., EUSIPCO 2023](https://arxiv.org/html/2303.01879v2)). Our head uses
  the final embedding; trying the concatenated mid-level features costs nothing on the device (same
  forward pass).
- **A tiny CNN from scratch** is not realistic with 79 Commons clips plus own segments: the DCASE
  low-complexity entries (128 kB, 30 M MACs) all distil from large teachers trained on 64 h of data
  ([DCASE 2025 reports, e.g. arXiv 2509.09262](https://arxiv.org/html/2509.09262v1)). Distilling mn05 into a
  smaller student is a later option if the S31 budget gets tight, not now.

### Adjust the head: prototypes and strike-aligned decisions

Our own report says the trained head does not beat the pretrained rule (bowls 84 % both, bells 28 % vs
24 %, gongs 24 % vs 17 %) and that on the owner's segments the gate costs bowls (69 % without AI, 41 %
pretrained, 63 % trained). Three changes, all cheap:

1. **Prototypes of the owner's own bowls.** During the learning round, store each bowl's mn05 embedding
   (mean of a few windows). At run time, cosine similarity to the nearest prototype is a second opinion
   that says "this is one of my bowls", independent of AudioSet's idea of a bowl. Prototypical networks on
   frozen embeddings are the standard few-shot baseline (DCASE few-shot bioacoustics, 5 examples per
   class: [Tang et al. 2021](https://dcase.community/documents/challenge2021/technical_reports/DCASE2021_Tang_54_task5.pdf));
   a frozen pretrained encoder with a prototype head is a strong baseline
   ([Pisa thesis](https://dione.lib.unipi.gr/xmlui/handle/unipi/18248)). On the board this is the pattern
   ESP-DL already ships for faces: enrol embeddings, match by cosine with a threshold
   ([ESP-DL face recognition example](https://components.espressif.com/components/espressif/esp-dl/versions/2.0.0/examples/face_recognition);
   [ESP-DL `recognition` module](https://docs.espressif.com/projects/esp-dl/en/latest/introduction/esp_dl_project.html)).
2. **Decide per strike, not per half second.** Run the gate on the window starting at the detector's
   onset (0 to 1 s after it). A window that mixes the tail of a gong with a new bowl is the hardest case for
   a clip-level tagger; aligned windows are what the DSP already provides for free.
3. **Pick the operating point from a curve.** Report the gate's ROC or precision-recall curve over
   thresholds instead of one point, then choose the threshold for the asymmetric cost the light document
   states (a wrong colour costs more than a missed change)
   ([Ebbers et al., threshold-independent evaluation](https://arxiv.org/pdf/2201.13148)).

**Board parity.** ESP-DL's audio front end is a Kaldi-style Fbank
([ESP-DL audio module](https://docs.espressif.com/projects/esp-dl/en/latest/introduction/esp_dl_project.html)),
EfficientAT uses its own `AugmentMelSTFT` at 32 kHz. `esp_dl_work/fbank_check.py` already compares them;
whichever is used on the board must be the one the head is trained on, and the 16 kHz microphone path
(band-limited to 8 kHz) must be the one the Mac bench feeds in.

## 3. Vision

### Teacher-student from OWLv2: keep

- OWLv2 is itself the product of self-training on pseudo-boxes
  ([Minderer, Gritsenko, Houlsby, NeurIPS 2023](https://arxiv.org/pdf/2306.09683)), and the pipeline
  "open-vocabulary detector labels, small detector trains, a person reviews" is common
  ([DART](https://arxiv.org/pdf/2407.09174); [Roboflow, Grounding DINO to YOLO-NAS](https://roboflow.com/train/grounding-dino-and-yolo-nas)).
- **How far auto-labels go.** Voxel51's benchmark trained edge detectors only on auto-labels: about 90 to
  95 % of the human-label result on VOC and COCO classes, under 0.10 mAP on LVIS, whose rare and specialised
  classes the foundation models label poorly; they recommend targeted human annotation for such classes,
  and found moderate thresholds (0.2 to 0.5) better than strict ones (0.8 to 0.9), which cost recall
  ([Voxel51](https://voxel51.com/blog/zero-shot-auto-labeling-rivals-human-performance)). Singing bowls,
  mallets and rainsticks are LVIS-like. Our base run (mAP50 0.184 against the teacher's own labels, mallet
  and rattle near 0) fits that picture.
- **Microcontroller distillation of a vision-language model** exists for classification-style zero-shot
  (TinyVLM: 285 KB RAM on an STM32H7, [arXiv 2603.00136](https://www.alphaxiv.org/abs/2603.00136)), not
  yet for boxes; a closed-set ESPDet-Pico is the right target.

### How many reviewed labels

There is no single number; the sources bracket it. Ultralytics: at least 1500 images and 10,000 instances
a class for full accuracy from scratch
([Ultralytics tips](https://docs.ultralytics.com/yolov5/tutorials/tips_for_best_training_results/)); a
first model from about 50 representative images a class
([Roboflow forum](https://discuss.roboflow.com/t/roboflow-3-0-and-yolo-8-11-transfer-learning-advice-needed/10152));
50 to 250 fully annotated images on VOC07 lift a weakly supervised detector clearly
([arXiv 2207.12112](https://arxiv.org/pdf/2207.12112)); active selection beats random selection for the same
budget ([Aghdam et al., ICCV 2019](https://openaccess.thecvf.com/content_ICCV_2019/papers/Aghdam_Active_Learning_for_Deep_Detection_Neural_Networks_ICCV_2019_paper.pdf)).
DETECTOR_CHOICE.md's target of 150 to 300 reviewed images a class from at least 10 sessions is
consistent. The order matters more than the total:

1. **A reviewed validation set first** (about 300 frames, split by session, the owner's room included).
   Until then every mAP measures agreement with OWLv2, not with the room.
2. **Fewer classes**: bowl, gong, player (hand or mallet merged). The fusion rule needs no rattle or
   rainstick box (the audio gate already keeps them from colouring), and the mallet head is found by colour.
3. **Review where teacher and student disagree** (active selection), plus one-shot image-guided OWLv2 with
   a crop of the owner's bowl as a second teacher ([HF OWLv2](https://huggingface.co/docs/transformers/model_doc/owlv2)).

### "Audio decides, vision confirms": keep

- Late fusion of separately trained audio and image classifiers is robust and copes with a missing
  modality ([Slizovskaia, Gómez, Haro, ICMR 2017](https://repositori.upf.edu/items/3903024a-0627-48dd-bab7-b3cce1dcf5b2));
  audio and image classifiers for instruments reach similar F1 (0.75 and 0.77) and make similar confusions
  ([Slizovskaia et al., SMC 2016](https://mtg.upf.edu/node/3542)).
- Several instruments of one kind are told apart by motion, not appearance
  ([Music Gesture, CVPR 2020](https://arxiv.org/abs/2004.09476)); drum transcription used visual hit
  detection per drum and an optimal assignment of regions to instrument classes, improving the audio result
  ([McGuinness et al., EUSIPCO 2007](https://researchportal.ip-paris.fr/en/publications/visual-analysis-for-drum-sequence-transcription/)).
  That is our tracker's design.
- In audio-visual separation networks, late fusion suits "sustained and harmonically rich sounds", middle
  fusion transient ones ([Hu et al., BMVC 2025](https://bmva-archive.org.uk/bmvc/2025/assets/papers/Paper_493/paper.pdf));
  a different task, but the same direction for ringing bowls.
- **Upgrade the join**: with learned spectral templates (section 1), the camera's job becomes assigning
  7 audio templates to 7 bowl tracks once (Hungarian assignment over strike co-occurrences, as in
  McGuinness et al.), instead of per-bowl votes.

## 4. Light experience

Nothing found contradicts `docs/SOUND_LIGHT_EXPERIENCE.md`. Points to state more exactly:

- **Red flash.** WCAG defines a red flash as "any pair of opposing transitions involving a saturated red",
  with no luminance threshold ([W3C SC 2.3.1](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html)).
  A kick on Root (or a kick towards white from red) is therefore a red flash however small; the safety
  comes from the rate (1 per 2 s, under the 3 a second limit), not from "8 points under the flash line".
  The README and the light document should say "under the general-flash threshold and far under the
  flash rate", not "under the WCAG flash line" without qualification.
- **Area.** WCAG's 25 % of a 10 degree field exemption is for screens; room lamps and a TV as screen lamp
  fill the field, so no amplitude exemption applies to them. The document says this for the TV; it holds
  for every lamp.
- **Brightness is not luminance.** The 0.07 luminance step is computed from brightness points; how a
  bulb maps its brightness value to light output was not found in Hue's public pages
  ([Hue brightness FAQ](https://www.philips-hue.com/en-us/explore-hue/faq/bulbs/how-bright-are-hue-bulbs)).
  Measure one kick with a phone lux meter at the mat, as section 7 already plans.
- **Low dimming flicker.** At 30 % some LED lamps dim by PWM; IEEE 1789 recommends low percent flicker
  below 90 Hz ([DOE summary of IEEE 1789-2015](https://www.energy.gov/eere/ssl/articles/flicker-understanding-new-ieee-recommended-practice);
  the standard is listed inactive since 03.2026, [IEEE](https://standards.ieee.org/standard/1789-2015.html)).
  Not a contradiction, but check the real lamps at the default level with a phone slow-motion video; it
  also explains banding in the camera picture.

## 5. Evaluation

What is already good: recordings as the resampling unit, every number with n and an interval, a stated
ground truth per source with its reliability, a validated alignment, latency with a stated resolution,
light measures tied to the photosensitivity guidance, the data hash and commits for reproduction.

What a reviewer would ask for:

| Ask | Why | How |
|---|---|---|
| **Precision, not only hit rate** | "right if shown at some time from 0.1 s before to the next strike or 3 s" rewards a light that cycles through colours; false colour changes are what a lying participant notices | event-based precision, recall, F and error rate ([sed_eval](https://tut-arg.github.io/sed_eval/sound_event.html)); a 7 x 7 confusion matrix per mode |
| **Standard onset metric for the onset detector itself** | separates "found the strike" from "named the bowl" | mir_eval onset F with the 50 ms window ([mir_eval](https://mir-eval.readthedocs.io/latest/api/onset.html)); note-level onset plus pitch class within 50 cents ([mir_eval transcription](https://mir-eval.readthedocs.io/latest/api/transcription.html)) |
| **A held-out test set** | the constants (`FLUX_MIN`, `SWITCH_MS`, partial windows) were tuned on the owner's 24 to 25.10. recordings, which are also scored | freeze a test set of new recordings never looked at while tuning; report dev and test apart |
| **More than one set and room** | all own rounds are one set of seven bowls in one room; YouTube strikes come from 2 recordings | at least 3 more sets (incl. crystal) and 3 rooms; rubbed (sung) bowls as their own group, they have no onset |
| **Baselines** | shows what the hand-made method is worth | the same mapping on pYIN, a plain peak picker and Basic Pitch ([Bittner et al., ICASSP 2022](https://ar5iv.labs.arxiv.org/html/2203.09893)) |
| **Ablations** | which part earns its keep | strike path on/off, partial rule on/off, gate on/off, Flow vs Strike (exists) |
| **Gate as a curve** | one operating point hides the trade-off | ROC or PR per class, or PSDS ([Ebbers et al.](https://arxiv.org/pdf/2201.13148)) |
| **Label agreement** | one person labelled everything | a second person on 20 % of segments, Cohen's kappa |
| **On the board** | the Mac numbers skip the microphone, gain, lamps | microphone to visible lamp change with a phone slow-motion video; memory and CPU per task |
| **People** | the claim is "feels calm" | the three-question form of SOUND_LIGHT_EXPERIENCE.md section 7, after 3 real sessions |

## The five most valuable next changes

| Rank | Change | Expected effect | Effort |
|---|---|---|---|
| 1 | **Learned bowls as spectral templates with real-time non-negative decomposition** (section 1): store each bowl's whole spectrum in the existing learning round; decompose every hop onto 7 bowl templates plus noise and gong; a strike is an activation jump; colour from the newly active bowl | removes partial confusion and masking by a louder ringing bowl in one step; handles untuned sets (the G#3 "root" case); gives the camera a clean audio identity to assign. Est., to be confirmed by change 2: many of the remaining own-round misses (3 of 28 in Flow) and of the announced-video misses are of this kind | medium: 2 to 3 days C with a host test, plus a rerun of the evaluation; under 1 % CPU est. |
| 2 | **Evaluation that survives review** (section 5): frozen held-out test set from new sessions and other sets, precision and confusion matrix, mir_eval/sed_eval event metrics, a pYIN and Basic Pitch baseline, ablations | turns "93 % on our rounds" into a claim a reader can trust; shows where changes 1, 4, 5 help | 1 to 2 days code (the pipeline has stages for it) plus recording sessions |
| 3 | **A human-reviewed validation set for the detector and fewer classes** (bowl, gong, player) | first real accuracy number for vision; dead classes stop costing capacity and review time; then review where student and OWLv2 disagree | 1 day review (about 300 frames) and one pipeline rerun |
| 4 | **Gate: owner-bowl prototypes and strike-aligned windows, threshold from a curve** | win back the bowls the gate drops (91 to 84 % on Commons, 69 to 63 % on own segments) while keeping gongs and voices out; the prototype doubles as an "is this one of my bowls" check for the camera rescue rule | 1 day on the Mac (embeddings exist); on the board the ESP-DL enrol-and-match pattern |
| 5 | **Bowl-aware candidate scoring and a SuperFlux-style flux** for the Notes and Solfeggio mappings: bowl-mode template (1, 2.5 to 3.1, 5.0 to 5.7) beside the harmonic one; maximum filter over frequency and log bands in the flux | better confidence for bowls with low mode ratios (bells: 43 % colour share in Flow), fewer onsets from beating; helps users who never learn their bowls | a few hours in C and a rerun; host tests exist |

**Status 26.10.2026.** Change 5 is in both apps (ChakraA 6b34ca8, ChakraV 02ca726), each half behind its
own flag: strikes right went from 83 to 87 % in Flow and 87 to 90 % in Strike (70 strikes), the
hand-marked own rounds from 13 to 14 of 14, latency unchanged; bells gained only 1 to 2 points. The
log-spaced bands were tried and left out: they found 54 to 66 of the 70 strikes against 67 with linear
bins, because they flatten the mallet's broadband attack. Change 3 is running (detector round 2).

Not ranked, but do before the blog: correct the "under the WCAG flash line" wording (section 4), and run
`review` on the AGPL question for the detector weights (DETECTOR_CHOICE.md), as the rules require for legal
paths.

## Sources not reachable

The arXiv version 1106.5657 of the bowl paper is withdrawn (the same study is 1106.6348); the MDPI study on
Grounding DINO auto-labels (Applied Sciences 14(6) 2232) and the IPSJ paper on weighted audio-visual
instrument recognition refused automated readers and are not cited.
