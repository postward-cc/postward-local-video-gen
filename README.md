# postward-local-media-gen

> Local image and video generation toolkit for Postward users.

This repository packages the operational knowledge, workflows, scripts, and
OMP skill needed to run local media generation on consumer NVIDIA GPUs.
Current adapters:

- **Image**: Stable Diffusion WebUI Forge / SDXL (existing local installation)
- **Video**: ComfyUI + MiniMax H3 open weights
- **Upscale**: NVIDIA RTX Video Super Resolution
- **Agent interface**: `SKILL.md` plus hardware-aware CLI modules

The repository is intentionally **skill-first** rather than MCP-first. A model
can inspect the decision tree, detect the local hardware, select a compatible
profile, queue a job, and recover from common failures. An MCP adapter can be
added later on top of the stable CLI seam.

## What the skill supports

- text-to-video (T2V)
- image-to-video (I2V)
- reference-to-video (R2V template; Ref2VA weights are separate)
- multi-shot narrative sequences with explicit frame provenance
- RTX VSR upscaling
- local image-generation coordination through a shared GPU lease
- one GPU inference job at a time, with persistent queue state

## Start here

```bash
git clone https://github.com/postward-cc/postward-local-media-gen.git
cd postward-local-media-gen
cat SKILL.md
python scripts/doctor.py
```

Install the local adapter without modifying system Python or CUDA:

```bash
./bootstrap.sh
```

The bootstrap is idempotent and does **not** download H3 weights. See
`INSTALL.md` for options, `skill.json` for the machine-readable contract, and
`reference/license-compliance.md` before downloading licensed assets.

`doctor.py` returns JSON with GPU name, VRAM, free VRAM, CUDA/PyTorch state,
RAM, disk, weights detected, and the recommended profile.
## Repository layout

```text
postward-local-media-gen/
├── SKILL.md                              OMP entrypoint
├── skill.json                            machine-readable skill manifest
├── INSTALL.md                            installation contract
├── bootstrap.sh                          isolated idempotent bootstrap
├── CONTEXT.md                            domain glossary
├── README.md                             this file
├── docs/adr/                             architectural decisions
│   └── 0001-skill-primary-interface.md
├── reference/                            model-facing operational references
│   ├── hardware-profiles.md
│   ├── concurrency.md
│   ├── image-generation.md
│   ├── license-compliance.md
│   └── workflow-recipes.md
├── scripts/                              hardware and queue interfaces
│   ├── doctor.py
│   └── job_queue.py
└── comfyui-runtime/                      ComfyUI implementation adapter
    ├── RUNBOOK.md
    ├── launch.sh
    ├── fetch_h3_weights.sh
    ├── run_workflow.py
    ├── build_upscale_workflow.py
    ├── submit_rtx_vsr.py
    ├── run_hogwarts_shots.py
    ├── monitor.py
    └── workflows/
```

## Hardware profiles

| VRAM | Default policy |
|---:|---|
| <8 GB | Do not use the official H3 8 GB profile; use a separately licensed INT4 profile or stop |
| 8–10 GB | INT8 + NVFP4, low-VRAM/offload, 0.2–0.4 MP, one job |
| 12–16 GB | INT8 + NVFP4, 0.4–0.6 MP, test high-VRAM mode |
| 16 GB+ | Native/high-VRAM profile, smoke test before 0.98 MP |

Validated baseline: RTX 4060 8 GB, 62 GB RAM, NVIDIA driver 580.173.02,
CUDA 13.0 runtime, PyTorch 2.11.0+cu128.

## Bootstrap the local adapter

```bash
./bootstrap.sh
```

The bootstrap creates an isolated environment under `comfyui-runtime/venv/`,
installs ComfyUI and its custom nodes, and does not download model weights.
Use:

```bash
python scripts/doctor.py
LICENSE_OK=1 ./comfyui-runtime/fetch_h3_weights.sh
./comfyui-runtime/launch.sh
```

See `INSTALL.md` for `--dry-run`, skip options, uninstall, and hardware-aware
installation details. The H3 weight download remains license-gated.

## Queueing and concurrent requests

Two H3 jobs must not use the GPU simultaneously. Use the persistent queue:

```bash
python scripts/job_queue.py enqueue \
  --kind h3-t2v \
  --payload '{"prompt":"a cinematic train station at dawn"}'

python scripts/job_queue.py list
python scripts/job_queue.py status JOB_ID
python scripts/job_queue.py cancel JOB_ID
```

To execute a command while holding the GPU lease:

```bash
python scripts/job_queue.py run --kind h3-t2v -- \
  python comfyui-runtime/run_workflow.py ...
```

CPU-only ffmpeg work may run concurrently. Forge image inference and H3 video
inference share the same GPU lease.

## Verified video chain

On the RTX 4060 baseline:

```text
T2V 0.4 MP / 5 s       → 864×480, ~8 min
I2V continuity 0.6 MP  → 800×800, ~6 min
RTX VSR 2×             → 1600×1600, ~6 s
```

For narrative videos, use unique per-shot input names and a manifest containing
the source frame SHA-256. Never reuse a generic `last_frame.png` from a previous
run; stale source assets are indistinguishable from valid continuity unless
provenance is recorded.

Full commands and troubleshooting are in `comfyui-runtime/RUNBOOK.md`.

## License

The MiniMax H3 weights are governed by the
[MINIMAX H3 Community License](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE).
The reviewed revision lists the UK, EU, US, and South Korea as Excluded
Territories requiring separate licensing. Users are responsible for reviewing
the current terms and obtaining any required license.

The repository's scripts and skill references are intended for Postward
internal use. Upstream ComfyUI, model, and custom-node licenses remain
applicable to their respective artifacts.

## Provenance

- ComfyUI v0.36.0, commit `ee71d5c`
- Comfy-Org workflows revision `3c1df78`
- Comfy-Org H3 model revision `4cc1d817`
- Nvidia RTX nodes: `Comfy-Org/Nvidia_RTX_Nodes_ComfyUI`
