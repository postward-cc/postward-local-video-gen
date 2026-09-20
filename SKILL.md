# Postward Local Media Generation

Use this skill when a user asks OMP to generate or transform images or videos
locally on the workstation. This skill covers image generation through Forge,
MiniMax H3 T2V/I2V/R2V video generation, multi-shot continuity, and NVIDIA RTX
Video Super Resolution.

## Operating contract

1. Run `scripts/doctor.py` before choosing a workflow.
2. Read `reference/hardware-profiles.md` and use the detected profile.
3. Check license state before downloading H3 weights.
4. Acquire the GPU job lock before starting inference.
5. Run one GPU inference job at a time. Queue additional jobs.
6. Use a unique job/output directory for every request.
7. Record the source-image hash for every I2V shot.
8. Return the job ID, output paths, resolution, duration, and any warnings.

## Capabilities

- Text → video: `comfyui-runtime/run_workflow.py` with the official H3 T2V template.
- Image → video: `comfyui-runtime/build_upscale_workflow.py` with a verified
  first-frame input and the official H3 I2V template.
- Multi-shot narrative: `comfyui-runtime/run_hogwarts_shots.py`; customize its
  `SHOTS` data, preserve each shot's source frame, and never reuse a generic
  stale `last_frame.png` from another run.
- RTX VSR: `comfyui-runtime/submit_rtx_vsr.py`.
- Local image generation: use the separate Forge installation described in
  `reference/image-generation.md` when it exists. Forge and H3 share the GPU
  lock; never run both inference engines simultaneously.

## Hardware decision tree

| Detected state | Action |
|---|---|
| No CUDA GPU | Do not start H3; explain that this skill requires an NVIDIA GPU. |
| < 8 GB VRAM | Do not download the official 8 GB profile. Recommend a separately licensed INT4 profile or stop. |
| 8–10 GB VRAM | INT8 + NVFP4, `--lowvram`, 0.2–0.4 MP, one job only. |
| 12–16 GB VRAM | INT8 + NVFP4, low/high VRAM depending on doctor output, 0.4–0.6 MP. |
| 16 GB+ VRAM | Consider high-VRAM/native 0.98 MP after a smoke test. |

Never infer a profile from the GPU model name alone; use measured free VRAM,
RAM, disk, driver and PyTorch CUDA availability.

## Concurrent requests

The interface accepts concurrent logical requests, but the implementation must
serialize GPU inference:

```text
request A ─┐
request B ─┼── persistent queue + GPU lock ── one inference at a time
request C ─┘
```

CPU-only work such as ffmpeg frame extraction, metadata inspection, and output
copying may run concurrently if disk/RAM limits allow. If the user asks for
three videos, enqueue three jobs and report one `running` plus two `queued`; do
not launch three ComfyUI prompts at once.

Use:

```bash
python scripts/job_queue.py enqueue --kind h3-t2v --payload '{"prompt":"..."}'
python scripts/job_queue.py list
python scripts/job_queue.py status JOB_ID
python scripts/job_queue.py cancel JOB_ID
```

For a direct command that must hold the GPU lock:

```bash
python scripts/job_queue.py run --kind h3-t2v -- \
  python comfyui-runtime/run_workflow.py ...
```

## License gate

H3 weights are not downloaded implicitly. The user must explicitly confirm the
applicable MiniMax license. The downloader requires:

```bash
LICENSE_OK=1 ./comfyui-runtime/fetch_h3_weights.sh
```

The skill must never set `LICENSE_OK=1` based on inference or silently bypass
the gate. See `reference/license-compliance.md`.

## Failure policy

- OOM: mark the job failed, preserve the log, lower resolution/duration or use
  a more aggressive offload profile; do not retry the same request unchanged.
- Process crash: mark orphaned `running` jobs as `interrupted` on the next
  doctor/queue invocation and release the lock.
- Missing model: report the exact missing filename and the license-gated
  download command.
- Wrong source frame: fail before submission if the declared source path or
  SHA-256 does not match the job manifest.
- Concurrent Forge/H3 use: wait for the other engine or ask the user before
  stopping a known service; never kill unrelated GPU processes.

## Output contract

Every completed generation should return:

```json
{
  "job_id": "...",
  "status": "success",
  "outputs": ["/absolute/path/to/video.mp4"],
  "resolution": "864x480",
  "duration_seconds": 5.2,
  "audio": "aac stereo 32000 Hz",
  "local_inference": true,
  "warnings": []
}
```

The model should link or state the final output path, not ask the user to search
through ComfyUI history manually.
