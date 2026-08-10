#!/usr/bin/env python3
"""Generate the PWA icon set for Masjid Events Perlis.

Pure-stdlib PNG encoder (zlib + struct) — no external image libraries.
Draws a rounded-square accent-green tile with a white crescent + five-pointed
star motif at 192x192 and 512x512 (plus a maskable-friendly padding since the
motif sits well within the safe zone).

Usage:
    python3 tools/gen_icons.py                  # writes public/assets/icon-{192,512}.png
    python3 tools/gen_icons.py --out /some/dir  # write PNGs somewhere else
"""

import argparse
import struct
import zlib
import math
from pathlib import Path

ACCENT = (0x0F, 0x6B, 0x3A, 255)
WHITE = (255, 255, 255, 255)


def chunk(kind, data):
    return (struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))


def encode_png(width, height, pixels):
    """Serialize an RGBA pixel buffer (list of rows) to PNG bytes."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = bytearray()
    for row in pixels:
        raw.append(0)  # filter: none
        for px in row:
            raw += bytes(px)
    idat = zlib.compress(bytes(raw), 9)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def in_rounded_rect(x, y, size, inset, radius):
    """True if normalized point (x,y) in [0,1]^2 falls inside the rounded tile."""
    if not (inset <= x <= 1 - inset and inset <= y <= 1 - inset):
        return False
    corners = [(inset, inset), (1 - inset, inset),
               (inset, 1 - inset), (1 - inset, 1 - inset)]
    # inside the radius arc of any corner?
    for (cx, cy) in corners:
        dx = x - cx
        dy = y - cy
        cr = radius * size
        if (dx * dx + dy * dy) <= cr * cr:
            return True
    # within the straight middle band
    return True


def in_disc(x, y, cx, cy, r):
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def in_star(x, y, cx, cy, outer, inner, rot):
    """Point-in-polygon for a regular five-pointed star centred near (cx,cy)."""
    def star_vertices():
        pts = []
        for i in range(10):
            r = outer if i % 2 == 0 else inner
            a = rot + i * math.pi / 5
            pts.append((cx + r * math.sin(a), cy + r * math.cos(a)))
        return pts

    verts = star_vertices()
    inside = False
    j = len(verts) - 1
    for i in range(len(verts)):
        xi, yi = verts[i]
        xj, yj = verts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def sample_pixel(px, py, size, ss):
    """Average sub-samples (supersampling) to approximate anti-aliased edges."""
    r = g = b = a = 0
    n = ss * ss
    for sy in range(ss):
        for sx in range(ss):
            x = (px + (sx + 0.5) / ss) / size
            y = 1 - (py + (sy + 0.5) / ss) / size  # flip to y-up
            color = shape_color(x, y, size)
            r += color[0]
            g += color[1]
            b += color[2]
            a += color[3]
    return (round(r / n), round(g / n), round(b / n), round(a / n))


def shape_color(x, y, size):
    """Return the RGBA for a normalized point, or transparent if outside tile."""
    if not in_rounded_rect(x, y, size, inset=0.04, radius=0.16):
        return (0, 0, 0, 0)
    color = ACCENT
    # crescent moon
    if in_disc(x, y, 0.50, 0.48, 0.185) and not in_disc(x, y, 0.44, 0.545, 0.16):
        return WHITE
    # five-pointed star toward the crescent's open side
    if in_star(x, y, 0.30, 0.36, outer=0.075, inner=0.03, rot=0.0):
        return WHITE
    return color


def render(size, ss):
    pixels = []
    for py in range(size):
        row = []
        for px in range(size):
            row.append(sample_pixel(px, py, size, ss))
        pixels.append(row)
    return pixels


def write_icons(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        ss = 4 if size < 256 else 2
        png = encode_png(size, size, render(size, ss))
        path = out / f"icon-{size}.png"
        path.write_bytes(png)
        print(f"gen_icons: wrote {path} ({size}x{size}, {len(png)} bytes)")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="public/assets", help="directory for the PNGs")
    args = ap.parse_args()
    write_icons(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())