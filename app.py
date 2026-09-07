"""
Audio-Video Sync — FastAPI Backend v3
Deploy : Render (backend)  |  Local: python run_server.py
"""
import os, re, shutil, subprocess, tempfile, uuid, urllib.parse, unicodedata, sys
from pathlib import Path
from typing import List, Optional

import numpy as np
import scipy.signal as spsig
import soundfile as sf
import imageio_ffmpeg
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

def get_resource_path(relative_name: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_name
    return Path(__file__).parent / relative_name

def get_ffmpeg_binary() -> str:
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        if hasattr(sys, "_MEIPASS"):
            for p in Path(sys._MEIPASS).glob("**/ffmpeg*.exe"):
                return str(p)
        for p in Path(__file__).parent.glob("**/ffmpeg*.exe"):
            return str(p)
        return "ffmpeg"

_FFMPEG  = get_ffmpeg_binary()
TEMP_DIR = Path(tempfile.gettempdir()) / "av_sync_web"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

SR       = 16000
HOP_MS   = 10
FRAME_MS = 40

REJECT_CORR  = 0.08
REJECT_VOTES = 5
WARN_CORR    = 0.30
WARN_VOTES   = 15

# Supported output formats: ext -> (ffmpeg codec, mime, ffmpeg_format)
OUTPUT_FORMATS = {
    "m4a":  ("aac",         "audio/mp4",  "ipod"),
    "mp3":  ("libmp3lame",  "audio/mpeg", "mp3"),
    "wav":  ("pcm_s16le",   "audio/wav",  "wav"),
    "flac": ("flac",        "audio/flac", "flac"),
    "opus": ("libopus",     "audio/ogg",  "opus"),
    "aac":  ("aac",         "audio/aac",  "adts"),
}
DEFAULT_BITRATE = {"m4a": "256k", "mp3": "320k", "aac": "256k", "opus": "128k"}

app = FastAPI(title="AV Sync", version="3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


# ─────────────────────────────────────────────────────────────
# DSP
# ─────────────────────────────────────────────────────────────
def probe_dur(p: Path) -> float:
    r = subprocess.run([_FFMPEG, "-i", str(p)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr)
    if not m:
        raise RuntimeError(f"Cannot read duration: {p.name}")
    return int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))


def extract_mono(p: Path, max_d: float = None) -> np.ndarray:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        cmd = [_FFMPEG, "-y", "-i", str(p)]
        if max_d:
            cmd += ["-t", str(max_d)]
        cmd += ["-vn", "-ac", "1", "-ar", str(SR), tmp]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode(errors="replace")[-400:])
        data, _ = sf.read(tmp, dtype="float32", always_2d=False)
        return data.mean(axis=1) if data.ndim > 1 else data
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def spectral_flux(sig: np.ndarray, lo=300, hi=5000):
    hop = int(HOP_MS * SR / 1000)
    win = int(FRAME_MS * SR / 1000)
    sos = spsig.butter(4, [lo, hi], btype="bandpass", fs=SR, output="sos")
    sf2 = spsig.sosfiltfilt(sos, sig.astype(np.float64))
    _, _, Z = spsig.stft(sf2, fs=SR, nperseg=win, noverlap=win - hop)
    fl = np.sum(np.maximum(np.diff(np.abs(Z), axis=1), 0), axis=0)
    return np.arange(len(fl)) * hop / SR, fl.astype(np.float32)


def pick_peaks(times, flux, n=200):
    hop_s = float(times[1] - times[0]) if len(times) > 1 else HOP_MS / 1000
    md = max(1, int(0.06 / hop_s))
    q75, q25 = np.percentile(flux, [75, 25])
    thr = np.median(flux) + 1.5 * (q75 - q25)
    pks, _ = spsig.find_peaks(flux, height=thr, distance=md)
    if len(pks) > n:
        pks = pks[np.argsort(flux[pks])[-n:]]
    return times[pks]


def vote(pv, pa, extra, buf=12.0):
    mn, mx = -buf, max(extra, 0) + buf
    ds = [pa_ - pv_ for pv_ in pv for pa_ in pa if mn <= pa_ - pv_ <= mx]
    if not ds:
        return 0.0, 0
    ds = np.array(ds)
    bw = 0.02
    bins = np.arange(mn, mx + bw, bw)
    cts, edges = np.histogram(ds, bins=bins)
    ctr = (edges[:-1] + edges[1:]) / 2
    return float(ctr[int(np.argmax(cts))]), int(cts.max())


def refine(fv, fa, coarse):
    hs = HOP_MS / 1000
    nv, wf, cf = len(fv), int(0.5 / hs), int(coarse / hs)
    bc, bo = -1.0, coarse
    for dk in range(-wf, wf + 1):
        k = cf + dk
        sv = fv[-k:] if k < 0 else fv
        sa = fa[:nv + k] if k < 0 else fa[k:k + nv]
        n = min(len(sv), len(sa))
        if n < 20:
            continue
        sv, sa = sv[:n], sa[:n]
        ma, mb = sv.mean(), sa.mean()
        num = float(np.sum((sv - ma) * (sa - mb)))
        den = float(np.sqrt(np.sum((sv - ma)**2) * np.sum((sa - mb)**2))) + 1e-12
        c = num / den
        if c > bc:
            bc, bo = c, k * hs
    return bo, bc


def render_audio(src: Path, out: Path, offset: float, dur: float,
                 fmt: str) -> bool:
    codec, _, ffmt = OUTPUT_FORMATS[fmt]
    bitrate = DEFAULT_BITRATE.get(fmt)
    br_args = ["-b:a", bitrate] if bitrate else []

    if offset >= 0:
        # trim from start
        cmd = [_FFMPEG, "-y",
               "-ss", f"{offset:.6f}", "-i", str(src),
               "-t", f"{dur:.6f}",
               "-vn", "-c:a", codec] + br_args + ["-f", ffmt, str(out)]
    else:
        # pad silence at front
        delay_ms = abs(offset) * 1000
        cmd = [_FFMPEG, "-y", "-i", str(src),
               "-af", f"adelay={delay_ms:.1f}:all=1",
               "-t", f"{dur:.6f}",
               "-vn", "-c:a", codec] + br_args + ["-f", ffmt, str(out)]
    return subprocess.run(cmd, capture_output=True).returncode == 0


# ─────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────
@app.post("/api/sync")
async def sync_audio(
    video: UploadFile = File(...),
    audio: UploadFile = File(...),
    output_format: str = Form(default=""),
):
    sid = str(uuid.uuid4())[:8]
    d   = TEMP_DIR / sid
    d.mkdir(parents=True, exist_ok=True)

    safe_video_name = Path(video.filename or "video.mp4").name
    safe_audio_name = Path(audio.filename or "audio.m4a").name
    vp  = d / safe_video_name
    ap  = d / safe_audio_name
    logs: List[str] = []

    try:
        with open(vp, "wb") as f: shutil.copyfileobj(video.file, f)
        with open(ap, "wb") as f: shutil.copyfileobj(audio.file, f)

        # Resolve output format
        raw_ext = output_format.strip().lower().lstrip(".")
        if raw_ext not in OUTPUT_FORMATS:
            # default: same as input
            raw_ext = ap.suffix.lower().lstrip(".")
        if raw_ext not in OUTPUT_FORMATS:
            raw_ext = "m4a"
        fmt = raw_ext
        out = d / f"synced_{ap.stem}.{fmt}"

        logs.append(f"Input: {vp.name} + {ap.name} | Output format: {fmt}")

        dur_v = probe_dur(vp)
        dur_a = probe_dur(ap)
        extra = dur_a - dur_v
        logs.append(f"Video: {dur_v:.2f}s | Audio: {dur_a:.2f}s")

        sv = extract_mono(vp, dur_v)
        sa = extract_mono(ap, dur_a)

        if len(sv) < SR or len(sa) < SR:
            raise ValueError("File quá ngắn (cần ít nhất 1 giây).")

        tv, fv = spectral_flux(sv)
        ta, fa = spectral_flux(sa)
        pv = pick_peaks(tv, fv)
        pa = pick_peaks(ta, fa)
        logs.append(f"Peaks: video={len(pv)}, audio={len(pa)}")

        coarse, votes = vote(pv, pa, extra)
        logs.append(f"Voting: {coarse:+.3f}s ({votes} votes)")

        if votes < REJECT_VOTES:
            tv2, fv2 = spectral_flux(sv, 150, 8000)
            ta2, fa2 = spectral_flux(sa, 150, 8000)
            c2, v2 = vote(pick_peaks(tv2, fv2), pick_peaks(ta2, fa2), extra)
            if v2 > votes:
                coarse, votes, fv, fa = c2, v2, fv2, fa2
                logs.append(f"Wide-band retry: {coarse:+.3f}s ({votes} votes)")

        offset, corr = refine(fv, fa, coarse)
        logs.append(f"Final: {offset:+.4f}s | corr={corr:.4f}")

        if votes < REJECT_VOTES or corr < REJECT_CORR:
            return JSONResponse({"status": "too_noisy",
                                 "votes": votes,
                                 "correlation": round(corr, 4),
                                 "logs": logs})

        # Silence check
        usable = dur_a - offset if offset >= 0 else dur_a + abs(offset)
        silence_added = usable < dur_v
        silence_sec   = round(max(dur_v - usable, 0), 2) if silence_added else 0.0

        ok = render_audio(ap, out, offset, dur_v, fmt)
        if not ok or not out.exists():
            raise RuntimeError("FFmpeg render failed.")

        sz = round(out.stat().st_size / (1024 * 1024), 2)
        logs.append(f"Done: {out.name} ({sz} MB)")

        return JSONResponse({
            "status":         "success",
            "session_id":     sid,
            "filename":       out.name,
            "output_format":  fmt,
            "offset_sec":     round(offset, 3),
            "correlation":    round(corr, 4),
            "votes":          votes,
            "video_dur":      round(dur_v, 2),
            "audio_dur":      round(dur_a, 2),
            "silence_added":  silence_added,
            "silence_sec":    silence_sec,
            "low_confidence": corr < WARN_CORR or votes < WARN_VOTES,
            "logs":           logs,
            "download_url":   f"/api/download/{sid}/{urllib.parse.quote(out.name)}",
        })

    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e), "logs": logs},
                            status_code=500)


@app.get("/api/download/{sid}/{filename}")
async def download(sid: str, filename: str):
    s_dir = TEMP_DIR / sid
    if not s_dir.exists():
        raise HTTPException(404, "Session not found.")

    p = s_dir / filename
    if not p.exists():
        norm_target = unicodedata.normalize("NFC", filename)
        for f in s_dir.iterdir():
            if unicodedata.normalize("NFC", f.name) == norm_target:
                p = f
                break
        else:
            candidates = [f for f in s_dir.iterdir() if f.is_file() and f.name.startswith("synced_")]
            if candidates:
                p = candidates[0]
            else:
                raise HTTPException(404, "File not found.")

    real_filename = p.name
    _, mime, _ = OUTPUT_FORMATS.get(p.suffix.lstrip(".").lower(), ("", "application/octet-stream", ""))
    
    # RFC 5987 UTF-8 header encoding (must be ASCII safe for latin-1 HTTP headers)
    quoted_name = urllib.parse.quote(real_filename)
    return FileResponse(
        path=p,
        media_type=mime,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted_name}"}
    )


@app.get("/", response_class=HTMLResponse)
async def ui():
    idx = get_resource_path("index.html")
    if not idx.exists():
        idx = Path("index.html")
    return HTMLResponse(idx.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
