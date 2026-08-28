---
name: animated-sticker-board-cutter
description: "Create an eight-piece animated sticker pack workflow from a reference character or an existing 4×2 board: prepare the identity-consistent board, write a constrained 10-second Gemini animation prompt, then locally split the returned white-background video into transparent APNG and GIF stickers with QA and ZIP packages. Also use when only the local StickerFaster replacement/cutting stage is requested."
---

# Animated Sticker Pack Workflow

Produce an identity-consistent 4×2 animated sticker pack from reference image through final local downloads, without paying a cutting website.

## Route by starting material

- **Reference character only:** run Phase A, give the user the finished board, then run Phase B. Pause until the user supplies the generated video, unless a video-generation tool is explicitly requested and available.
- **Finished 4×2 static board:** skip Phase A and run Phase B.
- **Finished animation video:** skip directly to Phase C.

Do not repeat a phase whose artifact the user has already accepted.

## Phase A — create the 4×2 character board

Create a landscape 4×2 board with eight isolated character stickers in reading order. Preserve identity, face or device shape, hair or casing, key features, proportions, and clothing style. Give every cell a distinct strong reaction and pose. Keep generous transparent spacing, no overlaps, no text, no watermark, and preferably no grid lines. A transparent board is preferred; the Gemini prompt will request a white video background for reliable local removal.

For the established console character, the eight reactions are:

```text
爆笑,震惊,疑惑,委屈,得意,翻白眼,无语,愤怒
```

Show the board for user review before using it as an animation reference. Fix identity drift, missing limbs, overlap, or inconsistent cell placement first.

## Phase B — write the Gemini 10-second prompt

Use the accepted 4×2 board as the only character, styling, and layout reference. The prompt must require:

- About 10 seconds, landscape, white background, no grid lines, numbering, captions, watermark, or new characters.
- Fixed camera; no cuts, zoom, reframing, or cell movement.
- Each character remains centered in its original cell and never crosses a cell boundary.
- Seconds `0–5` and `5–10` contain clearly different, large actions and expressions, changing naturally at about second 5.
- Eight explicit action pairs, listed 1–8 in board reading order as `first-half action → second-half action`.
- Strong meme-reaction timing rather than tiny breathing, blinking, or hand jitter only.

If the user has not supplied action pairs, derive them from the eight board reactions and present one best prompt. Do not add dialogue, sound-dependent timing, or scenery unless requested. The reusable prompt pattern is in [references/usage.md](references/usage.md).

## Phase C — cut and export locally

### Required input

- An existing video containing fixed-position characters on a white or near-white background.
- The grid shape, defaulting to `4×2`.
- The source segment. Default to `0–2 seconds` unless the user specifies another action window.
- Optional sticker labels. If labels are known, pass them in reading order from left to right, then top to bottom.

Ask only for information that is actually missing. A request containing a video, grid shape, and desired segment is complete.

### Execute

1. Inspect the input with `ffprobe`. Preserve the source file.
2. Choose a new output directory in a writable workspace. Do not reuse a non-empty directory.
3. Run `scripts/export_sticker_board.py`.
4. Let `grid-mode=auto` first look for full-length dark grid lines. It automatically falls back to equal cells when a clean line grid is absent.
5. The script removes only near-white regions connected to cell edges. This protects enclosed white details such as eyes, shirts, and device casing.
6. Require the generated QA report to pass, then visually inspect the transparent preview on a contrasting background. Check the middle and late portions of the animation, not only frame one.
7. Return clickable links to the all-formats ZIP, APNG ZIP, GIF ZIP, preview, and output directory.

Default command:

```bash
python3 <skill-dir>/scripts/export_sticker_board.py \
  "/absolute/path/source.mp4" \
  --output "/absolute/path/new-output-folder" \
  --columns 4 --rows 2 --start 0 --duration 2
```

When the eight expressions are the established console-character set, use:

```text
爆笑,震惊,疑惑,委屈,得意,翻白眼,无语,愤怒
```

## Quality gates

Do not report completion unless all applicable checks pass:

- Exactly one APNG and one GIF per selected cell and action window.
- APNG: square `320×320`, transparent corners, multiple unique frames, approximately 2 seconds by default.
- GIF: square `240×240`, transparent corners, multiple unique frames, approximately 2 seconds by default.
- No grid line, neighboring character, opaque white rectangle, text, or unexpected crop in the preview.
- Every ZIP opens and contains the expected files.

If the preview retains white areas, lower `--white-threshold` in small steps, such as `235 → 230 → 225`. If pale outer parts of the character disappear, raise it, such as `235 → 240 → 245`. Never use a global white color key: it creates holes in white facial and clothing details.

If characters cross cells, the background is complex, or the board moves relative to the camera, stop and explain that this deterministic local cutter is not the correct method.

For one eight-sticker pack, export one two-second window such as `0–2`. To turn both Gemini action halves into separate stickers, run the cutter twice, such as `0–2` and `5–7`, with different labels and output directories; this produces sixteen stickers.

## Boundaries

- Operate the cutting stage locally; do not upload to StickerFaster or another service unless the user explicitly asks.
- Do not buy points, subscribe, or perform a checkout.
- Do not delete or replace the source video.
- Treat a non-empty output directory as owned by the user; choose a new directory instead of clearing it.

For command options, output contents, alternate segments, explicit grid coordinates, and troubleshooting, read [references/usage.md](references/usage.md).
