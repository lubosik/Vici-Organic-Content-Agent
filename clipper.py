"""
Clip pipeline: Apify download → ffmpeg cut → Remotion 16:9 overlay → send to Telegram.
Primary: Apify scraper_one/yt-downloader (no system yt-dlp needed)
Fallback: yt-dlp
Output: 1920x1080 (16:9) MP4
"""

import os
import json
import shutil
import subprocess
import tempfile
import requests
from pathlib import Path
from datetime import datetime
from apify_client import ApifyClient

REMOTION_DIR = Path(__file__).parent / "remotion"
PUBLIC_DIR = REMOTION_DIR / "public"


def _ts_to_seconds(ts: str) -> float:
    """Convert MM:SS or HH:MM:SS to seconds."""
    parts = ts.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return float(ts)


def _ffmpeg_path() -> str:
    """Find ffmpeg — checks PATH, common locations, and Remotion's bundled copy."""
    import shutil as sh
    if sh.which("ffmpeg"):
        return "ffmpeg"
    for p in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/nix/store/*/bin/ffmpeg"]:
        import glob
        matches = glob.glob(p)
        if matches:
            return matches[0]
    # Try Remotion's bundled ffmpeg
    try:
        result = subprocess.run(
            ["node", "-e", "const {getRemotionEnvironment} = require('remotion'); console.log('ok')"],
            cwd=str(REMOTION_DIR), capture_output=True, text=True, timeout=10
        )
        # Remotion stores ffmpeg in node_modules
        bundled = list(Path(REMOTION_DIR / "node_modules").rglob("ffmpeg"))
        bundled = [b for b in bundled if b.is_file() and os.access(b, os.X_OK)]
        if bundled:
            return str(bundled[0])
    except Exception:
        pass
    return "ffmpeg"  # Let it fail with a clear message


def _get_video_duration(path: str) -> float:
    """Get video duration in seconds via ffprobe."""
    ffmpeg = _ffmpeg_path()
    ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
    try:
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True, text=True, timeout=30
        )
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception:
        return 30.0


def download_via_apify(youtube_url: str, output_path: str) -> bool:
    """Download YouTube video via Apify scraper_one/yt-downloader."""
    try:
        client = ApifyClient(os.getenv("APIFY_API_KEY"))
        print(f"[CLIPPER] Downloading via Apify: {youtube_url}")
        run = client.actor("scraper_one/yt-downloader").call(
            run_input={"url": youtube_url, "quality": "720p"},
            timeout_secs=300
        )
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if not items:
            print("[CLIPPER] Apify returned no items")
            return False

        download_url = items[0].get("downloadUrl", "")
        if not download_url:
            print("[CLIPPER] No downloadUrl in Apify response")
            return False

        print(f"[CLIPPER] Downloading from URL: {download_url[:80]}...")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(download_url, stream=True, timeout=300)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

        size = Path(output_path).stat().st_size
        print(f"[CLIPPER] Downloaded {size // 1024 // 1024}MB to {output_path}")
        return size > 100_000  # At least 100KB
    except Exception as e:
        print(f"[CLIPPER] Apify download failed: {e}")
        return False


def download_via_ytdlp(youtube_url: str, output_path: str) -> bool:
    """Fallback: download via yt-dlp."""
    try:
        import yt_dlp
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        ydl_opts = {
            "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
            "merge_output_format": "mp4",
            "outtmpl": output_path,
            "quiet": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        return Path(output_path).exists() and Path(output_path).stat().st_size > 100_000
    except Exception as e:
        print(f"[CLIPPER] yt-dlp fallback failed: {e}")
        return False


def cut_clip(full_video_path: str, start_ts: str, end_ts: str, output_path: str) -> bool:
    """Cut a clip from start_ts to end_ts using ffmpeg."""
    ffmpeg = _ffmpeg_path()
    print(f"[CLIPPER] Cutting {start_ts} → {end_ts}")
    result = subprocess.run([
        ffmpeg, "-y",
        "-i", full_video_path,
        "-ss", start_ts,
        "-to", end_ts,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        output_path
    ], capture_output=True, text=True, timeout=180)

    if result.returncode != 0:
        print(f"[CLIPPER] ffmpeg cut failed: {result.stderr[-500:]}")
        return False
    print(f"[CLIPPER] Cut saved: {output_path}")
    return True


def remotion_available() -> bool:
    """Check if Remotion is available for branded overlay."""
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0 and (REMOTION_DIR / "package.json").exists()
    except Exception:
        return False


def render_overlay(clip_path: str, hook_text: str, output_path: str) -> bool:
    """Add Vici branding via Remotion (16:9). Falls back to ffmpeg text overlay."""
    if not remotion_available():
        return _ffmpeg_text_overlay(clip_path, hook_text, output_path)

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    clip_filename = "current_clip.mp4"
    shutil.copy(clip_path, PUBLIC_DIR / clip_filename)

    duration_s = _get_video_duration(clip_path)
    fps = 30
    duration_frames = round(duration_s * fps)

    props = {
        "src": clip_filename,
        "hookText": hook_text,
        "durationInFrames": duration_frames,
        "fps": fps,
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(props, f)
        props_path = f.name

    try:
        if not (REMOTION_DIR / "node_modules").exists():
            subprocess.run(["npm", "install"], cwd=str(REMOTION_DIR), check=True, timeout=120)

        print(f"[CLIPPER] Remotion rendering 16:9 overlay...")
        result = subprocess.run([
            "npx", "remotion", "render",
            "src/index.ts", "ViciClip", output_path,
            "--props", props_path,
            "--codec", "h264",
            "--log", "error",
        ], cwd=str(REMOTION_DIR), capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            print(f"[CLIPPER] Remotion failed: {result.stderr[-300:]}")
            return _ffmpeg_text_overlay(clip_path, hook_text, output_path)

        print(f"[CLIPPER] Remotion render complete")
        return True
    except Exception as e:
        print(f"[CLIPPER] Remotion error: {e}")
        return _ffmpeg_text_overlay(clip_path, hook_text, output_path)
    finally:
        try:
            os.unlink(props_path)
        except Exception:
            pass


def _ffmpeg_text_overlay(clip_path: str, hook_text: str, output_path: str) -> bool:
    """Fast ffmpeg fallback: burn hook text + brand watermark onto 16:9 clip."""
    ffmpeg = _ffmpeg_path()
    safe_hook = hook_text.replace("'", "").replace(":", " ")[:72]
    brand = "VICIPEPTIDES.COM"

    filter_str = (
        f"drawtext=text='{safe_hook}':fontsize=44:fontcolor=white"
        f":x=(w-text_w)/2:y=80:shadowcolor=black:shadowx=2:shadowy=2,"
        f"drawtext=text='{brand}':fontsize=24:fontcolor=0x00D4AA"
        f":x=w-280:y=h-60:shadowcolor=black:shadowx=1:shadowy=1"
    )

    result = subprocess.run([
        ffmpeg, "-y",
        "-i", clip_path,
        "-vf", filter_str,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac",
        output_path
    ], capture_output=True, text=True, timeout=180)

    if result.returncode != 0:
        print(f"[CLIPPER] ffmpeg overlay failed: {result.stderr[-200:]}")
        shutil.copy(clip_path, output_path)
    return True


def produce_clip(youtube_url: str, start_ts: str, end_ts: str, hook_text: str) -> str | None:
    """
    Full pipeline: download → cut → 16:9 Vici-branded overlay.
    Returns path to final MP4, or None on failure.
    """
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    work_dir = Path(f"output/clips/{date_str}")
    work_dir.mkdir(parents=True, exist_ok=True)

    full_path = str(work_dir / "full.mp4")
    cut_path = str(work_dir / "cut.mp4")
    final_path = str(work_dir / "final.mp4")

    # Download
    ok = download_via_apify(youtube_url, full_path)
    if not ok:
        print("[CLIPPER] Apify failed, trying yt-dlp...")
        ok = download_via_ytdlp(youtube_url, full_path)
    if not ok:
        return None

    # Cut
    if not cut_clip(full_path, start_ts, end_ts, cut_path):
        return None

    # Clean up full download to save disk
    try:
        os.remove(full_path)
    except Exception:
        pass

    # Overlay
    render_overlay(cut_path, hook_text, final_path)

    result_path = final_path if Path(final_path).exists() else cut_path
    if Path(result_path).exists():
        try:
            from content_db import save_rendered_clip
            save_rendered_clip(
                source_url=youtube_url,
                start_time=start_ts,
                end_time=end_ts,
                hook_text=hook_text,
                file_path=result_path,
            )
        except Exception:
            pass
        return result_path
    return None
