# ADR 0001: Skill as the Primary Agent Interface

- Status: accepted
- Date: 2026-09-21

## Context

Postward wants an OMP model to request local image and video generation on
machines with different NVIDIA GPUs. The execution is long-running and GPU
memory is the limiting resource. The model must choose resolution, offload, and
workflow based on detected hardware.

## Decision

Make the repository an OMP skill bundle with a small local CLI/runtime seam.
Treat MCP as an optional adapter, not the primary interface.

The skill teaches the model the decision tree, license gate, concurrency policy,
workflow recipes, and failure recovery. `doctor.py` detects the machine. The
job queue and GPU lease serialize inference.

## Consequences

Positive:

- Hardware differences are handled at runtime rather than hidden in a fixed
  MCP schema.
- The skill composes with OMP's existing shell, browser, and other media tools.
- The same scripts remain directly usable by humans and CI.
- A future MCP adapter can call the stable CLI interface without moving logic.

Negative:

- The model must parse structured CLI results or use the queue commands.
- The initial implementation does not provide a network-shared service.
- Long-running jobs require persistent local state and orphan recovery.

## Rejected alternative

A first-class MCP-only server was rejected because it would expose a large
hardware-dependent schema, add a process lifecycle/port to every installation,
and make the primary interface less portable across workstations.
