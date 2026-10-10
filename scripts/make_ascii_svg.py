#!/usr/bin/env python3
"""
Convert a prepped grayscale image into a clean, monochrome ASCII-art SVG
with a one-shot typewriter terminal reveal animation.

Each row is revealed with a left-to-right clip wipe plus an advancing block
cursor riding the edge, staggered top -> bottom, so the portrait prints
once and freezes.
"""
import argparse
import html
import os
import sys
from PIL import Image, ImageEnhance

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.join(HERE, "..", "source-prepped.png")
DEFAULT_OUT = os.path.join(HERE, "..", "portrait-ascii.svg")

# Bright (sparse) -> Dark (dense); leading space washes out background
RAMP = " .`:-=+*cs#%@"


def generate_ascii_svg(src_path, out_path, cols=110, static=False):
    if not os.path.exists(src_path):
        print(f"ERROR: Source image not found: {src_path}", file=sys.stderr)
        sys.exit(1)

    art_w_target = 800
    cell_w = art_w_target / cols
    cell_h = cell_w * 15 / 8
    rows = round(cols * 8 / 15)

    contrast = 1.05
    brightness = 1.0
    gamma = 1.18
    white_floor = 0.80

    pad = 20
    titlebar_h = 30
    status_h = 30
    art_w = cols * cell_w
    art_h = rows * cell_h
    canvas_w = art_w + pad * 2
    canvas_h = titlebar_h + art_h + status_h + pad

    bg = "#0d1117"
    bg2 = "#111722"
    frame = "#30363d"
    title_text = "#7d8590"
    ink = "#c9d1d9"
    cursor_color = "#c9d1d9"

    row_dur = 5.8 / rows
    stagger = row_dur

    im = Image.open(src_path).convert("L")
    im = ImageEnhance.Brightness(im).enhance(brightness)
    im = ImageEnhance.Contrast(im).enhance(contrast)
    im = im.resize((cols, rows), Image.Resampling.LANCZOS)
    px = im.load()

    rows_txt = []
    for y in range(rows):
        chars = []
        for x in range(cols):
            lum = px[x, y] / 255.0
            lum = pow(lum, gamma)
            if lum >= white_floor:
                chars.append(" ")
                continue
            idx = int((1.0 - lum) * (len(RAMP) - 1) + 0.5)
            idx = max(0, min(len(RAMP) - 1, idx))
            chars.append(RAMP[idx])
        rows_txt.append("".join(chars))

    art_top = titlebar_h + pad * 0.35

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w:.1f}" height="{canvas_h:.1f}" '
        f'viewBox="0 0 {canvas_w:.1f} {canvas_h:.1f}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        '<defs>',
        f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">',
        f'<stop offset="0" stop-color="{bg2}"/><stop offset="1" stop-color="{bg}"/>',
        '</linearGradient></defs>',
        f'<rect width="{canvas_w:.1f}" height="{canvas_h:.1f}" rx="12" fill="url(#bg)"/>',
        f'<rect x="0.5" y="0.5" width="{canvas_w-1:.1f}" height="{canvas_h-1:.1f}" rx="12" fill="none" stroke="{frame}" stroke-width="1"/>',
        f'<line x1="0" y1="{titlebar_h}" x2="{canvas_w:.1f}" y2="{titlebar_h}" stroke="{frame}"/>',
    ]

    for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        parts.append(f'<circle cx="{pad + i*16}" cy="{titlebar_h/2}" r="5" fill="{dotcol}"/>')
    parts.append(
        f'<text x="{canvas_w/2:.1f}" y="{titlebar_h/2 + 4}" fill="{title_text}" font-size="12" '
        f'text-anchor="middle">helloabhishek2004@github: ~$ ./portrait.sh</text>'
    )

    font_size = cell_h * 0.86
    for ry, line in enumerate(rows_txt):
        y = art_top + ry * cell_h + cell_h * 0.74
        row_y = art_top + ry * cell_h
        delay = ry * stagger
        safe = html.escape(line)
        text = (
            f'<text xml:space="preserve" x="{pad}" y="{y:.1f}" fill="{ink}" '
            f'font-size="{font_size:.1f}" textLength="{art_w:.1f}" lengthAdjust="spacing">{safe}</text>'
        )

        if static:
            parts.append(text)
            continue

        parts.append(
            f'<clipPath id="r{ry}"><rect x="{pad}" y="{row_y:.1f}" height="{cell_h:.2f}" width="0">'
            f'<animate attributeName="width" from="0" to="{art_w:.1f}" begin="{delay:.3f}s" '
            f'dur="{row_dur:.2f}s" fill="freeze"/></rect></clipPath>'
        )
        parts.append(f'<g clip-path="url(#r{ry})">{text}</g>')
        parts.append(
            f'<rect y="{row_y+1:.1f}" width="{cell_w:.1f}" height="{cell_h-2:.2f}" fill="{cursor_color}" opacity="0">'
            f'<animate attributeName="x" from="{pad}" to="{pad+art_w:.1f}" begin="{delay:.3f}s" '
            f'dur="{row_dur:.2f}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.85" begin="{delay:.3f}s"/>'
            f'<set attributeName="opacity" to="0" begin="{delay+row_dur:.3f}s"/></rect>'
        )

    # Status bar with blinking prompt cursor
    status_line_y = titlebar_h + art_h + pad * 0.35
    status_y = status_line_y + 19
    parts.append(f'<line x1="0" y1="{status_line_y:.1f}" x2="{canvas_w:.1f}" y2="{status_line_y:.1f}" stroke="{frame}"/>')
    parts.append(
        f'<text x="{pad}" y="{status_y:.1f}" fill="{title_text}" font-size="13">'
        f'helloabhishek2004@github:~$ whoami <tspan fill="{ink}">Abhishek</tspan></text>'
    )
    status_chars = len("helloabhishek2004@github:~$ whoami Abhishek ")
    parts.append(
        f'<rect x="{pad + status_chars * 13 * 0.6:.1f}" y="{status_y-12:.1f}" width="8" height="14" fill="{ink}">'
        f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" dur="1s" repeatCount="indefinite"/></rect>'
    )

    parts.append("</svg>")
    svg = "".join(parts)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {out_path} ({len(svg)} bytes; canvas: {canvas_w:.0f}x{canvas_h:.0f}, cols: {cols}, rows: {rows})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate typewriter ASCII SVG portrait")
    parser.add_argument("src", nargs="?", default=DEFAULT_SRC, help="Source prepped image")
    parser.add_argument("out", nargs="?", default=DEFAULT_OUT, help="Target output SVG")
    parser.add_argument("--cols", type=int, default=110, help="Column count (default 110)")
    parser.add_argument("--static", action="store_true", help="Generate static SVG without animations")
    args = parser.parse_args()

    generate_ascii_svg(args.src, args.out, cols=args.cols, static=args.static)
