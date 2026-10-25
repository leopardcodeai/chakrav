#!/bin/sh
# What: starts the ESP-GSP simulator of the ChakraV app (chakra with a camera view) for the
#       ESP-Mosaico on the Mac, in the browser (the address it prints, usually http://127.0.0.1:3222/) or headless
#       with one dumped frame.
# Why:  the board is on order (24.10.2026); the UI, chakra_core.c and the detection run here
#       first, fed with real audio by tools/chakra_feed.py and camera frames by tools/camera_live.py.
#       No ESP-IDF needed for the preview.
# Pitfalls:
#   * --interactive needs the esp-gsp 1.5.1 component; it lives in the LeopardCode state folder
#     (downloaded from components.espressif.com), set through ESP_GSP_COMPONENT_DIR.
#   * Ports: audio 8710 (CHAKRA_FEED_PORT), lines 8711 (CHAKRA_AI_PORT: the AI sound gate and the
#     camera), so it never collides with the chakra app (8698, 8699). The preview takes 3222 or the
#     next free port; the "Preview:" line names it.
#   * The camera needs macOS's camera permission for the app that runs this; refused, camera_live.py
#     says so and waits. Frames live only in one overwritten temp file.
#   * Firmware builds need ESP-IDF master at the commit pinned in the workspace README.
# Usage:  ./sim.sh            browser preview for 10 min (CHAKRA_SIM_SECONDS=28800 for a day)
#         ./sim.sh --live     the same, with the Mac's microphone and AI sound gate
#                             (tools/chakra_feed.py mic --ai) and its camera (tools/camera_live.py)
#         ./sim.sh --demo     the same, with demo bowls and the drawn demo scene with its boxes
#         ./sim.sh --frame    headless, the scene alone: writes frame.png next to this script
#         ./sim.sh --dry-run  prints what it would run
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
WS=$(cd "$HERE/../../workspace" && pwd)
GSP="$HOME/Library/Application Support/LeopardCode/mosaico/esp-gsp-1.5.1"
URL=https://components-file.espressif.com/components/espressif/esp-gsp/1.5.1/espressif__esp-gsp-v1.5.1.zip
export CHAKRA_FEED_PORT="${CHAKRA_FEED_PORT:-8710}" CHAKRA_AI_PORT="${CHAKRA_AI_PORT:-8711}"
if [ "${1:-}" = "--dry-run" ]; then
  [ -d "$GSP" ] || echo "would download $URL to $GSP"
  echo "would run: python3 $WS/mosaico.py project sim --project $HERE --interactive (audio $CHAKRA_FEED_PORT, lines $CHAKRA_AI_PORT)"
  echo "  --live: python3 tools/chakra_feed.py mic --ai --wait; python3 tools/camera_live.py --wait"
  echo "  --demo: python3 tools/chakra_feed.py demo --rounds 50 --wait; python3 tools/camera_live.py --demo --demo-boxes --wait"
  exit 0
fi
if [ ! -d "$GSP" ]; then
  mkdir -p "$GSP" && curl -s -m 120 -o "$GSP.zip" "$URL" && unzip -q "$GSP.zip" -d "$GSP" && rm "$GSP.zip"
fi
cd "$WS"
if [ "${1:-}" = "--frame" ]; then
  python3 mosaico.py project sim --project "$HERE" --headless --frames 30 --dump-ppm "$HERE/frame.ppm"
  sips -s format png "$HERE/frame.ppm" --out "$HERE/frame.png" >/dev/null && rm "$HERE/frame.ppm"
  echo "$HERE/frame.png"
else
  echo "Browser: the Preview: line below (3222 or the next free port)"
  # The feeders connect once the simulator listens (they retry), and end with it.
  case "${1:-}" in
    --live)
      python3 "$HERE/tools/chakra_feed.py" mic --ai --wait &
      python3 "$HERE/tools/camera_live.py" --wait & ;;
    --demo)
      python3 "$HERE/tools/chakra_feed.py" demo --rounds 50 --wait &
      python3 "$HERE/tools/camera_live.py" --demo --demo-boxes --wait & ;;
  esac
  ESP_GSP_COMPONENT_DIR="$GSP" exec python3 mosaico.py project sim --project "$HERE" --interactive --duration "${CHAKRA_SIM_SECONDS:-600}"
fi
