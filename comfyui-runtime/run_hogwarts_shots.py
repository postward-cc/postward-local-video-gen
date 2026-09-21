#!/usr/bin/env python3
"""
Multi-shot Hogwarts narrative orchestrator.

Sequentially generates 4 shots at 0.6 MP, each using the previous
shot's last frame as the next first_frame (I2V continuity). Then
concatenates via ffmpeg and runs the RTX VSR upscale.

Usage:
  ./run_hogwarts_shots.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_workflow  # noqa: E402

SHOTS = [
    {
        "name": "shot1-smile",
        "megapixels": 0.4,
        "duration": 3.0,
        "prompt": (
            "The exact girl from the first frame is Julia. Preserve her exact "
            "face, age, long brown hair, brown eyes, Gryffindor robe and identity. "
            "No new character, no replacement girl, no balloons, no unrelated "
            "objects. Julia sits at a wooden desk in a candlelit Hogwarts "
            "Transfiguration classroom. She smiles warmly at the camera, then "
            "turns her head slowly to look at the professor at the chalkboard. "
            "Preserve the classroom, owl and composition. Cinematic warm amber "
            "lighting, magical atmosphere, natural room ambience only, no dialogue, 24fps."
        ),
        "seed": 100,
        "first_frame": "julia-hogwarts.png",
    },
    {
        "name": "shot2-stands",
        "megapixels": 0.4,
        "duration": 3.0,
        "prompt": (
            "Continue from the exact previous frame. Keep the same Julia: same "
            "face, age, long brown hair, brown eyes, Gryffindor robe and identity. "
            "Do not create a different girl. No balloons and no unrelated scene. "
            "Julia pushes back her chair, stands up from her desk, gathers her "
            "books and walks toward the heavy stone classroom doorway. Preserve "
            "the Hogwarts Transfiguration classroom and warm candlelight. Natural ambience only, no dialogue, 24fps."
        ),
        "seed": 101,
        "first_frame": "last_frame.png",
    },
    {
        "name": "shot3-corridor",
        "megapixels": 0.4,
        "duration": 3.0,
        "prompt": (
            "Continue from the exact previous frame and preserve Julia's identity "
            "exactly: same face, age, long brown hair, brown eyes, Gryffindor robe. "
            "No different girl, no balloons, no unrelated subjects. Julia walks "
            "through a long Hogwarts stone corridor lined with lit torches and "
            "magical paintings. Dust motes drift in torchlight, arched stone "
            "ceiling, slow camera dolly following her. Warm cinematic lighting, natural ambience only, no dialogue, 24fps."
        ),
        "seed": 102,
        "first_frame": "last_frame.png",
    },
    {
        "name": "shot4-window",
        "megapixels": 0.4,
        "duration": 3.0,
        "prompt": (
            "Continue from the exact previous Hogwarts corridor frame. Preserve "
            "the same Julia and her visual identity until the camera reaches the "
            "window; do not introduce a different girl or balloons. The camera "
            "moves toward a tall arched window and reveals a breathtaking view "
            "of Hogwarts surroundings: Scottish highlands, vast green lake, "
            "distant mountains and Hogwarts castle towers. Golden-hour sunlight "
            "streams through the window. Cinematic wide shot, natural ambience only, no dialogue, 24fps."
        ),
        "seed": 103,
        "first_frame": "last_frame.png",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stage_frame(frame_name: str, target_name: str,
                comfyui_input: Path, shots_dir: Path) -> Path:
    """Copy the intended frame to a unique ComfyUI input name.

    Continuity frames must be sourced from the current run's shots directory
    before checking ComfyUI/input/. Reusing a generic `last_frame.png` from a
    previous run caused the Julia sequence to jump to an unrelated balloon.
    """
    search_paths = [
        shots_dir / frame_name,
        comfyui_input / frame_name,
        HERE / "outputs" / frame_name,
        HERE / "outputs" / "hogwarts" / frame_name,
    ]
    src = next((p for p in search_paths if p.exists()), None)
    if src is None:
        raise FileNotFoundError(f"first_frame not found in any of: {search_paths}")

    target = comfyui_input / target_name
    if src.resolve() != target.resolve():
        shutil.copy2(src, target)
    print(f"[stage] source={src} target={target} sha256={sha256_file(target)[:16]}")
    return target


def extract_last_frame(mp4: Path, out_png: Path) -> Path:
    """Extract the last frame from an MP4 using ffmpeg."""
    cmd = ["ffmpeg", "-y", "-sseof", "-0.1", "-i", str(mp4),
           "-frames:v", "1", "-update", "1", str(out_png)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_png


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots-dir", type=Path, default=HERE / "outputs" / "hogwarts-v2")
    ap.add_argument("--comfyui-input", type=Path, default=HERE / "ComfyUI" / "input")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--aspect-ratio", default="16:9 (Widescreen)")
    args = ap.parse_args()

    args.shots_dir.mkdir(parents=True, exist_ok=True)
    args.comfyui_input.mkdir(parents=True, exist_ok=True)
    summary = []
    manifest = []

    for i, shot in enumerate(SHOTS, 1):
        print(f"\n========== SHOT {i}/{len(SHOTS)}: {shot['name']} ==========")
        input_name = f"{shot['name']}-first.png"
        source = stage_frame(shot["first_frame"], input_name,
                             args.comfyui_input, args.shots_dir)

        workflow_json = args.shots_dir / f"{shot['name']}.json"
        subprocess.run([
            sys.executable, str(HERE / "build_upscale_workflow.py"),
            "--frame", str(source),
            "--aspect-ratio", args.aspect_ratio,
            "--megapixels", str(shot["megapixels"]),
            "--duration", str(shot["duration"]),
            "--turbo-steps", "8",
            "--seed", str(shot["seed"]),
            "--prompt", shot["prompt"],
            "--out", str(workflow_json),
        ], check=True)

        out_dir = args.shots_dir / shot["name"]
        rc = subprocess.run([
            sys.executable, str(HERE / "run_workflow.py"),
            str(workflow_json),
            "--megapixels", str(shot["megapixels"]),
            "--duration", str(shot["duration"]),
            "--turbo-steps", "8",
            "--seed", str(shot["seed"]),
            "--prompt", shot["prompt"],
            "--out-dir", str(out_dir),
            "--server", args.server,
            "--timeout", str(args.timeout),
        ]).returncode
        if rc != 0:
            print(f"!!! shot {i} failed with rc={rc}")
            return rc

        mp4s = sorted(out_dir.glob("*.mp4"),
                      key=lambda p: p.stat().st_mtime)
        if not mp4s:
            print(f"!!! no mp4 produced for shot {i}")
            return 1
        latest_mp4 = mp4s[-1]

        last_png = args.shots_dir / "last_frame.png"
        extract_last_frame(latest_mp4, last_png)
        dest = args.shots_dir / f"{shot['name']}.mp4"
        shutil.copy2(latest_mp4, dest)
        summary.append(dest)
        manifest.append({
            "shot": shot["name"],
            "prompt": shot["prompt"],
            "seed": shot["seed"],
            "first_frame": input_name,
            "first_frame_sha256": sha256_file(source),
            "output": str(dest),
            "output_sha256": sha256_file(dest),
            "megapixels": shot["megapixels"],
            "aspect_ratio": args.aspect_ratio,
        })
        print(f"[ok] shot {i} → {dest}")

    (args.shots_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )

    print("\n========== CONCATENATING ==========")
    concat_list = args.shots_dir / "concat.txt"
    with concat_list.open("w") as f:
        for mp4 in summary:
            f.write(f"file '{mp4.resolve()}'\n")
    final_mp4 = args.shots_dir / "julia-hogwarts-all.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-ar", "32000", "-movflags", "+faststart",
        str(final_mp4),
    ], check=True)
    print(f"[concat] → {final_mp4}")

    info = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate,duration,nb_frames",
        "-of", "csv=p=0", str(final_mp4),
    ]).decode().strip()
    print(f"[probe] {info}")
    print(f"\nDONE. Final concat: {final_mp4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
