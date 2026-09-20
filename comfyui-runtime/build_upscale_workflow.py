#!/usr/bin/env python3
"""
Build a 0.6 MP H3 first-frame-to-video workflow that reuses an existing
0.4 MP clip's last frame as the seed for continuity.

Usage:
  ./build_upscale_workflow.py \
    --frame outputs/0.4mp/last_frame.png \
    --megapixels 0.6 \
    --duration 2.0 \
    --prompt "Same as base" \
    --out workflows/upscale-0.6mp.json
"""
from __future__ import annotations
import argparse
import json
import shutil
from pathlib import Path


# I2V workflow constants (from Comfy-Org pinned revision 3c1df78)
NODE_RES_SELECTOR_ID = 115
NODE_H3_ID = 105  # I2V workflow's subgraph instance node id is 105 (not 140)
NODE_LOAD_IMAGE_ID = 114


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", type=Path,
                    default=Path("workflows/video_minimax_h3_i2v.json"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--frame", type=Path, required=True,
                    help="Path to PNG/JPG to seed the generation (file copied to ComfyUI/input/)")
    ap.add_argument("--megapixels", type=float, default=0.6)
    ap.add_argument("--duration", type=float, default=2.0)
    ap.add_argument("--turbo-steps", type=int, default=8)
    ap.add_argument("--seed", type=int, default=43)
    ap.add_argument("--prompt", type=str, default="A small red balloon floats gently above a calm city street at golden hour, soft warm light, gentle breeze, cinematic 24fps.")
    ap.add_argument("--comfyui-input", type=Path,
                    default=Path("ComfyUI/input"))
    args = ap.parse_args()

    # Copy the seed frame into ComfyUI's input dir so LoadImage finds it
    args.comfyui_input.mkdir(parents=True, exist_ok=True)
    target = args.comfyui_input / args.frame.name
    if args.frame.resolve() != target.resolve():
        shutil.copy2(args.frame, target)
        print(f"[copy] {args.frame} -> {target}")
    else:
        print(f"[copy] already in place: {target}")

    # Load I2V template + patch
    wf = json.loads(args.template.read_text())
    for node in wf["nodes"]:
        nid = node.get("id")
        if nid == NODE_LOAD_IMAGE_ID:
            # Set the image filename to the seed frame
            node.setdefault("widgets_values_named", {})["image"] = args.frame.name
            node["widgets_values"][0] = args.frame.name
        elif nid == NODE_RES_SELECTOR_ID:
            node["widgets_values"][1] = float(args.megapixels)
            node.setdefault("widgets_values_named", {})["megapixels"] = float(args.megapixels)
        elif nid == NODE_H3_ID:
            nmd = node.setdefault("widgets_values_named", {})
            nmd["value_1"] = float(args.duration)   # duration
            nmd["noise_seed"] = int(args.seed)
            nmd["value_2"] = int(args.turbo_steps)
            nmd["value"] = True
            nmd["prompt"] = args.prompt

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(wf, indent=2))
    print(f"[write] {args.out}")
    print(f"[params] megapixels={args.megapixels}, duration={args.duration}s, "
          f"turbo_steps={args.turbo_steps}, seed={args.seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
