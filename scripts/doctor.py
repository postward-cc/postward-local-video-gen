#!/usr/bin/env python3
"""Detect local media-generation capabilities and recommend a profile."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "comfyui-runtime"


def command(*args: str) -> str | None:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def memory_gb() -> float | None:
    try:
        data = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            data[key] = int(value.strip().split()[0])
        return round(data["MemTotal"] / 1024 / 1024, 1)
    except (OSError, KeyError, ValueError):
        return None


def torch_info() -> dict:
    """Probe the runtime venv, even when doctor runs from system Python."""
    probe = RUNTIME / "venv" / "bin" / "python"
    if not probe.exists():
        probe = Path(sys.executable)
    code = (
        "import json, torch; "
        "ok=torch.cuda.is_available(); "
        "p=torch.cuda.get_device_properties(0) if ok else None; "
        "print(json.dumps({'available':ok,'torch':torch.__version__,"
        "'compiled_cuda':torch.version.cuda,"
        "'gpu':p.name if p else None,"
        "'vram_gb':round(p.total_memory/1024**3,2) if p else None,"
        "'vram_mb':round(p.total_memory/1024**2) if p else None,"
        "'compute_capability':list(torch.cuda.get_device_capability(0)) if p else None}))"
    )
    try:
        return json.loads(subprocess.check_output([str(probe), "-c", code], text=True))
    except Exception as exc:
        return {"available": False, "python": str(probe), "error": str(exc)}


def main() -> int:
    gpu_query = command(
        "nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version",
        "--format=csv,noheader,nounits",
    )
    gpu = None
    if gpu_query:
        parts = [part.strip() for part in gpu_query.split(",", 3)]
        if len(parts) == 4:
            gpu = {"name": parts[0], "vram_mb": int(parts[1]),
                   "free_vram_mb": int(parts[2]), "driver": parts[3]}

    torch = torch_info()
    total_mb = int(torch.get("vram_mb") or (gpu or {}).get("vram_mb", 0))
    if total_mb < 7800:
        profile = "constrained: do not use the official 8 GB H3 profile"
    elif total_mb < 12000:
        profile = "4060-8gb: INT8+NVFP4, lowvram, 0.2-0.4 MP, one GPU job"
    elif total_mb < 16000:
        profile = "midrange: INT8+NVFP4, low/high VRAM, 0.4-0.6 MP"
    else:
        profile = "native: high-VRAM profile, smoke-test before 0.98 MP"

    disk = shutil.disk_usage(RUNTIME)
    weights_dir = RUNTIME / "ComfyUI" / "models"
    weights = (sorted(str(p.relative_to(RUNTIME)) for p in
               weights_dir.glob("**/*.safetensors"))
               if weights_dir.exists() else [])
    result = {
        "root": str(ROOT),
        "runtime": str(RUNTIME),
        "gpu": gpu,
        "torch": torch,
        "ram_gb": memory_gb(),
        "disk_free_gb": round(disk.free / 1024**3, 1),
        "disk_warning": disk.free < 20 * 1024**3,
        "weights_present": weights,
        "recommended_profile": profile,
        "gpu_concurrency": 1,
    }
    print(json.dumps(result, indent=2))
    return 0 if torch.get("available") else 2


if __name__ == "__main__":
    raise SystemExit(main())
