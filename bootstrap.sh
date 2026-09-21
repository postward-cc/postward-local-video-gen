#!/usr/bin/env bash
# Bootstrap the local media-generation runtime without modifying system Python/CUDA.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME="$ROOT/comfyui-runtime"
VENV="$RUNTIME/venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu128}"
COMFYUI_VERSION="${COMFYUI_VERSION:-v0.36.0}"
COMFYUI_REPO="${COMFYUI_REPO:-https://github.com/comfyanonymous/ComfyUI.git}"
RTX_NODES_REPO="${RTX_NODES_REPO:-https://github.com/Comfy-Org/Nvidia_RTX_Nodes_ComfyUI.git}"
DRY_RUN=0
SKIP_COMFYUI=0
SKIP_PYTHON_DEPS=0

usage() {
  cat <<'EOF'
Usage: ./bootstrap.sh [options]

Options:
  --dry-run             Check prerequisites and print actions only.
  --skip-comfyui       Do not clone/update ComfyUI or RTX custom nodes.
  --skip-python-deps   Do not create the venv or install Python packages.
  -h, --help           Show this help.

Environment:
  PYTHON_BIN            Python executable used only to create the venv.
  TORCH_INDEX_URL       PyTorch wheel index; default is cu128.
  COMFYUI_VERSION       ComfyUI git tag; default is v0.36.0.
EOF
}

run() {
  if (( DRY_RUN )); then
    printf '+ '
    printf '%q ' "$@"
    printf '\n'
  else
    "$@"
  fi
}

while (($#)); do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --skip-comfyui) SKIP_COMFYUI=1 ;;
    --skip-python-deps) SKIP_PYTHON_DEPS=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if ! command -v git >/dev/null; then
  echo "ERROR: git is required." >&2; exit 1
fi
if ! command -v "$PYTHON_BIN" >/dev/null; then
  echo "ERROR: Python executable not found: $PYTHON_BIN" >&2; exit 1
fi
if ! command -v nvidia-smi >/dev/null; then
  echo "ERROR: nvidia-smi not found. Install a compatible NVIDIA driver first." >&2; exit 1
fi

run mkdir -p "$RUNTIME" "$RUNTIME/downloads" "$RUNTIME/hf-cache" \
  "$RUNTIME/logs" "$RUNTIME/outputs" "$RUNTIME/state" "$RUNTIME/workflows"

if (( ! SKIP_PYTHON_DEPS )); then
  if [[ ! -x "$VENV/bin/python" ]]; then
    echo "Creating isolated Python environment: $VENV"
    run "$PYTHON_BIN" -m venv "$VENV"
  fi
  VENV_PYTHON="$VENV/bin/python"
  run "$VENV_PYTHON" -m pip install --upgrade pip
  run "$VENV_PYTHON" -m pip install torch torchvision torchaudio --index-url "$TORCH_INDEX_URL"
else
  VENV_PYTHON="$VENV/bin/python"
  if [[ ! -x "$VENV_PYTHON" && ! $DRY_RUN ]]; then
    echo "ERROR: --skip-python-deps requested but $VENV_PYTHON does not exist." >&2
    exit 1
  fi
fi

if (( ! SKIP_COMFYUI )); then
  if [[ ! -d "$RUNTIME/ComfyUI/.git" ]]; then
    run git clone --depth 1 --branch "$COMFYUI_VERSION" "$COMFYUI_REPO" "$RUNTIME/ComfyUI"
  fi
  if (( ! SKIP_PYTHON_DEPS )); then
    run "$VENV_PYTHON" -m pip install -r "$RUNTIME/ComfyUI/requirements.txt"
    run "$VENV_PYTHON" -m pip install sageattention nvidia-vfx 'huggingface_hub[cli]>=0.24'
  fi

  RTX_DIR="$RUNTIME/ComfyUI/custom_nodes/Nvidia_RTX_Nodes_ComfyUI"
  if [[ ! -d "$RTX_DIR/.git" ]]; then
    run git clone --depth 1 "$RTX_NODES_REPO" "$RTX_DIR"
  fi
fi

if (( ! DRY_RUN )); then
  echo
  echo "Bootstrap complete. H3 weights were NOT downloaded."
  echo
  "$VENV_PYTHON" "$ROOT/scripts/doctor.py" || true
  echo
  echo "Next steps:"
  echo "  1. Review $ROOT/reference/license-compliance.md"
  echo "  2. If licensed: LICENSE_OK=1 $RUNTIME/fetch_h3_weights.sh"
  echo "  3. Start: $RUNTIME/launch.sh"
else
  echo "Dry run complete; no files or packages were changed."
fi
