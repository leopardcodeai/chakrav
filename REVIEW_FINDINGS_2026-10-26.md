# Review-Befunde 26.10.2026

## Wer wirklich gelesen hat

| Achse | Reviewer | Stand | Anmerkung |
|---|---|---|---|
| standards | codex | gelesen | 884 Bytes Ausgabe |
| standards | gemini | nichts geliefert | exit 1, leere Ausgabe:     at process.processTicksAndRejections (node:internal/process/task_queues:104:5) |
| standards | coderabbit | gelesen | 0 Befunde |

Zweck: recht (angegeben (--zweck); Rechtspfad: Fristen, Vertraege, personenbezogene Daten). Achsen: standards. Gelesen: codex, coderabbit. Rohausgaben: `~/Library/Application Support/LeopardCode/review_agent/runs/2026-10-26/chakrav`. Jeder Befund unten ist am Code verifiziert; Unverifiziertes steht hier nicht.

## Offen

⚠️ Die Achsen werden nicht verrechnet: ein Befund der einen hebt keinen der anderen auf.

| # | Achse | Befund | Quelle | Schwere |
|---|---|---|---|---|
| 1 | standards | `tools/make_detector_data.py`: frame names from `int(t)` collide for `--step` under 1 s, image and labels overwrite each other while the counts keep both | codex, verified | mittel |
| 2 | standards | `tools/make_detector_data.py`: one existing label file marks the whole video done; a run stopped mid-video never fetches the rest | codex, verified | mittel |

The legal question (esp-detection is AGPL-3.0, the repo Apache-2.0; Ultralytics says trained weights fall under the AGPL) was not contradicted by either reviewer; it stays an owner decision (docs/DETECTOR_CHOICE.md). Gemini delivered nothing.

## Behoben

| 1, 2 | names in milliseconds; a video counts as done only once `done/<video>` is written at its end | next commit |

## Verworfen nach Verifikation

(Fehlbefunde mit Grund)
