# Install `postward-local-media-gen`

This repository is both an OMP skill and a local runtime bootstrap. A model
can clone the repo, read `SKILL.md`, run the doctor, and bootstrap the local
adapters without modifying system Python or the system CUDA toolkit.

## Fast path

```bash
git clone https://github.com/postward-cc/postward-local-media-gen.git
cd postward-local-media-gen
./bootstrap.sh
```

`bootstrap.sh` does **not** download MiniMax H3 weights. Those files are about
41 GB and are protected by an explicit license gate.

## What bootstrap installs

Inside `comfyui-runtime/venv/` only:

- PyTorch, torchvision, torchaudio from the cu128 wheel index
- ComfyUI v0.36.0
- Sage Attention
- `nvidia-vfx`
- `huggingface_hub` CLI support
- `Comfy-Org/Nvidia_RTX_Nodes_ComfyUI`

It also creates the runtime directories and runs `scripts/doctor.py` using the
new venv. The system Python and `/usr/local/cuda` are not changed.

## Options

```bash
./bootstrap.sh --help
./bootstrap.sh --dry-run
./bootstrap.sh --skip-comfyui
./bootstrap.sh --skip-python-deps
TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128 ./bootstrap.sh
```

`--dry-run` prints actions and checks prerequisites without creating the venv,
cloning ComfyUI, or installing packages.

## Hardware behavior

The bootstrap detects `nvidia-smi`, but installation is intentionally conservative:
it installs the common cu128 PyTorch runtime and leaves generation profile
selection to `scripts/doctor.py` and `SKILL.md`.

```bash
python scripts/doctor.py
```

The doctor reports a profile:

- `4060-8gb`: INT8 + NVFP4, low-VRAM/offload, 0.2–0.4 MP
- `midrange`: 12–16 GB, 0.4–0.6 MP
- `native`: 16 GB+, smoke-test before 0.98 MP

## H3 license gate

After bootstrap, review the current MiniMax H3 license and confirm that your
use is permitted. Then, and only then:

```bash
LICENSE_OK=1 ./comfyui-runtime/fetch_h3_weights.sh
```

The script downloads the exact pinned components described in
`comfyui-runtime/PENDING_WEIGHTS.md`. It refuses to run without
`LICENSE_OK=1`.

## Start ComfyUI

```bash
./comfyui-runtime/launch.sh
```

Open `http://127.0.0.1:8188`.

## Run a job safely

One GPU inference job is allowed at a time:

```bash
python scripts/job_queue.py run --kind h3-t2v -- \
  python comfyui-runtime/run_workflow.py \
    comfyui-runtime/workflows/video_minimax_h3_t2v.json \
    --megapixels 0.4 --duration 5 --turbo-steps 8 \
    --prompt "A cinematic train station at dawn" \
    --out-dir comfyui-runtime/outputs/train-station
```

For concurrent logical requests, enqueue them rather than starting multiple
ComfyUI prompts:

```bash
python scripts/job_queue.py enqueue --kind h3-t2v \
  --payload '{"prompt":"a castle in the clouds"}'
python scripts/job_queue.py list
```

## Image generation

The H3 runtime is for video. If Forge is already installed at `/opt/aigen/forge`,
use `reference/image-generation.md` for local image generation. Forge and H3
share the same GPU lease; do not run both inference engines simultaneously on an
8 GB card.

## Uninstall

The bootstrap only creates/clones content under this repository. To remove the
runtime without touching system Python or CUDA:

```bash
rm -rf comfyui-runtime/venv comfyui-runtime/ComfyUI
rm -rf comfyui-runtime/hf-cache comfyui-runtime/state
```

Do not delete model files unless you have confirmed they are no longer needed.
