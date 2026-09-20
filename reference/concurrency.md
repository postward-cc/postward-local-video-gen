# Concurrency and Job Lifecycle

## Policy

One GPU inference job at a time. Multiple logical requests are accepted through
the persistent queue. CPU-only ffmpeg work may run concurrently when resources
allow.

## Lifecycle

```text
queued → running → success
                 ├→ failed
                 ├→ cancelled
                 └→ interrupted
```

Every job gets a unique directory under `state/jobs/<job_id>/` or the configured
output root. Never share a generic `output.mp4` between jobs.

## Orphan recovery

On startup or `doctor.py`, a `running` job whose PID no longer exists becomes
`interrupted`. The GPU lease is then eligible for a new job.

## Fairness

Default FIFO. A priority flag may be added later, but interactive requests
must not starve a long queued batch. Cancellation is allowed for queued jobs;
running jobs are terminated only by explicit user request.

## Why not run two H3 jobs?

The 8 GB profile stages roughly 20 GB of diffusion weights and 15 GB of text
encoder weights in system RAM while swapping active layers through the GPU.
Launching a second sampler destroys the VRAM budget and usually produces OOM or
unusable swap thrashing.
