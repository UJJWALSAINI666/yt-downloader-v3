#!/usr/bin/env bash
set -e

# Ensure ffmpeg binaries are executable
chmod +x "$(dirname "$0")/bin/ffmpeg" || true
chmod +x "$(dirname "$0")/bin/ffprobe" || true

# Add local bin to PATH (Railway project root is /app)
export PATH="$PATH:$(pwd)/bin"

# Optional: tell yt-dlp/ffmpeg where to look (usually PATH is enough)
export FFMPEG_BINARY=ffmpeg
export FFPROBE_BINARY=ffprobe

# Start your app (pick one):
if command -v gunicorn >/dev/null 2>&1 && [ -f "app.py" ]; then
  # Change the module:app if your Flask entrypoint is different
  exec gunicorn app:app --bind 0.0.0.0:${PORT:-8080} --workers ${WORKERS:-1} --threads ${THREADS:-4} --timeout ${TIMEOUT:-120}
elif [ -f "app.py" ]; then
  exec python app.py
else
  echo "Cannot find app.py or gunicorn. Please adjust start.sh to your project."
  exit 1
fi
