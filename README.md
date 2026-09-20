# postward-local-video-gen

Local AI video generation tool for Postward users — runs the open-weights
**MiniMax H3** video model plus **NVIDIA RTX Video Super Resolution** on a
consumer NVIDIA GPU (8 GB+ VRAM). ComfyUI-based, fully offline.

## What it does

Generate short cinematic videos (with native stereo audio) from:

- a **text prompt** (T2V)
- an **input image** as the first frame (I2V)
- a **chain** of multi-shot sequences with frame-to-frame continuity

Then optionally upscale the result with NVIDIA's hardware-accelerated RTX VSR.

All weights are open and run locally — no API calls, no cloud.

## Hardware target

Validated on **NVIDIA RTX 4060 8 GB** (Linux, driver 580.173.02, CUDA 13.0
runtime). Should also run on other 8 GB+ NVIDIA cards (RTX 30/40 series).
The pipeline is tuned for 8 GB with heavy CPU/RAM offloading; larger VRAM
makes things faster but is not required.

## Quick start

```bash
git clone https://github.com/postward-cc/postward-local-video-gen
cd postward-local-video-gen
ls comfyui-runtime/      # scripts, docs, workflows
cat comfyui-runtime/RUNBOOK.md    # full reference
```

For a one-command bootstrap on a clean machine:

```bash
cd comfyui-runtime
uv venv --python 3.12 venv && source venv/bin/activate
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
git clone --depth 1 --branch v0.36.0 https://github.com/comfyanonymous/ComfyUI.git
uv pip install -r ComfyUI/requirements.txt sageattention nvidia-vfx
git clone --depth 1 https://github.com/Comfy-Org/Nvidia_RTX_Nodes_ComfyUI ComfyUI/custom_nodes/Nvidia_RTX_Nodes_ComfyUI
LICENSE_OK=1 ./fetch_h3_weights.sh   # downloads ~41 GB of H3 weights
./launch.sh                          # http://127.0.0.1:8188
```

## Repository layout

```
postward-local-video-gen/
├── README.md                     this file
└── comfyui-runtime/              all scripts, docs, and workflows
    ├── RUNBOOK.md                commands, verified timings, troubleshooting
    ├── PENDING_WEIGHTS.md        weight sizes + license matrix
    ├── LICENSE_GRANT.txt         audit trail (UK license)
    ├── launch.sh                  ComfyUI launcher with lowvram flags
    ├── fetch_h3_weights.sh        license-gated weight downloader
    ├── run_workflow.py            generic workflow API submission
    ├── build_upscale_workflow.py I2V continuity workflow builder
    ├── submit_rtx_vsr.py          RTX Video Super Resolution client
    ├── run_hogwarts_shots.py      multi-shot orchestrator example
    ├── monitor.py                 VRAM/RAM CSV monitor
    └── workflows/                 Comfy-Org pinned revision 3c1df78
```

## Verified outputs (2026-09-20, RTX 4060 8 GB)

| Step | Resolution | Duration | Time |
|---|---|---|---|
| 0.2 MP smoke | 608×352 | 1.6 s | 2:39 |
| 0.4 MP standard | 864×480 | 5.2 s | 8:00 |
| 0.6 MP H3 upscale | 800×800 | 2.3 s | 6:00 |
| RTX VSR final | 1600×1600 | 2.3 s | 0:06 |

All outputs contain H.264 video + 32 kHz stereo AAC audio. See
`comfyui-runtime/RUNBOOK.md` for the full chain recipe.

## License

The MiniMax H3 model weights are governed by the
[MINIMAX H3 Community License Agreement](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE),
which excludes the UK, EU, US, and South Korea from the open release.
Users in those territories must hold a separate license before downloading.

The orchestration code in this repository is provided as-is for Postward
internal use.
