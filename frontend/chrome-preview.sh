#!/usr/bin/env bash
# Builds the app (when needed), serves the production build, and opens it in Chrome.
# Usage:  npm run chrome          (or:  bash chrome-preview.sh)
set -e
cd "$(dirname "$0")"

# Rebuild if dist is missing or stale
if [ ! -f dist/index.html ] || [ -n "$(find src index.html vite.config.js package.json -newer dist/index.html 2>/dev/null)" ]; then
  echo "[chrome] building production bundle..."
  npm run build
fi

PORT="${PORT:-4173}"
URL="http://localhost:${PORT}"

# Start the preview server (stop it when you exit with Ctrl+C)
npx vite preview --port "$PORT" --strictPort &
PREVIEW_PID=$!
trap 'kill $PREVIEW_PID 2>/dev/null || true' EXIT INT TERM

echo "[chrome] waiting for $URL ..."
for _ in $(seq 1 40); do
  curl -sf "$URL" >/dev/null 2>&1 && break
  sleep 0.25
done
if ! curl -sf "$URL" >/dev/null 2>&1; then
  echo "[chrome] preview server failed to start" >&2
  exit 1
fi
echo "[chrome] serving dist at $URL"

open_chrome() {
  # 1) Windows Chrome from WSL (this machine lives under /mnt/c)
  for exe in "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" \
             "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe"; do
    if [ -x "$exe" ]; then
      echo "[chrome] opening Windows Chrome"
      "$exe" --new-window "$URL" >/dev/null 2>&1 &
      return 0
    fi
  done
  # 2) Linux Chrome / Chromium
  for bin in google-chrome google-chrome-stable chromium chromium-browser; do
    if command -v "$bin" >/dev/null 2>&1; then
      echo "[chrome] opening $bin"
      "$bin" --new-window "$URL" >/dev/null 2>&1 &
      return 0
    fi
  done
  # 3) Fall back to the default browser
  if command -v wslview >/dev/null 2>&1; then wslview "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
  fi
  echo "[chrome] open this URL manually: $URL"
}

open_chrome
echo "[chrome] press Ctrl+C to stop the preview server"
wait $PREVIEW_PID