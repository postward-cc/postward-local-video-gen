#!/usr/bin/env python3
"""
Monitor VRAM, RAM, and (if running) ComfyUI inference progress.

Polls nvidia-smi and /proc/meminfo every 2s, plus optionally the ComfyUI
queue endpoint. Logs CSV to logs/monitor-<ts>.csv and prints a one-line
summary every 2s.

Usage:
  ./monitor.py [--server http://127.0.0.1:8188] [--out logs/monitor.csv] [--interval 2]
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib import request


def gpu_stats() -> tuple[int, int, int, str]:
    """Return (vram_used_mb, vram_total_mb, gpu_util_pct, gpu_name)."""
    out = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,name",
         "--format=csv,noheader,nounits"],
        text=True,
    ).strip()
    used, total, util, name = [x.strip() for x in out.split(",")]
    return int(used), int(total), int(util), name


def ram_stats() -> tuple[int, int]:
    """Return (ram_used_mb, ram_total_mb) from /proc/meminfo."""
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":", 1)
            info[k.strip()] = v.strip()
    def mb(s: str) -> int:
        n, unit = s.split()
        return int(int(n) / 1024 if unit == "kB" else int(n))
    return mb(info["MemTotal"]) - mb(info["MemAvailable"]), mb(info["MemTotal"])


def comfy_queue(server: str) -> dict:
    try:
        with request.urlopen(f"{server}/queue", timeout=3) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--interval", type=float, default=2.0)
    args = ap.parse_args()

    if args.out is None:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        args.out = Path(f"logs/monitor-{ts}.csv")

    args.out.parent.mkdir(parents=True, exist_ok=True)

    print(f"monitoring → {args.out}  (Ctrl-C to stop)")
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_iso", "t_sec", "vram_used_mb", "vram_total_mb",
                    "gpu_util_pct", "gpu_name", "ram_used_mb", "ram_total_mb",
                    "queue_running", "queue_pending", "queue_error"])
        t0 = time.time()
        while True:
            try:
                vu, vt, gu, gn = gpu_stats()
                ru, rt = ram_stats()
                q = comfy_queue(args.server)
                qr = len(q.get("queue_running", []))
                qp = len(q.get("queue_pending", []))
                qe = len(q.get("exec_info", {}).get("queue_remaining", [])) if "exec_info" in q else 0
                t = time.time() - t0
                w.writerow([datetime.now().isoformat(timespec="seconds"),
                            f"{t:.1f}", vu, vt, gu, gn, ru, rt, qr, qp, qe])
                f.flush()
                print(f"t={t:6.1f}s  vram={vu}/{vt}MB ({100*vu/vt:.0f}%)  "
                      f"gpu={gu}%  ram={ru/1024:.1f}/{rt/1024:.1f}GB  "
                      f"q_run={qr} q_pend={qp}")
            except KeyboardInterrupt:
                print("stopping")
                return 0
            except Exception as e:
                print(f"poll error: {e}")
            time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main()) if False else None
import sys as _sys
_sys.exit(main())
