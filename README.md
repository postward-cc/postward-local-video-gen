# postward-local-video-gen

> Local AI video generation tool for Postward users.
> Runs the open-weights **MiniMax H3** model + **NVIDIA RTX Video Super Resolution**
> on a consumer NVIDIA GPU (8 GB+ VRAM). Fully offline. ComfyUI-based.

Generate short cinematic videos with native stereo audio from a **text prompt**
or an **input image**. Multi-shot sequences with frame-to-frame continuity for
narrative clips. Hardware upscaling to 4× via NVIDIA VFX. No API calls, no
cloud, no per-token cost.

---

## Why this exists

Hosted video-generation APIs charge per-second and have rate limits. The
**MiniMax H3** model weights are public under the [MINIMAX H3 Community
License](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE) and run
entirely on consumer hardware. This repo wraps ComfyUI 0.36 around H3 with the
flags, scripts, and workflows that have been validated on a single RTX 4060
8 GB so other Postward team members can run it on similar GPUs without
rediscovering every gotcha.

## What you get

- **Text-to-video** (T2V): prompt → 5-second cinematic clip with synchronized audio
- **Image-to-video** (I2V): first-frame seed → animated continuation
- **Reference-to-video** (R2V): mix of reference images / video / audio (template only — needs separate Ref2VA weights)
- **Multi-shot sequences**: chain shots with frame-to-frame continuity for narrative arcs (≤30 s)
- **NVIDIA RTX Video Super Resolution**: free, hardware-accelerated 2× / 3× / 4× upscale

## Pipeline at a glance

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│   Prompt    │───►│   MiniMax H3 │───►│  MiniMax H3   │───►│ RTX Video    │
│   or Image  │    │   T2V @ 0.4  │    │  I2V @ 0.6    │    │ Super        │
│             │    │   MP (5 s)   │    │  MP (2 s)      │    │ Resolution   │
└─────────────┘    └─────────────┘    └──────────────┘    └──────────────┘
                       8 min              6 min                0:06
```

The script `comfyui-runtime/run_hogwarts_shots.py` orchestrates the full chain
end-to-end. Each shot's last frame becomes the next shot's first frame, giving
smooth visual continuity.

## Hardware requirements

| Component | Minimum | Recommended (validated) |
|---|---|---|
| GPU | NVIDIA RTX 3060 12 GB or RTX 4060 8 GB | **RTX 4060 8 GB (Ada, sm_89)** |
| VRAM | 8 GB | 8 GB (works with heavy offload) |
| RAM | 32 GB | **62 GB** (we hold ~40 GB of model weights + activations in RAM) |
| Disk | 100 GB free | **150 GB free** on `/home` (41 GB for weights, rest for outputs/swap) |
| CUDA driver | 535+ | **580.173.02** (CUDA 13.0 runtime) |
| Python | 3.11 or 3.12 | **3.12.3** |

PyTorch 2.11+ with cu128 wheels works on any RTX 30/40/50-series card.

## Verified benchmarks (RTX 4060 8 GB, 2026-09-20)

| Step | Resolution | Duration | Wall time | Output |
|---|---|---|---|---|
| T2V 0.2 MP smoke | 608×352 | 1.6 s | **2:39** | `MiniMax_H3_*.mp4` |
| T2V 0.4 MP standard | 864×480 | 5.2 s | **8:00** | `MiniMax_H3_*.mp4` |
| I2V 0.6 MP continue | 800×800 | 2.3 s | **6:00** | `MiniMax_H3_*.mp4` |
| RTX VSR 2× upscale | 1600×1600 | 2.3 s | **0:06** | `RTX_VSR_*.mp4` |
| Full chain (4 shots) | 864×480 | ~20 s | **~32 min** | one MP4 |

All outputs include H.264 video + 32 kHz stereo AAC audio, 24 fps.

## Quick start

### 1. Clone and inspect

```bash
git clone https://github.com/postward-cc/postward-local-video-gen
cd postward-local-video-gen
ls comfyui-runtime/         # scripts, docs, workflows
cat comfyui-runtime/RUNBOOK.md   # full reference
```

### 2. Bootstrap the runtime (clean machine, ~5 min)

```bash
cd comfyui-runtime
uv venv --python 3.12 venv && source venv/bin/activate
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
git clone --depth 1 --branch v0.36.0 https://github.com/comfyanonymous/ComfyUI.git
uv pip install -r ComfyUI/requirements.txt sageattention nvidia-vfx
git clone --depth 1 https://github.com/Comfy-Org/Nvidia_RTX_Nodes_ComfyUI \
    ComfyUI/custom_nodes/Nvidia_RTX_Nodes_ComfyUI
```

### 3. Download weights (gated — see License below)

```bash
LICENSE_OK=1 ./fetch_h3_weights.sh
```

### 4. Launch and generate

```bash
./launch.sh                              # GUI on http://127.0.0.1:8188
```

Then either:

- **Drag-and-drop** any `workflows/video_minimax_h3_*.json` into the GUI and click **Run**
- **CLI**: `./run_workflow.py workflows/video_minimax_h3_t2v.json --megapixels 0.4 --duration 5 --turbo-steps 8 --prompt "..."`

### 5. Upscale the output

```bash
./submit_rtx_vsr.py --input outputs/0.4mp/MiniMax_H3_*.mp4 --output-dir outputs/rtx-vsr --multiplier 2 --quality ULTRA
```

## Recipes

### Text-to-video, 5 s, 0.4 MP (the most common starting point)

```bash
./run_workflow.py workflows/video_minimax_h3_t2v.json \
  --megapixels 0.4 --duration 5.0 --turbo-steps 8 --seed 42 \
  --prompt "A small red balloon floats gently above a calm city street at golden hour, soft warm light, gentle breeze, cinematic 24fps." \
  --out-dir outputs/0.4mp
```

### Image-to-video (first frame becomes the seed)

```bash
cp my-photo.png ComfyUI/input/
./build_upscale_workflow.py \
  --frame ComfyUI/input/my-photo.png \
  --megapixels 0.6 --duration 2.0 --turbo-steps 8 \
  --prompt "The subject begins to move, the camera slowly pulls back" \
  --out workflows/i2v.json
./run_workflow.py workflows/i2v.json \
  --megapixels 0.6 --duration 2.0 --turbo-steps 8 \
  --out-dir outputs/i2v
```

### Multi-shot narrative (the Hogwarts example)

```bash
./run_hogwarts_shots.py    # generates 4 shots + concat; see file for prompts
```

Edit `SHOTS = [...]` in `run_hogwarts_shots.py` to define your own sequence.

## Repository layout

```
postward-local-video-gen/
├── README.md                        this file
└── comfyui-runtime/
    ├── RUNBOOK.md                   detailed commands, flags, troubleshooting
    ├── PENDING_WEIGHTS.md           weight sizes + license matrix
    ├── LICENSE_GRANT.txt            audit trail (UK license)
    ├── launch.sh                    ComfyUI launcher with lowvram flags
    ├── fetch_h3_weights.sh          license-gated weight downloader
    ├── run_workflow.py              generic API submission + subgraph inliner
    ├── build_upscale_workflow.py    I2V workflow builder
    ├── submit_rtx_vsr.py            RTX Video Super Resolution client
    ├── run_hogwarts_shots.py        multi-shot orchestrator
    ├── monitor.py                   VRAM/RAM CSV monitor
    └── workflows/                   Comfy-Org pinned revision 3c1df78
        ├── video_minimax_h3_t2v.json
        ├── video_minimax_h3_i2v.json
        ├── video_minimax_h3_r2v.json
        ├── upscale-0.6mp.json       generated
        └── rtx-vsr-upscale.json     generated
```

## Common flags (`./launch.sh`)

| Flag | Why |
|---|---|
| `--use-sage-attention` | ~2× faster than torch SDPA on RTX 4060 |
| `--disable-pinned-memory` | avoids a 0.30.x pinned-memory regression |
| `--fp16-vae` | forces Video VAE to fp16 (matches the safetensors); without it you get a dtype-mismatch crash |
| `--lowvram --reserve-vram 1.0` | diffusion + text encoder offload to 62 GB RAM; 1 GB VRAM headroom for activations |
| `./launch.sh novram` | most aggressive offload (use only if `--lowvram` OOMs) |

## Troubleshooting

| Symptom | Fix |
|---|---|
| `CUDA out of memory` during sampling | lower `--megapixels`, lower `--duration`, or use `./launch.sh novram` |
| `expected m1 and m2 to have the same dtype` from VAE | ensure `--fp16-vae` is set (it's in `launch.sh` by default) |
| Sage: `Input tensors must be on cuda` | don't use `--cpu-vae`; falls back to pytorch attention automatically |
| `Required input is missing: scale` from RTXVideoSuperResolution | use `submit_rtx_vsr.py`, not the saved-format conversion |
| `Resolution Selector` snaps to 1376×768 | `megapixels=1.0` is above H3's cap; use 0.98 |
| `Image #1, 1568x1142` saved at `attachment://N` | the multi-shot orchestrator expects frames in `ComfyUI/input/`; copy from the blob cache manually |

Full troubleshooting matrix in `comfyui-runtime/RUNBOOK.md`.

## License

The **MiniMax H3 model weights** are governed by the
[MINIMAX H3 Community License Agreement](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE).
As of the 2026-08-26 revision, the **United Kingdom, European Union, United States,
and South Korea are Excluded Territories**. Users in those regions must hold a
separate license before downloading, deploying, or offering H3 as a hosted
service. The `LICENSE_OK=1` gate on `fetch_h3_weights.sh` enforces this
explicitly inside the repo.

The **orchestration code, scripts, and workflows** in this repository are
released under the MIT license for Postward internal use. They are derived
from public Comfy-Org workflow templates (pinned revision `3c1df78`) and the
Nvidia_RTX_Nodes_ComfyUI custom node (Apache-2.0).

## Provenance

- ComfyUI: https://github.com/comfyanonymous/ComfyUI (commit `ee71d5c`, v0.36.0)
- MiniMax H3 weights: https://huggingface.co/Comfy-Org/MiniMax-H3 (revision `4cc1d817`)
- 8-step Turbo LoRA: https://huggingface.co/lightx2v/Minimax-h3-Turbo
- RTX VSR nodes: https://github.com/Comfy-Org/Nvidia_RTX_Nodes_ComfyUI
- Local-deploy guide: https://platform.minimax.io/docs/guides/local-deploy-h3

## Roadmap

- [ ] Add a one-shot shell bootstrap (`./bootstrap.sh`) that wraps the bootstrap steps
- [ ] Add a Stable Diffusion XL refiner pass for still-image quality
- [ ] Wire up audio-only generation via `MiniMax Music 3` (template is in `ComfyUI/blueprints/`)
- [ ] Add a small web UI wrapping the CLI (FastAPI + Alpine.js) so non-engineers can use it
- [ ] Investigate `Merserk/MiniMax-H3-INT4-ConvRot` (11 GB) as a fallback for sub-8 GB GPUs
- [ ] Pre-flight check: a `doctor.py` script that validates CUDA / torch / weights before any generation
