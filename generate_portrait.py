#!/usr/bin/env python3
"""
generate_portrait.py

Converts a photo into an animated, character-shaded SVG portrait for a
GitHub profile README. Designed to be re-run by a scheduled GitHub Action
so the piece subtly reshuffles over time (new glyph seed = new day).

Usage:
    python3 generate_portrait.py <input_photo> <output_svg> [--seed N] [--cols N]
"""

import sys
import argparse
import random
import numpy as np
from PIL import Image

# Density tiers: light -> dark. Each tier has a few candidate glyphs so the
# texture reads as "code" rather than a plain ASCII ramp, while brightness
# ordering stays correct.
TIERS = [
    [" "],  # background / fully blank
    [".", "`", "'", ":"],
    [";", ",", '"', "~"],
    ["-", "_", "+"],
    ["/", "\\", "|", "<", ">"],
    ["?", "!", "1", ")", "("],
    ["*", "i", "l", "I"],
    ["x", "n", "u", "v", "c"],
    ["z", "j", "t", "f", "r"],
    ["0", "O", "Q", "C"],
    ["#", "%", "@", "&", "B", "M", "W"],
]

BG_THRESHOLD = 0.93  # brightness (0-1) above which a cell is treated as background


def autocrop(im, pad_frac=0.06):
    arr = np.array(im.convert("RGB")).astype(np.float32)
    gray = arr.mean(axis=2) / 255.0
    mask = gray < 0.94
    ys, xs = np.where(mask)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    w, h = x1 - x0, y1 - y0
    pad_x, pad_y = int(w * pad_frac), int(h * pad_frac)
    x0 = max(0, x0 - pad_x)
    y0 = max(0, y0 - pad_y)
    x1 = min(im.width, x1 + pad_x)
    y1 = min(im.height, y1 + pad_y)
    return im.crop((x0, y0, x1, y1))


def brightness_grid(im, cols, rows):
    small = im.convert("L").resize((cols, rows), Image.BOX)
    arr = np.array(small).astype(np.float32) / 255.0
    return arr  # shape rows x cols, 0=dark .. 1=light


def pick_glyph(brightness, rng):
    if brightness >= BG_THRESHOLD:
        return None
    # invert: dark pixel -> high tier (dense glyph)
    ink = 1.0 - (brightness / BG_THRESHOLD)
    tier_idx = min(len(TIERS) - 1, int(ink * (len(TIERS) - 1)) + 1)
    tier_idx = max(1, tier_idx)
    candidates = TIERS[tier_idx]
    return rng.choice(candidates)


def build_svg(brightness, cell_w, cell_h, font_size, seed, accent, dim, bg):
    rows, cols = brightness.shape
    rng = random.Random(seed)
    width = cols * cell_w
    height = rows * cell_h

    n_groups = 9
    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="ui-monospace, SFMono-Regular, '
        f'Menlo, Consolas, monospace" font-size="{font_size}">'
    )

    style = [f"<style>", f"svg{{background:{bg};}}", "text{white-space:pre;}"]
    for g in range(n_groups):
        dur = round(rng.uniform(2.6, 5.5), 2)
        delay = round(rng.uniform(0, 4), 2)
        lo = round(rng.uniform(0.35, 0.55), 2)
        style.append(
            f".g{g}{{animation:flicker{g} {dur}s ease-in-out {delay}s infinite;}}"
            f"@keyframes flicker{g}{{0%,100%{{opacity:1;}}50%{{opacity:{lo};}}}}"
        )
    style.append("</style>")
    parts.append("".join(style))

    for r in range(rows):
        y = r * cell_h + font_size
        row_spans = []
        for c in range(cols):
            b = float(brightness[r, c])
            glyph = pick_glyph(b, rng)
            if glyph is None or glyph == " ":
                continue
            x = c * cell_w
            ink = 1.0 - min(b / BG_THRESHOLD, 1.0)
            opacity = round(0.35 + 0.65 * ink, 2)
            color = accent if rng.random() < 0.035 else dim if ink < 0.28 else "#eef3ff"
            group = rng.randrange(n_groups)
            glyph_esc = (
                glyph.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            row_spans.append(
                f'<tspan x="{x}" class="g{group}" fill="{color}" '
                f'fill-opacity="{opacity}">{glyph_esc}</tspan>'
            )
        if row_spans:
            parts.append(f'<text y="{y}">{"".join(row_spans)}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--cols", type=int, default=64)
    ap.add_argument("--cell-w", type=float, default=7.4)
    ap.add_argument("--cell-h", type=float, default=13.2)
    ap.add_argument("--font-size", type=float, default=11.5)
    ap.add_argument("--bg", type=str, default="#0d1117")
    ap.add_argument("--accent", type=str, default="#58a6ff")
    ap.add_argument("--dim", type=str, default="#6e7681")
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else random.randrange(1_000_000)

    im = Image.open(args.input)
    im = autocrop(im)
    aspect = im.height / im.width
    rows = max(1, round(args.cols * aspect * (args.cell_w / args.cell_h)))

    grid = brightness_grid(im, args.cols, rows)
    svg = build_svg(
        grid, args.cell_w, args.cell_h, args.font_size, seed, args.accent, args.dim, args.bg
    )

    with open(args.output, "w") as f:
        f.write(svg)

    print(f"wrote {args.output} ({args.cols}x{rows} grid, seed={seed})")


if __name__ == "__main__":
    main()
