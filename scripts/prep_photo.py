#!/usr/bin/env python3
"""
Prepares an input photo for ASCII conversion:
1. Isolates subject by removing background (rembg)
2. Normalizes contrast / applies CLAHE (Contrast Limited Adaptive Histogram Equalization)
3. Supports optional bilateral smoothing and difference-of-Gaussians edge enhancement
4. Composites subject onto white background with clean aspect-ratio preservation

Usage:
    python scripts/prep_photo.py "<path_to_input_photo>" [output_path] [--enhance]
"""
import argparse
import os
import sys

import cv2
import numpy as np
from PIL import Image
from rembg import new_session, remove

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "..", "source-prepped.png")


def prep_image(input_path, output_path, enhance_lines=False):
    if not os.path.exists(input_path):
        print(f"ERROR: Input photo not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading image from: {input_path}")
    raw_pil = Image.open(input_path).convert("RGBA")

    print("Removing background using rembg (u2netp session)...")
    session = new_session("u2netp")
    cut_pil = remove(raw_pil, session=session)

    rgb = np.array(cut_pil.convert("RGB"))
    alpha = np.array(cut_pil.split()[-1])  # 0 = background, 255 = foreground

    if np.sum(alpha > 20) == 0:
        print("WARNING: Alpha mask is completely transparent. Falling back to original image.", file=sys.stderr)
        alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    if enhance_lines:
        print("Applying bilateral filter and difference-of-Gaussians line enhancement...")
        smooth = gray.copy()
        for _ in range(3):
            smooth = cv2.bilateralFilter(smooth, 9, 40, 9)

        # Tone stretching
        subject_pixels = smooth[alpha > 128]
        if len(subject_pixels) > 0:
            lo, hi = np.percentile(subject_pixels, [2, 92])
            tone = np.clip((smooth.astype(np.float32) - lo) / max(hi - lo, 1), 0, 1)
        else:
            tone = smooth.astype(np.float32) / 255.0

        # Ridge enhancement (DoG)
        fine = cv2.GaussianBlur(smooth, (0, 0), 1.5).astype(np.float32)
        coarse = cv2.GaussianBlur(smooth, (0, 0), 6).astype(np.float32)
        lines = np.clip((coarse - fine) / 40.0, 0, 1)
        out = np.clip(tone - 0.6 * lines, 0, 1) * 255.0
    else:
        print("Applying CLAHE contrast equalization...")
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        eq = clahe.apply(gray)
        # Tone stretch on subject
        subject_pixels = eq[alpha > 128]
        if len(subject_pixels) > 0:
            lo, hi = np.percentile(subject_pixels, [3, 97])
            out = np.clip((eq.astype(np.float32) - lo) / max(hi - lo, 1), 0, 1) * 255.0
        else:
            out = eq.astype(np.float32)

    # Composite onto solid white background (white clears out to spaces in ASCII ramp)
    mask = cv2.GaussianBlur(alpha.astype(np.float32) / 255.0, (0, 0), 1.0)
    composite = out * mask + 255.0 * (1.0 - mask)

    # Square crop centered around subject bounding box
    ys, xs = np.where(alpha > 20)
    if len(xs) > 0 and len(ys) > 0:
        side = max(xs.max() - xs.min(), ys.max() - ys.min()) + 60
        cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
        canvas = np.full((side, side), 255, dtype=np.uint8)
        x0, y0 = cx - side // 2, cy - side // 2
        sx0, sy0 = max(x0, 0), max(y0, 0)
        sx1, sy1 = min(x0 + side, composite.shape[1]), min(y0 + side, composite.shape[0])

        dx0 = sx0 - x0
        dy0 = sy0 - y0
        dx1 = dx0 + (sx1 - sx0)
        dy1 = dy0 + (sy1 - sy0)
        canvas[dy0:dy1, dx0:dx1] = composite[sy0:sy1, sx0:sx1].astype(np.uint8)
        result = Image.fromarray(canvas, mode="L")
    else:
        result = Image.fromarray(composite.astype(np.uint8), mode="L")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    result.save(output_path)
    print(f"Prepped image saved to: {output_path} (size: {result.size})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare photo for ASCII rendering")
    parser.add_argument("input", help="Path to input photo")
    parser.add_argument("output", nargs="?", default=DEFAULT_OUT, help="Path to output prepped PNG")
    parser.add_argument("--enhance", action="store_true", help="Apply bilateral & DoG edge enhancement")
    args = parser.parse_args()

    prep_image(args.input, args.output, enhance_lines=args.enhance)
