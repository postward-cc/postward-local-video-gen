#!/usr/bin/env python3
"""Build an H3 I2V first-frame workflow with explicit provenance-friendly paths."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
NODE_RES_SELECTOR_ID = 115
NODE_H3_ID = 105
NODE_LOAD_IMAGE_ID = 114


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", type=Path,
                    default=HERE / "workflows/video_minimax_h3_i2v.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--frame", type=Path, required=True)
    ap.add_argument("--megapixels", type=float, default=0.6)
    ap.add_argument("--aspect-ratio", default="16:9 (Widescreen)",
                    choices=["16:9 (Widescreen)", "9:16 (Portrait Widescreen)",
                             "1:1 (Square)"])
    ap.add_argument("--duration", type=float, default=2.0)
    ap.add_argument("--turbo-steps", type=int, default=8)
    ap.add_argument("--seed", type=int, default=43)
    ap.add_argument("--prompt", type=str, default="")
    ap.add_argument("--comfyui-input", type=Path,
                    default=HERE / "ComfyUI" / "input")
    args = ap.parse_args()

    template = args.template if args.template.is_absolute() else HERE / args.template
    frame = args.frame if args.frame.is_absolute() else Path.cwd() / args.frame
    out = args.out if args.out.is_absolute() else Path.cwd() / args.out
    comfyui_input = (args.comfyui_input if args.comfyui_input.is_absolute()
                     else HERE / args.comfyui_input)

    if not frame.exists():
        raise FileNotFoundError(f"seed frame does not exist: {frame}")
    if not template.exists():
        raise FileNotFoundError(f"workflow template does not exist: {template}")

    comfyui_input.mkdir(parents=True, exist_ok=True)
    target = comfyui_input / frame.name
    if frame.resolve() != target.resolve():
        shutil.copy2(frame, target)
        print(f"[copy] {frame} -> {target}")
    else:
        print(f"[copy] already in place: {target}")

    wf = json.loads(template.read_text())
    for node in wf["nodes"]:
        nid = node.get("id")
        if nid == NODE_LOAD_IMAGE_ID:
            node.setdefault("widgets_values_named", {})["image"] = frame.name
            node["widgets_values"][0] = frame.name
        elif nid == NODE_RES_SELECTOR_ID:
            node["widgets_values"][0] = args.aspect_ratio
            node["widgets_values"][1] = float(args.megapixels)
            named = node.setdefault("widgets_values_named", {})
            named["aspect_ratio"] = args.aspect_ratio
            named["megapixels"] = float(args.megapixels)
        elif nid == NODE_H3_ID:
            nmd = node.setdefault("widgets_values_named", {})
            nmd["value_1"] = float(args.duration)
            nmd["noise_seed"] = int(args.seed)
            nmd["value_2"] = int(args.turbo_steps)
            nmd["value"] = True
            if args.prompt:
                nmd["prompt"] = args.prompt

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(wf, indent=2) + "\n")
    print(f"[write] {out}")
    print(f"[params] aspect={args.aspect_ratio}, megapixels={args.megapixels}, "
          f"duration={args.duration}s, turbo_steps={args.turbo_steps}, seed={args.seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
