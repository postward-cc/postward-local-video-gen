# License Compliance

MiniMax H3 weights are governed by the
[MINIMAX H3 Community License Agreement](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE).
The revision reviewed for this project lists the United Kingdom, European
Union, United States, and South Korea as Excluded Territories requiring a
separate license.

## Required behavior

- Never download H3 weights without an explicit user confirmation that the
  applicable separate license is granted.
- Keep the `LICENSE_OK=1` gate in `fetch_h3_weights.sh`.
- Record the confirmation in an audit file without storing confidential license
  documents or keys.
- Do not claim commercial rights for generated outputs unless the user's
  license covers them.
- Distinguish local open-weight inference from hosted API terms.

## Download gate

```bash
LICENSE_OK=1 ./comfyui-runtime/fetch_h3_weights.sh
```

The gate is an operational safeguard, not legal advice. Users remain
responsible for reviewing the current license before downloading or deploying.
