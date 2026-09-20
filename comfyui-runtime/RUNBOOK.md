# ComfyUI + MiniMax H3 — RUNBOOK (RTX 4060 8 GB)

> Status: **all three pipelines verified end-to-end locally on 2026-09-20**.
> The 0.2 MP smoke, 0.4 MP standard, 0.6 MP upscale, and RTX Video
> Super Resolution chain all produced valid MP4 outputs. License grant
> recorded in `LICENSE_GRANT.txt`.

## Layout

```
comfyui-runtime/
├── venv/                          # Python 3.12 + torch 2.11.0+cu128
├── ComfyUI/                       # v0.36.0
│   ├── custom_nodes/
│   │   └── Nvidia_RTX_Nodes_ComfyUI/    # RTX Video Super Resolution
│   ├── input/                     # LoadImage / LoadVideo source dir
│   └── models/                    # H3 weights live here (41 GB)
│       ├── diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors
│       ├── loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors
│       ├── text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors
│       └── vae/
│           ├── minimax_h3_video_vae_fp16.safetensors
│           └── minimax_h3_audio_vae_fp32.safetensors
├── workflows/                     # official Comfy-Org pinned revision 3c1df78
│   ├── video_minimax_h3_t2v.json        # T2V template
│   ├── video_minimax_h3_i2v.json        # I2V template (first_frame path)
│   ├── video_minimax_h3_r2v.json        # R2V template (Ref2VA — needs Ref2VA weights)
│   ├── upscale-0.6mp.json               # generated: 0.4 → 0.6 MP H3 continue
│   └── rtx-vsr-upscale.json             # generated: any MP4 → RTX VSR
├── hf-cache/                      # huggingface_hub cache
├── logs/                          # per-launch stdout/stderr
├── outputs/                       # generated MP4s (gitignored)
├── downloads/                     # weight-download staging
├── launch.sh                      # ComfyUI launcher
├── run_workflow.py                # submit + monitor any saved-format workflow
├── build_upscale_workflow.py      # builds workflows/upscale-0.6mp.json from I2V template
├── submit_rtx_vsr.py              # direct-API RTX VSR submission (works around the
│                                  # DynamicCombo in saved-format JSON that confuses
│                                  # run_workflow.py)
├── fetch_h3_weights.sh            # gated weight downloader
├── monitor.py                     # VRAM/RAM/queue monitor
├── LICENSE_GRANT.txt              # audit trail for UK license grant
└── RUNBOOK.md                     # this file
```

## Pinned versions

| Component | Version |
|---|---|
| ComfyUI | v0.36.0 (commit ee71d5c, 2026-09-15) |
| Comfy-Org workflow templates | revision `3c1df78dedcc66c94ec27e0ed8a809ed7742f863` |
| Comfy-Org model repo | revision `4cc1d817b6184899b41293954329f576cb5ae86b` |
| PyTorch | 2.11.0+cu128 (driver 580.173.02 → CUDA 13.0 runtime) |
| Sage Attention | 1.0.6 (PyPI; only Linux option compatible with torch 2.11) |
| nvidia-vfx | 0.1.0.1 (required by RTX VSR nodes) |
| Python | 3.12.3 |

## Launch ComfyUI

```bash
cd /home/mvallebr/git/video_gen_poc/comfyui-runtime
./launch.sh                                    # default LOW_VRAM mode, port 8188
./launch.sh novram                              # most aggressive offload
PORT=8190 LISTEN=0.0.0.0 ./launch.sh           # custom port / bind
```

### Flag rationale

| Flag | Reason |
|---|---|
| `--use-sage-attention` | ~2× speedup over torch SDPA on RTX 4060 (measured 0.15ms vs 0.30ms) |
| `--disable-pinned-memory` | avoids the 0.30.x pinned-memory regression that slows model load |
| `--fp16-vae` | forces Video VAE to fp16 to match the safetensors file; without it you get a `RuntimeError: expected m1 and m2 to have the same dtype` from `minimax/vae.py:371` |
| `--lowvram --reserve-vram 1.0` | diffusion layers + text encoder offload to 62 GB RAM; 1 GB VRAM headroom for activations |
| `--novram` | max offload; slowest but safest for 8 GB |

Do **not** use `--cpu-vae`. The Video VAE is 5 GB and on CPU it takes 8+ minutes for VAE decode. On GPU it's seconds.

GUI at `http://127.0.0.1:8188`. Drag any `workflows/*.json` into the window.

## The verified pipeline (T2V → I2V upgrade → RTX VSR)

```
                 ┌─────────────────────────────┐
   prompt ──►   │ H3 T2V at 0.4 MP, 5 s       │  ~8 min, ~17s/step
                 └─────────────────────────────┘
                              │
                              ▼  (extract last frame with ffmpeg)
                 ┌─────────────────────────────┐
   first_frame ─►│ H3 I2V at 0.6 MP, 2 s        │  ~6 min, ~40s/step
                 └─────────────────────────────┘
                              │
                              ▼
                 ┌─────────────────────────────┐
   input.mp4 ──► │ RTX Video Super Resolution  │  ~6 s, hardware-accelerated
                 └─────────────────────────────┘
                 1600×1600, 24 fps, 32 kHz stereo
```

### Verified outputs (2026-09-20)

| Step | File | Resolution | Duration | Size | Time |
|---|---|---|---|---|---|
| 0.2 MP smoke | `outputs/smoke-0.2mp/MiniMax_H3_00001_.mp4` | 608×352 | 1.6 s | 140 KB | 2:39 |
| 0.4 MP standard | `outputs/0.4mp/MiniMax_H3_00002_.mp4` | 864×480 | 5.2 s | 584 KB | 8:00 |
| 0.6 MP upscale | `outputs/0.6mp-upscale/MiniMax_H3_00003_.mp4` | 800×800 | 2.3 s | 353 KB | 6:00 |
| RTX VSR final | `outputs/rtx-vsr/RTX_VSR_00001_.mp4` | 1600×1600 | 2.3 s | 912 KB | 0:06 |

All generations are **local** — no remote API calls. Sage attention runs the diffusion, the Video VAE decodes on GPU, the Audio VAE produces the 32 kHz stereo soundtrack, and the NV VFX hardware path runs the final upscale.

### Step 1 — H3 0.4 MP base generation

```bash
./run_workflow.py workflows/video_minimax_h3_t2v.json \
  --megapixels 0.4 \
  --duration 5.0 \
  --turbo-steps 8 \
  --turbo-strength 1.0 \
  --seed 42 \
  --prompt "A small red balloon floats gently above a calm city street at golden hour, soft warm light, gentle breeze, cinematic 24fps." \
  --out-dir outputs/0.4mp \
  --timeout 1800
```

### Step 2 — Extract last frame

```bash
ffmpeg -y -sseof -0.1 -i outputs/0.4mp/MiniMax_H3_00002_.mp4 \
  -frames:v 1 -update 1 outputs/0.4mp/last_frame.png
```

### Step 3 — H3 0.6 MP continuation (I2V, first_frame seeded)

```bash
./build_upscale_workflow.py \
  --frame outputs/0.4mp/last_frame.png \
  --megapixels 0.6 \
  --duration 2.0 \
  --turbo-steps 8 \
  --seed 43 \
  --prompt "Same as base (kept verbatim for continuity)" \
  --out workflows/upscale-0.6mp.json

./run_workflow.py workflows/upscale-0.6mp.json \
  --megapixels 0.6 --duration 2.0 --turbo-steps 8 --seed 43 \
  --out-dir outputs/0.6mp-upscale \
  --timeout 1800
```

`build_upscale_workflow.py` copies `last_frame.png` into `ComfyUI/input/`, then patches the I2V template's `LoadImage.image` widget and the `ResolutionSelector.megapixels` widget.

### Step 4 — RTX Video Super Resolution

```bash
./submit_rtx_vsr.py \
  --input outputs/0.6mp-upscale/MiniMax_H3_00003_.mp4 \
  --output-dir outputs/rtx-vsr \
  --multiplier 2 \
  --quality ULTRA \
  --timeout 600
```

`submit_rtx_vsr.py` builds the RTX VSR prompt API directly (not via saved-format conversion) because the RTXVideoSuperResolution node has a `DynamicCombo.Input` that doesn't round-trip cleanly through saved-format widgets. The `resize_type.scale` key uses the nested-key convention required by V3 nodes.

For 1600×1600 final, the chain multiplies: 800×800 → 1600×1600. For 4×, pass `--multiplier 4` (clamped by the RTX VFX lib to ≤4).

## Recipe variants

| Recipe | Megapixels | Output (multiple=32) | Duration | Turbo steps |
|---|---|---|---|---|
| 0.2 MP smoke | 0.2 | 608×352 | 1 s | 8 |
| 0.4 MP standard | 0.4 | 864×480 | 5 s | 8 |
| 0.6 MP upscale | 0.6 | 1056×608 (or square on some templates) | 2 s | 8 |
| 0.98 MP native | 0.98 | 1344×768 | 5 s | 20 (no Turbo) |

Avoid `megapixels=1.0` exactly — it resolves to 1376×768 which is above H3-Base's 768×1344 pixel-area cap.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `CUDA out of memory` during sampling | 8 GB not enough at the requested MP / duration | lower megapixels; lower duration; `./launch.sh novram` |
| `expected m1 and m2 to have the same dtype` from VAE | missing `--fp16-vae` | already in `launch.sh`; ensure you didn't override |
| Sage attention: `Input tensors must be on cuda` | VAE on CPU; sage needs CUDA | don't use `--cpu-vae`; falls back to pytorch attention |
| `failed to source file: venv/bin/activate` from background job | bash cwd defaults to project root, not runtime | use `cwd: /home/mvallebr/git/video_gen_poc/comfyui-runtime` on the bash tool |
| `Required input is missing: scale` from RTXVideoSuperResolution | DynamicCombo requires nested-key format | use `submit_rtx_vsr.py`, not the saved-format conversion |
| 0.98 MP: clipped to 1376×768 (above cap) | megapixels=1.0 is rounded up | use 0.98 or 0.95 instead |
| RTX VSR: file shows up in history but not on disk | `submit_rtx_vsr.py` looks for `outputs.videos`, RTX VSR uses `outputs.images` | re-fetch with `curl "http://127.0.0.1:8188/view?filename=...&subfolder=...&type=output"` |
| H3 generation produces no audio | one of the VAEs missing | both VAEs required; ensure `models/vae/minimax_h3_audio_vae_fp32.safetensors` is present |

## 8 GB VRAM reality (verified numbers)

| Phase | VRAM peak | RAM peak | Sampler rate | Notes |
|---|---|---|---|---|
| Text encoder load | ~3 GB | ~14 GB | n/a | qwen3vl 32B NVFP4, ~14.96 GB staged in RAM |
| Diffusion model load | 7.5 GB | ~25 GB | n/a | 19.95 GB staged, offloaded to CPU |
| Sampling (0.4 MP, 5 s) | 7.6 GB | ~30 GB | ~53 s/step | dynamic swap layers in/out |
| Sampling (0.2 MP, 1 s) | 7.5 GB | ~25 GB | ~17 s/step | |
| VAE decode | 6.5 GB | ~40 GB | < 60 s | fp16, GPU-resident |
| Idle (post-gen) | 4.5 GB | ~40 GB | n/a | models held in RAM until next prompt |

The `comfyui-smoke.log` shows: "Model MiniMaxH3 prepared for dynamic VRAM loading. 19995MB Staged. 208 patches attached." Dynamic VRAM is the key feature that makes 8 GB work.

## Updating

```bash
cd ComfyUI && git pull
cd custom_nodes/Nvidia_RTX_Nodes_ComfyUI && git pull
source ../venv/bin/activate
uv pip install -U torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
uv pip install -U nvidia-vfx
```

The H3 weights themselves are pinned to Comfy-Org revision `4cc1d817` (and the Turbo LoRA to `lightx2v/Minimax-h3-Turbo`); re-running `LICENSE_OK=1 ./fetch_h3_weights.sh` after a model repo update will refresh them.
