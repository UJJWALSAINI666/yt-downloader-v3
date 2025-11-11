import os, re, glob, uuid, shutil, tempfile, threading
from shutil import which
from flask import Flask, request, jsonify, send_file, render_template_string, abort
from yt_dlp import YoutubeDL

app = Flask(__name__)

# ---------- Cookies from ENV (optional) ----------
cookies_data = os.environ.get("COOKIES_TEXT", "").strip()
if cookies_data:
    with open("cookies.txt", "w", encoding="utf-8") as f:
        f.write(cookies_data)
COOKIEFILE = "cookies.txt" if os.path.exists("cookies.txt") else None

# ---------- FFmpeg detection ----------
def ffmpeg_path():
    # which() returns None if not found
    return which("ffmpeg")

HAS_FFMPEG = bool(ffmpeg_path())

# ---------- Minimal HTML (same UI) ----------
HTML = """<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Mobile Video Downloader</title>
<style>
  :root{--bg:#0b1220;--card:#0f172a;--text:#e6eefc;--muted:#9fb0c8;--border:#263143;--primary:#4da3ff;--accent:#48f7b7}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,Segoe UI,Roboto; padding:16px}
  .wrap{max-width:900px;margin:auto} .box{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:18px}
  h2{margin:0 0 8px} .lead{margin:0 0 12px;color:var(--muted)}
  form{display:grid;gap:12px} .grid{display:grid;gap:10px;grid-template-columns:1fr}
  @media (min-width:720px){.grid{grid-template-columns:2fr 1fr 1fr auto}}
  label{display:block;margin-bottom:6px;color:var(--muted);font-size:13px}
  input,select,button{width:100%;padding:12px;border-radius:12px;border:1px solid var(--border);background:transparent;color:var(--text)}
  button{border:none;background:var(--primary);color:#fff;font-weight:700;cursor:pointer}
  .progress{height:12px;background:#1b2436;border-radius:999px;overflow:hidden} .bar{height:100%;width:0;background:linear-gradient(90deg,var(--primary),var(--accent))}
  #msg{min-height:1.2em}
  .preview{display:none;margin:8px 0;border:1px solid var(--border);border-radius:14px;overflow:hidden}
  .preview-row{display:flex;gap:12px;padding:10px;align-items:center}
  .thumb{width:120px;aspect-ratio:16/9;border-radius:10px;object-fit:cover;background:#223}
  .meta{min-width:0}.title{font-weight:700;margin:0 0 4px}.sub{color:var(--muted);margin:0;font-size:13px}
</style></head><body>
<main class="wrap"><section class="box">
  <h2>📥 Mobile Video Downloader</h2><p class="lead">Paste link → preview → pick format → download.</p>

  <div id="preview" class="preview" aria-live="polite">
    <div class="preview-row">
      <img id="thumb" class="thumb" alt="Thumbnail">
      <div class="meta"><p id="pTitle" class="title"></p><p id="pSub" class="sub"></p></div>
    </div>
  </div>

  <form id="frm">
    <div class="grid">
      <div><label>Video URL</label><input id="url" placeholder="https://www.youtube.com/watch?v=..." required></div>
      <div><label>Format</label>
        <select id="format">
          <option value="mp4_720" data-need-ffmpeg="1">720p MP4</option>
          <option value="mp4_1080" data-need-ffmpeg="1">1080p MP4</option>
          <option value="mp4_best">Best MP4 (single file)</option>
          <option value="audio_mp3" data-need-ffmpeg="1">Audio MP3</option>
        </select>
      </div>
      <div><label>Filename (optional)</label><input id="name" placeholder="My video"></div>
      <div style="align-self:end"><button id="goBtn" type="submit">Download</button></div>
    </div>

    <div style="margin-top:12px" class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div id="bar" class="bar"></div></div>
    <p id="msg" role="status"></p>
    <p class="tip">Note: High quality merge needs FFmpeg. On free hosts we auto-install.</p>
  </form>
</section></main>

<script>
let job=null,HAS_FFMPEG=false;
const bar=document.getElementById("bar"), msg=document.getElementById("msg"), btn=document.getElementById("goBtn");
const preview=document.getElementById("preview"), pTitle=document.getElementById("pTitle"), pSub=document.getElementById("pSub"), thumb=document.getElementById("thumb");
fetch("/env").then(r=>r.json()).then(j=>{HAS_FFMPEG=j.ffmpeg; if(!HAS_FFMPEG){[...document.querySelectorAll("[data-need-ffmpeg='1']")].forEach(o=>o.disabled=true); msg.textContent="FFmpeg not found → using single-file formats.";}}).catch(()=>{});
function showPreview(d){ if(!d||!d.title){preview.style.display="none";return;}
  preview.style.display="block"; pTitle.textContent=d.title||""; pSub.textContent=[d.channel,d.duration_str].filter(Boolean).join(" • "); if(d.thumbnail) thumb.src=d.thumbnail;
}
document.getElementById("url").addEventListener("input", e=>{
  const v=e.target.value.trim(); if(!/^https?:\/\//i.test(v)){preview.style.display="none";return;}
  setTimeout(()=>{fetch("/info",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:v})})
  .then(r=>r.json()).then(j=>{if(j&&j.title) showPreview(j);}).catch(()=>{});}, 400);
});
document.getElementById("frm").addEventListener("submit", async (e)=>{
  e.preventDefault(); btn.disabled=true; msg.textContent="Starting…"; bar.style.width="0%";
  const url=document.getElementById("url").value.trim(), fmt=document.getElementById("format").value, name=document.getElementById("name").value.trim();
  try{
    const r=await fetch("/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url, format_choice:fmt, filename:name})});
    const j=await r.json(); if(!r.ok){throw new Error(j.error||"Failed");} job=j.job_id; poll();
  }catch(err){ msg.textContent=err.message||"Error"; btn.disabled=false; }
});
async function poll(){
  if(!job) return;
  try{
    const r=await fetch("/progress/"+job); if(r.status===404){msg.textContent="Job expired"; btn.disabled=false; job=null; return;}
    const p=await r.json(); const pct=Math.max(0,Math.min(100,p.percent||0)); bar.style.width=pct+"%"; document.querySelector(".progress").setAttribute("aria-valuenow", String(pct));
    if(p.status==="finished"){ msg.textContent="Done! Preparing file…"; btn.disabled=false; window.location="/fetch/"+job; job=null; return; }
    if(p.status==="error"){ msg.textContent=p.error||"Failed"; btn.disabled=false; job=null; return; }
    setTimeout(poll, 700);
  }catch(e){ msg.textContent="Network error"; btn.disabled=false; job=null; }
}
</script></body></html>"""

# ---------- Jobs ----------
JOBS = {}

class Job:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.tmp = tempfile.mkdtemp(prefix="mvd_")
        self.percent = 0
        self.status = "queued"
        self.file = None
        self.error = None
        JOBS[self.id] = self

# ---------- Helpers ----------
YTDLP_URL_RE = re.compile(r"^https?://", re.I)

def format_map_for_env():
    if HAS_FFMPEG:
        # FFmpeg available → we can merge
        return {
            "mp4_720"  : "bv*[ext=mp4][height<=720]+ba[ext=m4a]/b[ext=mp4][height<=720]/b",
            "mp4_1080" : "bv*[ext=mp4][height<=1080]+ba[ext=m4a]/b[ext=mp4][height<=1080]/b",
            "mp4_best" : "bv*+ba/b",
            "audio_mp3": "bestaudio/best"
        }
    else:
        # No merge → pick a single mp4 file
        return {
            "mp4_720"  : "b[ext=mp4][height<=720]/b[ext=mp4]",
            "mp4_1080" : "b[ext=mp4][height<=1080]/b[ext=mp4]",
            "mp4_best" : "b[ext=mp4]/b",
            "audio_mp3": None
        }

def run_download(job, url, fmt_key, filename):
    try:
        if not YTDLP_URL_RE.match(url):
            job.status="error"; job.error="Invalid URL"; return

        fmt = format_map_for_env().get(fmt_key)
        if fmt is None:
            job.status="error"; job.error="FFmpeg required for selected format"; return

        def hook(d):
            if d.get("status")=="downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
                job.percent = int((d.get("downloaded_bytes",0) * 100) / total)
            elif d.get("status")=="finished":
                job.percent = 100

        # Output path in tmp dir
        base = (filename.strip() if filename else "%(title)s").rstrip(".")
        out = os.path.join(job.tmp, base + ".%(ext)s")

        opts = {
            "format": fmt,
            "outtmpl": out,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [hook],
            "retries": 3,
            "fragment_retries": 3,
            "concurrent_fragment_downloads": 4,
            "paths": {"home": job.tmp, "temp": job.tmp},
            # Workaround for SABR/nsig by using Android client + UA
            "extractor_args": {"youtube": {"player_client": ["android"]}},
            "http_headers": {
                "User-Agent": "com.google.android.youtube/19.17.34 (Linux; U; Android 13) gzip"
            }
        }
        if COOKIEFILE:
            opts["cookiefile"] = COOKIEFILE
        if HAS_FFMPEG:
            opts["ffmpeg_location"] = ffmpeg_path()
            opts["merge_output_format"] = "mp4"
            if fmt_key == "audio_mp3":
                opts.setdefault("postprocessors", []).append(
                    {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}
                )

        with YoutubeDL(opts) as y:
            y.extract_info(url, download=True)

        files = glob.glob(os.path.join(job.tmp, "*"))
        if not files:
            raise RuntimeError("No file produced")
        job.file = max(files, key=os.path.getsize)
        job.status = "finished"

    except Exception as e:
        job.status="error"; job.error=str(e)[:300]

# ---------- Routes ----------
@app.post("/start")
def start():
    d = request.json or {}
    job = Job()
    threading.Thread(target=run_download, args=(job, d.get("url",""), d.get("format_choice","mp4_best"), d.get("filename","")), daemon=True).start()
    return jsonify({"job_id": job.id})

@app.post("/info")
def info():
    d = request.json or {}
    url = d.get("url","")
    try:
        opts = {"skip_download": True, "quiet": True, "noplaylist": True}
        if COOKIEFILE: opts["cookiefile"] = COOKIEFILE
        opts["extractor_args"] = {"youtube": {"player_client": ["android"]}}
        with YoutubeDL(opts) as y:
            info = y.extract_info(url, download=False)
        title = info.get("title",""); channel = info.get("uploader") or info.get("channel",""); thumb = info.get("thumbnail")
        dur = int(info.get("duration") or 0); dur_str = f"{dur//60}:{dur%60:02d}"
        return jsonify({"title":title,"thumbnail":thumb,"channel":channel,"duration_str":dur_str})
    except Exception:
        return jsonify({"error":"Preview failed"}), 400

@app.get("/progress/<id>")
def progress(id):
    j = JOBS.get(id)
    if not j: abort(404)
    return jsonify({"percent": j.percent, "status": j.status, "error": j.error})

@app.get("/fetch/<id>")
def fetch(id):
    j = JOBS.get(id)
    if not j or not j.file: abort(404)
    resp = send_file(j.file, as_attachment=True, download_name=os.path.basename(j.file))
    threading.Thread(target=lambda: (shutil.rmtree(j.tmp, ignore_errors=True), JOBS.pop(id, None)), daemon=True).start()
    return resp

@app.get("/env")
def env():
    return jsonify({"ffmpeg": HAS_FFMPEG})

@app.get("/")
def home():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
