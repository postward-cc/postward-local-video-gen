#!/usr/bin/env python3
"""
Submit a ComfyUI workflow JSON to a running server, monitor its execution,
and save the produced video file.

Usage:
  ./run_workflow.py <workflow.json> [--megapixels 0.2] [--duration 1.0]
                    [--turbo-steps 8] [--turbo-strength 1.0] [--seed 42]
                    [--server http://127.0.0.1:8188] [--out-dir outputs/smoke]
                    [--prompt "..."]

The script edits only the well-known widget values for the MiniMax H3 local
workflows (ResolutionSelector + subgraph IO). Anything else in the JSON is
untouched. Subgraphs are inlined before API conversion.
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

# Known node IDs in the T2V workflow (Comfy-Org pinned revision 3c1df78)
NODE_RES_SELECTOR_ID = 115
NODE_H3_ID = 140  # default; I2V/R2V workflows may use a different id (auto-detected below)

# Subgraph UUID for the MiniMax H3 node across workflows
H3_SUBGRAPH_UUID = "79dd8a95-ce9d-4c14-b264-2162e8bec5ce"


def detect_h3_node_id(workflow: dict) -> int:
    """Find the H3 subgraph instance node id in the workflow."""
    sg_ids = {sg["id"] for sg in workflow.get("definitions", {}).get("subgraphs", [])}
    sg_ids.add(H3_SUBGRAPH_UUID)
    for n in workflow.get("nodes", []):
        if n.get("type") in sg_ids:
            return n["id"]
    return NODE_H3_ID  # fallback

# IO slot names exposed by the H3 subgraph (must match sub_io_targets keys below)
H3_IO_PROMPT = "prompt"
H3_IO_WIDTH = "width"
H3_IO_HEIGHT = "height"
H3_IO_DURATION = "value_1"            # labeled "duration"
H3_IO_SEED = "noise_seed"
H3_IO_UNET = "unet_name"
H3_IO_CLIP = "clip_name"
H3_IO_VIDEO_VAE = "vae_name"
H3_IO_AUDIO_VAE = "vae_name_1"
H3_IO_TURBO_MODE = "value"            # labeled "turbo_mode"
H3_IO_LORA = "lora_name"
H3_IO_TURBO_STRENGTH = "strength_model_1"  # labeled "turbo_model_strength"
H3_IO_TURBO_STEPS = "value_2"        # labeled "turbo_steps"


def patch_workflow(workflow: dict, *, megapixels: float | None,
                   duration: float | None, turbo_steps: int | None,
                   turbo_strength: float | None, seed: int | None,
                   prompt: str | None = None,
                   h3_node_id: int | None = None) -> dict:
    """In-place edits to a *copy* of the saved-format workflow."""
    wf = json.loads(json.dumps(workflow))  # deep copy
    h3_id = h3_node_id if h3_node_id is not None else detect_h3_node_id(wf)

    for node in wf["nodes"]:
        nid = node.get("id")
        if nid == NODE_RES_SELECTOR_ID and megapixels is not None:
            wv = node["widgets_values"]
            # [aspect_ratio, megapixels, multiple]
            wv[1] = float(megapixels)
            if "widgets_values_named" in node:
                node["widgets_values_named"]["megapixels"] = float(megapixels)

        elif nid == h3_id:
            nmd = node.setdefault("widgets_values_named", {})
            if duration is not None:
                nmd[H3_IO_DURATION] = float(duration)
            if seed is not None:
                nmd[H3_IO_SEED] = int(seed)
            if turbo_steps is not None:
                nmd[H3_IO_TURBO_STEPS] = int(turbo_steps)
            if turbo_strength is not None:
                nmd[H3_IO_TURBO_STRENGTH] = float(turbo_strength)
            if prompt is not None:
                nmd[H3_IO_PROMPT] = prompt
            nmd[H3_IO_TURBO_MODE] = True
    return wf


def inline_subgraphs(workflow: dict) -> dict:
    """Expand subgraph instances into their internal nodes with rewired links.

    A subgraph is a saved-format construct that wraps multiple atomic nodes
    behind a single user-facing block. The ComfyUI API expects a flat node
    graph, so we must:
      1. Replace each subgraph instance with its internal nodes (re-id'd).
      2. Re-target parent links that flowed through the subgraph IO.
      3. Apply the subgraph instance's widget values onto the internal nodes.
    """
    wf = json.loads(json.dumps(workflow))
    sg_defs = {sg["id"]: sg for sg in wf.get("definitions", {}).get("subgraphs", [])}

    subgraph_instances = [n for n in wf["nodes"] if n["type"] in sg_defs]
    if not subgraph_instances:
        return wf

    # Allocate new ids for inlined nodes
    max_id = max((n["id"] for n in wf["nodes"]), default=0)
    next_id = max_id + 100

    # For each subgraph instance: remap of internal id -> new id, and IO routing
    inlined_nodes: list[dict] = []
    sub_remaps: dict[int, dict[int, int]] = {}
    sub_io_targets: dict[int, dict[int, list[tuple[int, str]]]] = {}
    sub_output_sources: dict[int, dict[int, list[tuple[int, int]]]] = {}

    for sn in subgraph_instances:
        sg = sg_defs[sn["type"]]
        remap: dict[int, int] = {}
        for in_node in sg["nodes"]:
            new_id = next_id
            next_id += 1
            remap[in_node["id"]] = new_id
            inlined = json.loads(json.dumps(in_node))
            inlined["id"] = new_id
            inlined_nodes.append(inlined)
        sub_remaps[sn["id"]] = remap

        # Normalize internal links to tuples (link_id, src, src_slot, dst, dst_slot)
        normalized_links: list[tuple] = []
        for link in sg.get("links", []):
            if isinstance(link, dict):
                # dict format: {id, origin_id, origin_slot, target_id, target_slot, type}
                normalized_links.append(
                    (link["id"], link["origin_id"], link["origin_slot"],
                     link["target_id"], link["target_slot"])
                )
            elif isinstance(link, list) and len(link) >= 5:
                normalized_links.append((link[0], link[1], link[2], link[3], link[4]))

        # Build a helper: internal link_id -> (old_dst_node, old_dst_slot)
        sg_internal_links: dict[int, tuple[int, int]] = {
            lid: (dst, dst_slot) for (lid, _s, _ss, dst, dst_slot) in normalized_links
        }
        # And: internal link_id -> (old_src_node, old_src_slot)
        sg_internal_src: dict[int, tuple[int, int]] = {
            lid: (src, src_slot) for (lid, src, src_slot, _d, _ds) in normalized_links
        }

        # IO input -> internal target(s)
        io_targets: dict[int, list[tuple[int, str]]] = {}
        for io_slot_idx, io_in in enumerate(sg.get("inputs", [])):
            targets: list[tuple[int, str]] = []
            for internal_lid in io_in.get("linkIds", []):
                if internal_lid not in sg_internal_links:
                    continue
                old_dst, dst_slot = sg_internal_links[internal_lid]
                for n in sg["nodes"]:
                    if n["id"] == old_dst:
                        inputs = n.get("inputs", [])
                        if dst_slot < len(inputs):
                            targets.append(
                                (remap[old_dst], inputs[dst_slot]["name"])
                            )
                        break
            io_targets[io_slot_idx] = targets
        sub_io_targets[sn["id"]] = io_targets

        # Output -> internal source(s)
        out_sources: dict[int, list[tuple[int, int]]] = {}
        for out_slot_idx, out in enumerate(sg.get("outputs", [])):
            sources: list[tuple[int, int]] = []
            for internal_lid in out.get("linkIds", []):
                if internal_lid in sg_internal_src:
                    old_src, src_slot = sg_internal_src[internal_lid]
                    if old_src in remap:
                        sources.append((remap[old_src], src_slot))
            out_sources[out_slot_idx] = sources
        sub_output_sources[sn["id"]] = out_sources

    # New parent nodes
    new_parent_nodes = [n for n in wf["nodes"] if n["type"] not in sg_defs]
    new_parent_nodes.extend(inlined_nodes)

    # Build remapped subgraph internal links (link_id, src, src_slot, dst, dst_slot, type)
    remapped_internal_links: list[list] = []
    for sn in subgraph_instances:
        sg = sg_defs[sn["type"]]
        remap = sub_remaps[sn["id"]]
        for link in sg.get("links", []):
            if isinstance(link, dict):
                lid = link["id"]
                src = link["origin_id"]
                src_slot = link["origin_slot"]
                dst = link["target_id"]
                dst_slot = link["target_slot"]
                ltype = link.get("type", "")
            elif isinstance(link, list) and len(link) >= 6:
                lid, src, src_slot, dst, dst_slot, ltype = link[0], link[1], link[2], link[3], link[4], link[5]
            else:
                continue
            new_src = remap.get(src, src)
            new_dst = remap.get(dst, dst)
            remapped_internal_links.append([lid, new_src, src_slot, new_dst, dst_slot, ltype])

    # Track which parent links target a subgraph instance so we can rewrite
    # their values into the corresponding internal links (which have src=-10).
    parent_to_internal: list[tuple[list, list, list]] = []
    # (parent_link, internal_lid, sg_node_id)
    # The subgraph INSTANCE node has its own inputs[] array (ordered); the
    # subgraph DEFINITION has its own inputs[] (potentially different order).
    # Match by IO name, not by index.
    for link in wf.get("links", []):
        if len(link) < 6:
            continue
        lid, src, src_slot, dst, dst_slot, ltype = link
        if dst not in sub_io_targets:
            continue
        sn = next(n for n in subgraph_instances if n["id"] == dst)
        sg = sg_defs[sn["type"]]
        # Lookup IO name from the subgraph instance's inputs array
        sn_inputs = sn.get("inputs", [])
        if dst_slot >= len(sn_inputs):
            continue
        io_name = sn_inputs[dst_slot].get("name")
        if not io_name:
            continue
        # Find the IO definition in sg.inputs by name
        io_def = next((io for io in sg.get("inputs", []) if io.get("name") == io_name), None)
        if not io_def:
            continue
        for internal_lid in io_def.get("linkIds", []):
            parent_to_internal.append((link, internal_lid, dst))

    # Build remapped subgraph internal links, rewriting src=-10 → parent src
    remapped_internal_links: list[list] = []
    parent_src_overrides: dict[int, tuple[int, int]] = {}  # internal_lid → (new_src, new_src_slot)
    for parent_link, internal_lid, sn_id in parent_to_internal:
        lid, src, src_slot, dst, dst_slot, ltype = parent_link[:6]
        parent_src_overrides[internal_lid] = (src, src_slot)

    for sn in subgraph_instances:
        sg = sg_defs[sn["type"]]
        remap = sub_remaps[sn["id"]]
        for link in sg.get("links", []):
            if isinstance(link, dict):
                lid = link["id"]
                src = link["origin_id"]
                src_slot = link["origin_slot"]
                dst = link["target_id"]
                dst_slot = link["target_slot"]
                ltype = link.get("type", "")
            elif isinstance(link, list) and len(link) >= 6:
                lid, src, src_slot, dst, dst_slot, ltype = link[0], link[1], link[2], link[3], link[4], link[5]
            else:
                continue
            new_src = remap.get(src, src)
            new_dst = remap.get(dst, dst)
            # If this link's source was -10 (external entry), use the parent
            # link's src when available; otherwise the link is dead and we
            # skip it (the input is treated as a widget or unconnected).
            if lid in parent_src_overrides:
                new_src, src_slot = parent_src_overrides[lid]
            elif src == -10:
                # External entry with no parent override — drop the link.
                # The corresponding input will appear in saved_to_api as a
                # widget value (or absent if no widget was set).
                continue
            remapped_internal_links.append([lid, new_src, src_slot, new_dst, dst_slot, ltype])

    # Parent links: keep those not targeting subgraph instances; rewrite source
    # for those whose src was a subgraph instance (use internal sources instead).
    new_parent_links: list[list] = []
    for link in wf.get("links", []):
        if len(link) < 6:
            continue
        lid, src, src_slot, dst, dst_slot, ltype = link

        # Source = subgraph instance: fan out to internal sources
        if src in sub_output_sources:
            for new_src, new_src_slot in sub_output_sources[src].get(src_slot, []):
                new_parent_links.append([lid, new_src, new_src_slot, dst, dst_slot, ltype])
            continue

        # Destination = subgraph instance: drop. The internal link now carries
        # the external value via the rewritten source above.
        if dst in sub_io_targets:
            continue

        new_parent_links.append(link)

    # Combine: rewritten parent links + remapped subgraph internal links
    wf["nodes"] = new_parent_nodes
    wf["links"] = new_parent_links + remapped_internal_links

    # Apply widget values from subgraph instances onto internal nodes, AND
    # remove the corresponding link refs (so saved_to_api doesn't override
    # the widget value with a stale [-10, X] source ref).
    # A widget is applied when no parent link targets this IO. We detect
    # that by walking parent links BEFORE rewriting — but we want the
    # pre-rewrite parent links table, so capture BEFORE we mutate wf["links"].
    parent_link_targets: set[tuple[int, str]] = set()
    for link in workflow.get("links", []):
        if len(link) < 6:
            continue
        _, src, src_slot, dst, dst_slot, _ = link
        if dst not in sub_io_targets:
            continue
        sn = next(n for n in subgraph_instances if n["id"] == dst)
        sn_inputs = sn.get("inputs", [])
        if dst_slot < len(sn_inputs):
            io_name = sn_inputs[dst_slot].get("name")
            if io_name:
                parent_link_targets.add((sn["id"], io_name))

    for sn in subgraph_instances:
        named = sn.get("widgets_values_named", {})
        if not named:
            continue
        sg = sg_defs[sn["type"]]
        for io_slot_idx, io_in in enumerate(sg.get("inputs", [])):
            io_name = io_in["name"]
            # Parent link wins
            if (sn["id"], io_name) in parent_link_targets:
                continue
            if io_name not in named:
                continue
            value = named[io_name]
            for new_dst_id, new_dst_input in sub_io_targets[sn["id"]].get(io_slot_idx, []):
                for node in inlined_nodes:
                    if node["id"] == new_dst_id:
                        _set_widget_on_node(node, new_dst_input, value)
                        # Clear the link ref so API conversion uses widget value
                        for inp in node.get("inputs", []):
                            if inp.get("name") == new_dst_input:
                                inp["link"] = None
                                break
                        break

    # wf["nodes"] and wf["links"] already assigned above
    wf.pop("definitions", None)
    return wf


def _unused_internal_lid_to_src(sg, internal_lid: int) -> tuple[int, int]:
    """Legacy helper, unused after normalization fix."""
    return (-1, -1)


def _set_widget_on_node(node: dict, input_name: str, value) -> None:
    """Set a widget value on a node by input name."""
    if "widgets_values_named" in node:
        node["widgets_values_named"][input_name] = value
        return
    # Positional fallback
    for i, inp in enumerate(node.get("inputs", [])):
        w = inp.get("widget")
        if w and w.get("name") == input_name and i < len(node.get("widgets_values", [])):
            node["widgets_values"][i] = value
            return
    # No map and no positional match: synthesize a named map
    node.setdefault("widgets_values_named", {})[input_name] = value


def saved_to_api(workflow: dict) -> dict:
    """Convert a (saved-format) workflow to API-format prompt.

    API format: {"<node_id_str>": {"class_type": "<type>", "inputs": {...}}}
    Notes are skipped. Connected inputs become [src_node, slot] refs; the rest
    come from `widgets_values_named` (or positional `widgets_values`).
    """
    # Build link-id -> (src_node, src_slot) map
    link_map: dict[int, tuple[int, int]] = {}
    for link in workflow.get("links", []):
        if len(link) >= 5:
            link_map[link[0]] = (link[1], link[2])

    api: dict = {}
    for node in workflow.get("nodes", []):
        cls = node["type"]
        # Skip notes / docs
        if cls == "MarkdownNote" or "Note" in cls:
            continue
        nid = str(node["id"])
        inputs: dict = {}

        # 1. Add widgets (named preferred)
        named = node.get("widgets_values_named")
        if named:
            for k, v in named.items():
                inputs[k] = v
        else:
            for i, inp in enumerate(node.get("inputs", [])):
                w = inp.get("widget")
                if w is not None:
                    wv = node.get("widgets_values", [])
                    if i < len(wv):
                        inputs[inp["name"]] = wv[i]

        # 2. Override with link refs (wins over widgets)
        for inp in node.get("inputs", []):
            link_id = inp.get("link")
            if link_id is not None and link_id in link_map:
                src_node, src_slot = link_map[link_id]
                # ComfyUI's API expects string node IDs in connection refs
                # (because JSON object keys are always strings after parsing)
                inputs[inp["name"]] = [str(src_node), src_slot]

        api[nid] = {"class_type": cls, "inputs": inputs}

    return api


def submit(server: str, workflow: dict, client_id: str) -> str:
    payload = json.dumps({"prompt": workflow, "client_id": client_id}).encode()
    req = request.Request(
        f"{server}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    if "prompt_id" not in body:
        raise RuntimeError(f"submit failed: {body}")
    return body["prompt_id"]


def poll(server: str, prompt_id: str, *, timeout_s: int = 1800) -> dict:
    """Poll /history/{prompt_id} until success, error, or timeout."""
    start = time.time()
    last_status = None
    while time.time() - start < timeout_s:
        req = request.Request(f"{server}/history/{prompt_id}", method="GET")
        with request.urlopen(req, timeout=10) as resp:
            hist = json.loads(resp.read())
        entry = hist.get(prompt_id)
        if entry is not None:
            status_data = entry.get("status", {})
            cur_status = status_data.get("status_str", "?")
            if cur_status != last_status:
                print(f"[poll] status={cur_status}  t={time.time()-start:.1f}s")
                last_status = cur_status
            if cur_status in {"error", "failed"}:
                raise RuntimeError(
                    f"ComfyUI job failed: prompt_id={prompt_id}, "
                    f"status={cur_status}, messages={status_data.get('messages', [])}"
                )
            if status_data.get("completed", False):
                return entry
        time.sleep(3)
    raise TimeoutError(f"prompt {prompt_id} did not finish in {timeout_s}s")


def fetch_outputs(server: str, history_entry: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for nid, node_out in history_entry.get("outputs", {}).items():
        for media_key in ("videos", "gifs", "images"):
            for v in node_out.get(media_key, []):
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
    ap.add_argument("workflow", type=Path)
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--megapixels", type=float)
    ap.add_argument("--duration", type=float)
    ap.add_argument("--turbo-steps", type=int)
    ap.add_argument("--turbo-strength", type=float)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--prompt", type=str, default=None)
    ap.add_argument("--out-dir", type=Path, default=Path("outputs/run"))
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    wf = json.loads(args.workflow.read_text())
    wf = patch_workflow(
        wf,
        megapixels=args.megapixels,
        duration=args.duration,
        turbo_steps=args.turbo_steps,
        turbo_strength=args.turbo_strength,
        seed=args.seed,
        prompt=args.prompt,
    )

    # Inline subgraphs so the API sees a flat node graph
    wf = inline_subgraphs(wf)

    client_id = f"runner-{os.getpid()}-{int(time.time())}"
    print(f"[submit] server={args.server} client={client_id}")
    api_prompt = saved_to_api(wf)
    print(f"[submit] API format: {len(api_prompt)} nodes")
    pid = submit(args.server, api_prompt, client_id)
    print(f"[submit] prompt_id={pid}")

    entry = poll(args.server, pid, timeout_s=args.timeout)
    print(f"[poll] done")

    files = fetch_outputs(args.server, entry, args.out_dir)
    if not files:
        print("ERROR: no media produced", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
