"""
Full video production pipeline:
1. Get trending topic (from caller or DataForSEO)
2. Generate script
3. ElevenLabs voiceover
4. Remotion motion video (animated text on Vici brand background)
5. Return MP4 path
"""

import os
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

REMOTION_DIR = Path(__file__).parent / "remotion"


def produce_topic_video(topic: str, compound: str, hook: str, key_data: str,
                        duration_s: int = 60, format_type: str = "Science Revelation") -> dict:
    """
    Full pipeline: generate script -> ElevenLabs voiceover -> Remotion motion video.
    Returns dict with script, voiceover_path, video_path, success.
    """
    from forge import generate_script, generate_broll_list
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
        script_path = output_dir / "script.txt"
        script_path.write_text(script)
        result["script"] = script
        result["script_path"] = str(script_path)
    except Exception as e:
        result["error"] = f"Script generation failed: {e}"
        return result

    # 2. Voiceover
    print("[VIDEO] Generating voiceover...")
    vo_path = str(output_dir / "voiceover.mp3")
    try:
        vo_ok = generate_voiceover(script, vo_path)
    except Exception as e:
        print(f"[VIDEO] Voiceover error: {e}")
        vo_ok = False
    result["voiceover_path"] = vo_path if vo_ok else None
    result["voiceover_ok"] = vo_ok

    if not vo_ok:
        result["error"] = "Voiceover generation failed"
        return result

    # 3. Get voiceover duration for Remotion
    try:
        probe = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", vo_path
        ], capture_output=True, text=True, timeout=15)
        vo_duration = float(json.loads(probe.stdout)["format"]["duration"])
    except Exception:
        vo_duration = float(duration_s)

    # 4. Render with Remotion ViciTopicVideo composition
    print(f"[VIDEO] Rendering Remotion motion video ({vo_duration:.0f}s)...")
    video_path = str(output_dir / "video.mp4")

    # Extract 3-4 key points from script for text overlays
    lines = [line.strip() for line in script.split('.') if len(line.strip()) > 20]
    key_points = lines[:4] if len(lines) >= 4 else lines

    fps = 30
    duration_frames = round(vo_duration * fps)

    props = {
        "hookText": hook[:80],
        "keyPoints": key_points,
        "voiceover": "voiceover.mp3",
        "durationInFrames": duration_frames,
        "fps": fps,
        "compound": compound,
    }

    # Copy voiceover to Remotion public dir so staticFile() can serve it
    remotion_public = REMOTION_DIR / "public"
    remotion_public.mkdir(parents=True, exist_ok=True)
    shutil.copy(vo_path, remotion_public / "voiceover.mp3")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(props, f)
        props_path = f.name

    try:
        if not (REMOTION_DIR / "node_modules").exists():
            print("[VIDEO] Installing Remotion node_modules...")
            subprocess.run(["npm", "install"], cwd=str(REMOTION_DIR), check=True, timeout=120)

        render_result = subprocess.run([
            "npx", "remotion", "render",
            "src/index.ts", "ViciTopicVideo", video_path,
            "--props", props_path,
            "--codec", "h264",
            "--log", "error",
            "--timeout", "60000",
        ], cwd=str(REMOTION_DIR), capture_output=True, text=True, timeout=600)

        if render_result.returncode == 0 and Path(video_path).exists():
            result["video_path"] = video_path
            result["success"] = True
            print(f"[VIDEO] Done: {video_path}")
        else:
            stderr = render_result.stderr[-300:] if render_result.stderr else "no stderr"
            print(f"[VIDEO] Remotion render failed: {stderr}")
            result["error"] = f"Remotion render failed: {stderr}"
            result["success"] = False

    except Exception as e:
        result["error"] = f"Render error: {e}"
        result["success"] = False
    finally:
        try:
            os.unlink(props_path)
        except Exception:
            pass

    return result
