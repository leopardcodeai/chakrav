# Sound and light: how a sound journey should look

Research for ChakraA and ChakraV, 26 October 2026. Question: how should sound detection and camera detection
work together, and how should the light behave, so that a sound journey (singing bowls, gongs, chimes,
drums, rain sticks, voice) feels good, with light the facilitator can adjust? No code was changed for this
document; every number marked "start value" is a proposal to measure, not a measured result.

## 1. Recommendations, ranked

| # | Recommendation | Why (section) | Today in the code |
|---|---|---|---|
| 1 | **Rate-limit the strike kick to at most 1 per 2 s (hard ceiling 3 per s), and never kick per drum beat.** A kick is a flash by the WCAG definition (more than 10 % luminance up and down). Shamanic drumming runs at about 3.7 to 4 beats a second, inside the 3 to 30 Hz band that triggers photosensitive seizures. | 3.1 | `chakra_core_set_sound()` sets `kick = 1` on every gate strike, with no rate limit; `ai_gate.py` can flag a strike every 50 ms chunk. |
| 2 | **Gong: a slow swell, not a kick.** Brightness +10 to +15 points rising over 1 to 2 s, falling with the gong over 5 to 10 s, no shift towards white, never a colour change. | 3.2, 4 | Gong strike = the same kick as a drum: +40 points and 35 % towards white, fading in about 0.9 s. |
| 3 | **Audio alone decides the colour; the camera may only veto, rescue or break a tie.** On disagreement, keep the colour: a missed change costs little in a journey, a wrong colour costs a lot. | 5 | Tracker marks "played" and learns bowls; no influence on the light yet (README "Next" 5). |
| 4 | **Flow is the only default for a lying journey; Strike is for practice, teaching, learning bowls and demos.** | 4 | Flow is the default (0.4 s lock, about 1.6 s fade; 3 s with the gate). Good. |
| 5 | **Dim by default: start value 30 % brightness instead of 60 %**, and keep the blue end (Throat, Third eye, Crown) a little lower in the evening. Evening guidance is at most 10 lux melanopic at the eye. | 3.3 | `brightness = 60`. |
| 6 | **Never go dark by itself; never cut.** In silence hold the colour; after a long silence drift over 20 to 30 s to a warm base glow. Darkness and the final brightening are the facilitator's actions. | 3.4, 4 | Lamps keep their colour in silence (`on_light` returns for chakra < 0). Good; no base glow and no "return" ramp yet. |
| 7 | **One phase control instead of many sliders: Arrive, Journey, Return.** Each phase sets reaction, fades, afterglow and brightness. Hide sensitivity, fade speed, kick strength and afterglow. | 6 | Settings show Brightness, Sensitivity, Afterglow, Flow/Strike, mapping, gate. |
| 8 | **Send each lamp at most 2 commands per kick or swell** (one up with a short transition, one down with a long one) and stay under 10 commands a second per Hue bridge (1 a second for groups). | 3.5 | During a kick `light()` goes out every third tick (about 8 a second per lamp), each with a 1.5 s transition in Flow. |
| 9 | **The screen lamp on a TV is the largest flash area in the room; give it the gentlest kick** (half the lamps' amount, or none). | 3.1 | Same kick as the device screen. |
| 10 | **Measure it** with the eight numbers in section 7 (changes per minute, short-lived colours, wrong-colour share per instrument, time to colour, flashes per second, brightness step, lamp command rate, facilitator overrides). | 7 | `tests/analyse.sh` already gives the wrong-colour share per instrument. |

**Built on 26.10.2026** (owner: "ja"), in both apps (`components/app_chakra/chakra_light.c`, host test
`tests/test_light.c`): 1 (one kick per 2 s, 8 points and 8 % white, largest luminance step 0.07 instead of
0.34; the rate is what keeps it safe, see 3.1), 2 (gong swell +12 over 1.5 s, down over 7 s; the gate says "gong" through a second head,
`tools/bench/gong_head.py` in ChakraA), 5 (brightness 30 %, without the evening ceiling for blue) and 8 (two
commands per kick or swell, network lamps at most 8 a second).

### Light per instrument class (start values)

| Sound | Colour | Brightness | Lamps | Screen |
|---|---|---|---|---|
| **Singing bowl** (metal, crystal), tuning fork: steady pitch, gate says bowl | takes the chakra's colour | phase level | Flow fade 2 to 3 s, holds through the ring | same, plus tuner ring |
| **Gong** (wash or single strike) | stays | swell +10 to +15 points, up 1 to 2 s, down 5 to 10 s | one up and one down command | same swell, no white |
| **Chimes** (koshi, wind chimes, tingsha) | stays | nothing | nothing | at most a faint sparkle, 5 points |
| **Drum** (frame drum, shamanic drum, ocean drum strikes) | stays | nothing per beat; at most 1 small pulse (5 to 10 points) per 2 s | nothing | at most the same capped pulse |
| **Rain stick, shaker, ocean drum rolling** | stays | nothing | nothing | nothing |
| **Voice**: speech, guidance | stays | nothing | nothing | nothing |
| **Voice**: chakra toning, a held vowel on a note for 1.5 s or more | only with "Voice colours" on (off by default) | phase level | Flow fade 3 s | same |
| **Silence** | holds, then after 30 s drifts over 20 to 30 s to the base glow | falls to the phase's base | slow | same |

### Phases (start values)

| Phase | When | Reaction | Brightness | Silence | Kick |
|---|---|---|---|---|---|
| **Arrive** | people come in and settle; talking | no reaction: steady base glow (warm amber, like Hue "Relax" at about 2250 K) | 30 to 40 % | n/a | none |
| **Journey** | bowls, gong waves, peak | Flow with the AI gate; fade 2 to 3 s; a colour holds at least 3 s unless a new strike comes | 20 to 35 % | hold 30 s, then drift to base | gong swell only, at most 1 per 2 s |
| **Return** | integration and closing, a tap by the facilitator | colour freezes, then over 60 to 120 s rises to warm white (about 2700 K) | ends at 40 to 50 % | n/a | none |

Strike stays available as a fourth choice under "more" for practice, demos and learning bowls.

### What the facilitator sees and what stays hidden

| Show (one tap each) | Hide or derive |
|---|---|
| Phase: Arrive, Journey, Return | Sensitivity: auto from the room's noise floor |
| Brightness (one slider, default 30 %) | Afterglow, fade speeds: from the phase |
| Colour: Auto or one fixed colour (exists) | Kick and swell strength: fixed at the safe values |
| Lamps (exists) | Camera fps, boxes, Cloud AI: on the Camera page, for experiments only |
| Optional: Voice colours (off) | Gate thresholds, tracker constants |

## 2. What the apps do today (the base for this)

From `README.md` of both apps and `components/app_chakra/chakra_core.c`, `chakra_detect.c`, `main/main.c`,
`tools/ai_gate.py` and `tools/bowl_tracker.py`:

- **Colour.** Seven chakra colours (Root `E0262B` to Crown `9B3FC8`), notes C root to B crown (A = 440 or
  432 Hz), Solfeggio, or learned bowls. A chakra locks after 256 ms from silence, needs 640 ms of a steadier
  tone to switch, and strikes are found by spectral flux at least 0.5 s apart.
- **Flow and Strike.** Flow: about 1.6 s fade on the screen (`FADE_FLOW`), 1.5 s transition to the lamps.
  Strike: 0.3 s on the screen, 0.1 s to the lamps. With the AI gate on, fades are about 3 s (`FADE_AI`).
- **AI gate.** EfficientAT mn05 every 0.5 s over the last second; bowl-like sounds may change the colour,
  others keep it. A jump of 12 dB over the last half second is sent at once as a strike. On 91 recordings it
  cut gongs colouring the room from 60 % to 21 %, voices from 46 % to 4 %, at the price of bowls 91 % to 83 %.
- **Strike kick** (only with the gate on): brightness +40 points and 35 % towards white, decaying to a tenth in
  about 0.9 s; lamps get a command every third 40 ms tick while it lasts. In silence the kick lights the last
  chakra's colour.
- **Silence.** The screen keeps an afterglow (default 1.5 s); the lamps keep their last colour.
- **Camera (ChakraV, v0).** 1, 2 or 4 fps; OWLv2 on the Mac (0.09 s a frame) through `detect_owl.py`; the
  tracker keeps bowls, marks a bowl "played" when a hand or mallet moves on it, and learns from votes (2 votes)
  which bowl sounds which chakra, and the direction of a row of 7 from 3 strikes. Its result does not touch
  the light yet.

## 3. Practice, products and limits for light in a sound journey

### 3.1 Flashing and flicker: the hard limit

- The Epilepsy Society: 3 to 30 flashes a second are the most common triggers, 16 to 25 the most likely;
  sensitivity under 3 Hz is uncommon, some people react up to 60 Hz. Single or double camera flashes are not
  likely to pose a risk; LED lights flashing against a dark background that fill the view are a named trigger.
  [Epilepsy Society factsheet, April 2025](https://epilepsysociety.org.uk/sites/default/files/2025-04/PhotosensitiveepilepsyApril2025.pdf)
- WCAG 2.3.1: at most 3 flashes in any second. A general flash is a pair of opposing changes in relative
  luminance of 10 % or more; a red flash is a pair of transitions involving a saturated red (R/(R+G+B) of 0.8
  or more). Area matters: up to 25 % of a 10 degree field is exempt.
  [W3C Understanding SC 2.3.1](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html)
- **For us:** a full kick (+40 points, 35 % towards white) is a general flash. Our Root red has
  R/(R+G+B) = 0.73, near the red-flash line; Hue lamps may render it more saturated. A TV used as the screen
  lamp fills far more than 25 % of the view: it is the strongest flash source in the room.
- **What keeps us safe is the rate, not the size of the step** (correction of 26.10.2026, from
  `APPROACH_REVIEW.md` section 4). WCAG's red flash has no luminance threshold: any pair of opposing
  transitions involving a saturated red counts, so a kick on Root (or towards white from red) is a red flash
  however small. And the 25 % area exemption is written for screens; room lamps and a TV as the screen lamp
  fill the field of view, so it does not apply. Even the 8-point kick therefore counts as a flash. The
  safety margin is that it comes at most once every 2 s, far under 3 a second. We have not measured
  compliance with WCAG 2.3.1 on real lamps and claim none.
- Rhythmic drumming in sound and shamanic work runs at about 220 beats a minute in Harner's core shamanism, a
  little under 4 Hz ([encyclopedia entry "Drums and drumming"](https://slovaronline.com/browse/b8a3e075-0594-30d0-8a04-5c6370b8c68c/drums-and-drumming)),
  and "theta drumming" is studied at 4 beats a second
  ([Neural tracking at theta predicts drumming induced altered states, Hebrew University](https://cris.huji.ac.il/en/publications/neural-tracking-at-theta-predicts-drumming-induced-altered-states/)).
  A kick on every beat would be a 4 Hz flash, inside the trigger band. Hence recommendation 1.
- Deliberate flicker products exist for the opposite purpose: the Lucia N°03 light uses a stroboscope to induce
  hypnagogic states with closed eyes ([MIND Foundation](https://mind-foundation.org/lucia-light/)), and even a
  wellness publisher warns that it may trigger seizures in people with light-induced epilepsy
  ([goop](https://goop.com/wellness/mindfulness/light-travel/)). ChakraA and ChakraV should stay clearly
  outside that category.

### 3.2 Eyes are mostly closed, and closed eyes see red and brightness

- Participants lie down with eyes closed, often with eye pillows or covers
  ([Healthline, gong bath](https://www.healthline.com/health/gong-bath);
  [Stillness and Sound event notes](https://www.tickettailor.com/events/stillnessandsound/2245022)).
- The eyelid passes about 9 % of light at 630 nm but only about 0.5 % at 550 nm and 0.4 % at 490 nm
  ([Bierman, Figueiro, Rea 2011, J Biomed Opt; LRC PDF](https://www.lrc.rpi.edu/resources/newsroom/pdf/2011/eyelid8511.pdf)).
  With closed eyes, a colour change between green, blue and violet is barely seen; a brightness jump and
  anything red (Root, Sacral, and every kick towards white, which adds red) is seen roughly 20 times more.
- **For us:** with closed eyes the light is felt as brightness. Kicks and swells are the part of the light
  people notice most; colour mostly matters at arrival and return, when eyes are open.

### 3.3 Dim and warm, especially in the evening

- Facilitator guides agree on dim light or candlelight, no harsh overhead light
  ([The Ohm Store guide](https://www.theohmstore.co/blogs/our-stories/how-to-create-a-sound-bath-a-guide-to-facilitating-for-friends-and-clients));
  care homes and event rooms use low lighting, LED candles and drapes
  ([Hengist Field gong bath](https://hengist-field.nellsar.com/gong-bath-meditation-experience-at-hengist-field-care-home/);
  [Chicago Parks EarthGong](https://chicagoparksfoundation.org/seeinggreen/2017/10/2/earthgong-bath-dream-in-2016)).
  These are practice blogs, not studies.
- Expert consensus on evening light: starting 3 hours before bedtime, at most 10 lux melanopic EDI at the eye,
  with short wavelengths reduced; the sleep environment at most 1 lux
  ([Brown et al. 2022, PLOS Biology](https://pmc.ncbi.nlm.nih.gov/articles/PMC8929548/)). Blue and violet
  light weigh most in melanopic terms, so the Throat, Third eye and Crown colours deserve a lower ceiling in
  evening sessions.
- 2700 K was rated better for relaxation than 4000 K in an office study
  ([Manav 2005, via IKU repository](https://openaccess.iku.edu.tr/handle/11413/1089)); Hue's own "Relax" scene
  sits at about 2250 K ([Hueblog](https://hueblog.com/2024/02/14/displaying-the-exact-colour-temperature-for-philips-hue-in-kelvin/)).
  Warm amber is the natural base glow and return light.

### 3.4 Changes should be visible but subtle; journeys have phases

- Philips Research (40 observers, RGB LEDs on a living room wall): there is a clear gap between the speed at
  which a colour change becomes visible and the speed at which it stops feeling subtle; "subtle" was read as
  pleasant, gentle and smooth. People are more sensitive to hue changes than to saturation changes, and more
  in the orange region than in the blue
  ([Murdoch, Sekulovski, Seuntiëns 2011, IS&T CIC](https://library.imaging.org/cic/articles/19/1/art00052)).
  For us: fades of 2 to 3 s for a hue change, and extra care between Root, Sacral and Solar plexus.
- A sound journey has an arc: grounding start, building, a peak (often the gong), integration with gentler
  sounds, a closing with silence and a gentle return
  ([Mysticryst guide](https://mysticryst.com/blogs/the-mystic-journal/sound-baths-creating-immersive-healing-experiences);
  [Holland Center sound bath outline](https://hollandcenter.org/wp-content/uploads/2025/08/ff-123c0775eb1f802a3b9c96c4522d1801-ff-Fox-Sound-Bath-Outline.pdf)).
  The peak is exactly where the gong sounds, so the gong must not cause the strongest light event.
- **Gap:** no source was found in which sound healers rate colour-changing light during a journey, or name
  transition times. The phase table above is our inference from the sources, to be checked with facilitators.

### 3.5 Products and what they teach

| Product | What it does | Lesson for us |
|---|---|---|
| Philips Hue Sync (app, box) | music and video sync with four intensities, Subtle to Intense; pastel palettes for ambient music ([Signify press release 2018](https://www.signify.com/en-us/about/news/press-releases/2018/20180531-create-surround-sound-for-your-eyes-with-philips-hue-sync)) | one intensity control is enough; the calm end should be the default for us |
| Hue Entertainment API | streaming at up to 25 updates a second for low-latency effects ([Linkd Home review](https://linkdhome.com/articles/2019/8/21/review-philips-hue-play-bar); [hue-dansen](https://github.com/paxswill/hue-dansen)); about 80 ms video to light reported by [Harmonize](https://github.com/mcpcapital/harmonizeproject) | the only Hue path for synchronous kicks; not needed for slow fades and swells |
| Hue REST API | default transition 400 ms; about 10 commands a second to lights, 1 a second to groups ([Hue developer support](https://developers.meethue.com/support/)); `transitiontime` in 100 ms steps ([node-hue-api docs](https://raw.githubusercontent.com/peter-murray/node-hue-api/HEAD/docs/lightState.md)) | let the bulb do the fade: one command with a long transition instead of a stream |
| Nanoleaf Rhythm | microphone module, 8 visualizer modes; most go dark without sound; the microphone picks up almost any noise ([TechHive review](https://www.techhive.com/article/583051/nanoleaf-rhythm-review.html)) | going dark in silence and reacting to every noise is what a journey must avoid |
| DMX sound-active fixtures, ENTTEC EMU | built-in sound modes or software that listens and drives DMX ([ENTTEC](https://support.enttec.com/dmx-software/emu/how-to-make-lights-react-to-music)); a fitness studio found its beat scenes useless for "zone out" parts and wanted warm dim scenes ([ControlBooth](https://www.controlbooth.com/posts/297436/)) | beat sync fails in calm segments; frequency and level modes suit better ([Soundcy](https://soundcy.com/article/what-is-sound-active-lights)) |
| Lucia N°03 | deliberate stroboscopic flicker for closed-eye experiences | the opposite of our goal: no rhythmic light |

None of these recognises a bowl or a chakra note; that, and the calm defaults, is the gap ChakraA and ChakraV fill.

## 4. Why the per-instrument behaviour

- **Bowls carry the colour** because they carry a steady pitch the detection reads well (bowls keep their
  colour 83 to 91 % of the time in our 91-recording table) and because the chakra-note mapping is about them.
- **The gong is the peak, not a note.** Its many inharmonic partials give unstable or wrong pitches (60 % wrong
  colour without the gate). It is also the loudest moment; a white kick there would be the brightest flash of the
  evening at the moment of deepest immersion. A slow swell follows its bloom and long decay instead.
- **Drums are rhythm.** A light that follows the beat flashes at the beat (section 3.1). Drums also sit in
  the grounding part of a journey, where steadiness is the point.
- **Chimes, rain sticks, shakers** are transitions and texture; they colour nothing today (0 % in our table)
  and should not start doing so.
- **Voice** includes the facilitator's spoken guidance, which must never paint the room. Chakra toning (a
  held vowel per chakra) is a real practice, so it can be an opt-in.
- **Silence** is part of integration. The lamps already keep their colour; the screen's 1.5 s afterglow is
  short for a journey, which is why the phase sets it (30 s hold, then a slow drift to the base glow).

## 5. Hearing and seeing together

### 5.1 What research says

- **Late fusion is robust and cheap.** A CNN that fuses audio and video for instrument recognition in
  user-generated videos at a late stage gave state-of-the-art results and robustness to a missing modality
  ([Slizovskaia, Gómez, Haro, ICMR 2017](https://repositori.upf.edu/items/3903024a-0627-48dd-bab7-b3cce1dcf5b2)).
  Weighting each stream by its momentary reliability is the classic approach in audio-visual speech
  recognition ([EPFL, entropy-based stream weights](https://infoscience.epfl.ch/record/125044/files/icmi08.pdf));
  recent work keeps scalar confidence weights per modality and sets a missing modality's weight to zero
  ([confidence-weighted late fusion, arXiv 2605.01219](https://arxiv.org/pdf/2605.01219);
  [reliability-aware fusion, arXiv 2606.12495](https://arxiv.org/pdf/2606.12495)).
- **Where a sound comes from.** Audio-visual correspondence learns, without labels, which image region
  makes the sound ([Arandjelović, Zisserman, Objects that Sound, ECCV 2018](https://openaccess.thecvf.com/content_ECCV_2018/html/Relja_Arandjelovic_Objects_that_Sound_ECCV_2018_paper.html);
  [Zhao et al., The Sound of Pixels, ECCV 2018](https://openaccess.thecvf.com/content_ECCV_2018/html/Hang_Zhao_The_Sound_of_ECCV_2018_paper.html)).
  These models are far beyond an ESP32-S31, but they confirm the idea.
- **Several instruments of the same kind need motion.** Appearance cannot tell two violins apart; body and
  finger keypoints can ([Gan et al., Music Gesture, CVPR 2020](https://arxiv.org/abs/2004.09476)). Seven bowls in
  a row are that case: the bowl is found by the mallet or hand moving on it, which is what `bowl_tracker.py` does.
- **Closest precedent to our tracker.** For drum videos, drum tops were found as ellipses, hits detected by
  motion intensity in each region, and the regions labelled by instrument class from a partial audio
  transcription and colour cues, with an optimal assignment (Kuhn-Munkres); the visual analysis improved the
  audio transcription ([McGuinness, Gillet, O'Connor, Richard, EUSIPCO 2007](https://researchportal.ip-paris.fr/en/publications/visual-analysis-for-drum-sequence-transcription/)).
  Our "a bowl gets a vote for the chakra heard when it was played" is the same idea; a full assignment over all
  bowls and notes (instead of per-bowl votes) is the upgrade it suggests.
- **Vision alone cannot time a strike.** Vision-based onset detection is hard even at video frame rates
  ([Bazzica et al. 2017, clarinet onsets](https://arxiv.org/pdf/1706.09556)); at our 1 to 4 fps a strike falls
  between frames. Timing stays with the microphone.
- **How much delay people notice.** For speech, audio leading the picture is detected from about 45 ms and
  accepted to about 90 ms; audio lagging is detected from about 125 ms
  ([ITU-R BT.1359 summary, TV Technology](https://www.tvtechnology.com/opinions/av-synchronization-how-bad-is-bad);
  [NTIA report](https://its.ntia.gov/publications/download/11-474.pdf)). A light that follows a sound is the
  "audio leads" case, where the binding window is the narrower and untrainable one
  ([Cecere, Gross, Thut 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC4915493)). So a kick meant to look
  synchronous must reach the eye within about 50 to 100 ms of the strike; a fade that starts 0.4 s later is not
  read as synchronous at all, it reads as a response, and its latency does not matter.

### 5.2 The fusion rule for a small device

1. **Audio decides the colour.** Only a steady pitch near a note can change it.
2. **Class check, two votes:** the AI gate (audio class) and the camera (the instrument a hand or mallet plays
   at the onset). A change goes through when the pitch is steady and at least one says "bowl" and the other
   does not clearly say otherwise.
3. **On disagreement, hold.** Asymmetric cost: a missed change is barely noticed (eyes closed, colour still
   right from before); a wrong colour on a gong wash is.
4. **Vision as a rescue, narrowly.** When the gate says "other" but the camera saw a played bowl whose learned
   chakra equals the heard pitch's chakra, allow the change (the gate loses 8 to 17 % of bowls).
5. **Vision as a tie-break.** Two bowls ringing, an octave or partial ambiguity (a bowl's second mode at 2.5 to
   3.1 times the fundamental): take the candidate that matches the played bowl's learned chakra.
6. **Vision never sets a colour on its own, and never times anything.**
7. **Stale or dark means absent.** No frame for 1.5 s, a dark picture (luma under the camera light's
   threshold), or a track found in under a quarter of the last detections: the camera's weight is zero and
   audio leads alone, as the gate does after 5 s without a verdict.

| Pitch | Gate | Camera (played at onset) | Light |
|---|---|---|---|
| steady | bowl | bowl, nothing, or stale | change |
| steady | bowl | gong, drum or chime played, no bowl | hold, log the disagreement |
| steady | other | bowl played, learned chakra = heard chakra | change (rescue) |
| steady | other | nothing, other, or stale | hold; a gong strike swells |
| two candidates | bowl | played bowl matches one of them | change to that one |
| unsteady or none | any | bowl played | hold; only the screen box shows "played" |

### 5.3 Latency budget

| Step | Budget | Today |
|---|---|---|
| Strike to colour decision | Flow 0.4 to 0.6 s; Strike 0.13 s | 0.4 s and 0.13 s (README) |
| Camera evidence window | frames from 1.0 s before to 0.5 s after the onset | tracker looks back 3 frames (1.5 s at 2 fps) |
| Waiting for the camera | Flow: until the lock at 0.4 s, never longer; Strike: never wait, use only frames before the onset (mallet on its way) | not joined yet |
| Decision to screen | one 40 ms tick | 40 ms |
| Decision to lamp | not critical for fades and swells; a synchronous kick only through a streaming path | REST and WebSocket per command |
| Kick to the eye | 50 to 100 ms if it should look synchronous; otherwise make it a swell | screen yes, lamps no |

## 6. Settings: why fewer

- Hue Sync gets away with one intensity control (Subtle to Intense), and our house rule is little to read and
  one-to-three-word labels. A facilitator mid-session needs one thing: where in the journey we are.
- Sensitivity can be derived from the noise floor; afterglow and fade speeds from the phase; kick strength must
  not be a slider, because its safe range is narrow (section 3.1).
- The camera's fps, boxes and Cloud AI belong to experiments; during a session the boxes help nobody lying on a mat.
- ChakraA keeps the AI gate off by default by design (no AI unless asked). For ChakraV, where AI is the point,
  the gate on by default in Journey is worth considering; the owner decides.

## 7. What to measure to know it feels good

| Measure | How | Start target |
|---|---|---|
| Colour changes per minute | log of `light` lines over a session or `tests/analyse.sh` on a full recorded journey | report per phase; a journey of slow bowls should sit at a few a minute |
| Short-lived colours | share of colours that last under 3 s ("jumping") | under 5 % |
| Wrong-colour share per instrument | `tests/analyse.sh` table (gong, voice, drum, bowl), with and without the gate and with the camera rule | gong 10 % or less, voice 5 % or less, drum 1 %, bowls 85 % or more |
| Time to colour | strike to screen halfway; strike to first lamp command; strike to visible lamp change (phone slow-motion video) | Flow under 0.6 s to the decision; lamps visibly moving within 1 s |
| Flashes | luminance reversals of more than 10 % within any second, computed from the light log (relative luminance of the sent colour times brightness), screen lamp included | never more than 3 in a second; target at most 1 per 2 s |
| Brightness step | largest brightness change per second not caused by the facilitator | 15 points a second or less |
| Light level at the mat | a phone lux meter at eye height, lying, evening | single-digit to low double-digit lux |
| Lamp commands | commands per second per bridge from the log | under 10 a second to lights, 1 to groups |
| Facilitator overrides | taps on fixed colour, brightness or phase per session | falling over sessions |
| Participants | three questions after a session: calm (1 to 5), light fitted the sound (1 to 5), any light moment that disturbed (yes, when) | collect from 3 real sessions before tuning further |

## 8. Open points

- Facilitator interviews: no published source rates colour-changing light during a journey; the phase values here
  are inference and need 3 real sessions.
- Gate strike rate under sustained drumming: measured 26.10.2026 on two Commons drum recordings, 1.6 strikes a
  second (a snare cadence, 60 s) and 2.5 (djembe, 13 s); the limiter takes one per 2 s whatever the rate.
  A 4 Hz frame drum of our own is still to be recorded.
- The Hue Entertainment API (DTLS) would allow synchronous kicks on Hue lamps; with swells instead of kicks it may
  never be needed.
- Measure the evening level of the blue chakra colours on the real lamps before choosing their ceiling.
