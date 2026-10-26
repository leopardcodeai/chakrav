# ChakraV

<img src="docs/icon.svg" width="72" align="right" alt="ChakraV-Icon: eine Klangschale mit Kamera">

**Chakra mit Video: die Klangschale hören, den Raum sehen, ihn in der Farbe des Chakras leuchten lassen.**

ChakraV ist das experimentelle Geschwister von **[ChakraA](https://github.com/leopardcodeai/chakraa)**, der Audio-App,
für Espressifs [ESP-Mosaico](https://mosaico.espressif.com) (ESP32-S31, 2,16" Touchscreen 480 x 480, Mikrofon,
Kamerasteckplatz). Chakra hört eine Klangschale und färbt den Raum. ChakraV nimmt eine Kamera dazu, um zu
sehen, was möglich ist: ein breiter Rahmen um den Bildschirm leuchtet in der Farbe des gehörten Chakras, das
Live-Bild steht in der Mitte, Boxen markieren die Instrumente, und zwei Pillen zeigen, was sie hört und was
sie sieht. Englische Fassung (Quelle): [README.md](README.md).

## Welche App?

Es gibt zwei Apps aus demselben Code. Im Yoga und in der Klangarbeit wollen viele Menschen gar keine KI oder
nur KI, die im Raum bleibt: **[ChakraA](https://github.com/leopardcodeai/chakraa) ist dafür
gebaut.** Sie läuft ohne jede KI, ihre einzige KI-Funktion läuft lokal auf dem Gerät, und sie hat keine Kamera
und keine Cloud. **ChakraV ist ausdrücklich die experimentelle**: sie probiert aus, was eine Kamera und größere
Modelle bringen.

| | [ChakraA](https://github.com/leopardcodeai/chakraa) (Audio) | ChakraV (diese) |
|---|---|---|
| Hört | Mikrofon | Mikrofon und Kamera |
| KI | keine nötig; ein optionaler lokaler KI-Klangfilter, nur auf dem Gerät | so viel auf dem Gerät, wie der ESP32-S31 schafft, dazu optional Cloud-Modelle mit eigenem API-Schlüssel |
| Für | Räume ohne Kamera: die klassische, private Wahl | Experimente: was kann sie sehen und markieren? |
| Reife | an echten Aufnahmen getestet | v0 |

Wer keine Kamera braucht oder keine KI außerhalb des Geräts will, nimmt ChakraA.

**Das Licht ist in beiden gleich.** Leuchten, Anschlag-Kick, Überblendungen, Bildschirm-Lampe,
Farbeinstellungen und jede Lampeneinstellung kommen aus demselben Kerncode (`chakra_core.c`: `animate()`,
`light()`, die Farb- und Lampenseiten; `chakra_light.c`: Kick, Gong-Anschwellen, Lampentakt), und eine
Änderung daran wird in beiden Apps gemacht.

| Live-Ansicht | Einstellungen | Kamera | Anbindungen |
|---|---|---|---|
| ![Rahmen im Grün des Herzens, Demo-Szene mit drei markierten Instrumenten](docs/screen_main.png) | ![Farbe, Helligkeit, Empfindlichkeit, Nachklang, Zuordnung, Sprache, lokaler KI-Klangfilter](docs/screen_settings.png) | ![Kamera an oder aus, Boxen an oder aus, 1, 2 oder 4 fps, Quelle](docs/screen_camera.png) | ![Bildschirm-Lampe angehakt, die anderen Lampen nicht gekoppelt](docs/screen_connections.png) |

Alle Bildschirmfotos zeigen die gezeichnete Demo-Szene (`tools/camera_live.py --demo`), nie ein echtes Kamerabild.

## Stand: v0 (25.10.2026)

| Teil | Stand |
|---|---|
| Chakra-Erkennung, Lampen, Bildschirm-Lampe, lokaler KI-Klangfilter | wie in ChakraA (1cbd13c): Anschläge werden am spektralen Fluss erkannt, eine laut nachklingende Schale überdeckt die nächsten nicht mehr (7 von 7 Anschlägen einer Runde, in der Flow vorher nur Wurzel zeigte; 0,4 s in Flow, 0,1 s in Strike) |
| Rahmen in der Chakra-Farbe, mit Überblendung und Kick beim Anschlag | läuft im Simulator |
| Ruhiges Licht (26.10.2026): Helligkeit ab Werk 30 % (vorher 60 %; eine gespeicherte Einstellung bleibt); ein Anschlag kickt höchstens einmal alle 2 s, 8 Punkte und 8 % Richtung Weiß, unter der WCAG-Blitzgrenze, sodass eine Trommel mit 4 Schlägen je Sekunde nie im Takt blitzt; ein Gong kickt nie: die Lampen schwellen in 1,5 s um 12 Punkte an und in 7 s wieder ab, die Farbe bleibt, die Pille "gehört" sagt "Gong"; zwei Lampenbefehle je Kick oder Anschwellen, eine Hue-Bridge oder Home Assistant höchstens 8 je Sekunde | Host-Tests (`tests/run.sh`: eine Trommel mit 4 Hz gibt in 20 s 10 Kicks statt 83, 20 Lampenbefehle statt 250); der Gong-Kopf erkennt 45 % der Commons-Gongs und 33 % unserer eigenen (ChakraA `tools/bench/gong_head.py`), ein verpasster Gong bekommt den kleinen Kick |
| Live-Kamerabild: 16:9 wie das Bild des Kameramoduls, 400 x 224 (26.10.2026; vorher ein Quadrat 270 x 270), von der Mac-Kamera oder einem Video, 1, 2 oder 4 fps | läuft im Simulator (`tools/camera_live.py`, emuliert das Modul V1.4 oder V1.2) |
| Instrument-Boxen mit kurzer Beschriftung ("Schale", "Schale C"), bis zu 7, eine je Chakra-Schale | die Darstellung läuft; die Boxen kommen von einem **Platzhalter** (`--demo-boxes`) |
| Pille "gehört" (oranger Punkt, solange sie hört), Pille "gesehen" (grüner Punkt, solange sie sieht) | laufen |
| Spektrum: ein Band je Halbton, die Oktave des erkannten Tons und drei Halbtöne zu jeder Seite (A2 bis D4 für Oktave 3), sein Band in der Farbe seines Chakras; darunter die sieben Chakra-Punkte an ihren Tönen | läuft |
| Anzeigepunkt neben dem Zahnrad, wie bei iOS: grün, solange eine Kamera oder ein Video das Bild liefert, orange, solange nur das Mikrofon hört, grau für die Demo-Szene; kein Verbindungspunkt | läuft |
| Kameralicht: Aus, An, Auto (Standard; an, solange das Bild dunkel ist) | läuft im Simulator (die Mac-Kamera hat kein Licht, es wird gemeldet); auf dem Board die Blitz-LEDs des Moduls (GPIO34), geschrieben, noch nicht gelaufen |
| Einstellungen: Einstellungen, Anbindungen, **Kamera** (an, Boxen, fps, Cloud-KI) | laufen; auf dem Board als Einstellungsversion 5 gespeichert |
| Cloud-KI (experimentell) | ein **Platzhalter**: die Einstellung und `tools/cloud_vision.py` gibt es, in v0 wird nichts gesendet |
| Kamera auf dem Board | **geschrieben, baut, noch nicht gelaufen** (das Board ist bestellt): `main/camera.c` öffnet das Modul, unterscheidet V1.4 von V1.2, macht das 16:9-Bild und seine Helligkeit, schaltet den Blitz |

**Eine echte Erkennung gibt es noch nicht.** Die Boxen auf den Bildschirmfotos sind die Positionen der
Demo-Szene; über der echten Kamera schickt `--demo-boxes` Boxen, die glaubhaft wandern und nichts markieren.
Ohne den Schalter kommen keine Boxen, und die Pille "gesehen" sagt "Nichts".

## Hardware: das Kameramodul

Erwartet wird der ESP-Mosaico mit dem **Kameramodul V1.4 (SC101IOT)**; das ältere **V1.2 (OV3640)**
läuft auch. Beide stecken nur im **linken Steckplatz**. Welches es ist, fragt die App den Sensor selbst
(PID 0xDA4A SC101IOT, 0x364C oder 0x3641 OV3640; nur wenn das scheitert, zählt die Bildgröße), und nennt es
auf der Seite Kamera ("SC101IOT v1.4 · 1280 × 720"). Das EEPROM des Steckplatzes wird protokolliert, kann
die beiden aber nicht unterscheiden. BSP: esp-mosaico-bsp 7cbfb39 (22.10.2026, mit der PWDN-Korrektur für
den SC101IOT). Hintergrund: `docs/CAMERA_BOARD_QUESTIONS.md`.

| Kameramodule | V1.4 (erwartet) | V1.2 |
|---|---|---|
| Sensor | SC101IOT, 1 MP, 2,9 µm Pixel (besser im dämmrigen Raum) | OV3640, 3 MP, 1,75 µm Pixel |
| Bild | 1280 x 720 UYVY, 15 fps | 1024 x 768 UYVY, 25 fps |
| Objektiv | 3,1 mm F1,8, **manueller Fokus**, 73 x 42 Grad | 68 Grad diagonal |
| Einbau | quer (Eigentümer 26.10.2026): das Bild bleibt 1280 x 720 | quer: 1024 x 768 |
| 16:9-Bild der App, 400 x 224 | **das ganze Bild**, 1280 x 5/16, 73 x 42 Grad | die mittleren 916 x 512 mit 7/16, etwa 51 x 30 Grad |
| Blitz | zwei LEDs an GPIO34, LOW = an, Open Drain (aus, wenn der Host schläft) | ebenso |

- **Das Bild ist 16:9, wie die Zielkamera sieht** (Eigentümer 26.10.2026: "Bildausschnitt wie bei
  Zielkamera 16:9"): 400 x 224 auf dem Bildschirm. Die PPA des Boards skaliert in Schritten von 1/16;
  1280 x 5/16 = 400 ist der breiteste Schritt, der in das 424 px breite Feld passt. 224 statt 225 Zeilen
  halten den JPEG-Encoder auf ganzen 16 x 16-Blöcken (400 = 25 x 16, 224 = 14 x 16); eine Zeile von 225
  fällt weg. V1.2 liefert dieselbe Größe aus ihren mittleren 916 x 512 mit 7/16 (6/16 ihres ganzen
  16:9-Streifens wären 384 x 216, ein Bild anderer Größe). Seitlich eingebaut (`CHAKRA_CAM_LANDSCAPE 0`,
  `--mount portrait`) ist das Bild ein 16:9-Streifen quer durch das aufrechte Hochkantbild, 712 x 400 mit
  9/16, etwa 42 x 26 Grad bei V1.4.
- **Ausrichtung.** Der Sensor liest ungespiegelt aus. Quer: keine Drehung, kein Spiegeln. Seitlich: 90 Grad
  gegen den Uhrzeigersinn gedreht, ungespiegelt (das wahre Bild; die Vorschau des Kits zeigt es
  gespiegelt). Zwei Bauschalter in `main/camera.c`: `CHAKRA_CAM_TURN_180`, wenn das Bild kopfsteht,
  `CHAKRA_CAM_MIRROR` für die Selfie-Ansicht. Welchen der Einbau braucht, zeigt der Test mit Textblatt und
  Pfeil in `main/camera.c` (CHECK ON THE BOARD).
- **Einmal scharf stellen.** Das Objektiv der V1.4 hat manuellen Fokus: bei offenem Live-Bild einmal auf
  den Abstand der Schalen drehen, dann so lassen.
- **Licht.** Die Blitz-LEDs sind das Kameralicht (Aus, An, Auto). Wie lange sie an bleiben dürfen (Wärme)
  und die Dunkel-Schwelle der Automatik mit dem helleren Sensor der V1.4 werden noch am Board gemessen.

## KI: zuerst auf dem Gerät, die Cloud zum Vergleich

1. **Auf dem Gerät.** So viel, wie der ESP32-S31 selbst rechnen kann, über ESP-DL: der lokale KI-Klangfilter
   (EfficientAT mn05, w8a16, derselbe, den `tools/ai_gate.py` auf dem Mac nutzt) und ein Instrumentendetektor
   wie ESPDet-Pico. Beides sind **bisher Schätzungen**: das Board ist bestellt, auf Hardware ist nichts gemessen.
2. **In der Cloud, optional.** Bild- und Audiomodelle mit eigenem API-Schlüssel (zum Beispiel OpenAI oder
   Gemini), zum Vergleich mit dem, was auf dem Gerät läuft. **Standardmäßig aus** (Kamera-Seite, Cloud-KI).
   Sie läuft nur, wenn sie eingeschaltet **und** ein Schlüssel vorhanden ist. Schlüssel kommen nur aus dem
   sicheren Speicher des Geräts (verschlüsselter NVS; `tools/provision.py` soll sie schreiben, in v0 noch nicht) oder auf dem Mac aus
   dem Schlüsselbund über die Umgebung (`OPENAI_API_KEY`, `GEMINI_API_KEY`); nie aus einer Datei in diesem
   Repository. Ein Cloud-Aufruf schickt ein Bild des Raums an den Anbieter: nur einschalten, wo das in Ordnung
   ist. In v0 baut `tools/cloud_vision.py` die Anfrage und sendet nichts.

## Im Simulator starten

Nötig sind macOS, Python 3, ffmpeg (`brew install ffmpeg`), Pillow für die Demo-Szene und der
Mosaico-Workspace neben diesem Ordner (`../../workspace`).

```sh
./sim.sh --demo     # Browser-Vorschau (die ausgegebene Adresse): Demo-Schalen, die gezeichnete Szene mit Boxen
./sim.sh --live     # Mikrofon des Macs mit lokalem KI-Klangfilter und die Kamera des Macs
./sim.sh            # die App allein; selbst füttern:
python3 tools/chakra_feed.py tone 174.6           # ein Ton (Herz)
python3 tools/camera_live.py --demo --demo-boxes  # die Demo-Szene
python3 tools/camera_live.py --video FILE --detect  # ein Video, wie es das Modul V1.4 sähe (--module v1.2)
python3 tools/screens.py /tmp/chakrav-shots       # die vier Bildschirmfotos oben (nur Demo-Quellen)
```

Ports: Audio auf 8710 (`CHAKRA_FEED_PORT`), Zeilen auf 8711 (`CHAKRA_AI_PORT`: Urteile des KI-Klangfilters,
Bilder und Boxen der Kamera); ChakraV und Chakra teilen sich so nie einen Port. Die Vorschau nimmt 3222 oder
den nächsten freien Port; `sim.sh` gibt ihn aus.

**Das Modul, emuliert.** `camera_live.py --module v1.4` (Standard) oder `v1.2` macht aus einem Video das
aufrechte Bild des Moduls (so skaliert, dass es es füllt, mittig), nimmt davon den 16:9-Streifen des
Bildes für die App (bei V1.4 das ganze Bild) und gibt dem Detektor das ganze aufrechte Bild in 3/4 Größe
(960 x 540), wo er Schalen viel besser erkennt; seine Boxen müssen bei V1.4 nicht verschoben werden, sie
gehören schon zum Bild. Von der Mac-Kamera nimmt es ihr Bild im Bildwinkel des Moduls (V1.4: fast alles),
der Detektor bekommt es in doppelter Bildgröße. Die Quellzeile auf der Seite Kamera sagt, was
emuliert wird ("Video · SC101IOT v1.4 emulated").

**Kamera und Privatsphäre.** macOS fragt einmal nach der Kamera-Erlaubnis für die App, die
`camera_live.py` startet; wird sie verweigert, sagt das Skript das und wartet, es umgeht nichts. Bilder gibt
es nur in einer temporären Datei in einem privaten Ordner, die jedes neue Bild überschreibt und die am Ende
gelöscht wird. Steht die Kamera auf Aus, hält ffmpeg an, und die Kamera des Macs ist ebenfalls aus.

## Im Ideas-Launcher

Unsere Vibe-Mode-Launcher-Simulation (`tools/mosaico_launcher.py` im Mosaico-Workspace, http://127.0.0.1:3300,
nicht Teil dieses Repositorys) hat eine Kachel ChakraV:

- **Live** (Standard): `chakra_feed.py mic --ai` (Mikrofon und lokaler KI-Klangfilter, wenn seine venv da ist; Farben an die
  Bildschirm-Lampe) und `camera_live.py` (Kamera des Macs, ohne Boxen).
- **Demo** (`--demo chakrav`): Demo-Schalen und `camera_live.py --demo --demo-boxes`.
- Zum Schließen die obere Leiste 3 s halten, wie in jeder App.

## Gestaltung

Nach unseren Mosaico-Gestaltungsregeln (DESIGN.md im Workspace): obere Leiste mit Titel, Uhr, Kamera- und Mikrofonpunkt und Zahnrad; Inter; Pillen h/2; wenig
Text; Englisch zuerst, Deutsch in den Einstellungen. Der Rahmen ist 28 px breit (20 px war die andere
Variante; 28 wirkt mehr wie Licht). Seine Innenkante folgt dem Bildschirmradius minus Rahmen, mindestens
8 px; zwei dunkle Schleier lassen ihn weich nach innen auslaufen, weil ESP-GSP keine Unschärfe kennt. Das
Kamerabild hat den Bildschirmradius von 20 px über den Ringmaskentrick aus DESIGN.md "Media". Aufbau
(26.10.2026): das 400 x 224 große Bild unter der oberen Leiste, seine Kanten sind die Kanten der Zeilen
darunter: der Name (28 px) mit Note und Hz, dann die Pillen Gehört und Gesehen (34 px) und das Spektrum.

Gestaltungsvorbilder (25.10.2026):

- [Philips Ambilight](https://www.philips.ca/c-p/42PDL7906T_12): das Licht verlängert das Bild an die Wand;
  hier verlängert der Rahmen den Klang in den Raum.
- [Apple-Intelligence-Randleuchten](https://vp0.com/blogs/apple-intelligence-glow-border-effect-code-ios-free-ios-template-vibe-coding-gui):
  ein leuchtender Rand ist ein Zustand, keine Dekoration; er kommt mit dem Ton und geht mit ihm.
- [Material Design, Objekterkennung im Live-Kamerabild](https://m2.material.io/design/machine-learning/object-detection-live-camera.html):
  ein gefundenes Objekt mit einem durchgehenden Rechteck und kurzer Beschriftung markieren.
- [Google Nest Hub, Ambient-Modus](https://www.techadvisor.com/article/732792/how-to-change-ambient-mode-on-google-nest-hub.html):
  ein ruhiger Bildschirm, der sich dem Licht im Raum anpasst.
- [Framer Border Glow Pro](https://www.framer.com/marketplace/components/border-glow-pro/): ein weich
  gestreuter Rand statt einer harten Kontur.

## Als Nächstes

1. **Echte Erkennung auf dem Mac**: ein Open-Vocabulary-Detektor wie OWL-ViT ("singing bowl", "tuning
   fork", "gong", "chimes", "drum") in `camera_live.py` statt des Platzhalters. Dort testen, wo es schwer ist:
   - **Wenig Licht.** Klangräume sind dämmrig. `tools/check_frames.py` an zwei frei lizenzierten Testvideos
     (25.10.2026): ein schwebender Gong im dunklen Raum hatte im Mittel eine Helligkeit von 6 von 255 bei
     einem Kontrast von 19, 59 % der Zeit flach; eine Gong- und Trommelsitzung war hell (109, Kontrast 84).
     Den Detektor an beiden messen.
   - **Wechselnder Hintergrund.** Das Gong-und-Trommel-Video änderte sich im Mittel um 8,4 Helligkeitsstufen
     pro Bild (bis 12), das dunkle um 0,5: Menschen und Licht bewegen sich. Prüfen, dass die Boxen am
     Instrument bleiben und nicht mit dem Hintergrund springen.
   - **Hilft das Licht?** Die Automatik des Kameralichts schaltete im dunklen Video nach 2 s ein und blieb an.
     Auf dem Board den Detektor mit und ohne Blitz-LED messen, und ihre Wärme im Dauerbetrieb.
   Die Trainings-Pipeline (ESPDet-Pico, AGPL-3.0) liegt getrennt in `../chakrav_detector`, nur lokal.
2. **Auf dem Board**: `main/camera.c` mit dem echten Modul laufen lassen und prüfen, was dort als CHECK ON
   THE BOARD steht (Ausrichtung mit Textblatt und Pfeil, PID des Moduls und EEPROM des Steckplatzes, Farben, die 400 x 224 der PPA aus jedem Modul, die Wärme des Blitzes, die Dunkel-Schwelle
   der Automatik); dann ein trainiertes ESPDet-Pico auf dem ESP32-S31 für die Instrumente; ein Canvas-Ziel
   statt JPEG-Bildern.
3. Die KI auf dem Gerät am Board messen: Klangfilter und Detektor, Laufzeit und Speicher.
4. Der echte Cloud-Aufruf hinter Cloud-KI, um seine Boxen mit denen auf dem Gerät zu vergleichen.
5. Gehörtes und Gesehenes verbinden: ein Anschlag auf der markierten Schale lässt ihre Box aufleuchten.

## Lizenz

Apache-2.0. Von [LeopardCode.AI](https://leopardcode.ai). Ein Licht- und Klangwerkzeug, kein Medizinprodukt.
