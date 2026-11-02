#!/usr/bin/env python3
"""Labelled frame strip from a (proxy) video for choosing shots and x_offsets.

Each frame is labelled with its source time; a cyan box marks the centred 9:16 window the
vertical reframe shows (1080 of 2592 px at 135%), so the subject can be checked against it.
Usage: strip.py <video> <out.jpg> <fps> a-b[:label] [a-b[:label] ...]
"""
import io
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont


def main():
    if len(sys.argv) < 5:
        sys.exit("usage: strip.py <video> <out.jpg> <fps> a-b[:label] ...")
    video, out, fps = sys.argv[1], sys.argv[2], float(sys.argv[3])
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 15)
    W, H = 240, 135
    tiles = []
    for win in sys.argv[4:]:
        rng, _, label = win.partition(":")
        a, b = map(float, rng.split("-"))
        t = a
        while t <= b + 1e-6:
            png = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
                                  "-vf", f"scale={W}:{H}", "-f", "image2pipe", "-vcodec", "png", "-"],
                                 capture_output=True, check=True).stdout
            im = Image.open(io.BytesIO(png)).convert("RGB")
            d = ImageDraw.Draw(im)
            bw = W * 1080 / 2592
            x0 = (W - bw) / 2
            d.rectangle([x0, 0, x0 + bw, H - 1], outline=(0, 255, 255))
            d.rectangle([0, 0, 78, 18], fill=(0, 0, 0))
            d.text((2, 1), f"{t:.2f}", fill=(255, 230, 0), font=font)
            if label and t == a:
                d.rectangle([0, H - 18, W, H], fill=(0, 0, 0))
                d.text((2, H - 18), label, fill=(255, 255, 255), font=font)
            tiles.append(im)
            t += 1 / fps
    C = 8
    R = (len(tiles) + C - 1) // C
    sheet = Image.new("RGB", (C * W, R * H))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % C) * W, (i // C) * H))
    sheet.save(out, quality=82)
    print(out, len(tiles))


if __name__ == "__main__":
    main()
