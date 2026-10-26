#!/usr/bin/env python3
"""Generates the ChakraV app's ESP-GSP scene ui/main.json (480 x 480) and its charset.

What: ChakraV is the chakra app with a camera. The whole screen is the light: a thick frame in the
      chakra's colour runs around the edge (FRAME px, fading softly into the dark panel inside it,
      faded and kicked by chakra_core.c). Inside the panel: the top bar (title, clock, dot, gear),
      the live camera view in the centre, 16:9 like the camera module's frame, with up to seven
      instrument marks over it (a coloured box with a label pill each), and below it the chakra's name with the note and Hz, a "heard" pill
      (what the AI sound gate hears), a "seen" pill (what the boxes show) and a small spectrum (one
      band a semitone, the tone's octave and a little more) with the seven chakra dots under it.
      The gear opens the settings in three tabs: Settings, Connections and Camera (camera on or
      off, boxes on or off, 1, 2 or 4 frames a second, the experimental Cloud AI). Holding the top
      bar 3 s closes the app.
Why:  owner 25.10.2026: "eine neue App, wo man auch das Kamerabild in einem Live-Mode sieht und wie
      er die Instrumente markiert und was er erkennt"; "einen dickeren Rahmen, wo die Farbe dargestellt
      ist, und zentral die Kamera, und dann drunter noch paar Elemente".
Pitfalls:
  * Bound text needs font_charset_file; every character the C code may set must be in
    charset.txt (built here from STRINGS). Bound text cannot take text_vertical_align.
  * Colour setters are RGB565 natively; chakra_core.c uses the _rgb888 variants.
  * ESP-GSP 1.5.1 rounds an image's background and border, not its pixels, and clip_children is
    rectangular: a ring in the panel's colour masks the camera's corners (DESIGN.md, Media).
  * The camera frame is a runtime JPEG (chakra_core_set_frame) of exactly CAM_W x CAM_H; one image
    slot is reused. Decoded at 4 bytes a pixel it takes about 360 KB, so a frame and its pending
    replacement fit the 2 MB image cache with room to spare (the house doorbell's 448 x 336 did not).
  * The view is 16:9 (owner 26.10.2026: "Bildausschnitt wie bei Zielkamera 16:9"; it was a 270 px
    square before): the module is mounted for landscape, so the V1.4 SC101IOT's whole 1280 x 720
    frame (73 x 42 degrees) is the view. The board's PPA scales in steps of 1/16 only (ESP-IDF
    ppa.rst): 1280 x 5/16 = 400, the widest step inside the 424 px panel (6/16 = 480 is the whole
    screen). 224 rows, not 720 x 5/16 = 225: whole 16 px blocks for the JPEG encoder (main/camera.c).
    V1.2 OV3640 (1024 x 768): its centre 916 x 512 at 7/16 gives the same 400 x 224 (6/16 of its whole
    16:9 band would be 384 x 216, a frame of another size). tools/camera_live.py emulates both.
  * The rows below take the view's width (CONTENT_W = CAM_W), so their edges line up with it.
  * Box geometry is a bounded dynamic field, set in pixels inside the camera view (chakra_core.c):
    x and y move the box with its pill. A dynamic w or h resizes only a container's own fill, not
    its border, so the four edges are thin fills (8 setters a box; the core spreads them over ticks).
Usage:  make_scene.py               writes main.json, charset.txt and icons.txt next to it
        CHAKRAV_FRAME=20 make_scene.py   another frame width (design variants; default 28)
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
MED, BOLD, XBOLD, ICONS = "fonts/Inter-Medium.ttf", "fonts/Inter-Bold.ttf", "fonts/Inter-ExtraBold.ttf", "fonts/MaterialDesignIcons.ttf"
CHARSET, ICON_CHARSET = "charset.txt", "icons.txt"
WHITE, IDLE_BG, INK, ORANGE, SHADOW = "#FFFFFF", "#17141F", "#1C1E1E", "#FF9500", "#E2E2E7"
MUTED, FAINT = "#FFFFFFAD", "#FFFFFF70"
PANEL, TILE = "#0E0C12", "#221F2A"   # the dark panel inside the frame; a pill or card on it
CHAKRA_RGB = ["#E0262B", "#F47A1F", "#F2B705", "#2FA84F", "#1E88E5", "#4B3FB5", "#9B3FC8"]
SCREEN_RADIUS = 20  # ~/Coding/esp/DESIGN.md
# The coloured frame's width; the owner asked for 18 to 28. 28 chosen on 25.10.2026 against 20: the light
# reads as the frame of the room's colour, and the rows below still fit (tools/screens.py --frame).
FRAME = int(os.environ.get("CHAKRAV_FRAME", "28"))
CAM_W, CAM_H = 400, 224  # the 16:9 camera view; chakra_core.h CHAKRA_CAM_W/H, tools/camera_live.py W, H
CAM_X = (480 - CAM_W) // 2
CONTENT_W = CAM_W        # the rows below the view: name, pills, spectrum, aligned with its edges
CONTENT_X = (480 - CONTENT_W) // 2
TOP_H = 52               # the top bar inside the panel
CAM_Y = FRAME + TOP_H + 16
ROW1_GAP, ROW2_GAP = 20, 50  # the view to the name row; the name row's top to the pills' top
BOXES = 7                # chakra_core.h CHAKRA_BOXES: one a chakra bowl
EDGE, BOX_MIN = 3, 16    # a box's edge width; its smallest width and height
PLAY_EDGE = 6            # a played box's edges, thicker
SEEN, PLAYED = "#8E8E93", "#FF9F0A"  # a mark only seen: quiet grey; being played: amber, thick
PILL_MAX = 150           # a box's label pill at its widest; chakra_core.c PILL_MAX
PILL_MIN, PILL_H = 30, 18  # its narrowest ("Gong" fits) and its height; chakra_core.c PILL_MIN
BARS = 18                # the spectrum below the view, one band a semitone: the locked tone's octave and 3 semitones
                         # either side (chakra_core.h CHAKRA_VIEW_BANDS)
BAR_PITCH, BAR_W = 8, 6  # a band's step and width; chakra_core.c BAR_PITCH, BAR_W
BAND_NOTE0 = 9           # the window starts on an A (A2 for octave 3), so band j is note (9 + j) % 12
SPEC_W = BARS * BAR_PITCH - (BAR_PITCH - BAR_W)
BAR_X0 = CONTENT_X + CONTENT_W - SPEC_W
HEARD_W, SEEN_W, PILL_GAP = 112, 128, 8  # the pills beside it
ROW_H = 34                # their height; the spectrum's bars are as tall, its dots below them
NOTE_TO_CHAKRA = [0, 0, 1, 1, 2, 3, 3, 4, 4, 5, 6, 6]  # chakra_detect.c, C .. B
DOT_NOTES = [0, 2, 4, 5, 7, 9, 11]  # each chakra's dot sits at its natural note, C .. B
CAM_DOT, MIC_DOT, IDLE_DOT = "#30D158", "#FF9F0A", "#8E8E93"  # DESIGN.md: Apple's dark-mode indicator colours
# Material Design Icons 7.4.47: cog, home-assistant, lightbulb, wifi, bluetooth, check-circle, monitor,
# waveform (heard), eye-outline (seen), camera, camera-off
COG, HA, BULB, WIFI, BT, CHECK, MONITOR = 0xF0493, 0xF07D0, 0xF0335, 0xF05A9, 0xF00AF, 0xF05E0, 0xF0379
WIFI_OFF, WIFI_SYNC = 0xF05AA, 0xF16C7  # the connection in the top bar, beside the gear (DESIGN.md)
WAVE, EYE, CAMERA, CAMERA_OFF, CLOUD = 0xF147D, 0xF06D0, 0xF0100, 0xF05DF, 0xF0163
MIC, VIDEO, FLASH, MOVIE = 0xF036C, 0xF0567, 0xF0241, 0xF0381  # microphone, video, flash, movie (demo)
ON, OFF = "#6E5ACF", "#3A3744"  # DESIGN.md: chosen, not chosen
LAMPS = 4  # rows in the lamp list; chakra_core.h CHAKRA_LAMPS
SLIDERS = [("bright", "Brightness", 10, 100, 30), ("hue", "Colour", 0, 359, 0), ("sens", "Sensitivity", 1, 10, 8),
           ("hold", "Afterglow", 5, 50, 15)]
OPTIONS = [("map_notes", "Notes"), ("map_solf", "Solfeggio"), ("map_bowls", "Bowls"), ("lang_en", "EN"), ("lang_de", "DE")]

# Every string the C side may put into a bound label (chakra_core.c, both languages), for the
# charset; English is the default, German is chosen in the settings.
STRINGS = [
    "Root", "Sacral", "Solar plexus", "Heart", "Throat", "Third eye", "Crown",
    "Wurzel", "Sakral", "Solarplexus", "Herz", "Hals", "Stirn", "Krone",
    "Ready", "Strike a bowl or hum", " ct", "+", ".", ",", "Bereit", "Schale anschlagen", "Hz", "dB", "%", " s", " · ",
    "Settings", "Einstellungen", "Connections", "Anbindungen", "Camera", "Kamera", "Auto", "Colour", "Farbe", "°",
    "Local AI sound gate", "Lokaler KI-Klangfilter", "Off", "On", "Aus", "An", "Boxes", "Boxen", "Frame rate", "Bildrate", "fps",
    "Source", "Quelle", "Cloud AI", "Cloud-KI", "beta", "cloud stub", "Light", "Licht", "dark", "dunkel",
    "Video", "Demo scene", "Demo-Szene", "Mac camera", "Mac-Kamera", "No camera yet", "Noch keine Kamera", "Waiting for camera",
    "Warte auf Kamera", "Camera off", "Kamera aus", "Bowl", "Schale", "Other", "Anderes", "Quiet", "Still", "Tone",
    "Ton", "Nothing", "Nichts", "Boxes off", "Boxen aus", "Bowl C#", "Schale ABCDEFG#", "Tuning fork", "Stimmgabel",
    "Gong", "Drum", "Trommel", "Chimes", "Klangspiel", "Hand",
    "Screen lamp", "Bildschirm-Lampe", "localhost", "http://", "Brightness", "Helligkeit", "Sensitivity", "Empfindlichkeit", "Afterglow", "Nachklang",
    "Mapping", "Zuordnung", "Notes", "Noten", "Solfeggio", "Bowls", "Schalen", "Strike your", "bowl",
    "Hold the tone", "Ton halten", "learned", "angelernt", "/", "Flow", "Strike", "Fließen", "Anschlag", "Language", "Sprache", "English", "Deutsch",
    "Home Assistant", "Hue", "Wi-Fi", "WLAN", "Bluetooth",
    "not paired", "nicht gekoppelt", "Living room LED strip", "EN", "DE",
    "Hold: close ChakraV", "Halten: ChakraV schließen", "Closing ChakraV", "ChakraV wird geschlossen", "--:--",
]

objects: list = []


def add(kind, name=None, parent=None, **fields):
    o = {"type": kind}
    if parent:
        o["parent_name"] = parent
    else:
        o["parent"] = -1
    if name:
        o["name"] = name
    o.update(fields)
    objects.append(o)
    return name


def group(name, parent, x, y, w, h, hidden=True, **extra):
    """Container whose only job is visibility."""
    return add("container", name, parent, x=x, y=y, w=w, h=h, hidden=hidden, bind=name, bind_target="visible", **extra)


def text(name, parent, x, y, w, h, size, font, color, align="left", sample="", charset=CHARSET, **extra):
    fields = dict(x=x, y=y, w=w, h=h, text=sample, font_size=size, font=font, fg_color=color,
                  text_align=align, bind=name, font_charset_file=charset)
    fields.update(extra)
    return add("label", name, parent, **fields)


def icon(parent, x, y, size, code, color=WHITE, name=None):
    fields = dict(x=x, y=y, w=size, h=size, text=chr(code), font_size=size, font=ICONS, fg_color=color,
                  text_align="center", font_charset_file=ICON_CHARSET)
    return add("label", name, parent, **fields)


def radius_at(inset):
    """The corner radius of an edge running parallel to the screen's corner, `inset` px in (at least 8)."""
    return max(8, SCREEN_RADIUS - inset)


def option(name, parent, x, y, w, h, label, chosen=False, size=15):
    add("button", name, parent, x=x, y=y, w=w, h=h, radius=h // 2, bg_color=ON if chosen else OFF,
        bind=name, bind_target="color", callback=name)
    text(f"lbl_{name}", name, 0, (h - 20) // 2, w, 20, size, BOLD, WHITE, align="center", sample=label)


def frame_and_panel():
    # The light: the whole screen in the chakra's colour (faded and kicked by chakra_core.c). The
    # panel covers it except for the frame; two veils of growing darkness before the panel let the
    # frame glow softly inwards (no blur in GSP), so only one colour setter runs per tick.
    add("container", "bg", None, x=0, y=0, w=480, h=480, bg_color=IDLE_BG, bind="bg", bind_target="color")
    for inset, alpha in ((FRAME - 8, 80), (FRAME - 4, 165)):
        add("container", None, None, x=inset, y=inset, w=480 - 2 * inset, h=480 - 2 * inset,
            radius=radius_at(inset), bg_color="#000000", bg_opacity=alpha)
    add("container", None, None, x=FRAME, y=FRAME, w=480 - 2 * FRAME, h=480 - 2 * FRAME,
        radius=radius_at(FRAME), bg_color=PANEL)


def camera_view():
    # The view's own tile (seen while waiting or with the camera off), then the frame on top.
    add("container", None, None, x=CAM_X, y=CAM_Y, w=CAM_W, h=CAM_H, radius=SCREEN_RADIUS, bg_color=TILE)
    group("grp_cam_wait", None, CAM_X, CAM_Y, CAM_W, CAM_H, hidden=False)
    text("cam_icon", "grp_cam_wait", (CAM_W - 72) // 2, CAM_H // 2 - 52, 72, 72, 72, ICONS, FAINT, align="center",
         sample=chr(CAMERA), charset=ICON_CHARSET)
    text("cam_wait_text", "grp_cam_wait", 0, CAM_H // 2 + 34, CAM_W, 26, 17, BOLD, MUTED, align="center",
         sample="Waiting for camera", overflow="ellipsis")
    group("grp_cam_img", None, CAM_X, CAM_Y, CAM_W, CAM_H)
    add("image", "cam_img", "grp_cam_img", x=0, y=0, w=CAM_W, h=CAM_H, image="art/cam_placeholder.png",
        bind="cam_img", bind_target="resource", fit="contain")
    # Instrument marks: a box per slot, its geometry dynamic, its label pill at the top left inside.
    # The clip keeps a box and its pill inside the view; the ring below rounds their corners too.
    add("container", "box_clip", None, x=CAM_X, y=CAM_Y, w=CAM_W, h=CAM_H, bg_opacity=0, clip_children=True)
    for i in range(BOXES):
        # A dynamic w or h resizes a container's fill only (its border stays at the authored size),
        # so each edge is a thin fill of its own: top and left grow from the corner, right and
        # bottom move with the box's width and height.
        g = f"grp_box_{i}"
        add("container", g, "box_clip", hidden=True, bind=g, bind_target="visible",
            x={"default": 20 + 30 * i, "min": 0, "max": CAM_W, "property": "x"},
            y={"default": 40 + 24 * i, "min": 0, "max": CAM_H, "property": "y"}, w=CAM_W, h=CAM_H, bg_opacity=0)
        dyn_w = {"default": 140, "min": BOX_MIN, "max": CAM_W, "property": "width"}
        dyn_h = {"default": 110, "min": BOX_MIN, "max": CAM_H, "property": "height"}
        # Seen: these thin edges in grey. Played: the group grp_play_i below adds thick amber edges.
        # (GSP 1.5.1 refuses a bound colour on a container with a dynamic size: "Invalid GSB render
        # effects"; so the played look is a second layer that is shown or hidden.)
        add("container", f"box_t_{i}", g, x=0, y=0, w=dyn_w, h=EDGE, bg_color=SEEN)
        add("container", f"box_l_{i}", g, x=0, y=0, w=EDGE, h=dyn_h, bg_color=SEEN)
        add("container", f"box_r_{i}", g, x={"default": 137, "min": 0, "max": CAM_W, "property": "x"}, y=0,
            w=EDGE, h=dyn_h, bg_color=SEEN)
        add("container", f"box_b_{i}", g, x=0, y={"default": 107, "min": 0, "max": CAM_H, "property": "y"},
            w=dyn_w, h=EDGE, bg_color=SEEN)
        p = f"grp_play_{i}"
        add("container", p, g, x=0, y=0, w=CAM_W, h=CAM_H, bg_opacity=0, hidden=True, bind=p, bind_target="visible")
        add("container", f"play_t_{i}", p, x=0, y=0, w=dyn_w, h=PLAY_EDGE, bg_color=PLAYED)
        add("container", f"play_l_{i}", p, x=0, y=0, w=PLAY_EDGE, h=dyn_h, bg_color=PLAYED)
        add("container", f"play_r_{i}", p, x={"default": 137, "min": 0, "max": CAM_W, "property": "x"}, y=0,
            w=PLAY_EDGE, h=dyn_h, bg_color=PLAYED)
        add("container", f"play_b_{i}", p, x=0, y={"default": 107, "min": 0, "max": CAM_H, "property": "y"},
            w=dyn_w, h=PLAY_EDGE, bg_color=PLAYED)
        # The label pill: its width follows the text (chakra_core.c estimates it), at most PILL_MAX.
        # A box at the view's right edge moves its tag left, so the clip never cuts the label.
        tag = f"box_tag_{i}"
        # Only the name, in Inter Bold 10 px (owner 25.10.2026: "kürzere Beschreibungen ... kleinere
        # Schrift"): grey says seen, amber says played.
        add("container", tag, g, x={"default": 0, "min": -PILL_MAX, "max": 0, "property": "x"}, y=0,
            w=PILL_MAX, h=PILL_H, bg_opacity=0)
        add("container", f"box_pill_{i}", tag, x=0, y=0, w={"default": 44, "min": PILL_MIN, "max": PILL_MAX, "property": "width"},
            h=PILL_H, radius=PILL_H // 2, bg_color=SEEN)
        add("container", f"box_ppill_{i}", tag, x=0, y=0, hidden=True, bind=f"box_ppill_{i}", bind_target="visible",
            w={"default": 44, "min": PILL_MIN, "max": PILL_MAX, "property": "width"}, h=PILL_H, radius=PILL_H // 2,
            bg_color=PLAYED)
        text(f"box_label_{i}", tag, 7, 3, PILL_MAX - 10, 13, 10, BOLD, INK, sample="Bowl", overflow="ellipsis")
    band = SCREEN_RADIUS // 2  # DESIGN.md: >= 0.42 x the radius covers the corner
    add("container", None, None, x=CAM_X - band, y=CAM_Y - band, w=CAM_W + 2 * band, h=CAM_H + 2 * band,
        radius=SCREEN_RADIUS + band, bg_color="#00000000", border_color=PANEL, border_width=band)
    add("container", None, None, x=CAM_X - 2, y=CAM_Y - 2, w=CAM_W + 4, h=CAM_H + 4, radius=SCREEN_RADIUS + 2,
        bg_color="#00000000", border_color="#FFFFFF24", border_width=2)


def below_view():
    # Row 1: the chakra's name left, note and Hz right. Row 2: heard, seen, the small spectrum.
    # The 16:9 view left more height than the square: the rows are larger and further apart
    # (owner 26.10.2026, "ruhig und lesbar"), name 28 px, pills 34 px with 15 px text.
    y1 = CAM_Y + CAM_H + ROW1_GAP
    text("name_text", None, CONTENT_X, y1, 210, 36, 28, XBOLD, WHITE, sample="Ready", overflow="ellipsis")
    text("sub_text", None, CONTENT_X + 210, y1 + 9, CONTENT_W - 210, 22, 17, BOLD, MUTED, align="right",
         sample="Strike a bowl or hum", overflow="ellipsis")
    y2 = y1 + ROW2_GAP
    # Row 2: heard and seen at the left, the spectrum at the right (SPEC_W, from the row's right edge).
    for key, x, w, code, sample in (("heard", CONTENT_X, HEARD_W, WAVE, "Bowl"),
                                    ("seen", CONTENT_X + HEARD_W + PILL_GAP, SEEN_W, EYE, "Bowl")):
        add("container", None, None, x=x, y=y2, w=w, h=ROW_H, radius=ROW_H // 2, bg_color=TILE)
        add("container", f"{key}_dot", None, x=x + 12, y=y2 + 13, w=8, h=8, radius=4, bg_color=OFF,
            bind=f"{key}_dot", bind_target="color")
        icon(None, x + 26, y2 + 8, 18, code, color=MUTED)
        text(f"{key}_text", None, x + 48, y2 + 8, w - 56, 20, 15, BOLD, WHITE, sample=sample, overflow="ellipsis")
    # The spectrum as an analyser shows it: one band a semitone on a log axis, neutral white, the
    # octave of the last locked tone with three semitones either side (A2 to D4 for octave 3;
    # chakra_core.c moves the window); the locked tone's band lights in its note's colour. Under it
    # the seven chakra dots at their notes' bands, C .. B; the shown chakra's dot bright and larger.
    # Fixed colours with only heights, x and visible flags bound (GSP 1.5.1 refuses a bound colour
    # on a container with a dynamic size).
    pitch, bw, bh = BAR_PITCH, BAR_W, ROW_H - 8
    x0 = BAR_X0
    for b in range(BARS):
        x = x0 + b * pitch
        add("progress", f"bar_{b}", None, x=x, y=y2, w=bw, h=bh, vertical=True, min=0, max=100, value=0,
            bg_color="#FFFFFF1A", fg_color="#FFFFFFC8", radius=2)
        group(f"grp_hot_{b}", None, x, y2, bw, bh)
        add("progress", f"hot_{b}", f"grp_hot_{b}", x=0, y=0, w=bw, h=bh, vertical=True, min=0, max=100, value=0,
            bg_color="#00000000", fg_color=CHAKRA_RGB[NOTE_TO_CHAKRA[(BAND_NOTE0 + b) % 12]], radius=2)
    dy = y2 + bh + 5  # the dots' centre line
    for i in range(7):
        b = 12 - BAND_NOTE0 + DOT_NOTES[i]  # the note's band in the window
        add("container", f"dot_{i}", None, x=x0 + b * pitch + bw // 2 - 4, y=dy - 4, w=8, h=8, bg_opacity=0)
        add("container", None, f"dot_{i}", x=2, y=2, w=4, h=4, radius=2, bg_color=CHAKRA_RGB[i], bg_opacity=110)
        group(f"grp_dot_on_{i}", f"dot_{i}", 0, 0, 8, 8)
        add("container", None, f"grp_dot_on_{i}", x=1, y=1, w=6, h=6, radius=3, bg_color=CHAKRA_RGB[i])


def top_bar():
    y = FRAME
    add("button", "topbar", None, x=0, y=0, w=480 - FRAME - 56, h=FRAME + TOP_H, bg_opacity=0,
        events=[{"event": "press", "action": "call", "target_name": "hold_start"},
                {"event": "release", "action": "call", "target_name": "hold_end"}])
    add("label", None, None, x=FRAME + 14, y=y + 8, w=150, h=40, text="ChakraV", font_size=30, font=XBOLD,
        fg_color=WHITE)
    text("clock", None, 165, y + 10, 150, 36, 28, BOLD, WHITE, align="center", sample="12:00", overflow="clip")
    # The indicator dot, as iOS shows it (owner 25.10.2026, DESIGN.md): green while a camera or a video
    # feeds the view, orange while only the microphone listens, grey while nothing live does (the
    # drawn demo scene). The connection has no dot: it is the Wi-Fi glyph right of the dot
    # (chakra_core.c swaps it), then the gear, in ChakraA's spacing. Three fixed colours, each behind
    # a visible flag (chakra_core.c draw_mode).
    gx = 480 - FRAME - 54
    for key, rgb in (("cam", CAM_DOT), ("mic", MIC_DOT), ("idle", IDLE_DOT)):
        group(f"grp_{key}_dot", None, gx - 54, y + 21, 10, 10, hidden=key != "mic")
        add("container", None, f"grp_{key}_dot", x=0, y=0, w=10, h=10, radius=5, bg_color=rgb)
    text("wifi_icon", None, gx - 34, y + 13, 26, 26, 26, ICONS, MUTED, align="center", sample=chr(WIFI_SYNC),
         charset=ICON_CHARSET, overflow="clip")
    add("button", "gear", None, x=gx, y=y + 2, w=48, h=48, radius=24, bg_opacity=0, callback="gear")
    icon("gear", 7, 7, 34, COG)


def settings():
    """Over the panel below the top bar, three pages behind three tabs. Every label is bound: the
    language switches."""
    top = FRAME + TOP_H
    w = 480 - 2 * FRAME - 8      # content width inside the panel
    group("grp_settings", None, FRAME, top, 480 - 2 * FRAME, 480 - FRAME - top)
    add("container", None, "grp_settings", x=0, y=0, w=480 - 2 * FRAME, h=480 - FRAME - top,
        radius=radius_at(FRAME), bg_color=PANEL)
    tabs = [("tab_set", "Settings"), ("tab_conn", "Connections"), ("tab_cam", "Camera")]
    tw = (w - 2 * 6) // 3
    for j, (b, label) in enumerate(tabs):
        option(b, "grp_settings", 4 + j * (tw + 6), 4, tw, 34, label, chosen=j == 0, size=15)
    W = 480 - 2 * FRAME
    pw = W - 8     # a page row's width
    lx = 4         # a page row's left edge

    # Page 1, Settings: colour, brightness, detection, mapping, language, the AI sound gate.
    group("grp_page_set", "grp_settings", 0, 0, W, 480, hidden=False)
    option("col_auto", "grp_page_set", lx, 50, 74, 32, "Auto", chosen=True)
    d, gap = 32, (pw - 82 - 7 * 32) // 6
    for i in range(7):
        x = lx + 82 + i * (d + gap)
        group(f"grp_col_ring_{i}", "grp_page_set", x - 4, 46, d + 8, d + 8)
        add("container", None, f"grp_col_ring_{i}", x=0, y=0, w=d + 8, h=d + 8, radius=(d + 8) // 2,
            bg_opacity=0, border_color=WHITE, border_width=3)
        add("button", f"col_{i}", "grp_page_set", x=x, y=50, w=d, h=d, radius=d // 2, bg_color=CHAKRA_RGB[i],
            callback=f"col_{i}")
    for i, (key, label, lo, hi, val) in enumerate(SLIDERS):
        y = 92 + i * 48
        text(f"lbl_{key}", "grp_page_set", lx, y, 200, 20, 15, BOLD, WHITE, sample=label)
        if key == "hold":  # the after-glow row also chooses how fast colours follow
            text(f"val_{key}", "grp_page_set", lx + 104, y, 80, 20, 15, BOLD, MUTED, sample="1.5 s")
            for j, (b, lab) in enumerate([("react_flow", "Flow"), ("react_strike", "Strike")]):
                option(b, "grp_page_set", lx + pw - 156 + j * 80, y - 3, 76, 24, lab, chosen=j == 0, size=13)
        else:
            text(f"val_{key}", "grp_page_set", lx + pw - 156, y, 156, 20, 15, BOLD, MUTED, align="right", sample="60 %")
        if key == "hue":  # the chosen colour as a swatch beside the label
            add("container", "hue_swatch", "grp_page_set", x=lx + 96, y=y + 1, w=18, h=18, radius=9,
                bg_color="#FF0000", bind="hue_swatch", bind_target="color")
        add("slider", f"sl_{key}", "grp_page_set", x=lx, y=y + 21, w=pw, h=22, min=lo, max=hi, value=val,
            track_size=8, radius=11, bg_color=OFF, fg_color=WHITE, knob_color=WHITE, bind=f"sl_{key}",
            events=[{"event": "value", "action": "call", "target_name": f"sl_{key}"}])
    # Mapping left (notes, Solfeggio, the user's own bowls), language right. A tap on Bowls before any
    # are learned, or holding it, starts learning them.
    ws = [88, 92, 80, 58, 58]
    xs = [lx, lx + 92, lx + 188, lx + pw - 120, lx + pw - 58]
    for i, (b, label) in enumerate(OPTIONS):
        ev = ({"events": [{"event": "click", "action": "call", "target_name": b},
                          {"event": "long", "action": "call", "target_name": "bowls_learn"}]}
              if b == "map_bowls" else {"callback": b})
        add("button", b, "grp_page_set", x=xs[i], y=288, w=ws[i], h=32, radius=16,
            bg_color=ON if i in (0, 3) else OFF, bind=b, bind_target="color", **ev)
        text(f"lbl_{b}", b, 0, 6, ws[i], 20, 14, BOLD, WHITE, align="center",
             sample=label if label != "Notes" else "Notes 440")
    text("lbl_ai", "grp_page_set", lx, 337, 200, 20, 15, BOLD, WHITE, sample="Local AI sound gate", overflow="ellipsis")
    for j, (b, lab) in enumerate([("ai_off", "Off"), ("ai_on", "On")]):
        option(b, "grp_page_set", lx + pw - 156 + j * 80, 332, 76, 30, lab, chosen=j == 0)

    # Page 2, Connections: a row per lamp the platform knows (paired outside the app), ticked when it
    # follows the chakra; a lamp that is not paired is greyed and cannot be ticked. The screen lamp's
    # address stands large below, to be typed into a TV or laptop browser.
    group("grp_page_conn", "grp_settings", 0, 0, W, 480)
    for i in range(LAMPS):
        y = 50 + i * 50
        group(f"grp_lamp_{i}", "grp_page_conn", lx, y, pw, 44)
        row = f"lamp_{i}"
        add("button", row, f"grp_lamp_{i}", x=0, y=0, w=pw, h=44, radius=18, bg_color=TILE,
            bind=row, bind_target="color", callback=row)
        text(f"lamp_icon_{i}", row, 12, 10, 24, 24, 24, ICONS, WHITE, align="center", sample=chr(HA),
             charset=ICON_CHARSET)
        text(f"lamp_name_{i}", row, 48, 11, pw - 210, 22, 16, BOLD, WHITE, sample="Living room LED strip",
             overflow="ellipsis")
        text(f"lamp_info_{i}", row, pw - 160, 13, 120, 18, 13, MED, MUTED, align="right", sample="not paired",
             overflow="ellipsis")
        group(f"grp_check_{i}", row, pw - 34, 10, 24, 24)
        icon(f"grp_check_{i}", 0, 0, 24, CHECK)
        group(f"grp_veil_{i}", f"grp_lamp_{i}", 0, 0, pw, 44)
        add("container", None, f"grp_veil_{i}", x=0, y=0, w=pw, h=44, radius=18, bg_color=PANEL, bg_opacity=150)
    group("grp_url", "grp_page_conn", lx, 254, pw, 108)
    add("container", None, "grp_url", x=0, y=0, w=pw, h=108, radius=18, bg_color=TILE)
    icon("grp_url", 16, 14, 28, MONITOR)
    text("lbl_url", "grp_url", 56, 17, pw - 72, 24, 16, BOLD, MUTED, sample="Screen lamp", overflow="ellipsis")
    text("lamp_url", "grp_url", 12, 52, pw - 24, 44, 32, XBOLD, WHITE, align="center", sample="192.168.1.20:3310",
         overflow="ellipsis")

    # Page 3, Camera: on or off, boxes, the frame rate, the camera's light, the experimental Cloud AI
    # (a vision model with the user's own key, only on the Mac for now: tools/cloud_vision.py, a stub
    # that sends nothing in v0); the source as one quiet line with its glyph.
    group("grp_page_cam", "grp_settings", 0, 0, W, 480)
    rows = [("cam", "Camera", [("cam_off", "Off"), ("cam_on", "On")]),
            ("boxes", "Boxes", [("boxes_off", "Off"), ("boxes_on", "On")]),
            ("fps", "Frame rate", [("fps_1", "1"), ("fps_2", "2"), ("fps_4", "4")]),
            ("light", "Light", [("light_off", "Off"), ("light_on", "On"), ("light_auto", "Auto")]),
            ("cloud", "Cloud AI", [("cloud_off", "Off"), ("cloud_on", "On")])]
    step = 52
    for i, (key, label, opts) in enumerate(rows):
        y = 50 + i * step
        add("container", None, "grp_page_cam", x=lx, y=y, w=pw, h=step - 6, radius=18, bg_color=TILE)
        icon("grp_page_cam", lx + 14, y + 11, 24, {"cam": CAMERA, "boxes": 0xF0485, "fps": WAVE, "light": FLASH,
                                                     "cloud": CLOUD}[key], color=MUTED)
        text(f"lbl_{key}", "grp_page_cam", lx + 48, y + 13, 150, 20, 15, BOLD, WHITE, sample=label, overflow="ellipsis")
        bw = 62 if len(opts) == 2 else 54 if key == "light" else 48
        for j, (b, lab) in enumerate(opts):
            option(b, "grp_page_cam", lx + pw - 8 - len(opts) * (bw + 4) + 4 + j * (bw + 4), y + 8, bw, 30,
                   lab, chosen=(b in ("cam_on", "boxes_on", "fps_2", "light_auto", "cloud_off")), size=14)
    text("lbl_fps_unit", "grp_page_cam", lx + 48 + 92, 50 + 2 * step + 14, 40, 20, 13, MED, MUTED, sample="fps")
    # The light's state beside its label: "on", "off", "dark · on" (Auto saw a dark picture).
    text("light_state", "grp_page_cam", lx + 48 + 52, 50 + 3 * step + 14, 96, 18, 13, BOLD, ORANGE,
         sample="dark · on", overflow="ellipsis")
    text("lbl_cloud_beta", "grp_page_cam", lx + 48 + 76, 50 + 4 * step + 15, 90, 18, 12, BOLD, ORANGE, sample="beta")
    y = 50 + 5 * step + 8
    text("lbl_src", "grp_page_cam", lx + 4, y, 90, 20, 14, BOLD, MUTED, sample="Source")
    text("src_icon", "grp_page_cam", lx + 64, y - 1, 22, 22, 20, ICONS, MUTED, align="center", sample=chr(CAMERA),
         charset=ICON_CHARSET)
    text("cam_src", "grp_page_cam", lx + 92, y, pw - 96, 20, 14, BOLD, WHITE, align="right",
         sample="Video · SC101IOT v1.4 emulated", overflow="ellipsis")


def scene():
    frame_and_panel()
    camera_view()
    below_view()
    top_bar()
    settings()
    # Hold to close: the bar fills orange from the left over 3 s, over the frame's top and the top bar.
    group("grp_hold", None, 0, 0, 480, FRAME + TOP_H)
    add("progress", "hold_bar", "grp_hold", x=0, y=0, w=480, h=FRAME + TOP_H, min=0, max=1000, value=0,
        bg_color=SHADOW, fg_color=ORANGE, radius=0)
    text("hold_text", "grp_hold", 0, FRAME + 10, 480, 36, 24, XBOLD, INK, align="center",
         sample="Hold: close ChakraV", overflow="ellipsis")
    return {"screen": "chakra", "w": 480, "h": 480, "screen_bg": IDLE_BG, "font": MED,
            "default_font_size": 22, "swipe": False, "objects": objects}


def placeholder():
    """The camera image's compiled source: the view's tile colour at its exact size (never shown
    once a frame arrived; hidden until then)."""
    from PIL import Image  # only needed to (re)write the file
    out = HERE / "art/cam_placeholder.png"
    if out.is_file():
        with Image.open(out) as im:
            if im.size == (CAM_W, CAM_H):
                return
    out.parent.mkdir(exist_ok=True)
    Image.new("RGB", (CAM_W, CAM_H), TILE).save(out, optimize=True)


def main():
    placeholder()
    doc = scene()
    chars = set(" 0123456789:.,-–…·°%#×")
    chars.update(chr(c) for c in range(0x20, 0x7F))
    chars.update("ÄÖÜäöüß")
    for s in STRINGS:
        chars.update(s)
    (HERE / CHARSET).write_text("".join(sorted(chars)), encoding="utf-8")
    (HERE / ICON_CHARSET).write_text("".join(chr(c) for c in (COG, HA, BULB, WIFI, BT, CHECK, MONITOR, WIFI_OFF, WIFI_SYNC, WAVE, EYE,
                                                              CAMERA, CAMERA_OFF, 0xF0485, CLOUD, MIC, VIDEO, FLASH, MOVIE)),
                                     encoding="utf-8")
    (HERE / "main.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"main.json: {len(doc['objects'])} objects, frame {FRAME} px; charset.txt: {len(chars)} characters")


if __name__ == "__main__":
    main()
