#!/usr/bin/env python3
"""
Submit the RTX Video Super Resolution workflow directly via the ComfyUI API.

Builds the workflow JSON inline rather than going through saved-format
conversion, because the RTXVideoSuperResolution node has a DynamicCombo
input that's awkward to round-trip through saved-format widgets.

Usage:
  ./submit_rtx_vsr.py --input outputs/0.6mp-upscale/MiniMax_H3_00003_.mp4 \
                      --output-dir outputs/rtx-vsr \
                      --multiplier 2 \
                      --quality ULTRA
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from urllib import request, error


def build_workflow(mp4_path: Path, *, multiplier: float = 2.0,
                   quality: str = "ULTRA", fps: int = 24,
                   filename_prefix: str = "video/RTX_VSR") -> dict:
    return {
        # LoadVideo reads from ComfyUI/input/ — caller ensures the file is there
        "6": {
            "class_type": "LoadVideo",
            "inputs": {"file": mp4_path.name, "upload": "image"},
        },
        "7": {
            "class_type": "GetVideoComponents",
            "inputs": {"video": ["6", 0]},
        },
        "1": {
            "class_type": "RTXVideoSuperResolution",
            "inputs": {
                "images": ["7", 0],
                "resize_type": "scale by multiplier",
                "resize_type.scale": float(multiplier),
                "quality": quality,
            },
        },
        "8": {
            "class_type": "CreateVideo",
            "inputs": {
                "fps": fps,
                "bit_depth": "auto",
                "images": ["1", 0],
                "audio": ["7", 1],
            },
        },
        "9": {
            "class_type": "SaveVideo",
            "inputs": {
                "filename_prefix": filename_prefix,
                "format": "auto",
                "codec": "auto",
                "video": ["8", 0],
            },
        },
    }


def submit(server: str, prompt: dict, client_id: str) -> str:
    payload = json.dumps({"prompt": prompt, "client_id": client_id}).encode()
    req = request.Request(
        f"{server}/prompt", data=payload,
        headers={"Content-Type": "application/json"},
        method="POST")
    with request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    if "prompt_id" not in body:
        raise RuntimeError(f"submit failed: {body}")
    return body["prompt_id"]


def poll(server: str, prompt_id: str, *, timeout_s: int) -> dict:
    start = time.time()
    last = None
    while time.time() - start < timeout_s:
        with request.urlopen(f"{server}/history/{prompt_id}", timeout=10) as r:
            hist = json.loads(r.read())
        entry = hist.get(prompt_id)
        if entry is not None:
            s = entry.get("status", {}).get("status_str", "?")
            if s != last:
                print(f"[poll] {s}  t={time.time()-start:.1f}s")
                last = s
            if entry.get("status", {}).get("completed", False):
                return entry
        time.sleep(2)
    raise TimeoutError(f"timed out after {timeout_s}s")


def fetch_outputs(server: str, entry: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for nid, node_out in entry.get("outputs", {}).items():
        for v in node_out.get("videos", []):
            fn = v["filename"]
            sub = v.get("subfolder", "")
            ftype = v.get("type", "output")
            src = f"{server}/view?filename={fn}&type={ftype}&subfolder={sub}"
            dst = out_dir / fn
            with request.urlopen(src, timeout=120) as r, open(dst, "wb") as f:
                shutil.copyfileobj(r, f)
            saved.append(dst)
            print(f"[fetch] {dst}  ({dst.stat().st_size/1e6:.1f} MB)")
    return saved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--comfyui-input", type=Path, default=Path("ComfyUI/input"))
    ap.add_argument("--output-dir", type=Path, default=Path("outputs/rtx-vsr"))
    ap.add_argument("--multiplier", type=float, default=2.0)
    ap.add_argument("--quality", default="ULTRA",
                    choices=["LOW", "MEDIUM", "HIGH", "ULTRA"])
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    # Stage input file for ComfyUI's LoadVideo node
    args.comfyui_input.mkdir(parents=True, exist_ok=True)
    target = args.comfyui_input / args.input.name
    if target.resolve() != args.input.resolve():
        shutil.copy2(args.input, target)
        print(f"[copy] {args.input} -> {target}")

    prompt = build_workflow(target, multiplier=args.multiplier,
                            quality=args.quality, fps=args.fps)
    client_id = f"rtx-vsr-{os.getpid()}-{int(time.time())}"
    pid = submit(args.server, prompt, client_id)
    print(f"[submit] prompt_id={pid}")

    entry = poll(args.server, pid, timeout_s=args.timeout)
    print("[poll] done")

    files = fetch_outputs(args.server, entry, args.output_dir)
    return 0 if files else 1


if __name__ == "__main__":
    sys.exit(main())
