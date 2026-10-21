"""Create the app icons web/icon-192.png and web/icon-512.png (no extra libraries needed).

    python scripts/make_icons.py

Draws the same design as web/icon.svg: maroon rounded square, gold ring, cream leaf with a centre vein.
"""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAROON, GOLD, CREAM = (31, 42, 85), (226, 166, 0), (248, 243, 223)   # indigo, turmeric, palm leaf


def pixel(x: float, y: float) -> tuple[int, int, int, int]:
    """Colour at (x, y) in the 512 x 512 design space."""
    r = 112                                                      # rounded corners
    cx, cy = min(max(x, r), 512 - r), min(max(y, r), 512 - r)
    if (x - cx) ** 2 + (y - cy) ** 2 > r * r:
        return (0, 0, 0, 0)
    dx, dy = x - 256, y - 256
    if abs(math.hypot(dx, dy) - 150) <= 9:                       # gold ring
        return (*GOLD, 255)
    if 140 <= y <= 372:                                          # leaf: width follows a sine curve
        t = (y - 140) / 232
        half = 74 * math.sin(math.pi * t) ** 0.85
        if abs(dx) <= half:
            if abs(dx) <= 5 and 170 <= y <= 350:                 # vein
                return (*MAROON, 255)
            return (*CREAM, 255)
    return (*MAROON, 255)


def png(size: int, path: Path) -> None:
    s = 512 / size
    rows = []
    for py in range(size):
        row = bytearray(b"\x00")
        for px in range(size):
            acc = [0, 0, 0, 0]                                   # 2x2 supersampling for smooth edges
            for ox in (0.25, 0.75):
                for oy in (0.25, 0.75):
                    c = pixel((px + ox) * s, (py + oy) * s)
                    for k in range(4):
                        acc[k] += c[k]
            row += bytes(v // 4 for v in acc)
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))
    path.write_bytes(data)
    print(f"wrote {path.relative_to(ROOT)}  ({len(data) // 1024} KB)")


if __name__ == "__main__":
    for n in (192, 512):
        png(n, ROOT / "web" / f"icon-{n}.png")