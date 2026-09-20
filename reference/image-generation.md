# Local Image Generation Adapter

This repository's skill may coordinate with the existing Stable Diffusion WebUI
Forge installation when image generation is requested.

## Existing validated installation

- Forge: `/opt/aigen/forge`
- GUI: `http://127.0.0.1:7860`
- Model: `sd_xl_base_1.0.safetensors`
- Model directory: `/opt/aigen/forge/models/Stable-diffusion/`
- PyTorch: 2.5.1 + cu124
- GPU baseline: RTX 4060 8 GB
- Recommended: 1024×1024, batch size 1, 25–30 steps, DPM++ 2M Karras, CFG 7

## GPU sharing

Forge and ComfyUI/H3 are two adapters at the same GPU lease. Do not generate an
image and video concurrently on an 8 GB card. Check `nvidia-smi`, wait for the
other job, or stop the known service only after user approval.

## Ollama image generation

The previous experiment downloaded `x/flux2-klein:4b` but inference failed on
Linux because the Ollama image runner required MLX (`libmlxc.so`). Ollama remains
useful for local text/vision and cloud text models, but it is not the local image
adapter in this skill.

## Model additions

New Forge checkpoints and LoRAs require the same provenance discipline as H3:
record source, license, file size, hash, and target directory. Never download a
large checkpoint without checking free disk and applicable license terms.
