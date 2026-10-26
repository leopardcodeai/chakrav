# ChakraV

<img src="docs/icon.svg" width="72" align="right" alt="ChakraV-Icon: eine Klangschale mit Kamera">

**Chakra mit Video: die Klangschale hören, den Raum sehen, ihn in der Farbe des Chakras leuchten lassen.**

ChakraV ist das experimentelle Geschwister von **[ChakraA](https://github.com/leopardcodeai/chakraa)**, der
Audio-App, für Espressifs [ESP-Mosaico](https://mosaico.espressif.com) (ESP32-S31, 2,16" Touchscreen
480 x 480, Mikrofon, Kamerasteckplatz). Ein breiter Rahmen um den Bildschirm leuchtet in der Farbe des
gehörten Chakras, das Live-Bild steht in der Mitte, Boxen markieren die Instrumente, und zwei Pillen zeigen,
was sie hört und was sie sieht. Englische Fassung (Quelle): [README.md](README.md).

## Welche App?

Zwei Apps, ein Code. Im Yoga und in der Klangarbeit wollen viele Menschen gar keine KI oder nur KI, die im
Raum bleibt: **[ChakraA](https://github.com/leopardcodeai/chakraa) ist dafür gebaut.** Sie läuft ohne jede
KI, ihre einzige KI-Funktion läuft auf dem Gerät, und sie hat keine Kamera und keine Cloud. **ChakraV ist
ausdrücklich die experimentelle**: sie probiert aus, was eine Kamera und größere Modelle bringen.

| | [ChakraA](https://github.com/leopardcodeai/chakraa) (Audio) | ChakraV (diese) |
|---|---|---|
| Hört | Mikrofon | Mikrofon und Kamera |
| KI | keine nötig; ein optionaler lokaler KI-Klangfilter, nur auf dem Gerät | so viel auf dem Gerät, wie der ESP32-S31 schafft, dazu optional Cloud-Modelle mit eigenem API-Schlüssel |
| Für | Räume ohne Kamera: die klassische, private Wahl | Experimente: was kann sie sehen und markieren? |
| Reife | an echten Aufnahmen ausgewertet ([Bericht](https://github.com/leopardcodeai/chakraa/blob/main/docs/evaluation/report.md)) | v0 |

Wer keine Kamera braucht oder keine KI außerhalb des Geräts will, nimmt ChakraA.

| Live-Ansicht | Einstellungen | Kamera | Anbindungen |
|---|---|---|---|
| ![Rahmen im Grün des Herzens, Demo-Szene mit drei markierten Instrumenten, Herz F3 174,8 Hz](docs/screen_main.png) | ![Farbe, Helligkeit 30 %, Empfindlichkeit, Nachklang, Flow oder Strike, Zuordnung, Sprache, lokaler KI-Klangfilter](docs/screen_settings.png) | ![Kamera, Boxen, 1, 2 oder 4 fps, Kameralicht, Cloud-KI, Quelle 400 x 224](docs/screen_camera.png) | ![Bildschirm-Lampe angehakt, die anderen Lampen nicht gekoppelt](docs/screen_connections.png) |

Alle Bildschirmfotos zeigen die gezeichnete Demo-Szene (`tools/camera_live.py --demo`), nie ein echtes
Kamerabild.

## Was sie kann (v0, 26. Oktober 2026)

| | Teil | Stand |
|---|---|---|
| Hört | Chakra-Erkennung, Anschläge über den spektralen Fluss, Lampen, Bildschirm-Lampe, lokaler KI-Klangfilter | wie in ChakraA, derselbe C-Code |
| Leuchtet | Rahmen und Lampen in der Farbe des Chakras; ruhiges Licht: 30 % Helligkeit, ein Anschlag kickt höchstens alle 2 s, ein Gong schwillt an und behält die Farbe | Simulator und Host-Tests |
| Sieht | Live-Kamerabild 16:9, 400 x 224, von der Mac-Kamera oder einem Video, 1, 2 oder 4 fps | Simulator |
| Markiert | Instrumentenboxen mit kurzen Pillen („Bowl", „Bowl C"), bis zu 7: auf dem Mac durch OWLv2 (Zero-Shot) mit einem Tracker, der die Schalen hält und eine Reihe nach ihren Tönen benennt | nur Mac; auf dem Board noch kein Detektor |
| Zeigt | Pille „gehört" (oranger Punkt) und „gesehen" (grüner Punkt), Halbtonspektrum mit den Chakra-Punkten, Anzeigepunkt, WLAN-Symbol | Simulator |
| Kameralicht | Aus, An, Auto (an, solange das Bild dunkel ist), die Blitz-LEDs des Moduls | Simulator; Board geschrieben, nicht gelaufen |
| Cloud-KI | Einstellung und Aufbau der Anfrage | **Platzhalter**: in v0 wird nichts gesendet |
| Kamera am Board | `main/camera.c`: öffnet das Modul, unterscheidet V1.4 und V1.2 an der Sensorkennung, baut das 16:9-Bild | **geschrieben, baut, noch nicht gelaufen** (Board bestellt) |

**Das Licht ist in beiden Apps gleich.** Leuchten, Kick, Gong-Anschwellen, Überblendungen,
Bildschirm-Lampe und jede Lampeneinstellung kommen aus demselben Kerncode (`chakra_core.c`,
`chakra_light.c`), und eine Änderung daran wird in beiden gemacht. Sicher macht das Licht die Rate: ein Kick zählt als Blitz, wie klein er auch ist (ein roter nach
WCAG, und eine Raumlampe füllt das Blickfeld), deshalb kommt er höchstens alle 2 s, weit unter 3 pro
Sekunde; an echten Lampen ist das nicht gemessen. Wie gut das Hören funktioniert, misst die
Auswertung von ChakraA: 83 % der Anschläge richtig in Flow und 87 % in Strike über 70 Anschläge, 0,29 s und
0,03 s vom Anschlag zur Farbe.

![Von der Klangschale zur Farbe des Raums (Schaubild englisch)](docs/how-it-works.png)

## Das Kameramodul

Das ESP-Mosaico kommt voraussichtlich mit dem **Kameramodul V1.4 (SC101IOT)**, **quer** montiert; das ältere
**V1.2 (OV3640)** geht auch. Beide sitzen im linken Steckplatz. Die App liest die Sensorkennung und nennt das
Modul auf der Seite Kamera („SC101IOT v1.4 · 1280 × 720").

| | V1.4 (erwartet) | V1.2 |
|---|---|---|
| Sensor | SC101IOT, 1 MP, 2,9 µm Pixel (besser im dämmrigen Raum) | OV3640, 3 MP, 1,75 µm Pixel |
| Bild | 1280 x 720, 15 fps | 1024 x 768, 25 fps |
| Objektiv | 3,1 mm F1,8, manueller Fokus, 73 x 42 Grad | 68 Grad diagonal |
| Das 16:9-Bild der App, 400 x 224 | das ganze Bild bei 5/16 | die Mitte 916 x 512 bei 7/16, etwa 51 x 30 Grad |

Das Objektiv der V1.4 einmal auf den Abstand der Schalen scharf stellen, bei offener Live-Ansicht.

<details>
<summary><b>Kamera im Detail: Skalierung, Ausrichtung, Blitz</b></summary>

- **Warum 400 x 224.** Der PPA des Boards skaliert in 1/16-Schritten; 1280 x 5/16 = 400 ist die breiteste
  Stufe innerhalb des 424 px breiten Felds. 224 statt 225 Zeilen halten den JPEG-Encoder auf ganzen
  16 x 16-Blöcken.
- **Hochkant montiert.** Mit `CHAKRA_CAM_LANDSCAPE 0` (`--mount portrait` in der Emulation) ist das Bild ein
  16:9-Streifen quer durch das aufrechte Bild, 712 x 400 bei 9/16, etwa 42 x 26 Grad bei V1.4.
- **Ausrichtung.** Der Sensor liest ungespiegelt aus. Quer: nicht drehen, nicht spiegeln. Zwei Schalter in
  `main/camera.c`, `CHAKRA_CAM_TURN_180` und `CHAKRA_CAM_MIRROR`, dazu ein Test mit Textblatt und Pfeil für
  den ersten Lauf auf dem Board.
- **Modulkennung.** PID 0xDA4A ist der SC101IOT, 0x364C oder 0x3641 der OV3640; die Bildgröße nur, wenn das
  Lesen scheitert. Das EEPROM des Steckplatzes wird protokolliert, unterscheidet die beiden aber nicht. BSP:
  esp-mosaico-bsp 7cbfb39 (22.10.2026, mit der PWDN-Korrektur für den SC101IOT).
- **Blitz.** Zwei LEDs an GPIO34, LOW = an, Open Drain. Wie lange sie an bleiben dürfen (Wärme) und die
  Dunkelschwelle von Auto werden auf dem Board gemessen.
- Hintergrund: [docs/CAMERA_BOARD_QUESTIONS.md](docs/CAMERA_BOARD_QUESTIONS.md) (englisch).

</details>

## KI: zuerst auf dem Gerät, die Cloud zum Vergleich

1. **Auf dem Gerät**, über ESP-DL: der lokale KI-Klangfilter (EfficientAT mn05, derselbe wie in ChakraA)
   und ein Instrumentendetektor, ESPDet-Pico bei 320 x 320, geschätzt etwa 170 ms je Erkennung
   ([docs/DETECTOR_CHOICE.md](docs/DETECTOR_CHOICE.md)). Bisher Schätzungen: auf Hardware ist nichts gemessen.
2. **In der Cloud, optional**, mit eigenem API-Schlüssel, zum Vergleich mit dem Gerät. Standardmäßig aus
   (Seite Kamera, Cloud-KI); sie würde ein Bild des Raums an den Anbieter schicken. Schlüssel nur aus dem
   sicheren Speicher des Geräts oder auf dem Mac aus dem Schlüsselbund über die Umgebung; nie aus einer
   Datei in diesem Repository.

**Das Hören entscheidet, das Sehen bestätigt nur.** Eine Farbe ändert sich nur bei stehender Tonhöhe. Die
Kamera darf einen Wechsel anhalten, wenn sie einen Gong oder eine Trommel gespielt sah, eine Schale retten,
die der KI-Klangfilter verpasst hat, oder zwischen zwei klingenden Schalen entscheiden; sie setzt nie selbst
eine Farbe und misst nie einen Anschlag (1 bis 4 fps sind dafür zu langsam). Warum:
[docs/SOUND_LIGHT_EXPERIENCE.md](docs/SOUND_LIGHT_EXPERIENCE.md), Abschnitt 5 (englisch). In v0 noch nicht
verbunden.

## Im Simulator starten

Nötig sind macOS, Python 3, ffmpeg und Pillow sowie der Mosaico-Workspace neben diesem Ordner
(`../../workspace`).

```sh
./sim.sh --demo     # Browser-Vorschau (die ausgegebene Adresse): Demo-Schalen, die gezeichnete Szene mit Boxen
./sim.sh --live     # Mikrofon des Macs mit lokalem KI-Klangfilter und die Kamera des Macs
./sim.sh            # die App allein; selbst füttern:
python3 tools/chakra_feed.py tone 174.6             # ein Ton (Herz)
python3 tools/camera_live.py --demo --demo-boxes    # die Demo-Szene
python3 tools/camera_live.py --video FILE --detect  # ein Video, wie es das Modul V1.4 sähe, Boxen von OWLv2
python3 tools/screens.py /tmp/chakrav-shots         # die vier Bildschirmfotos oben (nur Demo-Quellen)
```

**Im Launcher.** Unsere Vibe-Mode-Launcher-Simulation (`tools/mosaico_launcher.py` im Mosaico-Workspace,
nicht Teil dieses Repositorys) hat eine Kachel ChakraV: Live (Mikrofon, KI-Klangfilter, Mac-Kamera) oder
Demo. Mit `--chakrav-video FILE` spielt ChakraV stattdessen ein Video: sein Bild durch seinen besten
16:9-Ausschnitt in der Ansicht, sein Ton an die Erkennung, und ein Knopf **Sound** spielt diesen Ton auf dem
Mac ab (beim Start an).

**Kamera und Privatsphäre.** macOS fragt einmal nach der Kamera-Erlaubnis; wird sie verweigert, wartet das
Skript und umgeht nichts. Bilder gibt es nur in einer temporären Datei, die jedes neue Bild überschreibt und
die am Ende gelöscht wird. Steht die Kamera auf Aus, hält ffmpeg an, und die Kamera des Macs ist ebenfalls
aus.

<details>
<summary><b>Ports, das emulierte Modul und das Zeilenprotokoll</b></summary>

Audio auf 8710 (`CHAKRA_FEED_PORT`), Zeilen auf 8711 (`CHAKRA_AI_PORT`); ChakraV und ChakraA teilen sich so
nie einen Port. Die Vorschau nimmt 3222 oder den nächsten freien Port.

`camera_live.py --module v1.4` (Standard) oder `v1.2` macht aus einem Video das Bild des Moduls, nimmt davon
den 16:9-Streifen für die App und gibt dem Detektor das ganze Bild in 3/4 Größe (960 x 540), wo er Schalen
viel besser erkennt. Die Quellzeile auf der Seite Kamera sagt, was emuliert wird
(„Video · SC101IOT v1.4 emulated").

| Zeile (Port 8711) | Bedeutung |
|---|---|
| `frame\t<path>\t<luma>` | ein JPEG von genau 400 x 224; seine mittlere Helligkeit steuert Auto beim Licht |
| `boxes\tclear`, dann `box\t<label>\t<x>\t<y>\t<w>\t<h>\t<conf>` | die Markierungen eines Bildes, normiert 0..1, höchstens 7 |
| `source\t<text>\t<camera\|video\|demo>` | die Quellzeile der Seite Kamera und der Anzeigepunkt |
| `sound\t<bowl\|other\|none>\t<strike>` | der lokale KI-Klangfilter; spricht er 5 s nicht, führt die Erkennung allein |
| `camera\t<on>\t<boxes>\t<fps>\t<cloud>` | zurück an jeden Client: die Kamera-Einstellungen |
| `camlight\t<on>\t<dark>` | zurück an jeden Client: das Kameralicht soll an oder aus sein |

</details>

<details>
<summary><b>Gestaltung</b></summary>

Nach unseren Mosaico-Gestaltungsregeln (DESIGN.md im Workspace): obere Leiste mit Titel, Uhr, Kamera- und
Mikrofonpunkt und Zahnrad; Inter; Pillen h/2; wenig Text; Englisch zuerst, Deutsch in den Einstellungen.
Der Rahmen ist 28 px breit; zwei dunkle Schleier lassen ihn weich nach innen auslaufen, weil ESP-GSP keine
Unschärfe kennt. Das 400 x 224-Bild steht unter der oberen Leiste, seine Kanten sind die Kanten der Zeilen
darunter: der Name mit Ton und Hz, dann die Pillen „gehört" und „gesehen" und das Spektrum.

Vorbilder (25.10.2026): [Philips Ambilight](https://www.philips.ca/c-p/42PDL7906T_12) (das Licht verlängert
das Bild an die Wand; hier verlängert der Rahmen den Klang in den Raum),
[Apple Intelligence Kantenleuchten](https://vp0.com/blogs/apple-intelligence-glow-border-effect-code-ios-free-ios-template-vibe-coding-gui)
(ein Leuchten am Rand ist ein Zustand, keine Dekoration),
[Material Design, Objekterkennung in der Live-Kamera](https://m2.material.io/design/machine-learning/object-detection-live-camera.html)
(ein durchgehendes Rechteck und ein kurzes Etikett),
[Google Nest Hub Umgebungsmodus](https://www.techadvisor.com/article/732792/how-to-change-ambient-mode-on-google-nest-hub.html),
[Framer Border Glow Pro](https://www.framer.com/marketplace/components/border-glow-pro/).

</details>

## Als Nächstes

1. **Ein eigener Detektor.** Auf dem Mac markiert OWLv2 mit dem Tracker Schalen auf hellen, klaren Bildern
   gut: sieben von sieben in fünf von sechs frei verfügbaren Videos mit Chakra-Sets, und nach einer
   Kalibrierrunde benennt er sieben Schalen nach ihren Tönen. In einer dämmrigen Sitzung mit Weitwinkel fand
   er zwei oder drei von vielen Schalen. `tools/make_detector_data.py` lässt OWLv2 Boxen auf Videobildern
   vorschlagen, ein Mensch prüft sie, und darauf wird ein kleiner ESPDet-Pico für den ESP32-S31 trainiert.
   Diese Trainingskette (AGPL-3.0) liegt getrennt in `../chakrav_detector`, nur lokal.
2. **Auf dem Board**: `main/camera.c` am echten Modul laufen lassen (Ausrichtung, Modulkennung, Farben,
   Wärme des Blitzes, Schwelle von Auto), dann den trainierten Detektor auf dem ESP32-S31.
3. Die KI auf dem Gerät am Board messen: Klangfilter und Detektor, Latenz und Speicher.
4. Der echte Cloud-Aufruf hinter Cloud-KI, um seine Boxen mit denen vom Gerät zu vergleichen.
5. Gehörtes und Gesehenes verbinden, nach der Regel oben.

## Wie sie gebaut ist

| Teil | Datei |
|---|---|
| Erkennung: FFT, Obertöne, Stetigkeit, Anschläge (spektraler Fluss), Zuordnungen | `components/app_chakra/chakra_detect.c` |
| Bildschirm: Rahmen, Kamerabild, Boxen, Pillen, Einstellungen | `components/app_chakra/chakra_core.c`, `ui/make_scene.py` |
| Licht: Kick, Gong-Anschwellen, die Farbregel des Klangfilters, Lampentakt | `components/app_chakra/chakra_light.c`, `tests/test_light.c` |
| Board: Mikrofon, WLAN, Lampen, Einstellungen (NVS-Schlüssel `chakrav`, Version 6) | `main/main.c` |
| Board: das Kameramodul, das 16:9-Bild, seine Helligkeit, der Blitz | `main/camera.c` |
| Simulatorseite und Einspeiser | `components/app_chakra/host/platform_pc.c`, `tools/chakra_feed.py`, `tools/camera_live.py` |
| Instrumente auf dem Mac: OWLv2, der Tracker, der beste 16:9-Ausschnitt eines Videos | `tools/detect_owl.py`, `tools/bowl_tracker.py`, `tools/best_crop.py` |
| Trainingsbilder für einen eigenen Detektor (privat, nie eingecheckt) | `tools/make_detector_data.py` |
| Bildschirmfotos und Prüfungen | `tools/screens.py`, `tools/sim_shot.py`, `tools/check_frames.py` |

Die internen Namen bleiben `app_chakra` und `gsp_chakra_*`, wie in ChakraA.

## Lizenz

Apache-2.0. Von [LeopardCode.AI](https://leopardcode.ai). Ein Licht- und Klangwerkzeug, kein Medizinprodukt.
