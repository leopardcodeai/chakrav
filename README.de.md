# ChakraV

**Chakra mit Video: die Klangschale hören, den Raum sehen, ihn in der Farbe des Chakras leuchten lassen.**

ChakraV ist das experimentelle Geschwister von **[ChakraA (Chakra Detection)](https://github.com/leopardcodeai/chakra-detection)**, der Audio-App,
für Espressifs [ESP-Mosaico](https://mosaico.espressif.com) (ESP32-S31, 2,16" Touchscreen 480 x 480, Mikrofon,
Kamerasteckplatz). Chakra hört eine Klangschale und färbt den Raum. ChakraV nimmt eine Kamera dazu, um zu
sehen, was möglich ist: ein breiter Rahmen um den Bildschirm leuchtet in der Farbe des gehörten Chakras, das
Live-Bild steht in der Mitte, Boxen markieren die Instrumente, und zwei Pillen zeigen, was sie hört und was
sie sieht. Englische Fassung (Quelle): [README.md](README.md).

## Welche App?

Es gibt zwei Apps aus demselben Code. Im Yoga und in der Klangarbeit wollen viele Menschen gar keine KI oder
nur KI, die im Raum bleibt: **[ChakraA](https://github.com/leopardcodeai/chakra-detection) ist dafür
gebaut.** Sie läuft ohne jede KI, ihre einzige KI-Funktion läuft lokal auf dem Gerät, und sie hat keine Kamera
und keine Cloud. **ChakraV ist ausdrücklich die experimentelle**: sie probiert aus, was eine Kamera und größere
Modelle bringen.

| | [ChakraA](https://github.com/leopardcodeai/chakra-detection) (Audio) | ChakraV (diese) |
|---|---|---|
| Hört | Mikrofon | Mikrofon und Kamera |
| KI | keine nötig; ein optionaler lokaler KI-Klangfilter, nur auf dem Gerät | so viel auf dem Gerät, wie der ESP32-S31 schafft, dazu optional Cloud-Modelle mit eigenem API-Schlüssel |
| Für | Räume ohne Kamera: die klassische, private Wahl | Experimente: was kann sie sehen und markieren? |
| Reife | an echten Aufnahmen getestet | v0 |

Wer keine Kamera braucht oder keine KI außerhalb des Geräts will, nimmt ChakraA.

**Das Licht ist in beiden gleich.** Leuchten, Anschlag-Kick, Überblendungen, Bildschirm-Lampe,
Farbeinstellungen und jede Lampeneinstellung kommen aus demselben Kerncode (`chakra_core.c`: `animate()`,
`light()`, die Farb- und Lampenseiten), und eine Änderung daran wird in beiden Apps gemacht.

| Live-Ansicht | Einstellungen | Kamera | Anbindungen |
|---|---|---|---|
| ![Rahmen im Grün des Herzens, Demo-Szene mit drei markierten Instrumenten](docs/screen_main.png) | ![Farbe, Helligkeit, Empfindlichkeit, Nachklang, Zuordnung, Sprache, lokaler KI-Klangfilter](docs/screen_settings.png) | ![Kamera an oder aus, Boxen an oder aus, 1, 2 oder 4 fps, Quelle](docs/screen_camera.png) | ![Bildschirm-Lampe angehakt, die anderen Lampen nicht gekoppelt](docs/screen_connections.png) |

Alle Bildschirmfotos zeigen die gezeichnete Demo-Szene (`tools/camera_live.py --demo`), nie ein echtes Kamerabild.

## Stand: v0 (25.10.2026)

| Teil | Stand |
|---|---|
| Chakra-Erkennung, Lampen, Bildschirm-Lampe, lokaler KI-Klangfilter | wie in ChakraA (676670f) |
| Rahmen in der Chakra-Farbe, mit Überblendung und Kick beim Anschlag | läuft im Simulator |
| Live-Kamerabild, Mac-Kamera, 1, 2 oder 4 fps | läuft im Simulator (`tools/camera_live.py`) |
| Instrument-Boxen mit Beschriftung, bis zu 4 | die Darstellung läuft; die Boxen kommen von einem **Platzhalter** (`--demo-boxes`) |
| Pillen "gehört" und "gesehen", kleines Spektrum | laufen |
| Einstellungen: Einstellungen, Anbindungen, **Kamera** (an, Boxen, fps, Cloud-KI) | laufen; auf dem Board als Einstellungsversion 5 gespeichert |
| Cloud-KI (experimentell) | ein **Platzhalter**: die Einstellung und `tools/cloud_vision.py` gibt es, in v0 wird nichts gesendet |
| Kamera auf dem Board | **noch nicht**: der Mosaico-Kameratreiber ist nicht eingebunden (`main/main.c`, TODO camera) |

**Eine echte Erkennung gibt es noch nicht.** Die Boxen auf den Bildschirmfotos sind die Positionen der
Demo-Szene; über der echten Kamera schickt `--demo-boxes` Boxen, die glaubhaft wandern und nichts markieren.
Ohne den Schalter kommen keine Boxen, und die Pille "gesehen" sagt "Nichts".

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
python3 tools/screens.py /tmp/chakrav-shots       # die vier Bildschirmfotos oben (nur Demo-Quellen)
```

Ports: Audio auf 8710 (`CHAKRA_FEED_PORT`), Zeilen auf 8711 (`CHAKRA_AI_PORT`: Urteile des KI-Klangfilters,
Bilder und Boxen der Kamera); ChakraV und Chakra teilen sich so nie einen Port. Die Vorschau nimmt 3222 oder
den nächsten freien Port; `sim.sh` gibt ihn aus.

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

Nach unseren Mosaico-Gestaltungsregeln (DESIGN.md im Workspace): obere Leiste mit Titel, Uhr, Punkt und Zahnrad; Inter; Pillen h/2; wenig
Text; Englisch zuerst, Deutsch in den Einstellungen. Der Rahmen ist 28 px breit (20 px war die andere
Variante; 28 wirkt mehr wie Licht). Seine Innenkante folgt dem Bildschirmradius minus Rahmen, mindestens
8 px; zwei dunkle Schleier lassen ihn weich nach innen auslaufen, weil ESP-GSP keine Unschärfe kennt. Das
Kamerabild hat den Bildschirmradius von 20 px über den Ringmaskentrick aus DESIGN.md "Media".

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
   fork", "gong", "chimes", "drum") in `camera_live.py` statt des Platzhalters.
2. **Auf dem Board**: die Mosaico-Kamera einbinden (esp_video, siehe `apps/camera`), dann ein trainiertes
   ESPDet-Pico auf dem ESP32-S31 für die Instrumente; ein Canvas-Ziel statt JPEG-Bildern.
3. Die KI auf dem Gerät am Board messen: Klangfilter und Detektor, Laufzeit und Speicher.
4. Der echte Cloud-Aufruf hinter Cloud-KI, um seine Boxen mit denen auf dem Gerät zu vergleichen.
5. Gehörtes und Gesehenes verbinden: ein Anschlag auf der markierten Schale lässt ihre Box aufleuchten.

## Lizenz

Apache-2.0. Von [LeopardCode.AI](https://leopardcode.ai). Ein Licht- und Klangwerkzeug, kein Medizinprodukt.
