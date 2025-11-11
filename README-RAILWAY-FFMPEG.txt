# Railway + FFmpeg (static) pack

This folder adds a static Linux AMD64 build of ffmpeg/ffprobe to your repo under `bin/`,
and a `start.sh` that (1) ensures execute bits, (2) exports PATH, and (3) starts your app.

## How to use

1) Copy the entire contents of this folder into the root of your Git repo.
   You should end up with:
   - bin/ffmpeg
   - bin/ffprobe
   - start.sh

2) Commit with executable flags (important on Git):
   ```bash
   git add bin/ffmpeg bin/ffprobe start.sh
   git update-index --chmod=+x bin/ffmpeg bin/ffprobe start.sh
   git commit -m "Add static ffmpeg + start.sh for Railway"
   git push
   ```

3) On Railway, set your **Start Command** to:
   ```bash
   bash start.sh
   ```

   (If you use a Procfile you can set:
   `web: bash start.sh`
   )

4) Ensure your app binds to `$PORT` (Gunicorn line in start.sh already does).

## Notes
- If your app file/module isn't `app:app`, edit the gunicorn line in `start.sh`.
- If you prefer Docker, add this to your Dockerfile instead of start.sh:
  ```Dockerfile
  COPY bin/ /app/bin/
  RUN chmod +x /app/bin/ffmpeg /app/bin/ffprobe
  ENV PATH="$PATH:/app/bin"
  ```
