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
        "duration": 5.0,
        "prompt": (
            "A young witch named Julia with long brown hair, wearing a black "
            "Gryffindor robe, sits at a wooden desk in a candlelit Hogwarts "
            "Transfiguration classroom. She smiles warmly at the camera, then "
            "turns her head slowly to look at the professor at the chalkboard. "
            "Cinematic warm amber lighting, magical atmosphere, 24fps."
        ),
        "seed": 100,
        # Shot 1 uses the user-supplied first frame
        "first_frame": "julia-hogwarts.png",
    },
    {
        "name": "shot2-stands",
        "megapixels": 0.4,
        "duration": 5.0,
        "prompt": (
            "Julia, the young witch with long brown hair, pushes back her chair "
            "and stands up from her wooden desk in a Hogwarts Transfiguration "
            "classroom. She gathers her books and walks toward the heavy stone "
            "doorway. Other students visible in soft background. Cinematic warm "
            "amber candlelight, 24fps."
        ),
        "seed": 101,
        # Shot 2 reads last_frame.png that run_workflow.py writes from shot 1
        "first_frame": "last_frame.png",
    },
    {
        "name": "shot3-corridor",
        "megapixels": 0.4,
        "duration": 5.0,
        "prompt": (
            "Wide cinematic shot of Julia, the young witch with long brown hair, "
            "walking down a long Hogwarts stone corridor lined with lit torches "
            "and magical paintings. Dust motes drift in the torchlight. Arched "
            "stone ceiling. Slow camera dolly following her. 24fps, warm cinematic."
        ),
        "seed": 102,
        "first_frame": "last_frame.png",
    },
    {
        "name": "shot4-window",
        "megapixels": 0.4,
        "duration": 5.0,
        "prompt": (
            "Breathtaking wide shot from inside a Hogwarts stone corridor, "
            "looking out through a tall arched window. The view shows the "
            "Scottish highlands — vast green lake, distant mountains, the "
            "towers of Hogwarts castle in the foreground. Golden hour sunlight "
            "streaming in through the window. Magical atmosphere, 24fps, "
            "cinematic wide shot."
        ),
        "seed": 103,
        "first_frame": "last_frame.png",
    },
]


def stage_frame(frame_name: str, comfyui_input: Path, shots_dir: Path) -> Path:
    """Ensure the named frame is in comfyui_input/. Returns its absolute path."""
    search_paths = [
        comfyui_input / frame_name,     # already staged
        shots_dir / frame_name,          # last_frame.png produced here
        HERE / "outputs" / frame_name,   # older outputs
        HERE / "outputs" / "hogwarts" / frame_name,
    ]
    src = next((p for p in search_paths if p.exists()), None)
    if src is None:
        raise FileNotFoundError(f"first_frame not found in any of: {search_paths}")
    target = comfyui_input / frame_name
    if src.resolve() != target.resolve():
        shutil.copy2(src, target)
        print(f"[stage] {src} → {target}")
    return target


def extract_last_frame(mp4: Path, out_png: Path) -> Path:
    """Extract the last frame from an MP4 using ffmpeg."""
    cmd = ["ffmpeg", "-y", "-sseof", "-0.1", "-i", str(mp4),
           "-frames:v", "1", "-update", "1", str(out_png)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_png


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots-dir", type=Path, default=HERE / "outputs" / "hogwarts")
    ap.add_argument("--comfyui-input", type=Path, default=HERE / "ComfyUI" / "input")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    args.shots_dir.mkdir(parents=True, exist_ok=True)
    args.comfyui_input.mkdir(parents=True, exist_ok=True)

    summary = []
    for i, shot in enumerate(SHOTS, 1):
        print(f"\n========== SHOT {i}/{len(SHOTS)}: {shot['name']} ==========")
        # Stage first_frame for ComfyUI's LoadImage
        stage_frame(shot["first_frame"], args.comfyui_input, args.shots_dir)

        # Build the I2V workflow JSON
        workflow_json = args.shots_dir / f"{shot['name']}.json"
        subprocess.run([
            sys.executable, str(HERE / "build_upscale_workflow.py"),
            "--frame", str(args.comfyui_input / shot["first_frame"]),
            "--megapixels", str(shot["megapixels"]),
            "--duration", str(shot["duration"]),
            "--turbo-steps", "8",
            "--seed", str(shot["seed"]),
            "--prompt", shot["prompt"],
            "--out", str(workflow_json),
        ], check=True)

        # Run the workflow
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

        # Find the MP4 in the output dir
        mp4s = sorted(out_dir.glob("*.mp4"))
        if not mp4s:
            print(f"!!! no mp4 produced for shot {i}")
            return 1
        latest_mp4 = mp4s[-1]

        # Save last_frame for next shot
        last_png = args.shots_dir / "last_frame.png"
        extract_last_frame(latest_mp4, last_png)

        # Copy the mp4 to shots_dir for easy concat later
        dest = args.shots_dir / f"{shot['name']}.mp4"
        shutil.copy2(latest_mp4, dest)
        summary.append(dest)
        print(f"[ok] shot {i} → {dest}")

    # --- Concatenate ---
    print("\n========== CONCATENATING ==========")
    concat_list = args.shots_dir / "concat.txt"
    with open(concat_list, "w") as f:
        for mp4 in summary:
            f.write(f"file '{mp4.resolve()}'\n")
    final_mp4 = args.shots_dir / "julia-hogwarts-all.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", str(final_mp4),
    ], check=True)
    print(f"[concat] → {final_mp4}")

    # --- Probe final ---
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
