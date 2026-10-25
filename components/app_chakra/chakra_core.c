// SPDX-License-Identifier: Apache-2.0
// Chakra app controller, see include/chakra_core.h. The scene is ui/main.json (make_scene.py);
// the gsp_chakra_* functions are generated from its names.
#include "chakra_core.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "bundle_gsp.h"

#define TICK_MS 40
#define FADE_FLOW 0.06f        // share of the way to the target colour per tick: about 1.6 s
#define FADE_STRIKE 0.35f      // about 0.3 s
#define FADE_AI 0.03f          // with the AI gate: about 3 s, the softest of the three
#define AI_HOLD_TICKS 50       // a bowl verdict lets the colour change for 2 s
#define GATE_ALIVE_TICKS 125   // no verdict for 5 s: the gate is gone and the detection leads alone again
#define KICK_DECAY 0.90f       // the strike kick fades to a tenth in about 0.9 s
#define KICK_WHITE 0.35f       // how far a full kick pushes the colour towards white
#define KICK_BRIGHT 40         // and the lamps' brightness up, in percent points
#define TUNE_STEP 0.25f        // the tuning ring follows a little slower than the reading
#define SUB_EVERY_TICKS 3      // the note line at most every 120 ms
#define HOLD_MS 3000
#define HOLD_STEP_MS 30
#define IDLE_RGB 0x17141Fu
#define ON_RGB 0x6E5ACFu       // a chosen option or a ticked lamp
#define OFF_RGB 0x3A3744u      // an option not chosen
#define ROW_RGB 0x2C2936u      // a lamp not ticked
#define LEARN_MS 1500          // a bowl must ring steadily this long to be learned
#define LEARN_CENTS 40.0f      // steady: within this of the running mean
#define HOP_MS (1000 * CHAKRA_HOP / CHAKRA_RATE)
#define DRAW_BUDGET_MS (TICK_MS / 2)  // optional drawing per tick, see spare()
#define SHADOW_SLOTS 256       // a power of two, about twice the scene's setters

/* Material Design Icons, UTF-8, as in make_scene.py: home-assistant, lightbulb, wifi, bluetooth, monitor. */
static const char *const KIND_ICON[] = {"\xf3\xb0\x9f\x90", "\xf3\xb0\x8c\xb5", "\xf3\xb0\x96\xa9", "\xf3\xb0\x82\xaf",
                                        "\xf3\xb0\x8d\xb9"};

/* Every word on the screen, English first (the default), German second. */
enum {
    S_READY, S_STRIKE, S_BRIGHT, S_SENS, S_HOLD, S_NOTES, S_NOT_PAIRED,
    S_KIND_HA, S_KIND_HUE, S_KIND_WIZ, S_KIND_BLE, S_KIND_SCREEN, S_HOLD_CLOSE, S_CLOSING, S_BOWLS, S_STRIKE_BOWL,
    S_HOLD_TONE, S_FLOW, S_STRIKE_MODE, S_SETTINGS, S_CONNECTIONS, S_AUTO, S_COLOUR, S_AI, S_OFF, S_ON,
    S_CAMERA, S_BOXES, S_FPS, S_SOURCE, S_WAITING, S_CAM_OFF, S_BOWL, S_OTHER, S_QUIET, S_TONE, S_NOTHING,
    S_BOXES_OFF, S_CLOUD, S_LIGHT, S_LIT, S_UNLIT, S_DARK, S_COUNT
};
static const char *const TEXT[2][S_COUNT] = {
    {"Ready", "Strike a bowl or hum", "Brightness", "Sensitivity", "Afterglow", "Notes", "not paired",
     "Home Assistant", "Hue", "Wi-Fi", "Bluetooth", "Screen lamp", "Hold: close ChakraV", "Closing ChakraV", "Bowls",
     "Strike your %s bowl", "hold the tone", "Flow", "Strike", "Settings", "Connections", "Auto", "Colour",
     "Local AI sound gate", "Off", "On", "Camera", "Boxes", "Frame rate", "Source", "Waiting for camera", "Camera off",
     "Bowl", "Other", "Quiet", "Tone", "Nothing", "Boxes off", "Cloud AI", "Light", "on", "off", "dark"},
    {"Bereit", "Schale anschlagen", "Helligkeit", "Empfindlichkeit", "Nachklang", "Noten",
     "nicht gekoppelt", "Home Assistant", "Hue", "WLAN", "Bluetooth", "Bildschirm-Lampe", "Halten: ChakraV schließen",
     "ChakraV wird geschlossen", "Schalen", "%s-Schale anschlagen", "Ton halten", "Fließen", "Anschlag",
     "Einstellungen", "Anbindungen", "Auto", "Farbe", "Lokaler KI-Klangfilter", "Aus", "An", "Kamera", "Boxen", "Bildrate",
     "Quelle", "Warte auf Kamera", "Kamera aus", "Schale", "Anderes", "Still", "Ton", "Nichts", "Boxen aus",
     "Cloud-KI", "Licht", "an", "aus", "dunkel"},
};

/* The detector's English labels in German; an unknown label is shown as it came. */
static const char *const LABEL_DE[][2] = {
    {"Singing bowl", "Klangschale"}, {"Tuning fork", "Stimmgabel"}, {"Drum", "Trommel"}, {"Chimes", "Klangspiel"},
};

#define SEEN_RGB 0x64D2FFu     // the seen pill's dot while a box is shown (box slot 0's colour)
#define HEARD_RGB 0x34C759u    // the heard pill's dot while a tone or a bowl sounds
#define HEARD_MS 1500          // an AI verdict older than this counts as nothing heard
#define BOX_EDGE 3             // ui/make_scene.py EDGE
#define BOX_MIN 16             // ui/make_scene.py BOX_MIN
#define PILL_MAX 150           // ui/make_scene.py PILL_MAX
#define FRAME_STALE_MS 5000    // no frame for this long: the view waits again, the mode mark shows the mic
/* The camera light's Auto (chakra_core_set_frame_luma): on after the picture's mean luma stayed
 * below LUMA_DARK for LIGHT_SWITCH_MS. The light brightens the picture itself, so it goes off again
 * only after LIGHT_MIN_ON_MS and once the luma is LUMA_BRIGHTER above what it was with the light
 * alone (measured LIGHT_BASE_MS after switching on): the room itself got brighter. */
#define LUMA_DARK 50
#define LUMA_BRIGHTER 30
#define LIGHT_SWITCH_MS 2000
#define LIGHT_MIN_ON_MS 10000
#define LIGHT_BASE_MS 1000
/* Material Design Icons, UTF-8: microphone, camera, video, movie (the demo scene). */
#define I_MIC "\xf3\xb0\x8d\xac"
#define I_CAMERA "\xf3\xb0\x84\x80"
#define I_VIDEO "\xf3\xb0\x95\xa7"
#define I_MOVIE "\xf3\xb0\x8e\x81"

/* The value a setter last sent; see put() below. */
typedef struct {
    uintptr_t setter;  // 0: a free slot
    uint64_t value;    // the value, or a hash of the text
} shadow_t;

struct chakra_core {
    esp_gsp_handle_t ui;
    chakra_core_config_t cfg;
    chakra_settings_t s;
    chakra_lamp_t lamps[CHAKRA_LAMPS];
    int lamp_count;
    void *timer;
    void *hold_timer;
    uint32_t hold_ms;
    uint32_t hold_since;  // now_ms() when the hold began
    uint32_t tick_start;  // now_ms() when this tick began
    bool hold_shown;
    bool settings_open;
    int page;             // settings page: 0 Settings, 1 Connections
    int shown;            // chakra on screen, -1 idle
    bool sounding;        // a gated-in tone this hop
    float cur[3];         // background now, 0..255
    uint32_t target_rgb;
    uint32_t drawn_rgb;
    float tune;           // tuning ring now, 0..100
    int tune_drawn;
    uint8_t bars[CHAKRA_BARS];       // the spectrum on screen
    uint8_t bars_want[CHAKRA_BARS];  // the last reading's spectrum
    int bar_next;                    // the bar the next spectrum pass starts with
    uint32_t ticks, sub_tick;
    uint32_t bowl_tick;   // the tick of the AI gate's last bowl verdict (settings.ai)
    uint32_t gate_tick;   // the tick of the gate's last verdict of any kind
    bool gate_heard;      // whether the gate has spoken at all: without it the setting changes nothing
    bool bowl_heard;      // whether there was one at all
    float kick;           // the strike kick now, 1 at a strike, decaying to 0
    int last_shown;       // the last chakra that had a colour: a kick in silence lights that one
    chakra_reading_t last;
    int learn;            // bowl being learned 0..6, -1 when not learning
    uint32_t learn_ms;
    float learn_sum, learn_mean, learn_prev;
    int learn_n;
    bool learn_gap;       // after a capture: wait for silence or another bowl
    int heard_kind;       // the AI gate's last verdict (CHAKRA_SOUND_*), whatever the AI setting
    uint32_t heard_ms;    // now() of that verdict
    bool picture;         // a camera frame is on screen
    struct {
        bool on;
        char label[40];
        float conf;
        int x, y, w, h;   // pixels inside the view
    } box[CHAKRA_BOXES];
    char cam_src[48];
    int src_kind;         // CHAKRA_SOURCE_*
    uint32_t frame_ms;    // now() of the last frame
    int luma;             // the last frame's mean luma, -1 unknown
    bool dark;            // the picture is dark (Auto's view of it)
    bool auto_lit;        // Auto has the light on
    bool lit;             // the light as last told to the platform
    bool lit_told;        // whether it was told at all
    uint32_t dark_since, bright_since, lit_at;
    int lit_base;         // the luma with the light alone, -1 until measured
    bool boxes_dirty;     // set_box or clear_boxes since the last tick
    esp_gsp_err_t last_error;
    shadow_t shadow[SHADOW_SLOTS];
};

static void err(struct chakra_core *c, esp_gsp_err_t e)
{
    if (e != ESP_GSP_OK) {
        c->last_error = e;
    }
}

// ------------------------------------------------------------------ setters --

/* Every setter is one round trip to the screen. In the simulator that is one frame of its host,
 * about 20 ms (measured 25.10.2026), so a tick that drew the fade, the tuning ring, the note line
 * and 16 bars took 100 to 500 ms instead of 40, and the hold-to-close gesture fell behind. The
 * value each setter sent last is kept, and an unchanged value is not sent again; put() picks the
 * right one of these by the setter's type. */
typedef esp_gsp_err_t (*set_bool_t)(esp_gsp_handle_t, bool);
typedef esp_gsp_err_t (*set_i32_t)(esp_gsp_handle_t, int32_t);
typedef esp_gsp_err_t (*set_rgb_t)(esp_gsp_handle_t, uint32_t);
typedef esp_gsp_err_t (*set_text_t)(esp_gsp_handle_t, const char *);

/* The setter's slot, or NULL when the table is full (then it always sends). */
static shadow_t *shadow_of(struct chakra_core *c, uintptr_t setter)
{
    size_t i = (size_t)(((uint64_t)setter * 0x9E3779B97F4A7C15ull) >> 40) & (SHADOW_SLOTS - 1);
    for (int n = 0; n < SHADOW_SLOTS; ++n, i = (i + 1) & (SHADOW_SLOTS - 1)) {
        if (c->shadow[i].setter == setter || c->shadow[i].setter == 0) {
            return &c->shadow[i];
        }
    }
    return NULL;
}

static bool unchanged(const shadow_t *s, uint64_t value)
{
    return s && s->setter && s->value == value;
}

/* Only a value the screen took is remembered; after an error the next call sends again. */
static void remember(struct chakra_core *c, shadow_t *s, uintptr_t setter, uint64_t value, esp_gsp_err_t e)
{
    err(c, e);
    if (s && e == ESP_GSP_OK) {
        s->setter = setter;
        s->value = value;
    }
}

static void put_bool(struct chakra_core *c, set_bool_t set, bool v)
{
    shadow_t *s = shadow_of(c, (uintptr_t)set);
    if (!unchanged(s, v)) {
        remember(c, s, (uintptr_t)set, v, set(c->ui, v));
    }
}

static void put_i32(struct chakra_core *c, set_i32_t set, int32_t v)
{
    shadow_t *s = shadow_of(c, (uintptr_t)set);
    if (!unchanged(s, (uint32_t)v)) {
        remember(c, s, (uintptr_t)set, (uint32_t)v, set(c->ui, v));
    }
}

static void put_rgb(struct chakra_core *c, set_rgb_t set, uint32_t v)
{
    shadow_t *s = shadow_of(c, (uintptr_t)set);
    if (!unchanged(s, v)) {
        remember(c, s, (uintptr_t)set, v, set(c->ui, v));
    }
}

static void put_text(struct chakra_core *c, set_text_t set, const char *text)
{
    uint64_t h = 0xCBF29CE484222325ull;  // FNV-1a
    for (const char *p = text; p && *p; ++p) {
        h = (h ^ (uint8_t)*p) * 0x100000001B3ull;
    }
    shadow_t *s = shadow_of(c, (uintptr_t)set);
    if (!unchanged(s, h)) {
        remember(c, s, (uintptr_t)set, h, set(c->ui, text));
    }
}

#define put(c, setter, v) _Generic((setter), set_bool_t: put_bool, set_i32_t: put_i32, set_rgb_t: put_rgb, \
                                   set_text_t: put_text)(c, setter, v)

static uint32_t now(const struct chakra_core *c)
{
    return c->cfg.now_ms ? c->cfg.now_ms(c->cfg.ctx) : 0;
}

/* Time left in this tick for drawing that can wait (the fade, the tuning ring, the note line,
 * the spectrum): what is skipped now is drawn with a later tick's values. On the board every
 * setter is quick and nothing waits; in the simulator about one such setter fits a tick. */
static bool spare(const struct chakra_core *c)
{
    return !c->cfg.now_ms || now(c) - c->tick_start < DRAW_BUDGET_MS;
}

static const char *T(const struct chakra_core *c, int id)
{
    return TEXT[c->s.lang == CHAKRA_LANG_DE ? 1 : 0][id];
}

static void haptic(struct chakra_core *c, int pattern)
{
    if (c->cfg.on_haptic) {
        c->cfg.on_haptic(pattern, c->cfg.ctx);
    }
}

void chakra_settings_defaults(chakra_settings_t *s)
{
    memset(s, 0, sizeof(*s));
    s->lamps = 0x01;
    s->brightness = 60;
    s->sensitivity = 8;
    s->hold_ds = 15;
    s->map = CHAKRA_MAP_NOTES;
    s->lang = CHAKRA_LANG_EN;
    s->a4 = 440;
    s->reaction = CHAKRA_FLOW;
    s->cam_on = 1;
    s->cam_boxes = 1;
    s->cam_fps = 2;
    s->cam_light = CHAKRA_CAM_LIGHT_AUTO;
}

void chakra_settings_detect(const chakra_settings_t *s, chakra_detect_config_t *out)
{
    chakra_detect_defaults(out);
    out->threshold_db = -30.0f - 5.0f * (float)s->sensitivity;
    out->hold_ms = (uint32_t)s->hold_ds * 100u;
    out->map = s->map == CHAKRA_MAP_SOLFEGGIO || s->map == CHAKRA_MAP_BOWLS ? (chakra_map_t)s->map : CHAKRA_MAP_NOTES;
    memcpy(out->bowl_hz, s->bowl_hz, sizeof(out->bowl_hz));
    out->a4_hz = s->a4 == 432 ? 432.0f : 440.0f;
    out->lock_ms = s->reaction == CHAKRA_STRIKE ? 128u : 384u;
    out->switch_ms = s->reaction == CHAKRA_STRIKE ? 256u : 1500u;
}

// ------------------------------------------------------------------ the light's colour --

/* A hue 0..359 at full saturation and value, as 0xRRGGBB. */
static uint32_t hue_rgb(int hue)
{
    hue = ((hue % 360) + 360) % 360;
    const int x = (hue % 60) * 255 / 60, seg = hue / 60;
    const int r[6] = {255, 255 - x, 0, 0, x, 255}, g[6] = {x, 255, 255, 255 - x, 0, 0}, b[6] = {0, 0, x, 255, 255, 255 - x};
    return ((uint32_t)r[seg] << 16) | ((uint32_t)g[seg] << 8) | (uint32_t)b[seg];
}

/* The fixed colour, or 0 when the colour follows the chakra (Auto). */
static uint32_t fixed_rgb(const struct chakra_core *c)
{
    if (c->s.color_mode == CHAKRA_COLOR_CHAKRA && chakra_info(c->s.color_value)) {
        return chakra_info(c->s.color_value)->rgb;
    }
    return c->s.color_mode == CHAKRA_COLOR_HUE ? hue_rgb(c->s.color_value) : 0;
}

// ------------------------------------------------------------------ drawing --

/* The name below the camera view and the frame's target colour (the symbol, the dots and the
 * tuning ring of the chakra app have no place on this screen: the frame and the view carry it). */
static void draw_chakra(struct chakra_core *c, int chakra)
{
    const chakra_info_t *info = chakra_info(chakra);
    const char *name = !info ? T(c, S_READY) : c->s.lang == CHAKRA_LANG_DE ? info->german : info->english;
    put(c, gsp_chakra_name_text_set_text, name);
    if (!info) {
        put(c, gsp_chakra_sub_text_set_text, T(c, S_STRIKE));
    }
    const uint32_t fixed = fixed_rgb(c);
    c->target_rgb = fixed ? fixed : info ? info->rgb : IDLE_RGB;
}

/* The note line, as a tuner shows it: "F#3 · 171.4 Hz" while the tone sounds (no cents: the line
 * shares its row with the name). */
static void draw_sub(struct chakra_core *c)
{
    if (!chakra_info(c->shown)) {
        return;
    }
    const chakra_reading_t *r = &c->last;
    const int tenths = (int)(r->freq_hz * 10.0f + 0.5f);
    char line[96];
    snprintf(line, sizeof(line), c->s.lang == CHAKRA_LANG_DE ? "%s%d · %d,%d Hz" : "%s%d · %d.%d Hz",
             chakra_note_name(r->note), r->octave, tenths / 10, tenths % 10);
    put(c, gsp_chakra_sub_text_set_text, line);
}

#define VIEW_BARS 8  // ui/make_scene.py BARS: the detection's 16 bands in pairs

static void draw_bars(struct chakra_core *c)
{
    static esp_gsp_err_t (*const set[VIEW_BARS])(esp_gsp_handle_t, int32_t) = {
        gsp_chakra_bar_0_set_value, gsp_chakra_bar_1_set_value, gsp_chakra_bar_2_set_value,
        gsp_chakra_bar_3_set_value, gsp_chakra_bar_4_set_value, gsp_chakra_bar_5_set_value,
        gsp_chakra_bar_6_set_value, gsp_chakra_bar_7_set_value};
    uint8_t bars[VIEW_BARS];
    for (int b = 0; b < VIEW_BARS; ++b) {
        const uint8_t x = c->bars_want[2 * b], y = c->bars_want[2 * b + 1];
        bars[b] = x > y ? x : y;
    }
    for (int k = 0; k < VIEW_BARS && spare(c); ++k) {
        const int b = (c->bar_next + k) % VIEW_BARS;
        const int d = (int)bars[b] - (int)c->bars[b];
        if (d >= 2 || d <= -2 || (bars[b] == 0 && c->bars[b] != 0)) {
            c->bars[b] = bars[b];
            put(c, set[b], bars[b]);
            c->bar_next = (b + 1) % VIEW_BARS;
        }
    }
}

// ------------------------------------------------------------------ camera, boxes, pills --

static const char *label_text(const struct chakra_core *c, const char *label)
{
    if (c->s.lang == CHAKRA_LANG_DE) {
        for (size_t i = 0; i < sizeof(LABEL_DE) / sizeof(LABEL_DE[0]); ++i) {
            if (strcmp(label, LABEL_DE[i][0]) == 0) {
                return LABEL_DE[i][1];
            }
        }
    }
    return label;
}

/* The view: the last frame, or its tile with an icon and a word (waiting, or off). */
static void draw_view(struct chakra_core *c)
{
    const bool live = c->s.cam_on && c->picture;
    put(c, gsp_chakra_grp_cam_img_set_visible, live);
    put(c, gsp_chakra_grp_cam_wait_set_visible, !live);
    put(c, gsp_chakra_cam_icon_set_text, c->s.cam_on ? "\xf3\xb0\x84\x80" : "\xf3\xb0\x97\x9f");  // camera, camera-off
    put(c, gsp_chakra_cam_wait_text_set_text, T(c, c->s.cam_on ? S_WAITING : S_CAM_OFF));
}

/* The seen pill: the most certain mark, or why there is none. */
static void draw_seen(struct chakra_core *c)
{
    int best = -1;
    for (int i = 0; i < CHAKRA_BOXES; ++i) {
        if (c->box[i].on && (best < 0 || c->box[i].conf > c->box[best].conf)) {
            best = i;
        }
    }
    const char *text = !c->s.cam_on ? T(c, S_CAM_OFF) : !c->s.cam_boxes ? T(c, S_BOXES_OFF)
                       : best < 0   ? T(c, S_NOTHING) : label_text(c, c->box[best].label);
    put(c, gsp_chakra_seen_text_set_text, text);
    put(c, gsp_chakra_seen_dot_set_color_rgb888, best >= 0 && c->s.cam_on && c->s.cam_boxes ? SEEN_RGB : OFF_RGB);
}

static void draw_boxes(struct chakra_core *c)
{
    static esp_gsp_err_t (*const vis[CHAKRA_BOXES])(esp_gsp_handle_t, bool) = {
        gsp_chakra_grp_box_0_set_visible, gsp_chakra_grp_box_1_set_visible, gsp_chakra_grp_box_2_set_visible,
        gsp_chakra_grp_box_3_set_visible};
    const bool show = c->s.cam_on && c->s.cam_boxes && c->picture;
    for (int i = 0; i < CHAKRA_BOXES; ++i) {
        if (!show || !c->box[i].on) {
            put(c, vis[i], false);  // a box is shown by draw_box_geometry, once it stands where it belongs
        }
    }
    draw_seen(c);
}

/* A box's eight edge setters and its label. Every setter is a round trip in the simulator (about
 * 20 ms), so this runs in the tick within the drawing budget: what is skipped now is drawn with a
 * later tick's values, and unchanged values cost nothing (put). */
static void draw_box_geometry(struct chakra_core *c)
{
#define BOX_SETTERS(i)                                                                                      \
    {gsp_chakra_grp_box_##i##_set_x, gsp_chakra_grp_box_##i##_set_y, gsp_chakra_box_t_##i##_set_width,        \
     gsp_chakra_box_l_##i##_set_height, gsp_chakra_box_r_##i##_set_x, gsp_chakra_box_r_##i##_set_height,      \
     gsp_chakra_box_b_##i##_set_y, gsp_chakra_box_b_##i##_set_width}
    static esp_gsp_err_t (*const set[CHAKRA_BOXES][8])(esp_gsp_handle_t, int32_t) = {
        BOX_SETTERS(0), BOX_SETTERS(1), BOX_SETTERS(2), BOX_SETTERS(3)};
#undef BOX_SETTERS
    static esp_gsp_err_t (*const set_label[CHAKRA_BOXES])(esp_gsp_handle_t, const char *) = {
        gsp_chakra_box_label_0_set_text, gsp_chakra_box_label_1_set_text, gsp_chakra_box_label_2_set_text,
        gsp_chakra_box_label_3_set_text};
    static esp_gsp_err_t (*const vis[CHAKRA_BOXES])(esp_gsp_handle_t, bool) = {
        gsp_chakra_grp_box_0_set_visible, gsp_chakra_grp_box_1_set_visible, gsp_chakra_grp_box_2_set_visible,
        gsp_chakra_grp_box_3_set_visible};
    static esp_gsp_err_t (*const set_tag[CHAKRA_BOXES])(esp_gsp_handle_t, int32_t) = {
        gsp_chakra_box_tag_0_set_x, gsp_chakra_box_tag_1_set_x, gsp_chakra_box_tag_2_set_x, gsp_chakra_box_tag_3_set_x};
    static esp_gsp_err_t (*const set_pill[CHAKRA_BOXES])(esp_gsp_handle_t, int32_t) = {
        gsp_chakra_box_pill_0_set_width, gsp_chakra_box_pill_1_set_width, gsp_chakra_box_pill_2_set_width,
        gsp_chakra_box_pill_3_set_width};
    if (!c->s.cam_on || !c->s.cam_boxes || !c->picture) {
        return;
    }
    for (int i = 0; i < CHAKRA_BOXES; ++i) {
        if (!c->box[i].on) {
            continue;
        }
        const int x = c->box[i].x, y = c->box[i].y, w = c->box[i].w, h = c->box[i].h;
        const int32_t v[8] = {x, y, w, h, w - BOX_EDGE, h, h - BOX_EDGE, w};
        for (int k = 0; k < 8; ++k) {
            if (!spare(c)) {
                return;
            }
            put(c, set[i][k], v[k]);
        }
        if (!spare(c)) {
            return;
        }
        char text[64];
        const int pct = (int)(c->box[i].conf * 100.0f + 0.5f);
        snprintf(text, sizeof(text), "%s %d %%", label_text(c, c->box[i].label), pct < 0 ? 0 : pct > 100 ? 100 : pct);
        put(c, set_label[i], text);
        if (!spare(c)) {
            return;
        }
        int chars = 0;  // Inter Bold 12 px: about 6.6 px a character, plus the pill's padding
        for (const char *p = text; *p; ++p) {
            chars += ((uint8_t)*p & 0xC0) != 0x80;
        }
        int pill = 18 + chars * 66 / 10;
        pill = pill < 40 ? 40 : pill > PILL_MAX ? PILL_MAX : pill;
        put(c, set_pill[i], pill);
        put(c, set_tag[i], x + pill > CHAKRA_CAM_W ? CHAKRA_CAM_W - (x + pill) : 0);
        put(c, vis[i], true);
    }
}

/* The heard pill: with the AI gate the last verdict (bowl, other, quiet), without it the detection
 * (a tone or quiet). */
static void draw_heard(struct chakra_core *c)
{
    int id = c->sounding ? S_TONE : S_QUIET;
    const bool fresh = c->heard_ms && now(c) - c->heard_ms < HEARD_MS;
    if (c->s.ai && fresh) {
        id = c->heard_kind == CHAKRA_SOUND_BOWL ? S_BOWL : c->heard_kind == CHAKRA_SOUND_OTHER ? S_OTHER : S_QUIET;
    }
    put(c, gsp_chakra_heard_text_set_text, T(c, id));
    put(c, gsp_chakra_heard_dot_set_color_rgb888, id == S_TONE || id == S_BOWL ? HEARD_RGB
                                                   : id == S_OTHER                ? 0xFF9F0Au
                                                                                  : OFF_RGB);
}

static void light(struct chakra_core *c);

/* Background towards the chakra's colour, tuning ring towards how well the tone sits. */
static void animate(struct chakra_core *c)
{
    const float t[3] = {(float)((c->target_rgb >> 16) & 0xFF), (float)((c->target_rgb >> 8) & 0xFF),
                        (float)(c->target_rgb & 0xFF)};
    uint32_t rgb = 0;
    for (int i = 0; i < 3; ++i) {
        const float d = t[i] - c->cur[i];
        const float fade = c->s.ai ? FADE_AI : c->s.reaction == CHAKRA_STRIKE ? FADE_STRIKE : FADE_FLOW;
        c->cur[i] = (d > -1.0f && d < 1.0f) ? t[i] : c->cur[i] + d * fade;
        const float shown = c->cur[i] + (255.0f - c->cur[i]) * KICK_WHITE * c->kick;  // a strike: towards white
        rgb = (rgb << 8) | (uint32_t)(shown + 0.5f);
    }
    if (c->kick > 0.0f) {
        c->kick = c->kick < 0.02f ? 0.0f : c->kick * KICK_DECAY;
        if (c->ticks % 3 == 0 || c->kick == 0.0f) {
            light(c);  // the lamps take the kick too, at most every third tick
        }
    }
    if (rgb != c->drawn_rgb && spare(c)) {
        c->drawn_rgb = rgb;
        put(c, gsp_chakra_bg_set_color_rgb888, rgb);  // the frame around the screen
    }
}

/* Words that only change with the language. */
static void draw_labels(struct chakra_core *c)
{
    put(c, gsp_chakra_lbl_tab_set_set_text, T(c, S_SETTINGS));
    put(c, gsp_chakra_lbl_tab_conn_set_text, T(c, S_CONNECTIONS));
    put(c, gsp_chakra_lbl_col_auto_set_text, T(c, S_AUTO));
    put(c, gsp_chakra_lbl_hue_set_text, T(c, S_COLOUR));
    put(c, gsp_chakra_lbl_url_set_text, T(c, S_KIND_SCREEN));
    put(c, gsp_chakra_lbl_bright_set_text, T(c, S_BRIGHT));
    put(c, gsp_chakra_lbl_sens_set_text, T(c, S_SENS));
    put(c, gsp_chakra_lbl_hold_set_text, T(c, S_HOLD));
    char notes[24];
    snprintf(notes, sizeof(notes), "%s %d", T(c, S_NOTES), c->s.a4 == 432 ? 432 : 440);
    put(c, gsp_chakra_lbl_map_notes_set_text, notes);
    put(c, gsp_chakra_lbl_map_bowls_set_text, T(c, S_BOWLS));
    put(c, gsp_chakra_lbl_react_flow_set_text, T(c, S_FLOW));
    put(c, gsp_chakra_lbl_react_strike_set_text, T(c, S_STRIKE_MODE));
    put(c, gsp_chakra_lbl_ai_set_text, T(c, S_AI));
    put(c, gsp_chakra_lbl_ai_off_set_text, T(c, S_OFF));
    put(c, gsp_chakra_lbl_ai_on_set_text, T(c, S_ON));
    put(c, gsp_chakra_lbl_tab_cam_set_text, T(c, S_CAMERA));
    put(c, gsp_chakra_lbl_cam_set_text, T(c, S_CAMERA));
    put(c, gsp_chakra_lbl_cam_off_set_text, T(c, S_OFF));
    put(c, gsp_chakra_lbl_cam_on_set_text, T(c, S_ON));
    put(c, gsp_chakra_lbl_boxes_set_text, T(c, S_BOXES));
    put(c, gsp_chakra_lbl_boxes_off_set_text, T(c, S_OFF));
    put(c, gsp_chakra_lbl_boxes_on_set_text, T(c, S_ON));
    put(c, gsp_chakra_lbl_fps_set_text, T(c, S_FPS));
    put(c, gsp_chakra_lbl_src_set_text, T(c, S_SOURCE));
    put(c, gsp_chakra_lbl_cloud_set_text, T(c, S_CLOUD));
    put(c, gsp_chakra_lbl_light_set_text, T(c, S_LIGHT));
    put(c, gsp_chakra_lbl_light_off_set_text, T(c, S_OFF));
    put(c, gsp_chakra_lbl_light_on_set_text, T(c, S_ON));
    put(c, gsp_chakra_lbl_light_auto_set_text, T(c, S_AUTO));
    put(c, gsp_chakra_lbl_cloud_off_set_text, T(c, S_OFF));
    put(c, gsp_chakra_lbl_cloud_on_set_text, T(c, S_ON));
}

static void draw_lamps(struct chakra_core *c)
{
    static esp_gsp_err_t (*const row_vis[CHAKRA_LAMPS])(esp_gsp_handle_t, bool) = {
        gsp_chakra_grp_lamp_0_set_visible, gsp_chakra_grp_lamp_1_set_visible, gsp_chakra_grp_lamp_2_set_visible,
        gsp_chakra_grp_lamp_3_set_visible};
    static esp_gsp_err_t (*const row_rgb[CHAKRA_LAMPS])(esp_gsp_handle_t, uint32_t) = {
        gsp_chakra_lamp_0_set_color_rgb888, gsp_chakra_lamp_1_set_color_rgb888, gsp_chakra_lamp_2_set_color_rgb888,
        gsp_chakra_lamp_3_set_color_rgb888};
    static esp_gsp_err_t (*const icon[CHAKRA_LAMPS])(esp_gsp_handle_t, const char *) = {
        gsp_chakra_lamp_icon_0_set_text, gsp_chakra_lamp_icon_1_set_text, gsp_chakra_lamp_icon_2_set_text,
        gsp_chakra_lamp_icon_3_set_text};
    static esp_gsp_err_t (*const name[CHAKRA_LAMPS])(esp_gsp_handle_t, const char *) = {
        gsp_chakra_lamp_name_0_set_text, gsp_chakra_lamp_name_1_set_text, gsp_chakra_lamp_name_2_set_text,
        gsp_chakra_lamp_name_3_set_text};
    static esp_gsp_err_t (*const info[CHAKRA_LAMPS])(esp_gsp_handle_t, const char *) = {
        gsp_chakra_lamp_info_0_set_text, gsp_chakra_lamp_info_1_set_text, gsp_chakra_lamp_info_2_set_text,
        gsp_chakra_lamp_info_3_set_text};
    static esp_gsp_err_t (*const check[CHAKRA_LAMPS])(esp_gsp_handle_t, bool) = {
        gsp_chakra_grp_check_0_set_visible, gsp_chakra_grp_check_1_set_visible, gsp_chakra_grp_check_2_set_visible,
        gsp_chakra_grp_check_3_set_visible};
    static esp_gsp_err_t (*const veil[CHAKRA_LAMPS])(esp_gsp_handle_t, bool) = {
        gsp_chakra_grp_veil_0_set_visible, gsp_chakra_grp_veil_1_set_visible, gsp_chakra_grp_veil_2_set_visible,
        gsp_chakra_grp_veil_3_set_visible};
    const char *url = NULL;
    for (int i = 0; i < CHAKRA_LAMPS; ++i) {
        const bool used = i < c->lamp_count;
        put(c, row_vis[i], used);
        if (!used) {
            continue;
        }
        const chakra_lamp_t *l = &c->lamps[i];
        const bool on = l->paired && (c->s.lamps & (1u << i));
        put(c, row_rgb[i], on ? ON_RGB : ROW_RGB);
        put(c, icon[i], KIND_ICON[l->kind]);
        put(c, name[i], l->name[0] ? l->name : T(c, S_KIND_HA + (int)l->kind));
        /* The screen lamp's row names itself; its address stands large in the card below. */
        put(c, info[i], !l->paired ? T(c, S_NOT_PAIRED) : l->kind == CHAKRA_LAMP_SCREEN ? "" : T(c, S_KIND_HA + (int)l->kind));
        put(c, check[i], on);
        put(c, veil[i], !l->paired);
        if (l->kind == CHAKRA_LAMP_SCREEN && l->paired && l->url[0] && !url) {
            url = l->url;
        }
    }
    put(c, gsp_chakra_grp_url_set_visible, url != NULL);
    put(c, gsp_chakra_lamp_url_set_text, url ? url : "");
}

/* The tabs and the page they show. */
static void draw_page(struct chakra_core *c)
{
    put(c, gsp_chakra_tab_set_set_color_rgb888, c->page == 0 ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_tab_conn_set_color_rgb888, c->page == 1 ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_tab_cam_set_color_rgb888, c->page == 2 ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_grp_page_set_set_visible, c->page == 0);
    put(c, gsp_chakra_grp_page_conn_set_visible, c->page == 1);
    put(c, gsp_chakra_grp_page_cam_set_visible, c->page == 2);
}

/* Beside the gear: a microphone while only sound is used, the source's glyph while frames come. */
static void draw_mode(struct chakra_core *c)
{
    const char *glyph = I_MIC;
    if (c->s.cam_on && c->picture) {
        glyph = c->src_kind == CHAKRA_SOURCE_VIDEO ? I_VIDEO : c->src_kind == CHAKRA_SOURCE_DEMO ? I_MOVIE : I_CAMERA;
    }
    put(c, gsp_chakra_mode_icon_set_text, glyph);
}

/* The light's state beside its label: "on", "off", "dark · on". */
static void draw_light_state(struct chakra_core *c)
{
    char text[40];
    if (c->dark && c->s.cam_on) {
        snprintf(text, sizeof(text), "%s · %s", T(c, S_DARK), T(c, c->lit ? S_LIT : S_UNLIT));
    } else {
        snprintf(text, sizeof(text), "%s", T(c, c->lit ? S_LIT : S_UNLIT));
    }
    put(c, gsp_chakra_light_state_set_text, text);
}

/* Page 3: camera, boxes, frame rate, light, Cloud AI, source. */
static void draw_camera_page(struct chakra_core *c)
{
    put(c, gsp_chakra_light_off_set_color_rgb888, c->s.cam_light == CHAKRA_CAM_LIGHT_OFF ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_light_on_set_color_rgb888, c->s.cam_light == CHAKRA_CAM_LIGHT_ON ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_light_auto_set_color_rgb888, c->s.cam_light == CHAKRA_CAM_LIGHT_AUTO ? ON_RGB : OFF_RGB);
    draw_light_state(c);
    put(c, gsp_chakra_src_icon_set_text, c->src_kind == CHAKRA_SOURCE_VIDEO  ? I_VIDEO
                                         : c->src_kind == CHAKRA_SOURCE_DEMO ? I_MOVIE
                                                                             : I_CAMERA);
    put(c, gsp_chakra_cam_off_set_color_rgb888, c->s.cam_on ? OFF_RGB : ON_RGB);
    put(c, gsp_chakra_cam_on_set_color_rgb888, c->s.cam_on ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_boxes_off_set_color_rgb888, c->s.cam_boxes ? OFF_RGB : ON_RGB);
    put(c, gsp_chakra_boxes_on_set_color_rgb888, c->s.cam_boxes ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_fps_1_set_color_rgb888, c->s.cam_fps == 1 ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_fps_2_set_color_rgb888, c->s.cam_fps == 2 ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_fps_4_set_color_rgb888, c->s.cam_fps == 4 ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_cloud_off_set_color_rgb888, c->s.cam_cloud ? OFF_RGB : ON_RGB);
    put(c, gsp_chakra_cloud_on_set_color_rgb888, c->s.cam_cloud ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_cam_src_set_text, c->cam_src);
}

static void draw_colour(struct chakra_core *c)
{
    static esp_gsp_err_t (*const ring[CHAKRA_COUNT])(esp_gsp_handle_t, bool) = {
        gsp_chakra_grp_col_ring_0_set_visible, gsp_chakra_grp_col_ring_1_set_visible,
        gsp_chakra_grp_col_ring_2_set_visible, gsp_chakra_grp_col_ring_3_set_visible,
        gsp_chakra_grp_col_ring_4_set_visible, gsp_chakra_grp_col_ring_5_set_visible,
        gsp_chakra_grp_col_ring_6_set_visible};
    const int mode = c->s.color_mode;
    put(c, gsp_chakra_col_auto_set_color_rgb888, mode == CHAKRA_COLOR_AUTO ? ON_RGB : OFF_RGB);
    for (int i = 0; i < CHAKRA_COUNT; ++i) {
        put(c, ring[i], mode == CHAKRA_COLOR_CHAKRA && c->s.color_value == i);
    }
    const uint32_t fixed = fixed_rgb(c);
    put(c, gsp_chakra_hue_swatch_set_color_rgb888, fixed ? fixed : OFF_RGB);  // grey while Auto
    char v[16];
    if (mode == CHAKRA_COLOR_HUE) {
        snprintf(v, sizeof(v), "%d°", c->s.color_value);
    } else {
        snprintf(v, sizeof(v), "%s", mode == CHAKRA_COLOR_AUTO ? T(c, S_AUTO) : "");
    }
    put(c, gsp_chakra_val_hue_set_text, v);
}

static void draw_settings(struct chakra_core *c)
{
    draw_page(c);
    draw_lamps(c);
    draw_colour(c);
    draw_camera_page(c);
    char v[24];
    snprintf(v, sizeof(v), "%d %%", c->s.brightness);
    put(c, gsp_chakra_val_bright_set_text, v);
    snprintf(v, sizeof(v), "%d dB", -30 - 5 * c->s.sensitivity);
    put(c, gsp_chakra_val_sens_set_text, v);
    snprintf(v, sizeof(v), c->s.lang == CHAKRA_LANG_DE ? "%d,%d s" : "%d.%d s", c->s.hold_ds / 10, c->s.hold_ds % 10);
    put(c, gsp_chakra_val_hold_set_text, v);
    /* A finger moves the sliders too, so they are never skipped as unchanged. */
    err(c, gsp_chakra_sl_bright_set_value(c->ui, c->s.brightness));
    if (c->s.color_mode == CHAKRA_COLOR_HUE) {
        err(c, gsp_chakra_sl_hue_set_value(c->ui, c->s.color_value));
    }
    err(c, gsp_chakra_sl_sens_set_value(c->ui, c->s.sensitivity));
    err(c, gsp_chakra_sl_hold_set_value(c->ui, c->s.hold_ds));
    put(c, gsp_chakra_map_notes_set_color_rgb888, c->s.map == CHAKRA_MAP_NOTES ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_map_solf_set_color_rgb888, c->s.map == CHAKRA_MAP_SOLFEGGIO ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_map_bowls_set_color_rgb888, c->s.map == CHAKRA_MAP_BOWLS ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_react_flow_set_color_rgb888, c->s.reaction == CHAKRA_FLOW ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_react_strike_set_color_rgb888, c->s.reaction == CHAKRA_STRIKE ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_ai_off_set_color_rgb888, c->s.ai ? OFF_RGB : ON_RGB);
    put(c, gsp_chakra_ai_on_set_color_rgb888, c->s.ai ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_lang_en_set_color_rgb888, c->s.lang == CHAKRA_LANG_EN ? ON_RGB : OFF_RGB);
    put(c, gsp_chakra_lang_de_set_color_rgb888, c->s.lang == CHAKRA_LANG_DE ? ON_RGB : OFF_RGB);
}

// ------------------------------------------------------------------ camera light --

/* Tells the platform when the light should change: Off, On, or Auto's verdict, never with the
 * camera off. */
static void apply_light(struct chakra_core *c)
{
    const bool want = c->s.cam_on && (c->s.cam_light == CHAKRA_CAM_LIGHT_ON ||
                                      (c->s.cam_light == CHAKRA_CAM_LIGHT_AUTO && c->auto_lit));
    if (!c->lit_told || want != c->lit) {
        c->lit = want;
        c->lit_told = true;
        if (c->cfg.on_cam_light) {
            c->cfg.on_cam_light(want, c->dark, c->cfg.ctx);
        }
    }
    draw_light_state(c);
}

/* Auto from the frames' luma, with hysteresis (LUMA_DARK and the lines below it). */
static void auto_light(struct chakra_core *c, int luma)
{
    const uint32_t t = now(c) ? now(c) : 1;
    if (!c->auto_lit) {
        c->dark = luma < LUMA_DARK;
        c->bright_since = 0;
        if (!c->dark) {
            c->dark_since = 0;
        } else if (!c->dark_since) {
            c->dark_since = t;
        } else if (t - c->dark_since >= LIGHT_SWITCH_MS) {
            c->auto_lit = true;
            c->lit_at = t;
            c->lit_base = -1;
        }
        return;
    }
    if (c->lit_base < 0 && t - c->lit_at >= LIGHT_BASE_MS) {
        c->lit_base = luma;  // the picture with the light alone
    }
    const bool brighter = c->lit_base >= 0 && luma > c->lit_base + LUMA_BRIGHTER && luma >= LUMA_DARK;
    if (!brighter || t - c->lit_at < LIGHT_MIN_ON_MS) {
        c->bright_since = 0;
    } else if (!c->bright_since) {
        c->bright_since = t;
    } else if (t - c->bright_since >= LIGHT_SWITCH_MS) {
        c->auto_lit = false;
        c->dark = false;
        c->dark_since = 0;
    }
}

static void settings_changed(struct chakra_core *c)
{
    draw_settings(c);
    if (c->cfg.on_settings) {
        c->cfg.on_settings(&c->s, c->cfg.ctx);
    }
}

static void light(struct chakra_core *c)
{
    if (!c->cfg.on_light) {
        return;
    }
    const uint32_t fixed = fixed_rgb(c);
    int bright = c->s.brightness + (int)((float)KICK_BRIGHT * c->kick + 0.5f);  // a strike kicks it up
    bright = bright > 100 ? 100 : bright;
    if (fixed) {  // a steady light: its own colour, whatever the detection hears
        c->cfg.on_light(c->s.color_mode == CHAKRA_COLOR_CHAKRA ? c->s.color_value : CHAKRA_FIXED_HUE, fixed, bright,
                        c->cfg.ctx);
        return;
    }
    const int which = c->shown >= 0 ? c->shown : c->kick > 0.0f ? c->last_shown : -1;
    const chakra_info_t *info = chakra_info(which);
    uint32_t rgb = info ? info->rgb : 0;
    if (rgb && c->kick > 0.0f) {  // the lamps go towards white with the kick, as the screen does
        uint32_t mixed = 0;
        for (int sh = 16; sh >= 0; sh -= 8) {
            const float v = (float)((rgb >> sh) & 0xFF);
            mixed = (mixed << 8) | (uint32_t)(v + (255.0f - v) * KICK_WHITE * c->kick + 0.5f);
        }
        rgb = mixed;
    }
    c->cfg.on_light(which, rgb, bright, c->cfg.ctx);
}

/* A new colour choice: the background, the lamps and the settings follow at once. */
static void colour_changed(struct chakra_core *c)
{
    draw_chakra(c, c->shown);
    draw_colour(c);
    if (c->cfg.on_settings) {
        c->cfg.on_settings(&c->s, c->cfg.ctx);
    }
    if (fixed_rgb(c) || c->shown >= 0) {
        light(c);
    }
}

static int colour_dot(const esp_gsp_event_t *event)
{
    return gsp_chakra_event_is_col_0(event)   ? 0
           : gsp_chakra_event_is_col_1(event) ? 1
           : gsp_chakra_event_is_col_2(event) ? 2
           : gsp_chakra_event_is_col_3(event) ? 3
           : gsp_chakra_event_is_col_4(event) ? 4
           : gsp_chakra_event_is_col_5(event) ? 5
           : gsp_chakra_event_is_col_6(event) ? 6
                                              : -1;
}

// ------------------------------------------------------------------ hold to close --

static void hold_stop(struct chakra_core *c)
{
    if (c->hold_timer) {
        esp_gsp_timer_delete(c->ui, c->hold_timer);
        c->hold_timer = NULL;
    }
    if (c->hold_shown) {
        c->hold_shown = false;
        put(c, gsp_chakra_grp_hold_set_visible, false);
        err(c, esp_gsp_set_press_feedback_enabled(c->ui, true));
    }
}

static void hold_tick(esp_gsp_handle_t ui, void *ctx)
{
    (void)ui;
    struct chakra_core *c = ctx;
    if (!c->hold_timer) {
        return;  // released while this call was already scheduled
    }
    /* Real time since the press, not the sum of the timer's periods: a late tick must not
     * stretch the 3 s. Without a clock the ticks are counted, as before. */
    c->hold_ms = c->cfg.now_ms ? now(c) - c->hold_since : c->hold_ms + HOLD_STEP_MS;
    if (c->hold_ms < HOLD_MS) {
        put(c, gsp_chakra_hold_bar_set_value, (int32_t)(c->hold_ms * 1000 / HOLD_MS));
        return;
    }
    esp_gsp_timer_delete(c->ui, c->hold_timer);
    c->hold_timer = NULL;
    put(c, gsp_chakra_hold_bar_set_value, 1000);
    put(c, gsp_chakra_hold_text_set_text, T(c, S_CLOSING));
    haptic(c, 2);
    if (c->cfg.on_close) {
        c->cfg.on_close(c->cfg.ctx);
    }
}

static void hold_start(struct chakra_core *c)
{
    if (c->hold_timer) {
        return;
    }
    c->hold_ms = 0;
    c->hold_since = now(c);
    put(c, gsp_chakra_hold_bar_set_value, 0);
    put(c, gsp_chakra_hold_text_set_text, T(c, S_HOLD_CLOSE));
    put(c, gsp_chakra_grp_hold_set_visible, true);
    // The press shade would darken the orange fill; off while held, back on release.
    err(c, esp_gsp_set_press_feedback_enabled(c->ui, false));
    c->hold_shown = true;
    c->hold_timer = esp_gsp_timer_create(c->ui, HOLD_STEP_MS, hold_tick, c);
    if (!c->hold_timer) {
        hold_stop(c);
    }
}

/* A cancelled press sends no release, so the lifted finger is also read here. */
static void on_pointer(esp_gsp_handle_t ui, int32_t x, int32_t y, bool pressed, void *ctx)
{
    (void)ui;
    (void)x;
    (void)y;
    if (!pressed) {
        hold_stop(ctx);
    }
}

// ------------------------------------------------------------------ learning the user's bowls --

/* The name row holds only the chakra's name here; the step and the tone go on the right. */
static void learn_draw(struct chakra_core *c, const chakra_reading_t *r)
{
    const chakra_info_t *info = chakra_info(c->learn);
    char line[96];
    put(c, gsp_chakra_name_text_set_text, c->s.lang == CHAKRA_LANG_DE ? info->german : info->english);
    if (r && r->tone && c->learn_n > 0) {
        const int tenths = (int)(c->learn_mean * 10.0f + 0.5f);
        snprintf(line, sizeof(line), c->s.lang == CHAKRA_LANG_DE ? "%d/7 · %d,%d Hz" : "%d/7 · %d.%d Hz", c->learn + 1,
                 tenths / 10, tenths % 10);
    } else {
        snprintf(line, sizeof(line), "%d/7 · %s", c->learn + 1, T(c, S_HOLD_TONE));
    }
    put(c, gsp_chakra_sub_text_set_text, line);
    c->tune = c->learn_n > 0 ? 100.0f * (float)c->learn_ms / LEARN_MS : 0.0f;
}

static void learn_step(struct chakra_core *c, int step)
{
    c->learn = step;
    c->learn_ms = 0;
    c->learn_n = 0;
    c->learn_sum = 0.0f;
    if (step < 0) {
        return;
    }
    draw_chakra(c, step);  // the step's colour and name
    learn_draw(c, NULL);
}

static void learn_start(struct chakra_core *c)
{
    c->settings_open = false;
    put(c, gsp_chakra_grp_settings_set_visible, false);
    c->learn_gap = false;
    c->shown = -1;
    learn_step(c, 0);
}

static void learn_finish(struct chakra_core *c)
{
    learn_step(c, -1);
    c->s.map = CHAKRA_MAP_BOWLS;
    settings_changed(c);
    c->shown = -1;
    draw_chakra(c, -1);
    haptic(c, 2);
}

/* One reading while learning: a steady tone for LEARN_MS becomes this step's bowl. */
static void learn_tick(struct chakra_core *c, const chakra_reading_t *r)
{
    const float f = r->freq_hz;
    if (c->learn_gap) {  // the bowl just learned still rings: wait for silence or a new sound
        if (!r->tone || fabsf(1200.0f * log2f(f / c->learn_prev)) > 150.0f) {
            c->learn_gap = false;
        }
        learn_draw(c, NULL);
        return;
    }
    if (r->tone && (c->learn_n == 0 || fabsf(1200.0f * log2f(f / c->learn_mean)) < LEARN_CENTS)) {
        c->learn_sum += f;
        c->learn_n++;
        c->learn_mean = c->learn_sum / (float)c->learn_n;
        c->learn_ms += HOP_MS;
    } else {
        c->learn_ms = 0;
        c->learn_n = 0;
        c->learn_sum = 0.0f;
    }
    if (c->learn_ms >= LEARN_MS) {
        c->s.bowl_hz[c->learn] = c->learn_mean;
        c->learn_prev = c->learn_mean;
        c->learn_gap = true;
        haptic(c, 1);
        if (c->learn + 1 >= CHAKRA_COUNT) {
            learn_finish(c);
            return;
        }
        learn_step(c, c->learn + 1);
        return;
    }
    learn_draw(c, r);
}

static bool bowls_learned(const struct chakra_core *c)
{
    for (int i = 0; i < CHAKRA_COUNT; ++i) {
        if (c->s.bowl_hz[i] <= 0.0f) {
            return false;
        }
    }
    return true;
}

// ------------------------------------------------------------------ events and tick --

static int lamp_row(const esp_gsp_event_t *event)
{
    return gsp_chakra_event_is_lamp_0(event)   ? 0
           : gsp_chakra_event_is_lamp_1(event) ? 1
           : gsp_chakra_event_is_lamp_2(event) ? 2
           : gsp_chakra_event_is_lamp_3(event) ? 3
                                                : -1;
}

static void on_event(esp_gsp_handle_t ui, const esp_gsp_event_t *event, void *ctx)
{
    (void)ui;
    struct chakra_core *c = ctx;
    const int row = lamp_row(event);
    const int dot = colour_dot(event);
    if (gsp_chakra_event_is_hold_start(event)) {
        hold_start(c);
    } else if (gsp_chakra_event_is_hold_end(event)) {
        hold_stop(c);
    } else if (gsp_chakra_event_is_gear(event) && c->learn >= 0) {
        learn_step(c, -1);  // the gear cancels learning; bowls learned so far stay
        draw_chakra(c, -1);
        haptic(c, 1);
    } else if (gsp_chakra_event_is_gear(event)) {
        c->settings_open = !c->settings_open;
        if (c->settings_open) {
            draw_settings(c);
        }
        put(c, gsp_chakra_grp_settings_set_visible, c->settings_open);
        haptic(c, 1);
    } else if (gsp_chakra_event_is_tab_set(event) || gsp_chakra_event_is_tab_conn(event) ||
               gsp_chakra_event_is_tab_cam(event)) {
        c->page = gsp_chakra_event_is_tab_conn(event) ? 1 : gsp_chakra_event_is_tab_cam(event) ? 2 : 0;
        draw_page(c);
        haptic(c, 1);
    } else if (gsp_chakra_event_is_cam_off(event) || gsp_chakra_event_is_cam_on(event)) {
        c->s.cam_on = gsp_chakra_event_is_cam_on(event) ? 1 : 0;
        if (!c->s.cam_on) {
            c->picture = false;  // the old frame goes with the camera; the next one comes fresh
            c->auto_lit = false;
            c->dark = false;
            c->dark_since = 0;
        }
        settings_changed(c);
        draw_view(c);
        draw_boxes(c);
        draw_mode(c);
        apply_light(c);
        haptic(c, 1);
    } else if (gsp_chakra_event_is_boxes_off(event) || gsp_chakra_event_is_boxes_on(event)) {
        c->s.cam_boxes = gsp_chakra_event_is_boxes_on(event) ? 1 : 0;
        settings_changed(c);
        draw_boxes(c);
        haptic(c, 1);
    } else if (gsp_chakra_event_is_fps_1(event) || gsp_chakra_event_is_fps_2(event) || gsp_chakra_event_is_fps_4(event)) {
        c->s.cam_fps = gsp_chakra_event_is_fps_1(event) ? 1 : gsp_chakra_event_is_fps_4(event) ? 4 : 2;
        settings_changed(c);
        haptic(c, 1);
    } else if (gsp_chakra_event_is_light_off(event) || gsp_chakra_event_is_light_on(event) ||
               gsp_chakra_event_is_light_auto(event)) {
        c->s.cam_light = gsp_chakra_event_is_light_off(event)  ? CHAKRA_CAM_LIGHT_OFF
                         : gsp_chakra_event_is_light_on(event) ? CHAKRA_CAM_LIGHT_ON
                                                               : CHAKRA_CAM_LIGHT_AUTO;
        settings_changed(c);
        apply_light(c);
        haptic(c, 1);
    } else if (gsp_chakra_event_is_cloud_off(event) || gsp_chakra_event_is_cloud_on(event)) {
        c->s.cam_cloud = gsp_chakra_event_is_cloud_on(event) ? 1 : 0;  // the platform decides what it may do
        settings_changed(c);
        haptic(c, 1);
    } else if (gsp_chakra_event_is_col_auto(event)) {
        c->s.color_mode = CHAKRA_COLOR_AUTO;
        colour_changed(c);
        haptic(c, 1);
    } else if (dot >= 0) {
        c->s.color_mode = CHAKRA_COLOR_CHAKRA;
        c->s.color_value = dot;
        colour_changed(c);
        haptic(c, 1);
    } else if (gsp_chakra_event_is_sl_hue(event)) {
        c->s.color_mode = CHAKRA_COLOR_HUE;
        c->s.color_value = (int)(int32_t)event->arg;
        colour_changed(c);
    } else if (row >= 0) {
        if (row >= c->lamp_count || !c->lamps[row].paired) {
            return;  // greyed: pair it outside the app first
        }
        c->s.lamps ^= (uint8_t)(1u << row);
        settings_changed(c);
        haptic(c, 1);
        if (c->shown >= 0 || fixed_rgb(c)) {
            light(c);  // a lamp ticked now joins at once
        }
    } else if (gsp_chakra_event_is_sl_bright(event)) {
        c->s.brightness = (int)(int32_t)event->arg;
        settings_changed(c);
        if (c->shown >= 0 || fixed_rgb(c)) {
            light(c);
        }
    } else if (gsp_chakra_event_is_sl_sens(event)) {
        c->s.sensitivity = (int)(int32_t)event->arg;
        settings_changed(c);
    } else if (gsp_chakra_event_is_sl_hold(event)) {
        c->s.hold_ds = (int)(int32_t)event->arg;
        settings_changed(c);
    } else if (gsp_chakra_event_is_bowls_learn(event) ||
               (gsp_chakra_event_is_map_bowls(event) && !bowls_learned(c))) {
        haptic(c, 1);
        learn_start(c);
    } else if (gsp_chakra_event_is_map_bowls(event)) {
        c->s.map = CHAKRA_MAP_BOWLS;
        settings_changed(c);
        haptic(c, 1);
    } else if (gsp_chakra_event_is_map_notes(event) && c->s.map == CHAKRA_MAP_NOTES) {
        c->s.a4 = c->s.a4 == 432 ? 440 : 432;  // a second tap on Notes switches the reference pitch
        draw_labels(c);
        settings_changed(c);
        haptic(c, 1);
    } else if (gsp_chakra_event_is_map_notes(event) || gsp_chakra_event_is_map_solf(event)) {
        c->s.map = gsp_chakra_event_is_map_solf(event) ? CHAKRA_MAP_SOLFEGGIO : CHAKRA_MAP_NOTES;
        settings_changed(c);
        haptic(c, 1);
    } else if (gsp_chakra_event_is_react_flow(event) || gsp_chakra_event_is_react_strike(event)) {
        c->s.reaction = gsp_chakra_event_is_react_strike(event) ? CHAKRA_STRIKE : CHAKRA_FLOW;
        settings_changed(c);
        haptic(c, 1);
    } else if (gsp_chakra_event_is_ai_off(event) || gsp_chakra_event_is_ai_on(event)) {
        c->s.ai = gsp_chakra_event_is_ai_on(event) ? 1 : 0;
        c->kick = 0.0f;
        settings_changed(c);
        haptic(c, 1);
    } else if (gsp_chakra_event_is_lang_en(event) || gsp_chakra_event_is_lang_de(event)) {
        c->s.lang = gsp_chakra_event_is_lang_de(event) ? CHAKRA_LANG_DE : CHAKRA_LANG_EN;
        draw_labels(c);
        draw_chakra(c, c->shown);
        draw_view(c);
        draw_boxes(c);
        draw_heard(c);
        draw_light_state(c);
        settings_changed(c);
        haptic(c, 1);
    }
}

static void tick(esp_gsp_handle_t ui, void *ctx)
{
    (void)ui;
    struct chakra_core *c = ctx;
    c->ticks++;
    c->tick_start = now(c);
    chakra_reading_t r;
    bool fresh = false;
    for (int budget = 0; budget < 8 && c->cfg.poll && c->cfg.poll(&r, c->cfg.ctx) > 0; ++budget) {
        fresh = true;
        if (r.chakra != c->shown) {  // never skip a change inside a burst
            break;
        }
    }
    if (c->learn >= 0) {
        if (fresh) {
            learn_tick(c, &r);
        }
        animate(c);
        return;
    }
    if (fresh) {
        const bool sounding = r.candidate >= 0 && r.candidate == r.chakra;
        if (sounding || r.chakra != c->shown) {
            c->last = r;  // the note line keeps the last real tone through the after-glow
        }
        c->last.chakra = r.chakra;
        c->sounding = sounding;
        /* With the AI gate, only a bowl-like sound may change the colour: a gong or a drum that
         * the detection reads as a tone keeps the colour and kicks the light instead. */
        const bool gate_live = c->gate_heard && c->ticks - c->gate_tick <= GATE_ALIVE_TICKS;
        const bool ai_blocks = c->s.ai && gate_live && r.chakra >= 0 &&
                               (!c->bowl_heard || c->ticks - c->bowl_tick > AI_HOLD_TICKS);
        if (r.chakra != c->shown && !ai_blocks) {
            const bool from_silence = c->shown < 0;
            if (r.chakra >= 0) {
                c->last_shown = r.chakra;
            }
            c->shown = r.chakra;
            draw_chakra(c, r.chakra);
            c->sub_tick = c->ticks;
            draw_sub(c);  // at once: the new name never stands over the old note
            if (r.chakra >= 0 && from_silence) {
                haptic(c, 1);
            }
            if (!fixed_rgb(c)) {
                light(c);  // a fixed colour stays, whatever is heard
            }
        }
        memcpy(c->bars_want, r.bars, sizeof(c->bars_want));
    }
    animate(c);
    if (c->shown >= 0 && c->sounding && c->ticks - c->sub_tick >= SUB_EVERY_TICKS && spare(c)) {
        c->sub_tick = c->ticks;
        draw_sub(c);
    }
    if (c->ticks % 3 == 0) {
        draw_heard(c);  // an AI verdict ages out after HEARD_MS
    }
    if (c->picture && c->ticks % 12 == 0 && now(c) - c->frame_ms > FRAME_STALE_MS) {
        c->picture = false;  // the source stopped: the view waits again, the mark shows the microphone
        draw_view(c);
        draw_boxes(c);
        draw_mode(c);
    }
    if (c->boxes_dirty) {
        c->boxes_dirty = false;
        draw_boxes(c);  // hides the boxes that did not come back, and the seen pill
    }
    draw_box_geometry(c);
    draw_bars(c);
}

// ------------------------------------------------------------------ public --

void chakra_core_set_sound(chakra_core_handle_t c, int kind, int strike)
{
    if (!c) {
        return;
    }
    c->gate_tick = c->ticks;
    c->gate_heard = true;
    c->heard_kind = kind;
    c->heard_ms = now(c) ? now(c) : 1;
    if (!c->s.ai) {
        return;  // the heard pill shows the detection then; the gate only leads with AI on
    }
    if (kind == CHAKRA_SOUND_BOWL) {
        c->bowl_tick = c->ticks;
        c->bowl_heard = true;
    } else if (kind == CHAKRA_SOUND_OTHER && strike) {
        c->kick = 1.0f;
        light(c);
    }
}

static uint32_t be16(const uint8_t *p)
{
    return ((uint32_t)p[0] << 8) | p[1];
}

/* A PNG's or JPEG's size from its header (as apps/house house_image_size). */
static bool chakra_image_size(const uint8_t *d, size_t n, int *w, int *h)
{
    if (!d || n < 24) {
        return false;
    }
    if (memcmp(d, "\x89PNG\r\n\x1a\n", 8) == 0 && memcmp(d + 12, "IHDR", 4) == 0) {
        *w = (int)((be16(d + 16) << 16) | be16(d + 18));
        *h = (int)((be16(d + 20) << 16) | be16(d + 22));
        return *w > 0 && *h > 0;
    }
    if (d[0] != 0xFF || d[1] != 0xD8) {
        return false;
    }
    /* JPEG: walk the segments to the first start-of-frame (SOF0..SOF15 without DHT, JPG, DAC). */
    size_t i = 2;
    while (i + 9 < n) {
        if (d[i] != 0xFF) {
            return false;
        }
        const uint8_t m = d[i + 1];
        if (m == 0xFF) {
            i++;
            continue;
        }
        const uint32_t len = be16(d + i + 2);
        if (m >= 0xC0 && m <= 0xCF && m != 0xC4 && m != 0xC8 && m != 0xCC) {
            *h = (int)be16(d + i + 5);
            *w = (int)be16(d + i + 7);
            return *w > 0 && *h > 0;
        }
        if (m == 0xD9 || m == 0xDA || len < 2) {
            return false;
        }
        i += 2 + len;
    }
    return false;
}

bool chakra_core_set_frame(chakra_core_handle_t c, const uint8_t *data, size_t size)
{
    if (!c || !c->s.cam_on) {
        return false;
    }
    int w = 0, h = 0;
    if (!chakra_image_size(data, size, &w, &h) || w != CHAKRA_CAM_W || h != CHAKRA_CAM_H) {
        return false;  // images play at their native size only: a wrong size would not fill the view
    }
    const esp_gsp_err_t e = gsp_chakra_cam_img_set_image(c->ui, data, size);
    err(c, e);
    if (e == ESP_GSP_OK) {
        c->frame_ms = now(c) ? now(c) : 1;
        if (!c->picture) {
            c->picture = true;
            draw_view(c);
            draw_boxes(c);
            draw_mode(c);
        }
    }
    return e == ESP_GSP_OK;
}

void chakra_core_set_box(chakra_core_handle_t c, int index, const char *label, float x, float y, float w, float h,
                         float confidence)
{
    if (!c || index < 0 || index >= CHAKRA_BOXES || !label) {
        return;
    }
    const float cx = x < 0 ? 0 : x > 1 ? 1 : x, cy = y < 0 ? 0 : y > 1 ? 1 : y;
    const int px = (int)(cx * CHAKRA_CAM_W + 0.5f), py = (int)(cy * CHAKRA_CAM_H + 0.5f);
    int pw = (int)(w * CHAKRA_CAM_W + 0.5f), ph = (int)(h * CHAKRA_CAM_H + 0.5f);
    pw = pw < BOX_MIN ? BOX_MIN : pw > CHAKRA_CAM_W - px ? CHAKRA_CAM_W - px : pw;  // inside the view
    ph = ph < BOX_MIN ? BOX_MIN : ph > CHAKRA_CAM_H - py ? CHAKRA_CAM_H - py : ph;
    snprintf(c->box[index].label, sizeof(c->box[index].label), "%s", label);
    c->box[index].conf = confidence;
    c->box[index].on = true;
    c->box[index].x = px;
    c->box[index].y = py;
    c->box[index].w = pw < BOX_MIN ? BOX_MIN : pw;
    c->box[index].h = ph < BOX_MIN ? BOX_MIN : ph;
    c->boxes_dirty = true;  // drawn in the tick: a frame's "clear" and its boxes arrive together
}

void chakra_core_clear_boxes(chakra_core_handle_t c)
{
    if (!c) {
        return;
    }
    for (int i = 0; i < CHAKRA_BOXES; ++i) {
        c->box[i].on = false;
    }
    c->boxes_dirty = true;  // the boxes that come back with this frame are not hidden first
}

void chakra_core_set_camera_source(chakra_core_handle_t c, int kind, const char *text)
{
    if (c) {
        c->src_kind = kind;
        snprintf(c->cam_src, sizeof(c->cam_src), "%s", text ? text : "");
        put(c, gsp_chakra_cam_src_set_text, c->cam_src);
        draw_camera_page(c);
        draw_mode(c);
    }
}

void chakra_core_set_frame_luma(chakra_core_handle_t c, int luma)
{
    if (!c || luma < 0 || !c->s.cam_on) {
        return;
    }
    c->luma = luma > 255 ? 255 : luma;
    auto_light(c, c->luma);
    apply_light(c);
}

void chakra_core_set_clock(chakra_core_handle_t c, const char *hhmm)
{
    if (c) {
        put(c, gsp_chakra_clock_set_text, hhmm);
    }
}

void chakra_core_set_connection(chakra_core_handle_t c, int state)
{
    static const uint32_t COLOURS[] = {0xFF453A, 0xFF9500, 0x34C759, 0x30B0C7};
    if (c && state >= 0 && state < 4) {
        put(c, gsp_chakra_conn_dot_set_color_rgb888, COLOURS[state]);
    }
}

void chakra_core_set_lamps(chakra_core_handle_t c, const chakra_lamp_t *lamps, int count)
{
    if (!c) {
        return;
    }
    c->lamp_count = count < 0 ? 0 : count > CHAKRA_LAMPS ? CHAKRA_LAMPS : count;
    for (int i = 0; i < c->lamp_count; ++i) {
        c->lamps[i] = lamps[i];
        c->lamps[i].name[sizeof(c->lamps[i].name) - 1] = '\0';
        if (!lamps[i].paired) {
            c->s.lamps &= (uint8_t)~(1u << i);
        }
    }
    draw_lamps(c);
    if (fixed_rgb(c)) {
        light(c);  // a stored steady colour lights the lamps as soon as they are known
    }
}

esp_gsp_err_t chakra_core_create(esp_gsp_handle_t ui, const chakra_core_config_t *config, chakra_core_handle_t *out)
{
    if (!out || !ui) {
        return ESP_GSP_ERR_INVALID_ARG;
    }
    *out = NULL;
    struct chakra_core *c = calloc(1, sizeof(*c));
    if (!c) {
        return ESP_GSP_ERR_NO_MEM;
    }
    c->ui = ui;
    c->shown = -1;
    c->learn = -1;
    c->last_shown = -1;
    c->tune_drawn = -1;
    if (config) {
        c->cfg = *config;
        c->s = config->settings;
    }
    if (c->s.brightness <= 0) {
        chakra_settings_defaults(&c->s);
    }
    c->target_rgb = c->drawn_rgb = IDLE_RGB;
    c->cur[0] = (IDLE_RGB >> 16) & 0xFF;
    c->cur[1] = (IDLE_RGB >> 8) & 0xFF;
    c->cur[2] = IDLE_RGB & 0xFF;
    if (c->s.color_mode < CHAKRA_COLOR_AUTO || c->s.color_mode > CHAKRA_COLOR_HUE) {
        c->s.color_mode = CHAKRA_COLOR_AUTO;  // a blob from before the colour setting, or damaged
    }
    if (c->s.cam_fps != 1 && c->s.cam_fps != 2 && c->s.cam_fps != 4) {
        c->s.cam_fps = 2;
    }
    c->s.cam_on = c->s.cam_on ? 1 : 0;
    c->s.cam_boxes = c->s.cam_boxes ? 1 : 0;
    c->s.cam_cloud = c->s.cam_cloud ? 1 : 0;
    if (c->s.cam_light < CHAKRA_CAM_LIGHT_OFF || c->s.cam_light > CHAKRA_CAM_LIGHT_AUTO) {
        c->s.cam_light = CHAKRA_CAM_LIGHT_AUTO;
    }
    c->luma = -1;
    c->lit_base = -1;
    draw_labels(c);
    draw_chakra(c, -1);
    draw_settings(c);
    draw_view(c);
    draw_boxes(c);
    draw_heard(c);
    draw_mode(c);
    apply_light(c);  // the platform learns the light's start state (off: no dark picture yet)
    esp_gsp_err_t e = esp_gsp_on_event(ui, on_event, c);
    if (e == ESP_GSP_OK) {
        e = esp_gsp_set_pointer_observer(ui, on_pointer, c);
    }
    if (e == ESP_GSP_OK) {
        c->timer = esp_gsp_timer_create(ui, TICK_MS, tick, c);
        if (!c->timer) {
            esp_gsp_on_event(ui, NULL, NULL);
            esp_gsp_set_pointer_observer(ui, NULL, NULL);
            e = ESP_GSP_ERR_NO_MEM;
        }
    }
    if (e != ESP_GSP_OK) {
        free(c);
        return e;
    }
    *out = c;
    return ESP_GSP_OK;
}

esp_gsp_err_t chakra_core_destroy(chakra_core_handle_t *handle)
{
    if (!handle || !*handle) {
        return ESP_GSP_OK;
    }
    struct chakra_core *c = *handle;
    esp_gsp_err_t e = esp_gsp_on_event(c->ui, NULL, NULL);
    if (e == ESP_GSP_OK) {
        e = esp_gsp_set_pointer_observer(c->ui, NULL, NULL);
    }
    if (e == ESP_GSP_OK && c->hold_timer) {
        e = esp_gsp_timer_delete(c->ui, c->hold_timer);
        c->hold_timer = NULL;
    }
    if (e == ESP_GSP_OK && c->timer) {
        e = esp_gsp_timer_delete(c->ui, c->timer);
    }
    if (e != ESP_GSP_OK) {
        return e;
    }
    free(c);
    *handle = NULL;
    return ESP_GSP_OK;
}
