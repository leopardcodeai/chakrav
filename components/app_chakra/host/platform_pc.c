// SPDX-License-Identifier: Apache-2.0
// Simulator side of the ChakraV app: audio arrives over loopback TCP from tools/chakra_feed.py
// (the Mac's microphone through ffmpeg, a test tone, a demo round or a WAV file), the same
// chakra_detect.c as on the board runs on it, and every light command goes back as a line, so
// the feeder can colour the screen lamp page (or, with --light, a real lamp in Home Assistant).
//
// Protocol, audio port (CHAKRA_FEED_PORT, default 8710): in, raw signed 16-bit little-endian mono
// samples at 16 kHz; out, one line per change: light\t<chakra -1..6>\t<RRGGBB>\t<brightness %>\t<transition s>\n,
// close\n for the hold gesture, and while a chakra is locked, at most twice a second when it
// changes, the reading for a lamp page:
// reading\t<chakra>\t<english>\t<german>\t<sanskrit>\t<note+octave>\t<Hz>\t<cents>\t<solfeggio Hz>\t<en|de>\n
// and about five times a second the spectrum window the screen shows, for the page's faint band:
// bars\t<MIDI note of the first band>\t<18 values 0..100>\n (one band a semitone, chakra_core.h)
// Line port (CHAKRA_AI_PORT, default 8711; up to LINE_CLIENTS at once: the AI sound gate through
// chakra_feed.py --ai and the camera through tools/camera_live.py), in:
//   sound\t<bowl|other|none>\t<strike 0|1>              the AI sound gate's verdict
//   frame\t<path>[\t<luma>]                             a JPEG of CHAKRA_CAM_W x CHAKRA_CAM_H, read at once;
//                                                        its mean luma 0..255 drives the light's Auto
//   box\t<label>\t<x>\t<y>\t<w>\t<h>\t<conf>[\t<played 0|1>]   a mark, normalised 0..1; a frame's boxes follow it
//   boxes\tclear                                          before each frame's boxes
//   source\t<text>[\t<camera|video|demo>]                 the Camera page's source line and the indicator dot
// out, to every line client when it connects and on each change of the settings:
//   camera\t<on 0|1>\t<boxes 0|1>\t<fps 1|2|4>\t<cloud 0|1>
// and whenever the camera's light should change (Off, On, Auto's verdict):
//   camlight\t<on 0|1>\t<dark 0|1>      the Mac's camera has no light to switch: camera_live.py reports it
// and whenever the detector's locked chakra changes (the sound, not the colour setting):
//   heard\t<chakra 0..6|-1>             camera_live.py's tracker binds the struck bowl to the note it heard
// 127.0.0.1 only. All socket work is non-blocking and runs in the core's 40 ms tick on the
// bridge's single thread.
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
#include <arpa/inet.h>

#include "chakra_core.h"
#include "gsp_sim_bridge.h"

#define CHUNK 4096
#define LINE_CLIENTS 4
#define LINE_MAX 512
#define FRAME_MAX (512 * 1024)  // a 270 x 270 JPEG is about 15 to 30 KB

static struct {
    chakra_core_handle_t core;
    chakra_detect_t *detect;
    int listener, client;
    int ai_listener;
    struct {
        int fd;
        char line[LINE_MAX];
        size_t len;
    } lines[LINE_CLIENTS];
    int box_next;      // the next box slot for this frame's boxes
    chakra_settings_t settings;  // the last on_settings, for the camera line
    uint8_t carry;     // an odd byte left from the last read
    bool has_carry;
    int16_t pcm[CHUNK];
    float samples[CHUNK];
    unsigned long hops;
    uint8_t lamps;     // ticked rows, from the last on_settings
    int reaction;
    int lang;          // CHAKRA_LANG_EN or CHAKRA_LANG_DE, for the reading line
} host = {.listener = -1, .client = -1, .ai_listener = -1};

static void nonblock(int fd)
{
    fcntl(fd, F_SETFL, fcntl(fd, F_GETFL, 0) | O_NONBLOCK);
}

static int listen_loopback(int port, const char *what)
{
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) {
        return -1;
    }
    int one = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    struct sockaddr_in a = {.sin_family = AF_INET, .sin_port = htons((uint16_t)port)};
    a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (bind(fd, (struct sockaddr *)&a, sizeof(a)) != 0 || listen(fd, 1) != 0) {
        fprintf(stderr, "chakrav: cannot listen on 127.0.0.1:%d (%s)\n", port, strerror(errno));
        close(fd);
        return -1;
    }
    nonblock(fd);
    fprintf(stderr, "chakrav: %s on 127.0.0.1:%d\n", what, port);
    return fd;
}

static int feed_port(void)
{
    const char *env = getenv("CHAKRA_FEED_PORT");
    return env ? atoi(env) : 8710;
}

/* The camera line for one line client: what it should send. */
static void send_camera(int fd)
{
    char line[64];
    snprintf(line, sizeof(line), "camera\t%d\t%d\t%d\t%d\n", host.settings.cam_on, host.settings.cam_boxes,
             host.settings.cam_fps, host.settings.cam_cloud);
    if (fd >= 0) {
        (void)!write(fd, line, strlen(line));
    }
}

/* A frame from camera_live.py: the file is read now (it is overwritten with the next one). */
static void take_frame(const char *path)
{
    static uint8_t *buf;
    if (!buf && !(buf = malloc(FRAME_MAX))) {
        return;
    }
    FILE *f = fopen(path, "rb");
    if (!f) {
        return;
    }
    const size_t n = fread(buf, 1, FRAME_MAX, f);
    fclose(f);
    const uint64_t t0 = gsp_sim_bridge_time_ms();
    const bool ok = n > 0 && n < FRAME_MAX && chakra_core_set_frame(host.core, buf, n);
    static unsigned long frames;
    if (getenv("CHAKRA_LOG") && frames++ % 10 == 0) {
        fprintf(stderr, "chakrav: frame %lu, %zu bytes, set_image %llu ms\n", frames, n,
                (unsigned long long)(gsp_sim_bridge_time_ms() - t0));
    }
    if (n > 0 && n < FRAME_MAX && !ok) {
        static unsigned long refused;
        if (refused++ % 50 == 0) {
            fprintf(stderr, "chakrav: frame refused (camera off, or not %dx%d)\n", CHAKRA_CAM_W, CHAKRA_CAM_H);
        }
    }
}

static void line_in(char *line)
{
    char *f[8];
    int n = 0;
    for (char *p = line; n < 8;) {
        f[n++] = p;
        char *tab = strchr(p, '\t');
        if (!tab) {
            break;
        }
        *tab = '\0';
        p = tab + 1;
    }
    if (strcmp(f[0], "sound") == 0 && n >= 2) {
        const int k = strcmp(f[1], "bowl") == 0    ? CHAKRA_SOUND_BOWL
                      : strcmp(f[1], "other") == 0 ? CHAKRA_SOUND_OTHER
                                                   : CHAKRA_SOUND_NONE;
        chakra_core_set_sound(host.core, k, n >= 3 ? atoi(f[2]) : 0);
    } else if (strcmp(f[0], "frame") == 0 && n >= 2) {
        take_frame(f[1]);
        if (n >= 3) {
            chakra_core_set_frame_luma(host.core, atoi(f[2]));
        }
    } else if (strcmp(f[0], "boxes") == 0) {
        host.box_next = 0;
        chakra_core_clear_boxes(host.core);
    } else if (strcmp(f[0], "box") == 0 && n >= 7 && host.box_next < CHAKRA_BOXES) {
        chakra_core_set_box(host.core, host.box_next++, f[1], strtof(f[2], NULL), strtof(f[3], NULL),
                            strtof(f[4], NULL), strtof(f[5], NULL), n >= 7 ? strtof(f[6], NULL) : 1.0f,
                            n >= 8 && atoi(f[7]) == 1);
    } else if (strcmp(f[0], "source") == 0 && n >= 2) {
        const int kind = n < 3 || strcmp(f[2], "camera") == 0 ? CHAKRA_SOURCE_CAMERA
                         : strcmp(f[2], "video") == 0         ? CHAKRA_SOURCE_VIDEO
                         : strcmp(f[2], "demo") == 0          ? CHAKRA_SOURCE_DEMO
                                                              : CHAKRA_SOURCE_NONE;
        chakra_core_set_camera_source(host.core, kind, f[1]);
    }
}

/* The camera's light: logged, and told to the line clients (camera_live.py prints it). */
static void on_cam_light(bool on, bool dark, void *ctx)
{
    (void)ctx;
    char line[32];
    snprintf(line, sizeof(line), "camlight\t%d\t%d\n", on ? 1 : 0, dark ? 1 : 0);
    fprintf(stderr, "chakrav: camera light %s%s\n", on ? "on" : "off", dark ? " (dark picture)" : "");
    for (int i = 0; i < LINE_CLIENTS; ++i) {
        if (host.lines[i].fd >= 0) {
            (void)!write(host.lines[i].fd, line, strlen(line));
        }
    }
}

/* The line port: accept up to LINE_CLIENTS, read what is there, act on every complete line. */
static void poll_lines(void)
{
    if (host.ai_listener >= 0) {
        int fd;
        while ((fd = accept(host.ai_listener, NULL, NULL)) >= 0) {
            int slot = -1;
            for (int i = 0; i < LINE_CLIENTS && slot < 0; ++i) {
                slot = host.lines[i].fd < 0 ? i : -1;
            }
            if (slot < 0) {
                close(fd);  // full: the oldest stay
                continue;
            }
            nonblock(fd);
            host.lines[slot].fd = fd;
            host.lines[slot].len = 0;
            send_camera(fd);
        }
    }
    for (int i = 0; i < LINE_CLIENTS; ++i) {
        if (host.lines[i].fd < 0) {
            continue;
        }
        char buf[2048];
        ssize_t r = read(host.lines[i].fd, buf, sizeof(buf));
        if (r == 0 || (r < 0 && errno != EAGAIN && errno != EWOULDBLOCK)) {
            close(host.lines[i].fd);
            host.lines[i].fd = -1;
            continue;
        }
        for (ssize_t k = 0; k < r; ++k) {
            if (buf[k] != '\n') {
                if (host.lines[i].len < LINE_MAX - 1) {
                    host.lines[i].line[host.lines[i].len++] = buf[k];
                }
                continue;
            }
            host.lines[i].line[host.lines[i].len] = '\0';
            host.lines[i].len = 0;
            line_in(host.lines[i].line);
        }
    }
}

static void send_text(const char *line)
{
    if (host.client >= 0) {
        (void)!write(host.client, line, strlen(line));
    }
}

static void on_light(int chakra, uint32_t rgb, int brightness, void *ctx)
{
    (void)ctx;
    if (!(host.lamps & 0x03)) {
        return;  // neither the screen lamp (row 0) nor the feeder's Home Assistant lamp (row 1) is ticked
    }
    char line[64];
    /* Lamps fade like the screen: Flow softly, Strike at once. */
    snprintf(line, sizeof(line), "light\t%d\t%06X\t%d\t%.1f\n", chakra, (unsigned)rgb, brightness,
             host.reaction == CHAKRA_STRIKE ? 0.1 : 1.5);
    fprintf(stderr, "chakrav: %s", line);
    send_text(line);
}

static void on_settings(const chakra_settings_t *s, void *ctx)
{
    (void)ctx;
    chakra_detect_config_t cfg;
    chakra_settings_detect(s, &cfg);
    chakra_detect_set_config(host.detect, &cfg);
    host.lamps = s->lamps;
    host.reaction = s->reaction;
    host.lang = s->lang;
    const bool camera_changed = s->cam_on != host.settings.cam_on || s->cam_boxes != host.settings.cam_boxes ||
                                s->cam_fps != host.settings.cam_fps || s->cam_cloud != host.settings.cam_cloud;
    host.settings = *s;
    if (camera_changed) {
        for (int i = 0; i < LINE_CLIENTS; ++i) {
            send_camera(host.lines[i].fd);
        }
    }
    fprintf(stderr, "chakrav: settings lamps=0x%02x bright=%d gate=%.0f dB hold=%u ms map=%d lang=%d\n", s->lamps,
            s->brightness, (double)cfg.threshold_db, (unsigned)cfg.hold_ms, (int)cfg.map, s->lang);
    if (s->map == CHAKRA_MAP_BOWLS) {
        fprintf(stderr, "chakrav: bowls %.1f %.1f %.1f %.1f %.1f %.1f %.1f Hz\n", (double)s->bowl_hz[0],
                (double)s->bowl_hz[1], (double)s->bowl_hz[2], (double)s->bowl_hz[3], (double)s->bowl_hz[4],
                (double)s->bowl_hz[5], (double)s->bowl_hz[6]);
    }
}

/* The core's clock (hold-to-close, drawing budget): the bridge's monotonic milliseconds. */
static uint32_t now_ms(void *ctx)
{
    (void)ctx;
    return (uint32_t)gsp_sim_bridge_time_ms();
}

static void on_close(void *ctx)
{
    (void)ctx;
    fprintf(stderr, "chakrav: top bar held 3 s, the board would go back to Vibe Mode now\n");
    send_text("close\n");
}

/* The locked chakra's reading for a lamp page (names, note, frequency, cents), only on a change
 * and at most every 500 ms; nothing while silent or when the feeder's lamp row is not ticked. */
static void send_reading(const chakra_reading_t *r)
{
    static int last_chakra = -2, last_cents = 999;
    static char last_note[8];
    static uint32_t last_ms;
    if (!(host.lamps & 0x01) || r->chakra < 0 || r->chakra >= CHAKRA_COUNT) {  // row 0: the screen lamp
        last_chakra = -2;
        return;
    }
    char note[8];
    snprintf(note, sizeof(note), "%s%d", chakra_note_name(r->note), r->octave);
    const uint32_t t = (uint32_t)gsp_sim_bridge_time_ms();
    const bool changed = r->chakra != last_chakra || r->cents != last_cents || strcmp(note, last_note) != 0;
    if (!changed || (r->chakra == last_chakra && t - last_ms < 500)) {
        return;
    }
    last_chakra = r->chakra;
    last_cents = r->cents;
    snprintf(last_note, sizeof(last_note), "%s", note);
    last_ms = t;
    const chakra_info_t *i = chakra_info(r->chakra);
    char line[192];
    snprintf(line, sizeof(line), "reading\t%d\t%s\t%s\t%s\t%s\t%.1f\t%+d\t%u\t%s\n", r->chakra, i->english, i->german,
             i->sanskrit, note, (double)r->freq_hz, r->cents, (unsigned)i->solfeggio_hz,
             host.lang == CHAKRA_LANG_DE ? "de" : "en");
    send_text(line);
}

/* The spectrum window for a lamp page's faint band (owner 25.10.2026: "damit man sieht, es arbeitet"):
 * bars\t<MIDI note of the first band>\t<CHAKRA_VIEW_BANDS values 0..100, comma-separated>, the same
 * window the screen shows, about five times a second while the screen lamp is ticked.
 * Shared lamp behaviour: the same as in the chakra app (ChakraA). */
static void send_bars(const chakra_reading_t *r)
{
    static uint32_t last_ms;
    const uint32_t t = now_ms(NULL);
    if (!(host.lamps & 0x01) || t - last_ms < 200) {
        return;
    }
    last_ms = t;
    const int first = chakra_core_band_window(host.core);
    char line[24 + CHAKRA_VIEW_BANDS * 4];
    int n = snprintf(line, sizeof(line), "bars\t%d\t", first);
    for (int i = 0; i < CHAKRA_VIEW_BANDS && n < (int)sizeof(line) - 5; ++i) {
        n += snprintf(line + n, sizeof(line) - (size_t)n, i ? ",%u" : "%u",
                      (unsigned)r->bars[first - CHAKRA_BAR_MIDI0 + i]);
    }
    snprintf(line + n, sizeof(line) - (size_t)n, "\n");
    send_text(line);
}

static int poll_audio(chakra_reading_t *out, void *ctx)
{
    (void)ctx;
    static int last_minute = -1, last_conn = -1;
    time_t now = time(NULL);
    struct tm tm;
    localtime_r(&now, &tm);
    if (tm.tm_min != last_minute) {
        last_minute = tm.tm_min;
        char hhmm[16];
        snprintf(hhmm, sizeof(hhmm), "%02d:%02d", tm.tm_hour, tm.tm_min);
        chakra_core_set_clock(host.core, hhmm);
    }
    const int conn = host.client >= 0 ? 3 : 1;
    if (conn != last_conn) {
        last_conn = conn;
        chakra_core_set_connection(host.core, conn);
    }
    poll_lines();
    if (host.listener >= 0) {
        int fd = accept(host.listener, NULL, NULL);
        if (fd >= 0) {
            if (host.client >= 0) {
                close(host.client);
            }
            nonblock(fd);
            host.client = fd;
            host.has_carry = false;
        }
    }
    if (host.client < 0) {
        return 0;
    }
    uint8_t *bytes = (uint8_t *)host.pcm;
    size_t have = 0;
    if (host.has_carry) {
        bytes[have++] = host.carry;
        host.has_carry = false;
    }
    ssize_t r = read(host.client, bytes + have, sizeof(host.pcm) - have);
    if (r == 0 || (r < 0 && errno != EAGAIN && errno != EWOULDBLOCK)) {
        close(host.client);
        host.client = -1;
        return 0;
    }
    if (r > 0) {
        have += (size_t)r;
    }
    if (have & 1) {
        host.carry = bytes[--have];
        host.has_carry = true;
    }
    const size_t n = have / 2;
    for (size_t i = 0; i < n; ++i) {
        host.samples[i] = (float)host.pcm[i] / 32768.0f;
    }
    const int hops = n ? chakra_detect_feed(host.detect, host.samples, n, out) : 0;
    host.hops += (unsigned long)hops;
    if (hops) {
        send_reading(out);
        send_bars(out);
        static int heard = -2;
        if (out->chakra != heard) {
            heard = out->chakra;
            char line[24];
            snprintf(line, sizeof(line), "heard\t%d\n", heard);
            for (int i = 0; i < LINE_CLIENTS; ++i) {
                if (host.lines[i].fd >= 0) {
                    (void)!write(host.lines[i].fd, line, strlen(line));
                }
            }
        }
    }
    /* CHAKRA_LOG=1: one reading a second on stderr, for tests against recordings. */
    static const char *log;
    static unsigned long logged;
    if (!log) {
        log = getenv("CHAKRA_LOG") ? "1" : "";
    }
    if (*log && hops && host.hops / 16 != logged) {
        logged = host.hops / 16;
        fprintf(stderr, "reading chakra=%d cand=%d f=%.1f note=%s%d cents=%+d conf=%.2f level=%.0f\n", out->chakra,
                out->candidate, (double)out->freq_hz, chakra_note_name(out->note), out->octave, out->cents,
                (double)out->confidence, (double)out->level_db);
    }
    return hops > 0;
}

esp_gsp_err_t gsp_bridge_app_init(esp_gsp_handle_t ui)
{
    host.listener = listen_loopback(feed_port(), "audio (s16le mono 16 kHz)");
    for (int i = 0; i < LINE_CLIENTS; ++i) {
        host.lines[i].fd = -1;
    }
    const char *ai_env = getenv("CHAKRA_AI_PORT");
    host.ai_listener = listen_loopback(ai_env ? atoi(ai_env) : 8711, "lines (AI sound gate, camera)");
    chakra_core_config_t cfg = {.poll = poll_audio, .on_light = on_light, .on_settings = on_settings,
                                .on_close = on_close, .now_ms = now_ms, .on_cam_light = on_cam_light};
    chakra_settings_defaults(&cfg.settings);
    host.lamps = cfg.settings.lamps;
    host.settings = cfg.settings;
    chakra_detect_config_t dc;
    chakra_settings_detect(&cfg.settings, &dc);
    host.detect = chakra_detect_create(&dc);
    if (!host.detect) {
        return ESP_GSP_ERR_NO_MEM;
    }
    const esp_gsp_err_t e = chakra_core_create(ui, &cfg, &host.core);
    if (e == ESP_GSP_OK) {
        /* Row 0 is the screen lamp the feeder forwards to (--lamp; ticked by default), its address
         * from CHAKRA_LAMP_URL (the launcher sets it, the LAN address with --lamp-lan). Row 1 is the
         * lamp the feeder sets in Home Assistant, paired only when sim.sh got CHAKRA_LIGHT. The
         * others show what the board can drive once paired outside the app. */
        const char *name = getenv("CHAKRA_LAMP_NAME"), *url = getenv("CHAKRA_LAMP_URL"), *ha = getenv("CHAKRA_LIGHT");
        chakra_lamp_t lamps[CHAKRA_LAMPS] = {
            {.kind = CHAKRA_LAMP_SCREEN, .paired = true},
            {.kind = CHAKRA_LAMP_HA, .paired = ha && *ha},
            {.kind = CHAKRA_LAMP_HUE},
            {.kind = CHAKRA_LAMP_WIZ},
        };
        if (url && strncmp(url, "http://", 7) == 0) {
            url += 7;  // typed without it, browsers add it
        }
        snprintf(lamps[0].url, sizeof(lamps[0].url), "%s", url && *url ? url : "127.0.0.1:3310");
        size_t n = strlen(lamps[0].url);
        if (n && lamps[0].url[n - 1] == '/') {
            lamps[0].url[n - 1] = '\0';
        }
        snprintf(lamps[1].name, sizeof(lamps[1].name), "%s", name && *name ? name : "Living room LED strip");
        chakra_core_set_lamps(host.core, lamps, CHAKRA_LAMPS);
        chakra_core_set_camera_source(host.core, CHAKRA_SOURCE_NONE, "No camera yet");  // camera_live.py names its source
    }
    return e;
}

void gsp_bridge_app_deinit(esp_gsp_handle_t ui)
{
    (void)ui;
    fprintf(stderr, "chakrav: %lu hops analysed\n", host.hops);
    chakra_core_destroy(&host.core);
    chakra_detect_destroy(host.detect);
    if (host.client >= 0) {
        close(host.client);
    }
    if (host.listener >= 0) {
        close(host.listener);
    }
    for (int i = 0; i < LINE_CLIENTS; ++i) {
        if (host.lines[i].fd >= 0) {
            close(host.lines[i].fd);
        }
    }
    if (host.ai_listener >= 0) {
        close(host.ai_listener);
    }
}
