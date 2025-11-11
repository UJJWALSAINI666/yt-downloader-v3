#!/usr/bin/env bash
set -e

# Show Python/pip versions
python -V || true
pip -V || true

# Ensure latest yt-dlp (nsig issues fix)
python -m pip install --upgrade --no-cache-dir yt-dlp

# Print versions for debugging
python - <<'PY'
import shutil, subprocess
print("yt-dlp version:")
subprocess.call(["yt-dlp", "--version"])
print("ffmpeg:", shutil.which("ffmpeg"))
PY

# Start Gunicorn (Flask app = app.py with 'app' variable)
# If your app object name or file is different, change below.
exec gunicorn app:app \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers 2 \
  --threads 8 \
  --timeout 360 \
  --keep-alive 60 \
  --access-logfile - \
  --error-logfile -
