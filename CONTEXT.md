# Postward Local Media Generation — Domain Context

This glossary defines the user-facing domain. It intentionally avoids paths,
frameworks, and implementation details.

## Media asset

A user-provided or generated image, video, or audio file. Assets have an
identity, provenance, and lifecycle. A generated asset must record the job that
created it.

## Generation job

One user-requested execution that produces one or more media assets. A job has a
stable ID, request parameters, hardware profile, lifecycle status, logs, and
output paths.

Statuses: `queued`, `running`, `success`, `failed`, `cancelled`, `interrupted`.

## Workflow

A reproducible graph describing how inputs become outputs. A workflow may be
text-to-video, image-to-video, reference-to-video, image generation, or video
upscale.

## Shot

A bounded narrative segment generated as one video clip. A multi-shot sequence
is a list of shots ordered in time. Each shot may use the preceding shot's last
frame as its first-frame continuity anchor.

## Continuity anchor

A specific image frame that constrains the identity, composition, or scene at a
shot boundary. A continuity anchor is not interchangeable with an arbitrary
file named `last_frame.png`; its source path and SHA-256 belong to the job
manifest.

## Hardware profile

The capabilities and operating limits detected on the current workstation:
GPU, VRAM, system RAM, CUDA/PyTorch state, free disk, and recommended
resolution/offload policy.

## GPU lease

Exclusive ownership of the workstation's inference GPU by one running
Generation job. CPU preprocessing may occur without the lease; model inference
may not.

## Queue

The persistent ordered set of Generation jobs waiting for the GPU lease. Queue
state survives model context loss and exposes job IDs for status/cancellation.

## Local inference

Execution in which model weights and input data are processed on the local
workstation. A successful local job must not rely on an external generation API.

## Media pipeline

An ordered composition of workflows, for example:

```text
Image → I2V shot → continuity shot → concat → RTX VSR → final video
```
