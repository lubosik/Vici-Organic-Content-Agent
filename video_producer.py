"""
Full video production pipeline — no Node.js required.
Uses PIL (Pillow) to create slide frames + ffmpeg to stitch with voiceover.
Output: 1080x1920 (9:16) MP4
"""

import os
import json
import subprocess
import shutil
import tempfile
from pathlib import Path
from datetime import datetime


def _get_ffmpeg() -> str:
    """Get ffmpeg binary path."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass
    for p in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        if Path(p).exists():
            return p
    import glob
    nix = glob.glob("/nix/store/*/bin/ffmpeg")
    if nix:
        return nix[0]
    raise RuntimeError("ffmpeg not found. Install imageio-ffmpeg or system ffmpeg.")


def _get_vo_duration(vo_path: str) -> float:
    """Get voiceover duration in seconds."""
    try:
        ffmpeg = _get_ffmpeg()
        ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
        r = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", vo_path],
            capture_output=True, text=True, timeout=15
        )
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return 60.0


def _create_slide_image(text: str, subtitle: str, index: int, total: int,
                        compound: str, output_path: str, width=1080, height=1920):
    """Create a single slide PNG using Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise RuntimeError("Pillow not installed. Run: pip install Pillow")

    CREAM = (245, 243, 239)
    NEAR_BLACK = (26, 26, 26)
    TEAL = (0, 212, 170)

    img = Image.new("RGB", (width, height), CREAM)
    draw = ImageDraw.Draw(img)

    # Top accent bar
    draw.rectangle([60, 80, width - 60, 84], fill=TEAL)

    # Try to load system fonts, fall back to default
    def _load_font(path: str, size: int):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            return ImageFont.load_default()

    font_candidates_serif = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/Library/Fonts/Georgia Bold.ttf",
    ]
    font_candidates_regular = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/Library/Fonts/Georgia.ttf",
    ]

    def _first_existing(candidates: list, size: int):
        for p in candidates:
            if Path(p).exists():
                return _load_font(p, size)
        return ImageFont.load_default()

    font_small = _first_existing(font_candidates_regular, 28)
    font_main = _first_existing(font_candidates_serif, 58)
    font_sub = _first_existing(font_candidates_regular, 32)

    # VICI wordmark
    draw.text((60, 44), "VICI", font=font_small, fill=NEAR_BLACK)

    # Compound badge (top right)
    if compound:
        badge_text = compound.upper()[:16]
        draw.rectangle([width - 260, 44, width - 60, 76], fill=NEAR_BLACK)
        draw.text((width - 250, 50), badge_text, font=font_small, fill=TEAL)

    # Main text -- word-wrap at ~22 chars per line
    def wrap_text(t, max_chars=22):
        words = t.split()
        lines, current = [], []
        for w in words:
            if sum(len(x) + 1 for x in current) + len(w) <= max_chars:
                current.append(w)
            else:
                if current:
                    lines.append(" ".join(current))
                current = [w]
        if current:
            lines.append(" ".join(current))
        return lines

    # Vertical center for main content
    main_lines = wrap_text(text, max_chars=22)
    line_height = 80
    total_text_h = len(main_lines) * line_height
    start_y = (height - total_text_h) // 2 - 60

    # Left teal accent bar for non-hook slides
    if index > 0:
        draw.rectangle([60, start_y - 10, 68, start_y + total_text_h + 10], fill=TEAL)

    for i, line in enumerate(main_lines):
        draw.text((90 if index > 0 else 60, start_y + i * line_height),
                  line, font=font_main, fill=NEAR_BLACK)

    # Subtitle / CTA
    if subtitle:
        sub_lines = wrap_text(subtitle, max_chars=38)
        sub_y = start_y + total_text_h + 40
        for sl in sub_lines[:2]:
            draw.text((60, sub_y), sl, font=font_sub, fill=(100, 100, 100))
            sub_y += 44

    # Bottom accent line
    draw.rectangle([60, height - 100, width - 60, height - 98], fill=NEAR_BLACK)

    # CTA bottom
    cta = "Free research guide, link in bio. For research use only."
    draw.text((width // 2 - 320, height - 80), cta, font=font_small, fill=(140, 140, 140))

    img.save(output_path, "PNG")


def produce_topic_video(topic: str, compound: str, hook: str, key_data: str,
                        duration_s: int = 60, format_type: str = "Science Revelation") -> dict:
    """
    Full pipeline: script -> ElevenLabs -> PIL slides -> ffmpeg video.
    No Node.js/npm required.
    """
    from forge import generate_script
    from elevenlabs_client import generate_voiceover

    date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_dir = Path(f"output/videos/{date_str}")
    output_dir.mkdir(parents=True, exist_ok=True)

    topic_dict = {
        "id": f"trend_{date_str}",
        "title": topic,
        "compound": compound,
        "hook": hook,
        "format": format_type,
        "duration_s": duration_s,
        "score": 9,
        "key_data": key_data,
    }

    result = {"topic": topic, "dir": str(output_dir), "success": False}

    # 1. Script
    print(f"[VIDEO] Generating script: {topic}")
    try:
        script = generate_script(topic_dict)
        (output_dir / "script.txt").write_text(script)
        result["script"] = script
    except Exception as e:
        result["error"] = f"Script generation failed: {e}"
        return result

    # 2. Voiceover
    print("[VIDEO] Generating voiceover...")
    vo_path = str(output_dir / "voiceover.mp3")
    vo_ok = generate_voiceover(script, vo_path)
    result["voiceover_path"] = vo_path if vo_ok else None
    result["voiceover_ok"] = vo_ok

    if not vo_ok:
        result["error"] = "Voiceover generation failed"
        return result

    # 3. Get duration
    vo_duration = _get_vo_duration(vo_path)
    print(f"[VIDEO] Voiceover duration: {vo_duration:.1f}s")

    # 4. Extract key points from script (sentences > 30 chars, up to 5)
    sentences = [s.strip() for s in script.replace('\n', ' ').split('.') if len(s.strip()) > 30]
    key_points = sentences[:5] if sentences else [key_data[:100]]

    # 5. Build slide images
    print("[VIDEO] Creating slide images...")
    slides_dir = output_dir / "slides"
    slides_dir.mkdir(exist_ok=True)
    slide_paths = []

    slides = [(hook, "", 0)] + [(kp, "", i + 1) for i, kp in enumerate(key_points)]
    slide_duration = vo_duration / max(len(slides), 1)

    for i, (text, sub, idx) in enumerate(slides):
        slide_path = str(slides_dir / f"slide_{i:03d}.png")
        try:
            _create_slide_image(text[:120], sub, idx, len(slides), compound, slide_path)
            slide_paths.append((slide_path, slide_duration))
        except Exception as e:
            print(f"[VIDEO] Slide {i} failed: {e}")

    if not slide_paths:
        result["error"] = "Slide generation failed -- Pillow may not be installed"
        return result

    # 6. ffmpeg: stitch slides + voiceover
    print("[VIDEO] Rendering with ffmpeg...")
    try:
        ffmpeg = _get_ffmpeg()
    except RuntimeError as e:
        result["error"] = str(e)
        return result

    video_path = str(output_dir / "video.mp4")

    try:
        # Build input list
        cmd = [ffmpeg, "-y"]
        for slide_path, dur in slide_paths:
            cmd += ["-loop", "1", "-t", f"{dur:.2f}", "-i", slide_path]
        cmd += ["-i", vo_path]

        n = len(slide_paths)
        # Build filter: scale + concat
        filter_parts = []
        for i in range(n):
            filter_parts.append(f"[{i}:v]scale=1080:1920,setsar=1[v{i}]")

        concat_inputs = "".join(f"[v{i}]" for i in range(n))
        filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=0[vout]")
        filter_str = ";".join(filter_parts)

        cmd += [
            "-filter_complex", filter_str,
            "-map", "[vout]",
            "-map", f"{n}:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            video_path
        ]

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            print(f"[VIDEO] ffmpeg error: {r.stderr[-400:]}")
            result["error"] = f"ffmpeg render failed: {r.stderr[-100:]}"
            return result

        if Path(video_path).exists() and Path(video_path).stat().st_size > 10000:
            result["video_path"] = video_path
            result["success"] = True
            size_mb = Path(video_path).stat().st_size // 1024 // 1024
            print(f"[VIDEO] Done: {video_path} ({size_mb}MB)")
        else:
            result["error"] = "Output file missing or empty"

    except Exception as e:
        result["error"] = f"Render error: {e}"

    return result
