#!/usr/bin/env bash
# Download MiniMax H3 weights into ComfyUI/models/.
#
# HARD GATE: this script refuses to download unless LICENSE_OK=1 is exported.
# The MiniMax H3 Community License (revised 2026-08-26) names the United Kingdom
# as an Excluded Territory. UK users must hold a separate license before
# downloading, deploying, or offering H3 as a hosted service.
#
# After the user confirms the UK license has been granted:
#   LICENSE_OK=1 ./fetch_h3_weights.sh
#
# Downloads go via huggingface-cli. Files are pinned to:
#   - Comfy-Org/MiniMax-H3  revision 4cc1d817b6184899b41293954329f576cb5ae86b
#   - lightx2v/Minimax-h3-Turbo (8-step Turbo LoRA, pinned at main on 2026-09-20)

set -euo pipefail

if [[ "${LICENSE_OK:-0}" != "1" ]]; then
  echo "ERROR: MiniMax H3 weights are gated behind license confirmation." >&2
  echo "       Re-run after the UK license is granted:" >&2
  echo "         LICENSE_OK=1 $0" >&2
  echo "       See PENDING_WEIGHTS.md for the legal basis." >&2
  exit 2
fi

cd "$(dirname "$0")"
# shellcheck disable=SC1091
source venv/bin/activate

export HF_HUB_DISABLE_TELEMETRY=1
export HF_HOME="${HF_HOME:-$PWD/hf-cache}"
mkdir -p "$HF_HOME" downloads

REVISION="4cc1d817b6184899b41293954329f576cb5ae86b"

# Use huggingface-cli when present; otherwise pip install it (it's tiny).
if ! python -c "import huggingface_hub" 2>/dev/null; then
  uv pip install "huggingface_hub[cli]>=0.24"
fi

MODEL_DIR="ComfyUI/models"

# 1. FL2VA diffusion (T2V + I2V)
hf download Comfy-Org/MiniMax-H3 \
  --revision "$REVISION" \
  --include "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors" \
  --local-dir "$MODEL_DIR"

# 2. NVFP4 text encoder
hf download Comfy-Org/MiniMax-H3 \
  --revision "$REVISION" \
  --include "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors" \
  --local-dir "$MODEL_DIR"

# 3. Video VAE
hf download Comfy-Org/MiniMax-H3 \
  --revision "$REVISION" \
  --include "vae/minimax_h3_video_vae_fp16.safetensors" \
  --local-dir "$MODEL_DIR"

# 4. Audio VAE
hf download Comfy-Org/MiniMax-H3 \
  --revision "$REVISION" \
  --include "vae/minimax_h3_audio_vae_fp32.safetensors" \
  --local-dir "$MODEL_DIR"

# 5. 8-step Turbo LoRA (from lightx2v, not Comfy-Org)
hf download lightx2v/Minimax-h3-Turbo \
  --include "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors" \
  --local-dir downloads/turbo-lora

mv downloads/turbo-lora/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors \
   ComfyUI/models/loras/

echo
echo "Done. Disk used:"
du -sh ComfyUI/models/* 2>/dev/null
df -h /home | tail -1
