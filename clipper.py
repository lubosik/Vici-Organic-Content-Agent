"""
Clip pipeline: download YouTube -> ffmpeg cut -> Remotion render -> MP4.
Requires: yt-dlp, ffmpeg, Node.js + npx (for Remotion).
"""

import os
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from content_db import save_rendered_clip

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


def _get_video_duration(path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True, text=True, timeout=30
        )
        return float(json.loads(result.stdout)["format"]["duration"])
    except Exception:
        return 30.0


def download_and_cut(youtube_url: str, start_ts: str, end_ts: str, output_path: str) -> bool:
    """
    Download YouTube video and cut to timestamp range.
    start_ts/end_ts format: "MM:SS" or "HH:MM:SS"
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    tmp_full = output_path.replace(".mp4", "_full.mp4")

    print(f"[CLIPPER] Downloading: {youtube_url}")
    dl = subprocess.run([
        "yt-dlp",
        "-f", "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "-o", tmp_full,
        youtube_url
    ], capture_output=True, text=True, timeout=300)

    if dl.returncode != 0:
        print(f"[CLIPPER] yt-dlp failed: {dl.stderr[-500:]}")
        return False

    print(f"[CLIPPER] Cutting {start_ts} -> {end_ts}")
    cut = subprocess.run([
        "ffmpeg", "-y",
        "-i", tmp_full,
        "-ss", start_ts,
        "-to", end_ts,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        output_path
    ], capture_output=True, text=True, timeout=120)

    try:
        os.remove(tmp_full)
    except Exception:
        pass

    if cut.returncode != 0:
        print(f"[CLIPPER] ffmpeg cut failed: {cut.stderr[-500:]}")
        return False

    print(f"[CLIPPER] Cut saved: {output_path}")
    return True


def remotion_available() -> bool:
    """Check if Node.js and Remotion are available."""
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0 and (REMOTION_DIR / "package.json").exists()
    except Exception:
        return False


def render_with_remotion(clip_path: str, hook_text: str, output_path: str) -> bool:
    """Add Vici branding + hook text overlay via Remotion. Falls back to ffmpeg overlay if Remotion unavailable."""
    if not remotion_available():
        return _ffmpeg_overlay(clip_path, hook_text, output_path)

    # Copy clip into Remotion public dir
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
        print(f"[CLIPPER] Remotion rendering {duration_frames} frames...")
        # Install deps if needed
        if not (REMOTION_DIR / "node_modules").exists():
            subprocess.run(["npm", "install"], cwd=str(REMOTION_DIR), check=True, timeout=120)

        result = subprocess.run([
            "npx", "remotion", "render",
            "src/index.ts",
            "ViciClip",
            output_path,
            "--props", props_path,
            "--codec", "h264",
            "--log", "error",
        ], cwd=str(REMOTION_DIR), capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            print(f"[CLIPPER] Remotion failed: {result.stderr[-500:]}")
            return _ffmpeg_overlay(clip_path, hook_text, output_path)

        print(f"[CLIPPER] Remotion render complete: {output_path}")
        return True
    except subprocess.TimeoutExpired:
        print("[CLIPPER] Remotion timed out, falling back to ffmpeg overlay")
        return _ffmpeg_overlay(clip_path, hook_text, output_path)
    finally:
        try:
            os.unlink(props_path)
        except Exception:
            pass


def _ffmpeg_overlay(clip_path: str, hook_text: str, output_path: str) -> bool:
    """Fast ffmpeg fallback: add hook text + brand watermark without Remotion."""
    # Escape special chars for ffmpeg drawtext
    safe_hook = hook_text.replace("'", "\\'").replace(":", "\\:")[:80]
    brand_text = "VICIPEPTIDES.COM"
    duration_s = _get_video_duration(clip_path)

    filter_complex = (
        f"[0:v]"
        f"drawtext=text='{safe_hook}':fontsize=36:fontcolor=white:x=40:y=40:"
        f"shadowcolor=black:shadowx=2:shadowy=2:enable='between(t,0,{duration_s - 3})',"
        f"drawtext=text='{brand_text}':fontsize=20:fontcolor=0x00D4AA:x=w-280:y=h-60:"
        f"shadowcolor=black:shadowx=1:shadowy=1"
        f"[v]"
    )

    result = subprocess.run([
        "ffmpeg", "-y",
        "-i", clip_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac",
        output_path
    ], capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        print(f"[CLIPPER] ffmpeg overlay failed: {result.stderr[-300:]}")
        # Last resort: copy the cut clip without overlay
        shutil.copy(clip_path, output_path)
    return True


def produce_clip(youtube_url: str, start_ts: str, end_ts: str, hook_text: str) -> str | None:
    """
    Full pipeline: download -> cut -> render with Vici branding.
    Returns path to final MP4, or None on failure.
    """
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    work_dir = Path(f"output/clips/{date_str}")
    work_dir.mkdir(parents=True, exist_ok=True)

    cut_path = str(work_dir / "cut.mp4")
    final_path = str(work_dir / "final.mp4")

    if not download_and_cut(youtube_url, start_ts, end_ts, cut_path):
        return None

    render_with_remotion(cut_path, hook_text, final_path)
    final_path_resolved = final_path if Path(final_path).exists() else cut_path

    if final_path_resolved and Path(final_path_resolved).exists():
        try:
            save_rendered_clip(
                source_url=youtube_url,
                start_time=start_ts,
                end_time=end_ts,
                hook_text=hook_text,
                file_path=final_path_resolved,
            )
        except Exception as e:
            print(f"[CLIPPER] DB save failed: {e}")

    return final_path_resolved
