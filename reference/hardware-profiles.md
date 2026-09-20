# Hardware Profiles

Run `python scripts/doctor.py` first. Profiles are recommendations, not
promises; the smoke generation is the final capacity check.

| Profile | VRAM | H3 configuration | Starting recipe |
|---|---:|---|---|
| `constrained` | <8 GB | Official INT8 profile is not supported by this repo | Do not download weights; obtain a separately licensed INT4 profile |
| `4060-8gb` | 8–10 GB | INT8 diffusion + NVFP4 text encoder, CPU/RAM offload, fp16 VAE | 0.2–0.4 MP, 1–5 s, 8-step Turbo LoRA |
| `midrange` | 12–16 GB | INT8 + NVFP4, low/high VRAM according to free memory | 0.4–0.6 MP, 2–5 s |
| `native` | 16 GB+ | high-VRAM or GPU-only after smoke test | 0.6–0.98 MP; use 0.98 rather than 1.0 |

## Shared-GPU rule

The Forge image pipeline and H3 video pipeline are mutually exclusive GPU
clients. Stop or idle one before starting the other. Desktop compositing and
Xorg are expected background users; reserve their observed VRAM in the profile.

## Capacity checks

Before a large job verify:

- free VRAM, not just total VRAM;
- available system RAM and swap pressure;
- free disk for outputs and temporary files;
- all required model files are present;
- no unrelated process owns most of the GPU.

A lower resolution or shorter duration is safer than retrying an OOM unchanged.
