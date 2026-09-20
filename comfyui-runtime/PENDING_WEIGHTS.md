# PENDING_WEIGHTS.md — do NOT download until UK license is confirmed

The MiniMax H3 Community License (revised 2026-08-26) names the United Kingdom
as an Excluded Territory. UK users must hold a separate license before
downloading, deploying, or offering H3 as a hosted service.

Source: https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE
Source: https://platform.minimax.io/docs/guides/local-deploy-h3.md

## Local-ComfyUI weights needed for the T2V setup

| File | Size on disk | Source | Destination |
|---|---:|---|---|
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 19.53 GB | `Comfy-Org/MiniMax-H3` revision `4cc1d817` | `ComfyUI/models/diffusion_models/` |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 14.61 GB | same | `ComfyUI/models/text_encoders/` |
| `minimax_h3_video_vae_fp16.safetensors` | 4.85 GB | same | `ComfyUI/models/vae/` |
| `minimax_h3_audio_vae_fp32.safetensors` | 0.56 GB | same | `ComfyUI/models/vae/` |
| `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | 1.82 GB | `lightx2v/Minimax-h3-Turbo` | `ComfyUI/models/loras/` |
| **Total** | **~41.4 GB** | | |

Sizes verified with HTTP HEAD on 2026-09-20.

## Optional extras (only if R2V is needed)

- `minimax_h3_ref2va_pruned_int8_convrot.safetensors` (19.5 GB) — Ref2VA diffusion model

## Disk math

| Path | Free now | After 41.4 GB download | Notes |
|---|---:|---:|---|
| `/home` | 71 GB | ~29 GB | Fits; leaves room for 1-2 generations (~50-200 MB each) |
| `/` | 181 GB | 181 GB | Fallback storage if `/home` runs out |

If `/home` pressure becomes a problem during large-scale runs, symlink
`ComfyUI/models/` to a path under `/var/data/` or `/`.

## What to do once license is confirmed

```bash
cd /home/mvallebr/git/video_gen_poc/comfyui-runtime
./fetch_h3_weights.sh   # see RUNBOOK.md for the script body
```

Then `./launch.sh` and load `workflows/video_minimax_h3_t2v.json` in the GUI.
