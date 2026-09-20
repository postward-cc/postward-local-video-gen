# Workflow Recipes

## T2V smoke

Use the official T2V template, 0.2 MP, 1 s requested duration, 8-step Turbo
LoRA. The model snaps duration to its valid `17k+5` frame grid.

## T2V standard

Use 0.4 MP, 5 s, 8-step Turbo LoRA. This is the validated RTX 4060 profile.
Expect roughly eight minutes per clip on the tested workstation.

## I2V continuity

Use a unique staged input filename for every shot. Record its SHA-256 in the
job manifest. Do not reuse a generic `last_frame.png` from a previous run.

1. Extract the previous shot's last frame.
2. Copy it to `ComfyUI/input/<job>-<shot>-first.png`.
3. Set the I2V loader to that exact filename.
4. Keep the same subject description and explicitly demand identity preservation.
5. Verify the generated first frame before continuing.

## Multi-shot narrative

Break a narrative into bounded shots. Avoid asking one generation to change
location, camera language, subject action, and composition all at once. The
continuity anchor controls the visual handoff; the prompt controls the action.

Concatenate with re-encoding rather than stream-copy when inputs have differing
DTS/time-base metadata. This avoids non-monotonic timestamp warnings and makes
seek/playback reliable.

## RTX VSR

Run RTX VSR only after the base video is valid and locally inspectable. The RTX
node uses a DynamicCombo input; use `submit_rtx_vsr.py` rather than guessing a
saved-format conversion.
